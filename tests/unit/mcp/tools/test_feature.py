"""Unit tests for MCP feature tools (sdd_feature_create, sdd_feature_list)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

from mcp.server.fastmcp import FastMCP

from sdd_server.infrastructure.security.rate_limiter import (
    RateLimitConfig,
    configure_rate_limiter,
)

# ---------------------------------------------------------------------------
# Break circular import: same pattern as test_spec.py
# ---------------------------------------------------------------------------


def _import_feature_module():
    """Import feature module with a temporary server stub to break circular import."""
    real_server = sys.modules.get("sdd_server.mcp.server")
    real_feature = sys.modules.get("sdd_server.mcp.tools.feature")

    # If already imported (by the real server), just return it
    if real_feature is not None and hasattr(real_feature, "register_tools"):
        return real_feature

    stub = MagicMock()
    sys.modules["sdd_server.mcp.server"] = stub

    try:
        sys.modules.pop("sdd_server.mcp.tools.feature", None)
        import sdd_server.mcp.tools.feature as feature_module

        return feature_module
    finally:
        if real_server is not None:
            sys.modules["sdd_server.mcp.server"] = real_server
        else:
            sys.modules.pop("sdd_server.mcp.server", None)


_feature_module = _import_feature_module()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_tool_fn(name: str):
    app = FastMCP("test")
    _feature_module.register_tools(app)
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
# sdd_feature_create
# ---------------------------------------------------------------------------


class TestSddFeatureCreate:
    async def test_success_returns_success_true(self) -> None:
        fn = _get_tool_fn("sdd_feature_create")
        mgr = _make_spec_manager()
        mgr.create_feature.return_value = Path("/proj/specs/auth")
        ctx = _make_ctx({"spec_manager": mgr})

        result = await fn(name="auth", description="Auth feature", ctx=ctx)

        assert result.get("success") is True
        assert result["feature"] == "auth"
        assert "path" in result

    async def test_exception_returns_error_dict(self) -> None:
        fn = _get_tool_fn("sdd_feature_create")
        mgr = _make_spec_manager()
        mgr.create_feature.side_effect = ValueError("invalid feature name")
        ctx = _make_ctx({"spec_manager": mgr})

        result = await fn(name="BAD NAME", ctx=ctx)

        assert "error" in result

    async def test_rate_limit_returns_rate_limited(self) -> None:
        fn = _get_tool_fn("sdd_feature_create")
        cfg = RateLimitConfig(requests_per_window=0, window_seconds=60)
        configure_rate_limiter(cfg)

        try:
            result = await fn(name="auth", ctx=None)
            assert result.get("error_code") == "RATE_LIMITED"
        finally:
            configure_rate_limiter(RateLimitConfig())

    async def test_path_in_result_is_stringified(self) -> None:
        fn = _get_tool_fn("sdd_feature_create")
        feature_dir = Path("/project/specs/payments")
        mgr = _make_spec_manager()
        mgr.create_feature.return_value = feature_dir
        ctx = _make_ctx({"spec_manager": mgr})

        result = await fn(name="payments", ctx=ctx)

        assert result["path"] == str(feature_dir)


# ---------------------------------------------------------------------------
# sdd_feature_list
# ---------------------------------------------------------------------------


class TestSddFeatureList:
    async def test_returns_features_and_count(self) -> None:
        fn = _get_tool_fn("sdd_feature_list")
        mgr = _make_spec_manager()
        mgr.list_features.return_value = ["auth", "billing", "payments"]
        ctx = _make_ctx({"spec_manager": mgr})

        result = await fn(ctx=ctx)

        assert result["features"] == ["auth", "billing", "payments"]
        assert result["count"] == 3

    async def test_empty_list_returns_zero_count(self) -> None:
        fn = _get_tool_fn("sdd_feature_list")
        mgr = _make_spec_manager()
        mgr.list_features.return_value = []
        ctx = _make_ctx({"spec_manager": mgr})

        result = await fn(ctx=ctx)

        assert result["features"] == []
        assert result["count"] == 0

    async def test_exception_returns_error(self) -> None:
        fn = _get_tool_fn("sdd_feature_list")
        mgr = _make_spec_manager()
        mgr.list_features.side_effect = RuntimeError("disk error")
        ctx = _make_ctx({"spec_manager": mgr})

        result = await fn(ctx=ctx)

        assert "error" in result
