"""EnforcementEngine — Phase 4 enforcement of spec-before-code workflow.

Runs four ordered checks and returns an EnforcementReport that callers (CLI
commands, MCP tools) use to decide whether to block or warn.

Checks (in order):
1. Spec structure  — are prd.md, arch.md, tasks.md present?
2. Spec validation — do spec files meet content rules?
3. Role reviews    — is every role in the checklist ticked? (WARNING only)
4. Git hook        — is the pre-commit hook installed?      (WARNING only)

Bypass logic: a BypassRecord whose action matches and whose timestamp is
within BYPASS_GRACE_SECONDS suppresses blocking (violations become warnings).
"""

from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from sdd_server.core.metadata import MetadataManager
from sdd_server.core.spec_manager import SpecManager
from sdd_server.core.spec_validator import SpecValidator
from sdd_server.infrastructure.git import GitClient
from sdd_server.models.state import BypassRecord
from sdd_server.models.validation import ValidationSeverity
from sdd_server.utils.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BYPASS_GRACE_SECONDS: int = int(os.getenv("SDD_BYPASS_GRACE_HOURS", "24")) * 3600

# Regex that matches a markdown role-review checkbox line:
#   - [ ] **Role Name** — ...
#   - [x] **Role Name** — ...
_ROLE_CHECKBOX_RE = re.compile(r"^- \[(?P<checked>[ xX])\] \*\*(?P<role>.+?)\*\*", re.MULTILINE)


# ---------------------------------------------------------------------------
# Report types
# ---------------------------------------------------------------------------


class ViolationSeverity(StrEnum):
    BLOCKING = "blocking"
    WARNING = "warning"


@dataclass
class Violation:
    rule: str
    message: str
    severity: ViolationSeverity
    suggestion: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "rule": self.rule,
            "message": self.message,
            "severity": self.severity.value,
            "suggestion": self.suggestion,
        }


@dataclass
class EnforcementReport:
    """Result of a full enforcement run."""

    blocked: bool
    violations: list[Violation] = field(default_factory=list)
    warnings: list[Violation] = field(default_factory=list)
    bypass_active: bool = False
    bypass_reason: str | None = None
    checks_run: int = 0
    checks_passed: int = 0

    def as_dict(self) -> dict[str, object]:
        return {
            "blocked": self.blocked,
            "allowed": not self.blocked,
            "violations": [v.as_dict() for v in self.violations],
            "warnings": [v.as_dict() for v in self.warnings],
            "bypass_active": self.bypass_active,
            "bypass_reason": self.bypass_reason,
            "checks_run": self.checks_run,
            "checks_passed": self.checks_passed,
        }


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class EnforcementEngine:
    """Runs enforcement checks and returns an EnforcementReport.

    Construct once per request from the services already initialised by the
    MCP lifespan or CLI command; the engine itself is stateless.
    """

    def __init__(
        self,
        project_root: Path,
        spec_manager: SpecManager,
        spec_validator: SpecValidator,
        git_client: GitClient,
        metadata_manager: MetadataManager,
    ) -> None:
        self._root = project_root
        self._spec_manager = spec_manager
        self._spec_validator = spec_validator
        self._git = git_client
        self._metadata = metadata_manager

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def run(self, action: str = "commit") -> EnforcementReport:
        """Run all checks synchronously and return an EnforcementReport."""
        all_violations: list[Violation] = []
        checks_run = 0
        checks_passed = 0

        # 1. Spec structure
        checks_run += 1
        struct_violations = self._check_spec_structure()
        if not struct_violations:
            checks_passed += 1
        all_violations.extend(struct_violations)

        # 2. Spec content validation
        checks_run += 1
        content_violations = self._check_spec_content()
        if not any(v.severity == ViolationSeverity.BLOCKING for v in content_violations):
            checks_passed += 1
        all_violations.extend(content_violations)

        # 3. Role review checklist (warning only)
        checks_run += 1
        review_violations = self._check_role_reviews()
        if not review_violations:
            checks_passed += 1
        all_violations.extend(review_violations)

        # 4. Git pre-commit hook (warning only)
        checks_run += 1
        hook_violations = self._check_git_hook()
        if not hook_violations:
            checks_passed += 1
        all_violations.extend(hook_violations)

        blocking = [v for v in all_violations if v.severity == ViolationSeverity.BLOCKING]
        warnings = [v for v in all_violations if v.severity == ViolationSeverity.WARNING]

        blocked = len(blocking) > 0

        # Check for an active bypass that suppresses the block
        bypass_active = False
        bypass_reason: str | None = None
        if blocked:
            bypass_record = self._find_active_bypass(action)
            if bypass_record is not None:
                bypass_active = True
                bypass_reason = bypass_record.reason
                blocked = False
                logger.info(
                    "enforcement_bypassed",
                    action=action,
                    reason=bypass_reason,
                )

        report = EnforcementReport(
            blocked=blocked,
            violations=blocking,
            warnings=warnings,
            bypass_active=bypass_active,
            bypass_reason=bypass_reason,
            checks_run=checks_run,
            checks_passed=checks_passed,
        )

        logger.info(
            "enforcement_complete",
            action=action,
            blocked=blocked,
            violations=len(blocking),
            warnings=len(warnings),
        )
        return report

    async def run_async(self, action: str = "commit") -> EnforcementReport:
        """Non-blocking wrapper around run() for MCP tool handlers."""
        return await asyncio.to_thread(self.run, action)

    # -------------------------------------------------------------------------
    # Checks
    # -------------------------------------------------------------------------

    def _check_spec_structure(self) -> list[Violation]:
        """Check 1: core spec files must exist."""
        issues = self._spec_manager.validate_structure()
        return [
            Violation(
                rule="missing_spec_file",
                message=issue,
                severity=ViolationSeverity.BLOCKING,
                suggestion="Run 'sdd init' or create the missing spec file manually.",
            )
            for issue in issues
        ]

    def _check_spec_content(self) -> list[Violation]:
        """Check 2: spec files must satisfy validation rules."""
        violations: list[Violation] = []
        try:
            result = self._spec_validator.validate_project(include_features=False)
            for spec_res in result.spec_results:
                for issue in spec_res.issues:
                    loc = spec_res.spec_type.value
                    if spec_res.feature:
                        loc = f"{spec_res.feature}/{loc}"
                    severity = (
                        ViolationSeverity.BLOCKING
                        if issue.severity == ValidationSeverity.ERROR
                        else ViolationSeverity.WARNING
                    )
                    violations.append(
                        Violation(
                            rule=issue.rule_name,
                            message=f"[{loc}] {issue.message}",
                            severity=severity,
                            suggestion=str(issue.suggestion)
                            if hasattr(issue, "suggestion") and issue.suggestion
                            else "",
                        )
                    )
        except Exception as exc:
            # Validator may fail when no spec files exist yet — treat as warning
            violations.append(
                Violation(
                    rule="validator_unavailable",
                    message=f"Spec validator could not run: {exc}",
                    severity=ViolationSeverity.WARNING,
                    suggestion="Ensure spec files exist before running preflight.",
                )
            )
        return violations

    def _check_role_reviews(self) -> list[Violation]:
        """Check 3: role review checklist in tasks.md (warnings only)."""
        violations: list[Violation] = []
        try:
            from sdd_server.models.spec import SpecType

            content = self._spec_manager.read_spec(SpecType.TASKS)
            for m in _ROLE_CHECKBOX_RE.finditer(content):
                checked = m.group("checked").strip().lower()
                role = m.group("role")
                if checked != "x":
                    violations.append(
                        Violation(
                            rule="role_review_incomplete",
                            message=f"Role review not completed: {role}",
                            severity=ViolationSeverity.WARNING,
                            suggestion=(
                                f"Run the {role.lower().replace(' ', '-')} recipe: "
                                f"goose run --recipe specs/recipes/{role.lower().replace(' ', '-')}.yaml"
                            ),
                        )
                    )
        except Exception:
            # tasks.md may not exist on a fresh project — skip silently
            pass
        return violations

    def _check_git_hook(self) -> list[Violation]:
        """Check 4: git pre-commit hook should be installed (warning only)."""
        if self._git.is_hook_installed("pre-commit"):
            return []
        return [
            Violation(
                rule="missing_git_hook",
                message="Git pre-commit hook is not installed",
                severity=ViolationSeverity.WARNING,
                suggestion="Run 'sdd init' to install the pre-commit hook.",
            )
        ]

    # -------------------------------------------------------------------------
    # Bypass
    # -------------------------------------------------------------------------

    def _find_active_bypass(self, action: str) -> BypassRecord | None:
        """Return the most recent active bypass for action, or None."""
        try:
            state = self._metadata.load()
        except Exception:
            return None

        now = datetime.now(UTC)
        active: list[BypassRecord] = []
        for record in state.bypasses:
            ts = record.timestamp
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
            elapsed = (now - ts).total_seconds()
            if record.action == action and elapsed < BYPASS_GRACE_SECONDS:
                active.append(record)

        if not active:
            return None
        # Return the most recent one
        return max(active, key=lambda r: r.timestamp)
