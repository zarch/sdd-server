"""Unit tests for EnforcementEngine (Phase 4)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

from sdd_server.core.enforcement import (
    BYPASS_GRACE_SECONDS,
    EnforcementEngine,
    EnforcementReport,
    Violation,
    ViolationSeverity,
)
from sdd_server.models.state import BypassRecord

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_engine(
    tmp_path: Path,
    *,
    struct_issues: list[str] | None = None,
    validation_blocking: bool = False,
    validation_warning: bool = False,
    role_reviews_incomplete: list[str] | None = None,
    hook_installed: bool = True,
    bypasses: list[BypassRecord] | None = None,
) -> EnforcementEngine:
    """Build an EnforcementEngine with mocked collaborators."""
    from sdd_server.core.enforcement import EnforcementEngine
    from sdd_server.core.metadata import MetadataManager
    from sdd_server.core.spec_manager import SpecManager
    from sdd_server.core.spec_validator import SpecValidator
    from sdd_server.infrastructure.git import GitClient
    from sdd_server.models.state import ProjectState
    from sdd_server.models.validation import ProjectValidationResult, ValidationSeverity

    spec_manager = MagicMock(spec=SpecManager)
    spec_manager.validate_structure.return_value = struct_issues or []

    # tasks.md content with role checkboxes
    if role_reviews_incomplete:
        tasks_content = "\n".join(
            f"- [ ] **{role}** — review needed" for role in role_reviews_incomplete
        )
    else:
        tasks_content = "- [x] **Architect** — done"
    spec_manager.read_spec.return_value = tasks_content

    spec_validator = MagicMock(spec=SpecValidator)
    if validation_blocking or validation_warning:
        from sdd_server.models.validation import SpecValidationResult

        issue_severity = (
            ValidationSeverity.ERROR if validation_blocking else ValidationSeverity.WARNING
        )
        mock_issue = MagicMock()
        mock_issue.rule_name = "test_rule"
        mock_issue.message = "Test issue"
        mock_issue.severity = issue_severity
        mock_issue.suggestion = "Fix it"

        spec_res = MagicMock(spec=SpecValidationResult)
        spec_res.issues = [mock_issue]
        spec_res.spec_type = MagicMock()
        spec_res.spec_type.value = "prd"
        spec_res.feature = None

        val_result = MagicMock(spec=ProjectValidationResult)
        val_result.spec_results = [spec_res]
        val_result.is_valid = not validation_blocking
        spec_validator.validate_project.return_value = val_result
    else:
        val_result = MagicMock(spec=ProjectValidationResult)
        val_result.spec_results = []
        val_result.is_valid = True
        spec_validator.validate_project.return_value = val_result

    git_client = MagicMock(spec=GitClient)
    git_client.is_hook_installed.return_value = hook_installed

    metadata = MagicMock(spec=MetadataManager)
    state = MagicMock(spec=ProjectState)
    state.bypasses = bypasses or []
    metadata.load.return_value = state

    return EnforcementEngine(
        project_root=tmp_path,
        spec_manager=spec_manager,
        spec_validator=spec_validator,
        git_client=git_client,
        metadata_manager=metadata,
    )


# ---------------------------------------------------------------------------
# EnforcementReport
# ---------------------------------------------------------------------------


class TestEnforcementReport:
    def test_as_dict_shape(self) -> None:
        report = EnforcementReport(blocked=True)
        d = report.as_dict()
        assert "blocked" in d
        assert "allowed" in d
        assert "violations" in d
        assert "warnings" in d
        assert "bypass_active" in d
        assert "bypass_reason" in d
        assert "checks_run" in d
        assert "checks_passed" in d

    def test_allowed_is_inverse_of_blocked(self) -> None:
        assert EnforcementReport(blocked=True).as_dict()["allowed"] is False
        assert EnforcementReport(blocked=False).as_dict()["allowed"] is True

    def test_violations_serialized(self) -> None:
        v = Violation(rule="r", message="m", severity=ViolationSeverity.BLOCKING, suggestion="s")
        report = EnforcementReport(blocked=True, violations=[v])
        d = report.as_dict()
        assert d["violations"][0] == {
            "rule": "r",
            "message": "m",
            "severity": "blocking",
            "suggestion": "s",
        }


# ---------------------------------------------------------------------------
# Violation
# ---------------------------------------------------------------------------


class TestViolation:
    def test_as_dict_includes_all_fields(self) -> None:
        v = Violation(
            rule="missing_spec_file",
            message="prd.md is missing",
            severity=ViolationSeverity.BLOCKING,
            suggestion="run sdd init",
        )
        d = v.as_dict()
        assert d["rule"] == "missing_spec_file"
        assert d["message"] == "prd.md is missing"
        assert d["severity"] == "blocking"
        assert d["suggestion"] == "run sdd init"

    def test_default_suggestion_is_empty(self) -> None:
        v = Violation(rule="r", message="m", severity=ViolationSeverity.WARNING)
        assert v.as_dict()["suggestion"] == ""


# ---------------------------------------------------------------------------
# Check 1: Spec structure
# ---------------------------------------------------------------------------


class TestCheckSpecStructure:
    def test_missing_spec_files_cause_blocking_violation(self, tmp_path: Path) -> None:
        engine = _make_engine(tmp_path, struct_issues=["prd.md is missing"])
        report = engine.run()
        assert report.blocked
        assert len(report.violations) == 1
        assert report.violations[0].rule == "missing_spec_file"
        assert report.violations[0].severity == ViolationSeverity.BLOCKING

    def test_no_struct_issues_passes_check(self, tmp_path: Path) -> None:
        engine = _make_engine(tmp_path, struct_issues=[])
        report = engine.run()
        # Without other issues, check should pass
        assert not any(v.rule == "missing_spec_file" for v in report.violations)

    def test_multiple_missing_files_produce_multiple_violations(self, tmp_path: Path) -> None:
        engine = _make_engine(tmp_path, struct_issues=["prd.md missing", "arch.md missing"])
        report = engine.run()
        assert len([v for v in report.violations if v.rule == "missing_spec_file"]) == 2


# ---------------------------------------------------------------------------
# Check 2: Spec content validation
# ---------------------------------------------------------------------------


class TestCheckSpecContent:
    def test_validation_error_is_blocking(self, tmp_path: Path) -> None:
        engine = _make_engine(tmp_path, validation_blocking=True)
        report = engine.run()
        assert report.blocked
        assert any(v.severity == ViolationSeverity.BLOCKING for v in report.violations)

    def test_validation_warning_is_non_blocking(self, tmp_path: Path) -> None:
        engine = _make_engine(tmp_path, validation_warning=True)
        report = engine.run()
        # warning only — may or may not be blocked (other checks might block)
        assert any(w.severity == ViolationSeverity.WARNING for w in report.warnings)

    def test_validator_exception_becomes_warning(self, tmp_path: Path) -> None:
        engine = _make_engine(tmp_path)
        engine._spec_validator.validate_project.side_effect = RuntimeError("broken")
        report = engine.run()
        assert any(w.rule == "validator_unavailable" for w in report.warnings)
        assert not report.blocked  # single warning must not block


# ---------------------------------------------------------------------------
# Check 3: Role review checklist
# ---------------------------------------------------------------------------


class TestCheckRoleReviews:
    def test_unchecked_role_produces_warning(self, tmp_path: Path) -> None:
        engine = _make_engine(tmp_path, role_reviews_incomplete=["Security Analyst"])
        report = engine.run()
        assert any(
            w.rule == "role_review_incomplete" and "Security Analyst" in w.message
            for w in report.warnings
        )

    def test_unchecked_role_is_non_blocking(self, tmp_path: Path) -> None:
        engine = _make_engine(tmp_path, role_reviews_incomplete=["Architect"])
        report = engine.run()
        assert not any(v.rule == "role_review_incomplete" for v in report.violations)

    def test_all_checked_produces_no_warning(self, tmp_path: Path) -> None:
        engine = _make_engine(tmp_path)
        # Default tasks content has [x] Architect
        report = engine.run()
        assert not any(w.rule == "role_review_incomplete" for w in report.warnings)

    def test_read_spec_exception_skipped_silently(self, tmp_path: Path) -> None:
        engine = _make_engine(tmp_path)
        engine._spec_manager.read_spec.side_effect = FileNotFoundError("no tasks.md")
        report = engine.run()
        # No crash, no role review warnings
        assert not any(w.rule == "role_review_incomplete" for w in report.warnings)


# ---------------------------------------------------------------------------
# Check 4: Git hook
# ---------------------------------------------------------------------------


class TestCheckGitHook:
    def test_missing_hook_produces_warning(self, tmp_path: Path) -> None:
        engine = _make_engine(tmp_path, hook_installed=False)
        report = engine.run()
        assert any(w.rule == "missing_git_hook" for w in report.warnings)

    def test_missing_hook_is_non_blocking(self, tmp_path: Path) -> None:
        engine = _make_engine(tmp_path, hook_installed=False)
        report = engine.run()
        assert not any(v.rule == "missing_git_hook" for v in report.violations)

    def test_hook_installed_produces_no_warning(self, tmp_path: Path) -> None:
        engine = _make_engine(tmp_path, hook_installed=True)
        report = engine.run()
        assert not any(w.rule == "missing_git_hook" for w in report.warnings)


# ---------------------------------------------------------------------------
# Bypass logic
# ---------------------------------------------------------------------------


class TestBypassLogic:
    def _make_bypass(
        self,
        action: str = "commit",
        seconds_ago: int = 100,
        reason: str = "testing",
    ) -> BypassRecord:
        ts = datetime.now(UTC) - timedelta(seconds=seconds_ago)
        return BypassRecord(timestamp=ts, actor="user", reason=reason, action=action)

    def test_active_bypass_unblocks_engine(self, tmp_path: Path) -> None:
        bypass = self._make_bypass(action="commit", seconds_ago=100)
        engine = _make_engine(
            tmp_path,
            struct_issues=["prd.md missing"],
            bypasses=[bypass],
        )
        report = engine.run(action="commit")
        assert not report.blocked
        assert report.bypass_active
        assert report.bypass_reason == "testing"

    def test_expired_bypass_does_not_unblock(self, tmp_path: Path) -> None:
        bypass = self._make_bypass(action="commit", seconds_ago=BYPASS_GRACE_SECONDS + 1)
        engine = _make_engine(
            tmp_path,
            struct_issues=["prd.md missing"],
            bypasses=[bypass],
        )
        report = engine.run(action="commit")
        assert report.blocked
        assert not report.bypass_active

    def test_bypass_for_different_action_does_not_apply(self, tmp_path: Path) -> None:
        bypass = self._make_bypass(action="push", seconds_ago=100)
        engine = _make_engine(
            tmp_path,
            struct_issues=["prd.md missing"],
            bypasses=[bypass],
        )
        report = engine.run(action="commit")
        assert report.blocked
        assert not report.bypass_active

    def test_most_recent_bypass_used(self, tmp_path: Path) -> None:
        old_bypass = self._make_bypass(action="commit", seconds_ago=3600, reason="old")
        new_bypass = self._make_bypass(action="commit", seconds_ago=10, reason="new")
        engine = _make_engine(
            tmp_path,
            struct_issues=["prd.md missing"],
            bypasses=[old_bypass, new_bypass],
        )
        report = engine.run(action="commit")
        assert report.bypass_reason == "new"

    def test_metadata_load_exception_means_no_bypass(self, tmp_path: Path) -> None:
        engine = _make_engine(tmp_path, struct_issues=["prd.md missing"])
        engine._metadata.load.side_effect = OSError("read error")
        report = engine.run(action="commit")
        assert report.blocked
        assert not report.bypass_active

    def test_naive_datetime_bypass_handled(self, tmp_path: Path) -> None:
        """BypassRecord with tzinfo=None should still be compared correctly."""
        ts = datetime.now() - timedelta(seconds=10)  # naive
        bypass = BypassRecord(timestamp=ts, actor="user", reason="naive", action="commit")
        engine = _make_engine(
            tmp_path,
            struct_issues=["prd.md missing"],
            bypasses=[bypass],
        )
        report = engine.run(action="commit")
        assert not report.blocked
        assert report.bypass_active


# ---------------------------------------------------------------------------
# Checks count
# ---------------------------------------------------------------------------


class TestChecksCount:
    def test_four_checks_always_run(self, tmp_path: Path) -> None:
        engine = _make_engine(tmp_path)
        report = engine.run()
        assert report.checks_run == 4

    def test_all_pass_when_clean(self, tmp_path: Path) -> None:
        engine = _make_engine(tmp_path, hook_installed=True)
        report = engine.run()
        # Hook installed, no struct issues, no validation issues, no unchecked roles
        assert report.checks_passed == 4

    def test_failing_struct_check_reduces_passed(self, tmp_path: Path) -> None:
        engine = _make_engine(tmp_path, struct_issues=["prd.md missing"])
        report = engine.run()
        assert report.checks_passed < 4


# ---------------------------------------------------------------------------
# run_async
# ---------------------------------------------------------------------------


class TestRunAsync:
    async def test_run_async_returns_report(self, tmp_path: Path) -> None:
        engine = _make_engine(tmp_path)
        report = await engine.run_async()
        assert isinstance(report, EnforcementReport)
        assert report.checks_run == 4

    async def test_run_async_propagates_blocked(self, tmp_path: Path) -> None:
        engine = _make_engine(tmp_path, struct_issues=["prd.md missing"])
        report = await engine.run_async(action="commit")
        assert report.blocked
