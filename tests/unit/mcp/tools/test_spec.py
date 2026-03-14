"""Unit tests for MCP spec tools (sdd_spec_read, sdd_spec_write, sdd_spec_list)."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

from mcp.server.fastmcp import FastMCP

from sdd_server.infrastructure.exceptions import SDDError, SpecNotFoundError
from sdd_server.infrastructure.security.rate_limiter import (
    RateLimitConfig,
    configure_rate_limiter,
)

# ---------------------------------------------------------------------------
# Break circular import: the spec module does `from sdd_server.mcp.server import
# LifespanContext` at module level, and server.py runs create_server() which in turn
# imports spec — a true circular import.
#
# Strategy: patch sys.modules["sdd_server.mcp.server"] BEFORE importing the spec
# module, then restore it afterwards so that later tests that import the real server
# module still work correctly.
# ---------------------------------------------------------------------------


def _import_spec_module():
    """Import spec module with a temporary server stub to break circular import."""
    real_server = sys.modules.get("sdd_server.mcp.server")
    real_spec = sys.modules.get("sdd_server.mcp.tools.spec")

    # If already imported (by the real server), just return it
    if real_spec is not None and hasattr(real_spec, "register_tools"):
        return real_spec

    # Inject a stub for server to prevent circular import
    stub = MagicMock()
    sys.modules["sdd_server.mcp.server"] = stub

    try:
        # Remove cached spec module if it exists with bad state
        sys.modules.pop("sdd_server.mcp.tools.spec", None)
        import sdd_server.mcp.tools.spec as spec_module

        return spec_module
    finally:
        # Restore original server module (or remove stub)
        if real_server is not None:
            sys.modules["sdd_server.mcp.server"] = real_server
        else:
            sys.modules.pop("sdd_server.mcp.server", None)


_spec_module = _import_spec_module()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_tool_fn(name: str):
    app = FastMCP("test")
    _spec_module.register_tools(app)
    return app._tool_manager._tools[name].fn


def _make_ctx(lifespan_context: dict):
    ctx = MagicMock()
    ctx.request_context.lifespan_context = lifespan_context
    return ctx


def _make_spec_manager(**kwargs) -> MagicMock:
    mgr = MagicMock()
    for k, v in kwargs.items():
        setattr(mgr, k, v)
    return mgr


# ---------------------------------------------------------------------------
# sdd_spec_read
# ---------------------------------------------------------------------------


class TestSddSpecRead:
    async def test_valid_spec_type_returns_content(self) -> None:
        fn = _get_tool_fn("sdd_spec_read")
        mgr = _make_spec_manager()
        mgr.read_spec.return_value = "# PRD content"
        ctx = _make_ctx({"spec_manager": mgr})

        result = await fn(spec_type="prd", ctx=ctx)

        assert result["content"] == "# PRD content"
        assert result["spec_type"] == "prd"

    async def test_invalid_spec_type_returns_error(self) -> None:
        fn = _get_tool_fn("sdd_spec_read")
        ctx = _make_ctx({})

        result = await fn(spec_type="invalid_type_xyz", ctx=ctx)

        assert "error" in result
        assert "invalid_type_xyz" in result["error"]

    async def test_spec_not_found_error_returns_error_dict(self) -> None:
        fn = _get_tool_fn("sdd_spec_read")
        mgr = _make_spec_manager()
        mgr.read_spec.side_effect = SpecNotFoundError("prd not found")
        ctx = _make_ctx({"spec_manager": mgr})

        result = await fn(spec_type="prd", ctx=ctx)

        assert "error" in result

    async def test_with_feature_name(self) -> None:
        fn = _get_tool_fn("sdd_spec_read")
        mgr = _make_spec_manager()
        mgr.read_spec.return_value = "feature content"
        ctx = _make_ctx({"spec_manager": mgr})

        result = await fn(spec_type="prd", feature="auth", ctx=ctx)

        assert result["feature"] == "auth"
        mgr.read_spec.assert_called_once()
        call_args = mgr.read_spec.call_args
        # feature argument should be "auth"
        assert "auth" in call_args[0] or "auth" in str(call_args)

    async def test_general_exception_returns_error(self) -> None:
        fn = _get_tool_fn("sdd_spec_read")
        mgr = _make_spec_manager()
        mgr.read_spec.side_effect = RuntimeError("unexpected failure")
        ctx = _make_ctx({"spec_manager": mgr})

        result = await fn(spec_type="prd", ctx=ctx)

        assert "error" in result


# ---------------------------------------------------------------------------
# sdd_spec_write
# ---------------------------------------------------------------------------


class TestSddSpecWrite:
    async def test_success_returns_success_true(self) -> None:
        fn = _get_tool_fn("sdd_spec_write")
        mgr = _make_spec_manager()
        ctx = _make_ctx({"spec_manager": mgr})

        result = await fn(spec_type="prd", content="# New PRD", ctx=ctx)

        assert result.get("success") is True
        assert result["spec_type"] == "prd"

    async def test_invalid_spec_type_returns_error(self) -> None:
        fn = _get_tool_fn("sdd_spec_write")
        ctx = _make_ctx({})

        result = await fn(spec_type="__bad__", content="x", ctx=ctx)

        assert "error" in result
        assert "__bad__" in result["error"]

    async def test_sdd_error_returns_format_error(self) -> None:
        fn = _get_tool_fn("sdd_spec_write")
        mgr = _make_spec_manager()
        from sdd_server.infrastructure.exceptions import ErrorCode, ErrorContext

        exc = SDDError(
            "write failed",
            code=ErrorCode.VALIDATION_FAILED,
            context=ErrorContext(correlation_id="corr-123"),
        )
        mgr.write_spec.side_effect = exc
        ctx = _make_ctx({"spec_manager": mgr})

        result = await fn(spec_type="prd", content="x", ctx=ctx)

        assert "error" in result
        assert "error_code" in result

    async def test_rate_limit_returns_rate_limited(self) -> None:
        fn = _get_tool_fn("sdd_spec_write")
        # Configure a limiter with 0 requests allowed per window
        cfg = RateLimitConfig(requests_per_window=0, window_seconds=60)
        configure_rate_limiter(cfg)

        try:
            result = await fn(spec_type="prd", content="x", ctx=None)
            assert result.get("error_code") == "RATE_LIMITED"
        finally:
            # Reset the rate limiter so other tests are unaffected
            configure_rate_limiter(RateLimitConfig())

    async def test_general_exception_returns_error(self) -> None:
        fn = _get_tool_fn("sdd_spec_write")
        mgr = _make_spec_manager()
        mgr.write_spec.side_effect = RuntimeError("disk full")
        ctx = _make_ctx({"spec_manager": mgr})

        result = await fn(spec_type="prd", content="x", ctx=ctx)

        assert "error" in result


# ---------------------------------------------------------------------------
# sdd_spec_list
# ---------------------------------------------------------------------------


class TestSddSpecList:
    async def test_returns_root_features_issues_keys(self) -> None:
        fn = _get_tool_fn("sdd_spec_list")
        mgr = _make_spec_manager()
        mgr.list_features.return_value = ["auth", "billing"]
        mgr.validate_structure.return_value = []
        # paths mock
        paths = MagicMock()
        paths.prd_path.exists.return_value = True
        paths.arch_path.exists.return_value = False
        paths.tasks_path.exists.return_value = True
        paths.context_hints_path.exists.return_value = False
        mgr.paths = paths
        ctx = _make_ctx({"spec_manager": mgr})

        result = await fn(ctx=ctx)

        assert "root" in result
        assert "features" in result
        assert "issues" in result
        assert result["features"] == ["auth", "billing"]

    async def test_root_reports_existing_files(self) -> None:
        fn = _get_tool_fn("sdd_spec_list")
        mgr = _make_spec_manager()
        mgr.list_features.return_value = []
        mgr.validate_structure.return_value = []
        paths = MagicMock()
        paths.prd_path.exists.return_value = True
        paths.arch_path.exists.return_value = True
        paths.tasks_path.exists.return_value = False
        paths.context_hints_path.exists.return_value = False
        mgr.paths = paths
        ctx = _make_ctx({"spec_manager": mgr})

        result = await fn(ctx=ctx)

        assert result["root"]["prd"] is True
        assert result["root"]["arch"] is True
        assert result["root"]["tasks"] is False

    async def test_exception_returns_error(self) -> None:
        fn = _get_tool_fn("sdd_spec_list")
        mgr = _make_spec_manager()
        mgr.list_features.side_effect = RuntimeError("boom")
        ctx = _make_ctx({"spec_manager": mgr})

        result = await fn(ctx=ctx)

        assert "error" in result
