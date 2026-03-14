"""Tests for sdd_preflight tool enforcement checks."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

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
) -> tuple[SpecManager, SpecValidator, GitClient]:
    """Return mocked preflight dependencies."""
    spec_manager = MagicMock(spec=SpecManager)
    spec_manager.validate_structure.return_value = structural_issues or []

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

    return spec_manager, spec_validator, git_client


async def _call_preflight(
    spec_manager: SpecManager,
    spec_validator: SpecValidator,
    git_client: GitClient,
    tmp_path: Path,
) -> dict:
    """Call the sdd_preflight logic directly (bypassing MCP context injection)."""
    # Inline the preflight logic since it is an inner async function registered
    # on the MCP server.  We replicate the core logic here and also test it via
    # direct invocation of the init module's registered tool.
    from mcp.server.fastmcp import FastMCP

    from sdd_server.mcp.tools.init import register_tools

    app = FastMCP("test")
    register_tools(app)

    # Invoke the tool by patching the dependencies at the module level and
    # passing a fake ctx that returns our mocks from lifespan_context.
    fake_ctx = MagicMock()
    fake_ctx.request_context.lifespan_context = {
        "spec_manager": spec_manager,
        "spec_validator": spec_validator,
        "git_client": git_client,
        "project_root": tmp_path,
    }

    # Get the registered tool function directly from the FastMCP instance
    tool_fn = None
    for tool in app._tool_manager.list_tools():
        if tool.name == "sdd_preflight":
            tool_fn = app._tool_manager._tools[tool.name].fn
            break

    assert tool_fn is not None, "sdd_preflight tool not registered"
    return await tool_fn(ctx=fake_ctx)


# ---------------------------------------------------------------------------
# Tests: allowed flag
# ---------------------------------------------------------------------------


class TestPreflightAllowed:
    @pytest.mark.asyncio
    async def test_allowed_when_all_checks_pass(self, tmp_path: Path) -> None:
        sm, sv, gc = _build_preflight_deps(tmp_path)
        result = await _call_preflight(sm, sv, gc, tmp_path)

        assert result["allowed"] is True

    @pytest.mark.asyncio
    async def test_not_allowed_when_structural_issues(self, tmp_path: Path) -> None:
        sm, sv, gc = _build_preflight_deps(tmp_path, structural_issues=["specs/prd.md not found"])
        result = await _call_preflight(sm, sv, gc, tmp_path)

        assert result["allowed"] is False
        assert len(result["structural_issues"]) == 1

    @pytest.mark.asyncio
    async def test_not_allowed_when_validation_errors(self, tmp_path: Path) -> None:
        # Build a ValidationResult with one ERROR-severity issue
        vr = MagicMock()
        vr.is_valid = False

        spec_res = MagicMock()
        spec_res.feature = None

        spec_type = MagicMock()
        spec_type.value = "prd"
        spec_res.spec_type = spec_type

        issue = MagicMock()
        issue.rule_name = "required_section"
        issue.message = "Missing ## Goals section"
        issue.severity = ValidationSeverity.ERROR
        spec_res.issues = [issue]

        vr.spec_results = [spec_res]

        sm, sv, gc = _build_preflight_deps(tmp_path, validation_result=vr)
        result = await _call_preflight(sm, sv, gc, tmp_path)

        assert result["allowed"] is False
        assert len(result["validation_errors"]) == 1
        assert "required_section" in result["validation_errors"][0]


# ---------------------------------------------------------------------------
# Tests: check counts
# ---------------------------------------------------------------------------


class TestPreflightCheckCounts:
    @pytest.mark.asyncio
    async def test_three_checks_total(self, tmp_path: Path) -> None:
        sm, sv, gc = _build_preflight_deps(tmp_path)
        result = await _call_preflight(sm, sv, gc, tmp_path)

        assert result["checks_total"] == 3

    @pytest.mark.asyncio
    async def test_all_three_pass(self, tmp_path: Path) -> None:
        sm, sv, gc = _build_preflight_deps(tmp_path)
        result = await _call_preflight(sm, sv, gc, tmp_path)

        assert result["checks_passed"] == 3

    @pytest.mark.asyncio
    async def test_one_check_fails_structural(self, tmp_path: Path) -> None:
        sm, sv, gc = _build_preflight_deps(tmp_path, structural_issues=["missing prd.md"])
        result = await _call_preflight(sm, sv, gc, tmp_path)

        assert result["checks_passed"] == 2  # validation + hook pass

    @pytest.mark.asyncio
    async def test_hook_missing_is_warning_not_blocking(self, tmp_path: Path) -> None:
        sm, sv, gc = _build_preflight_deps(tmp_path, hook_installed=False)
        result = await _call_preflight(sm, sv, gc, tmp_path)

        # Missing hook doesn't block
        assert result["allowed"] is True
        # But it shows as a warning
        assert any("pre-commit" in w for w in result["warnings"])


# ---------------------------------------------------------------------------
# Tests: warnings
# ---------------------------------------------------------------------------


class TestPreflightWarnings:
    @pytest.mark.asyncio
    async def test_warning_includes_severity_warning_issues(self, tmp_path: Path) -> None:
        vr = MagicMock()
        vr.is_valid = False

        spec_res = MagicMock()
        spec_res.feature = None

        spec_type = MagicMock()
        spec_type.value = "arch"
        spec_res.spec_type = spec_type

        issue = MagicMock()
        issue.rule_name = "optional_section"
        issue.message = "Recommended section missing"
        issue.severity = ValidationSeverity.WARNING
        spec_res.issues = [issue]

        vr.spec_results = [spec_res]

        sm, sv, gc = _build_preflight_deps(tmp_path, validation_result=vr)
        result = await _call_preflight(sm, sv, gc, tmp_path)

        # WARNING-level issues go to warnings, not validation_errors
        assert len(result["validation_errors"]) == 0
        assert any("optional_section" in w for w in result["warnings"])

    @pytest.mark.asyncio
    async def test_validator_crash_becomes_warning(self, tmp_path: Path) -> None:
        sm, sv, gc = _build_preflight_deps(tmp_path)
        sv.validate_project.side_effect = RuntimeError("no spec files")

        result = await _call_preflight(sm, sv, gc, tmp_path)

        assert any("validator" in w.lower() or "spec" in w.lower() for w in result["warnings"])
