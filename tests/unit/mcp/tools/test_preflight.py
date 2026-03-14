"""Tests for sdd_preflight MCP tool (EnforcementEngine-backed)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from sdd_server.core.metadata import MetadataManager
from sdd_server.core.spec_manager import SpecManager
from sdd_server.core.spec_validator import SpecValidator
from sdd_server.infrastructure.git import GitClient
from sdd_server.models.validation import ValidationSeverity

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_preflight_deps(
    tmp_path: Path,
    *,
    structural_issues: list[str] | None = None,
    validation_result: MagicMock | None = None,
    hook_installed: bool = True,
    tasks_content: str = "- [x] **Architect** — done",
) -> tuple[SpecManager, SpecValidator, GitClient, MetadataManager]:
    """Return mocked preflight dependencies."""
    spec_manager = MagicMock(spec=SpecManager)
    spec_manager.validate_structure.return_value = structural_issues or []
    spec_manager.read_spec.return_value = tasks_content

    spec_validator = MagicMock(spec=SpecValidator)
    if validation_result is None:
        vr = MagicMock()
        vr.is_valid = True
        vr.spec_results = []
        spec_validator.validate_project.return_value = vr
    else:
        spec_validator.validate_project.return_value = validation_result

    git_client = MagicMock(spec=GitClient)
    git_client.is_hook_installed.return_value = hook_installed

    metadata = MagicMock(spec=MetadataManager)
    state = MagicMock()
    state.bypasses = []
    metadata.load.return_value = state

    return spec_manager, spec_validator, git_client, metadata


async def _call_preflight(
    spec_manager: SpecManager,
    spec_validator: SpecValidator,
    git_client: GitClient,
    metadata_manager: MetadataManager,
    tmp_path: Path,
) -> dict:
    """Call the sdd_preflight MCP tool directly via FastMCP's tool registry."""
    from mcp.server.fastmcp import FastMCP

    from sdd_server.mcp.tools.init import register_tools

    app = FastMCP("test")
    register_tools(app)

    fake_ctx = MagicMock()
    fake_ctx.request_context.lifespan_context = {
        "spec_manager": spec_manager,
        "spec_validator": spec_validator,
        "git_client": git_client,
        "metadata_manager": metadata_manager,
        "project_root": tmp_path,
    }

    tool_fn = None
    for tool in app._tool_manager.list_tools():
        if tool.name == "sdd_preflight":
            tool_fn = app._tool_manager._tools[tool.name].fn
            break

    assert tool_fn is not None, "sdd_preflight tool not registered"
    return await tool_fn(ctx=fake_ctx)


# ---------------------------------------------------------------------------
# Tests: allowed / blocked flags
# ---------------------------------------------------------------------------


class TestPreflightAllowed:
    async def test_allowed_when_all_checks_pass(self, tmp_path: Path) -> None:
        sm, sv, gc, md = _build_preflight_deps(tmp_path)
        result = await _call_preflight(sm, sv, gc, md, tmp_path)

        assert result["allowed"] is True
        assert result["blocked"] is False

    async def test_not_allowed_when_structural_issues(self, tmp_path: Path) -> None:
        sm, sv, gc, md = _build_preflight_deps(
            tmp_path, structural_issues=["specs/prd.md not found"]
        )
        result = await _call_preflight(sm, sv, gc, md, tmp_path)

        assert result["allowed"] is False
        assert result["blocked"] is True
        assert any(v["rule"] == "missing_spec_file" for v in result["violations"])

    async def test_not_allowed_when_validation_errors(self, tmp_path: Path) -> None:
        vr = MagicMock()
        vr.is_valid = False

        spec_res = MagicMock()
        spec_res.feature = None
        spec_res.spec_type = MagicMock()
        spec_res.spec_type.value = "prd"

        issue = MagicMock()
        issue.rule_name = "required_section"
        issue.message = "Missing ## Goals section"
        issue.severity = ValidationSeverity.ERROR
        issue.suggestion = "Add a Goals section"
        spec_res.issues = [issue]
        vr.spec_results = [spec_res]

        sm, sv, gc, md = _build_preflight_deps(tmp_path, validation_result=vr)
        result = await _call_preflight(sm, sv, gc, md, tmp_path)

        assert result["allowed"] is False
        assert result["blocked"] is True
        violation_rules = [v["rule"] for v in result["violations"]]
        assert "required_section" in violation_rules


# ---------------------------------------------------------------------------
# Tests: check counts
# ---------------------------------------------------------------------------


class TestPreflightCheckCounts:
    async def test_four_checks_total(self, tmp_path: Path) -> None:
        sm, sv, gc, md = _build_preflight_deps(tmp_path)
        result = await _call_preflight(sm, sv, gc, md, tmp_path)

        assert result["checks_run"] == 4

    async def test_all_four_pass(self, tmp_path: Path) -> None:
        sm, sv, gc, md = _build_preflight_deps(tmp_path, hook_installed=True)
        result = await _call_preflight(sm, sv, gc, md, tmp_path)

        assert result["checks_passed"] == 4

    async def test_one_check_fails_structural(self, tmp_path: Path) -> None:
        sm, sv, gc, md = _build_preflight_deps(tmp_path, structural_issues=["missing prd.md"])
        result = await _call_preflight(sm, sv, gc, md, tmp_path)

        assert result["checks_passed"] < 4

    async def test_hook_missing_is_warning_not_blocking(self, tmp_path: Path) -> None:
        sm, sv, gc, md = _build_preflight_deps(tmp_path, hook_installed=False)
        result = await _call_preflight(sm, sv, gc, md, tmp_path)

        # Missing hook doesn't block
        assert result["allowed"] is True
        # But shows as a warning
        warning_rules = [w["rule"] for w in result["warnings"]]
        assert "missing_git_hook" in warning_rules


# ---------------------------------------------------------------------------
# Tests: warnings
# ---------------------------------------------------------------------------


class TestPreflightWarnings:
    async def test_warning_includes_severity_warning_issues(self, tmp_path: Path) -> None:
        vr = MagicMock()
        vr.is_valid = True  # no errors

        spec_res = MagicMock()
        spec_res.feature = None
        spec_res.spec_type = MagicMock()
        spec_res.spec_type.value = "arch"

        issue = MagicMock()
        issue.rule_name = "optional_section"
        issue.message = "Recommended section missing"
        issue.severity = ValidationSeverity.WARNING
        issue.suggestion = ""
        spec_res.issues = [issue]
        vr.spec_results = [spec_res]

        sm, sv, gc, md = _build_preflight_deps(tmp_path, validation_result=vr)
        result = await _call_preflight(sm, sv, gc, md, tmp_path)

        # WARNING-level issues go to warnings, not violations
        violation_rules = [v["rule"] for v in result["violations"]]
        assert "optional_section" not in violation_rules
        warning_rules = [w["rule"] for w in result["warnings"]]
        assert "optional_section" in warning_rules

    async def test_validator_crash_becomes_warning(self, tmp_path: Path) -> None:
        sm, sv, gc, md = _build_preflight_deps(tmp_path)
        sv.validate_project.side_effect = RuntimeError("no spec files")

        result = await _call_preflight(sm, sv, gc, md, tmp_path)

        warning_rules = [w["rule"] for w in result["warnings"]]
        assert "validator_unavailable" in warning_rules
        # Crash doesn't block
        assert result["allowed"] is True


# ---------------------------------------------------------------------------
# Tests: bypass
# ---------------------------------------------------------------------------


class TestPreflightBypass:
    async def test_bypass_active_suppresses_block(self, tmp_path: Path) -> None:
        from datetime import UTC, datetime, timedelta

        from sdd_server.models.state import BypassRecord

        ts = datetime.now(UTC) - timedelta(seconds=10)
        bypass = BypassRecord(timestamp=ts, actor="user", reason="hotfix", action="commit")

        sm, sv, gc, md = _build_preflight_deps(tmp_path, structural_issues=["prd.md missing"])
        state = MagicMock()
        state.bypasses = [bypass]
        md.load.return_value = state

        result = await _call_preflight(sm, sv, gc, md, tmp_path)

        assert result["allowed"] is True
        assert result["bypass_active"] is True
        assert result["bypass_reason"] == "hotfix"
