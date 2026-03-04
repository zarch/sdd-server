"""LLM-based spec-code alignment checker.

Architecture reference: arch.md Section 5.4

Approach:
1. Extract relevant spec sections (prd.md / arch.md).
2. Collect bounded code diff via GitClient.
3. Send {spec_context + code_diff} to AIClientBridge.run_alignment_check().
4. Parse structured JSON response into AlignmentReport.

Language-agnostic: no AST parsing; detects semantic misalignment only.
"""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sdd_server.models.base import SDDBaseModel
from sdd_server.models.spec import SpecType
from sdd_server.utils.logging import get_logger

if TYPE_CHECKING:
    from sdd_server.core.ai_client import AIClientBridge
    from sdd_server.core.spec_manager import SpecManager
    from sdd_server.infrastructure.git import GitClient

logger = get_logger(__name__)

# Maximum characters sent to the LLM per check (≈ 2 k tokens @ 4 chars/token)
_DEFAULT_MAX_CHARS = 32_000


# =============================================================================
# Domain models
# =============================================================================


class AlignmentStatus(StrEnum):
    """Overall or per-issue alignment status."""

    ALIGNED = "aligned"
    DIVERGED = "diverged"
    MISSING_SPEC = "missing_spec"
    MISSING_CODE = "missing_code"


class AlignmentIssue(SDDBaseModel):
    """A single spec-code misalignment found by the LLM."""

    file: str | None = None  # Source file path (relative), if applicable
    spec_ref: str  # e.g. "arch.md §5.3" or "prd.md Feature C"
    status: AlignmentStatus
    description: str
    suggested_action: str  # "update_spec" | "update_code" | "create_spec"
    severity: str  # "critical" | "warning" | "info"


class AlignmentReport(SDDBaseModel):
    """Full alignment report returned by AlignmentChecker."""

    overall_status: AlignmentStatus
    issues: list[AlignmentIssue] = []  # noqa: RUF012
    summary: dict[str, int] = {}  # noqa: RUF012
    tokens_used: int | None = None
    raw_response: str = ""


# =============================================================================
# Checker
# =============================================================================


class AlignmentChecker:
    """Verify spec-code alignment using LLM semantic analysis.

    Parameters
    ----------
    spec_manager:
        SpecManager instance for reading spec files.
    ai_client:
        AIClientBridge used to run the LLM alignment check.
    project_root:
        Absolute path to the project root.
    git_client:
        GitClient for diff generation. Optional; diff falls back to empty.
    source_dirs:
        Source directories to include in diff context.
    max_chars_per_check:
        Maximum characters of spec+diff sent per LLM call.
    """

    def __init__(
        self,
        spec_manager: SpecManager,
        ai_client: AIClientBridge,
        project_root: Path,
        git_client: GitClient | None = None,
        source_dirs: list[str] | None = None,
        max_chars_per_check: int = _DEFAULT_MAX_CHARS,
    ) -> None:
        self._spec_manager = spec_manager
        self._ai_client = ai_client
        self._project_root = project_root
        self._git_client = git_client
        self._source_dirs = source_dirs or ["src", "lib"]
        self._max_chars = max_chars_per_check

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def check_alignment(
        self,
        scope: str = "all",
    ) -> AlignmentReport:
        """Check alignment between specs and code.

        Args:
            scope: One of:
                - ``"all"``   — check whole project
                - ``"feature:<name>"`` — check a specific feature
                - ``"file:<path>"`` — focus on a single source file

        Returns:
            AlignmentReport with issues and overall status.
        """
        spec_context = await self._build_spec_context(scope)
        code_diff = await self._build_code_diff(scope)

        # Trim to budget
        combined = spec_context + "\n\n" + code_diff
        if len(combined) > self._max_chars:
            code_diff = code_diff[: max(0, self._max_chars - len(spec_context))]

        logger.info("Running alignment check", scope=scope, spec_chars=len(spec_context))

        result = await self._ai_client.run_alignment_check(spec_context, code_diff)

        if not result.success:
            logger.warning("Alignment check failed", error=result.error)
            return AlignmentReport(
                overall_status=AlignmentStatus.DIVERGED,
                summary={"error": 1},
                raw_response=result.error or "",
            )

        return self._parse_response(result.output)

    async def check_task_completion(
        self,
        task_id: str,
    ) -> tuple[bool, list[str]]:
        """Ask the LLM whether a task has been completed.

        Args:
            task_id: Task identifier (e.g. "t0000060").

        Returns:
            (completed, list_of_reasons_or_gaps)
        """
        spec_context = await self._build_spec_context("all")
        diff = await self._build_code_diff("all")

        prompt = (
            f"Has task {task_id!r} been fully implemented?\n\n"
            "## Spec context\n"
            f"{spec_context[:8000]}\n\n"
            "## Recent changes\n"
            f"{diff[:8000]}\n\n"
            'Reply with JSON: {"completed": true|false, "gaps": ["..."]}'
        )

        result = await self._ai_client.run_alignment_check(spec_context=prompt, code_diff="")
        if not result.success:
            return False, [result.error or "alignment check failed"]

        try:
            data = json.loads(result.output)
            completed: bool = bool(data.get("completed", False))
            gaps: list[str] = list(data.get("gaps", []))
            return completed, gaps
        except json.JSONDecodeError, KeyError:
            return False, ["could not parse LLM response"]

    async def summarize_codebase_structure(self) -> str:
        """Produce a concise text summary of the codebase file tree.

        Used for existing-project initialisation. Not AST-based; just
        walks the directory tree and describes key files.
        """
        lines: list[str] = ["# Codebase structure\n"]
        for source_dir in self._source_dirs:
            src_path = self._project_root / source_dir
            if not src_path.exists():
                continue
            for path in sorted(src_path.rglob("*")):
                if path.is_file():
                    rel = path.relative_to(self._project_root)
                    lines.append(f"  {rel}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _build_spec_context(self, scope: str) -> str:
        """Read relevant spec files and return them as a combined string."""
        parts: list[str] = []

        if scope.startswith("feature:"):
            feature = scope.split(":", 1)[1]
            for stype in (SpecType.PRD, SpecType.ARCH):
                try:
                    content = self._spec_manager.read_spec(stype, feature=feature)
                    parts.append(f"## Feature {stype.value.upper()} ({feature})\n{content}")
                except Exception:
                    pass
        else:
            # Global specs
            for stype in (SpecType.PRD, SpecType.ARCH):
                try:
                    content = self._spec_manager.read_spec(stype)
                    parts.append(f"## {stype.value.upper()}\n{content}")
                except Exception:
                    pass

        return "\n\n".join(parts)

    async def _build_code_diff(self, scope: str) -> str:
        """Generate a bounded git diff for the given scope."""
        if self._git_client is None:
            return ""

        try:
            if scope.startswith("file:"):
                file_path = scope.split(":", 1)[1]
                diff = self._git_client.get_diff(paths=[file_path])
            else:
                diff = self._git_client.get_diff()

            return diff if diff else ""
        except Exception as exc:
            logger.debug("Could not get git diff", error=str(exc))
            return ""

    def _parse_response(self, raw: str) -> AlignmentReport:
        """Parse LLM JSON response into AlignmentReport."""
        # Try to extract JSON block from the response
        json_str = raw.strip()
        if "```" in json_str:
            # Strip markdown code fences
            for block in json_str.split("```"):
                stripped = block.strip().lstrip("json").strip()
                if stripped.startswith("{"):
                    json_str = stripped
                    break

        try:
            data: dict[str, Any] = json.loads(json_str)
        except json.JSONDecodeError, ValueError:
            logger.warning("Could not parse alignment response as JSON", raw=raw[:200])
            return AlignmentReport(
                overall_status=AlignmentStatus.DIVERGED,
                summary={"parse_error": 1},
                raw_response=raw,
            )

        # Parse overall status
        try:
            overall = AlignmentStatus(data.get("overall_status", "diverged"))
        except ValueError:
            overall = AlignmentStatus.DIVERGED

        # Parse issues
        issues: list[AlignmentIssue] = []
        for raw_issue in data.get("issues", []):
            try:
                issues.append(
                    AlignmentIssue(
                        file=raw_issue.get("file"),
                        spec_ref=raw_issue.get("spec_ref", "unknown"),
                        status=AlignmentStatus(raw_issue.get("status", "diverged")),
                        description=raw_issue.get("description", ""),
                        suggested_action=raw_issue.get("suggested_action", "update_code"),
                        severity=raw_issue.get("severity", "warning"),
                    )
                )
            except ValueError, TypeError:
                continue

        summary: dict[str, int] = {
            k: int(v) for k, v in data.get("summary", {}).items() if isinstance(v, (int, float))
        }

        return AlignmentReport(
            overall_status=overall,
            issues=issues,
            summary=summary,
            tokens_used=data.get("tokens_used"),
            raw_response=raw,
        )
