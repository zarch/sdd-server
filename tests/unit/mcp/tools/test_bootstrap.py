"""Unit tests for MCP bootstrap tool (sdd_bootstrap_specs)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from mcp.server.fastmcp import FastMCP

from sdd_server.infrastructure.security.rate_limiter import (
    RateLimitConfig,
    configure_rate_limiter,
)

# ---------------------------------------------------------------------------
# Circular import workaround (same pattern as other MCP tool tests)
# ---------------------------------------------------------------------------


def _import_bootstrap_module():
    real_server = sys.modules.get("sdd_server.mcp.server")
    real_mod = sys.modules.get("sdd_server.mcp.tools.bootstrap")

    if real_mod is not None and hasattr(real_mod, "register_tools"):
        return real_mod

    stub = MagicMock()
    sys.modules["sdd_server.mcp.server"] = stub

    try:
        sys.modules.pop("sdd_server.mcp.tools.bootstrap", None)
        import sdd_server.mcp.tools.bootstrap as bootstrap_module

        return bootstrap_module
    finally:
        if real_server is not None:
            sys.modules["sdd_server.mcp.server"] = real_server
        else:
            sys.modules.pop("sdd_server.mcp.server", None)


_bootstrap = _import_bootstrap_module()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_tool_fn(name: str):
    app = FastMCP("test")
    _bootstrap.register_tools(app)
    return app._tool_manager._tools[name].fn


def _make_ctx(project_root: Path, ai_client=None):
    ctx = MagicMock()
    ctx.request_context.lifespan_context = {
        "project_root": project_root,
        "ai_client": ai_client or MagicMock(),
    }
    return ctx


def _make_client_result(success: bool = True, output: str = "", error: str | None = None):
    result = MagicMock()
    result.success = success
    result.output = output
    result.error = error
    return result


def _bootstrapper_envelope(**kwargs) -> str:
    """Build a single-line bootstrapper envelope JSON."""
    defaults = {
        "sdd_role": "spec-bootstrapper",
        "status": "completed",
        "summary": "Bootstrap complete",
        "mode": "generate",
        "generated": ["specs/prd.md", "specs/arch.md"],
        "skipped": [],
        "omitted_features": [],
        "stats": {
            "source_files_scanned": 10,
            "tests_analyzed": 5,
            "acs_generated": 3,
            "features_detected": 2,
        },
        "session_name": "sdd-spec-bootstrapper-default",
        "retry_hint": None,
    }
    defaults.update(kwargs)
    return json.dumps(defaults)


# ---------------------------------------------------------------------------
# TestBootstrapTool
# ---------------------------------------------------------------------------


class TestBootstrapTool:
    async def test_blocked_when_prd_exists_and_update_false(self, tmp_path: Path) -> None:
        """Guard: if prd.md exists and update_existing=False, return blocked without Goose."""
        (tmp_path / "specs").mkdir()
        (tmp_path / "specs" / "prd.md").write_text("# Existing PRD\n")

        fn = _get_tool_fn("sdd_bootstrap_specs")
        ai = MagicMock()
        ctx = _make_ctx(tmp_path, ai)

        result = await fn(update_existing=False, ctx=ctx)

        assert result["status"] == "blocked"
        assert "update_existing=true" in result["summary"]
        ai.invoke_role.assert_not_called()

    async def test_not_blocked_when_no_prd(self, tmp_path: Path) -> None:
        """No prd.md → proceed to Goose (update_existing=False is fine)."""
        fn = _get_tool_fn("sdd_bootstrap_specs")
        envelope = _bootstrapper_envelope()
        ai = MagicMock()
        ai.invoke_role = AsyncMock(return_value=_make_client_result(output=envelope))
        ctx = _make_ctx(tmp_path, ai)

        result = await fn(update_existing=False, ctx=ctx)

        ai.invoke_role.assert_called_once()
        assert result["status"] != "blocked"

    async def test_update_mode_passes_when_prd_exists(self, tmp_path: Path) -> None:
        """update_existing=True bypasses the guard even when prd.md exists."""
        (tmp_path / "specs").mkdir()
        (tmp_path / "specs" / "prd.md").write_text("# Existing PRD\n")

        fn = _get_tool_fn("sdd_bootstrap_specs")
        envelope = _bootstrapper_envelope(mode="update", status="completed")
        ai = MagicMock()
        ai.invoke_role = AsyncMock(return_value=_make_client_result(output=envelope))
        ctx = _make_ctx(tmp_path, ai)

        result = await fn(update_existing=True, ctx=ctx)

        ai.invoke_role.assert_called_once()
        assert result["status"] == "completed"

    async def test_max_features_clamped_to_20(self, tmp_path: Path) -> None:
        """max_features > 20 is silently clamped to 20."""
        fn = _get_tool_fn("sdd_bootstrap_specs")
        envelope = _bootstrapper_envelope()
        ai = MagicMock()
        ai.invoke_role = AsyncMock(return_value=_make_client_result(output=envelope))
        ctx = _make_ctx(tmp_path, ai)

        await fn(max_features=999, ctx=ctx)

        call_ctx = ai.invoke_role.call_args[0][1]
        assert int(call_ctx["max_features"]) <= 20

    async def test_recipe_path_passed_to_invoke_role(self, tmp_path: Path) -> None:
        """invoke_role receives the spec-bootstrapper recipe path."""
        fn = _get_tool_fn("sdd_bootstrap_specs")
        envelope = _bootstrapper_envelope()
        ai = MagicMock()
        ai.invoke_role = AsyncMock(return_value=_make_client_result(output=envelope))
        ctx = _make_ctx(tmp_path, ai)

        await fn(ctx=ctx)

        _, call_kwargs = ai.invoke_role.call_args
        recipe_path = call_kwargs.get("recipe_path")
        if recipe_path is None:
            recipe_path = ai.invoke_role.call_args[0][2]
        assert "spec-bootstrapper" in str(recipe_path)

    async def test_role_name_is_spec_bootstrapper(self, tmp_path: Path) -> None:
        """invoke_role is called with 'spec-bootstrapper' as the role name."""
        fn = _get_tool_fn("sdd_bootstrap_specs")
        envelope = _bootstrapper_envelope()
        ai = MagicMock()
        ai.invoke_role = AsyncMock(return_value=_make_client_result(output=envelope))
        ctx = _make_ctx(tmp_path, ai)

        await fn(ctx=ctx)

        role_name = ai.invoke_role.call_args[0][0]
        assert role_name == "spec-bootstrapper"

    async def test_rate_limit_returns_rate_limited(self) -> None:
        fn = _get_tool_fn("sdd_bootstrap_specs")
        cfg = RateLimitConfig(requests_per_window=0, window_seconds=60)
        configure_rate_limiter(cfg)

        try:
            result = await fn(ctx=None)
            assert result.get("error_code") == "RATE_LIMITED"
        finally:
            configure_rate_limiter(RateLimitConfig())


# ---------------------------------------------------------------------------
# TestEnvelopeParsing
# ---------------------------------------------------------------------------


class TestEnvelopeParsing:
    async def test_generated_list_extracted(self, tmp_path: Path) -> None:
        fn = _get_tool_fn("sdd_bootstrap_specs")
        envelope = _bootstrapper_envelope(
            generated=["specs/prd.md", "specs/arch.md", "specs/features/auth/prd.md"]
        )
        ai = MagicMock()
        ai.invoke_role = AsyncMock(return_value=_make_client_result(output=envelope))
        ctx = _make_ctx(tmp_path, ai)

        result = await fn(ctx=ctx)

        assert "specs/prd.md" in result["generated"]
        assert "specs/features/auth/prd.md" in result["generated"]

    async def test_skipped_list_extracted(self, tmp_path: Path) -> None:
        fn = _get_tool_fn("sdd_bootstrap_specs")
        envelope = _bootstrapper_envelope(
            skipped=[{"path": "specs/features/api/prd.md", "reason": "feature_dir_exists"}]
        )
        ai = MagicMock()
        ai.invoke_role = AsyncMock(return_value=_make_client_result(output=envelope))
        ctx = _make_ctx(tmp_path, ai)

        result = await fn(ctx=ctx)

        assert result["skipped"][0]["reason"] == "feature_dir_exists"

    async def test_stats_dict_extracted(self, tmp_path: Path) -> None:
        fn = _get_tool_fn("sdd_bootstrap_specs")
        envelope = _bootstrapper_envelope(
            stats={
                "source_files_scanned": 42,
                "tests_analyzed": 15,
                "acs_generated": 12,
                "features_detected": 4,
            }
        )
        ai = MagicMock()
        ai.invoke_role = AsyncMock(return_value=_make_client_result(output=envelope))
        ctx = _make_ctx(tmp_path, ai)

        result = await fn(ctx=ctx)

        assert result["stats"]["source_files_scanned"] == 42
        assert result["stats"]["features_detected"] == 4

    async def test_needs_retry_propagated(self, tmp_path: Path) -> None:
        fn = _get_tool_fn("sdd_bootstrap_specs")
        envelope = _bootstrapper_envelope(status="needs_retry", retry_hint="restart from step 4")
        ai = MagicMock()
        ai.invoke_role = AsyncMock(return_value=_make_client_result(success=False, output=envelope))
        ctx = _make_ctx(tmp_path, ai)

        result = await fn(ctx=ctx)

        assert result["status"] == "needs_retry"

    async def test_omitted_features_extracted(self, tmp_path: Path) -> None:
        fn = _get_tool_fn("sdd_bootstrap_specs")
        envelope = _bootstrapper_envelope(omitted_features=["big-module", "legacy"])
        ai = MagicMock()
        ai.invoke_role = AsyncMock(return_value=_make_client_result(output=envelope))
        ctx = _make_ctx(tmp_path, ai)

        result = await fn(ctx=ctx)

        assert "big-module" in result["omitted_features"]

    async def test_mode_field_extracted(self, tmp_path: Path) -> None:
        for mode in ("generate", "update"):
            fn = _get_tool_fn("sdd_bootstrap_specs")
            envelope = _bootstrapper_envelope(mode=mode)
            ai = MagicMock()
            ai.invoke_role = AsyncMock(return_value=_make_client_result(output=envelope))
            ctx = _make_ctx(tmp_path, ai)

            result = await fn(ctx=ctx)

            assert result["mode"] == mode

    async def test_envelope_amid_other_output_lines(self, tmp_path: Path) -> None:
        """Envelope is the last sdd_role JSON line even with other output before it."""
        fn = _get_tool_fn("sdd_bootstrap_specs")
        envelope_line = _bootstrapper_envelope(generated=["specs/prd.md"])
        raw_output = (
            "Scanning source tree...\n"
            '{"type": "text", "content": "step 3 done"}\n'
            f"{envelope_line}\n"
        )
        ai = MagicMock()
        ai.invoke_role = AsyncMock(return_value=_make_client_result(output=raw_output))
        ctx = _make_ctx(tmp_path, ai)

        result = await fn(ctx=ctx)

        assert result["generated"] == ["specs/prd.md"]

    async def test_failed_invocation_with_no_envelope_returns_error(self, tmp_path: Path) -> None:
        fn = _get_tool_fn("sdd_bootstrap_specs")
        ai = MagicMock()
        ai.invoke_role = AsyncMock(
            return_value=_make_client_result(success=False, output="", error="goose crashed")
        )
        ctx = _make_ctx(tmp_path, ai)

        result = await fn(ctx=ctx)

        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# TestPathValidation
# ---------------------------------------------------------------------------


class TestPathValidation:
    async def test_traversal_path_returns_error(self, tmp_path: Path) -> None:
        fn = _get_tool_fn("sdd_bootstrap_specs")
        ctx = _make_ctx(tmp_path)

        result = await fn(target_path="../../etc/passwd", ctx=ctx)

        assert "status" in result
        assert result["status"] == "error"

    async def test_default_target_path_uses_project_root(self, tmp_path: Path) -> None:
        fn = _get_tool_fn("sdd_bootstrap_specs")
        envelope = _bootstrapper_envelope()
        ai = MagicMock()
        ai.invoke_role = AsyncMock(return_value=_make_client_result(output=envelope))
        ctx = _make_ctx(tmp_path, ai)

        await fn(target_path=".", ctx=ctx)

        call_ctx = ai.invoke_role.call_args[0][1]
        assert str(tmp_path) in call_ctx["project_root"]
