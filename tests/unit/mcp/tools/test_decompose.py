"""Unit tests for MCP decompose tool (sdd_decompose_specs)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from mcp.server.fastmcp import FastMCP

from sdd_server.core.spec_decomposer import DecompositionResult, FeatureBoundary
from sdd_server.infrastructure.security.rate_limiter import (
    RateLimitConfig,
    configure_rate_limiter,
)

# ---------------------------------------------------------------------------
# Circular import workaround (same pattern as other MCP tool tests)
# ---------------------------------------------------------------------------


def _import_decompose_module():
    real_server = sys.modules.get("sdd_server.mcp.server")
    real_mod = sys.modules.get("sdd_server.mcp.tools.decompose")

    if real_mod is not None and hasattr(real_mod, "register_tools"):
        return real_mod

    stub = MagicMock()
    sys.modules["sdd_server.mcp.server"] = stub

    try:
        sys.modules.pop("sdd_server.mcp.tools.decompose", None)
        import sdd_server.mcp.tools.decompose as decompose_module

        return decompose_module
    finally:
        if real_server is not None:
            sys.modules["sdd_server.mcp.server"] = real_server
        else:
            sys.modules.pop("sdd_server.mcp.server", None)


_decompose_module = _import_decompose_module()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_tool_fn(name: str):
    app = FastMCP("test")
    _decompose_module.register_tools(app)
    return app._tool_manager._tools[name].fn


def _make_ctx(project_root: Path):
    ctx = MagicMock()
    ctx.request_context.lifespan_context = {"project_root": project_root}
    return ctx


def _make_result(
    features: list[FeatureBoundary] | None = None,
    skipped: list[dict] | None = None,
    files_created: list[str] | None = None,
    dry_run: bool = False,
    coverage_pct: float = 100.0,
) -> DecompositionResult:
    return DecompositionResult(
        features=features or [],
        skipped=skipped or [],
        unassigned_acs=[],
        coverage_pct=coverage_pct,
        files_created=files_created or [],
        dry_run=dry_run,
    )


def _make_boundary(slug: str = "auth", title: str = "Authentication") -> FeatureBoundary:
    return FeatureBoundary(
        slug=slug,
        title=title,
        acs=["AC-01", "AC-02"],
        content_blocks=["- **AC-01:** Login.", "- **AC-02:** Logout."],
        source_line_start=5,
        source_line_end=12,
    )


# ---------------------------------------------------------------------------
# TestSddDecomposeSpecs
# ---------------------------------------------------------------------------


class TestSddDecomposeSpecs:
    async def test_success_returns_ok_status(self, tmp_path: Path) -> None:
        fn = _get_tool_fn("sdd_decompose_specs")
        boundary = _make_boundary()
        result = _make_result(
            features=[boundary],
            files_created=["specs/features/auth/prd.md"],
        )
        ctx = _make_ctx(tmp_path)

        with patch(
            "sdd_server.mcp.tools.decompose.SpecDecomposer.decompose",
            return_value=result,
        ):
            out = await fn(ctx=ctx)

        assert out["status"] == "ok"
        assert len(out["features"]) == 1
        assert out["features"][0]["slug"] == "auth"

    async def test_dry_run_returns_dry_run_status(self, tmp_path: Path) -> None:
        fn = _get_tool_fn("sdd_decompose_specs")
        result = _make_result(dry_run=True)
        ctx = _make_ctx(tmp_path)

        with patch(
            "sdd_server.mcp.tools.decompose.SpecDecomposer.decompose",
            return_value=result,
        ):
            out = await fn(dry_run=True, ctx=ctx)

        assert out["status"] == "dry_run"

    async def test_skipped_list_included(self, tmp_path: Path) -> None:
        fn = _get_tool_fn("sdd_decompose_specs")
        result = _make_result(
            skipped=[{"slug": "billing", "reason": "already_exists"}],
        )
        ctx = _make_ctx(tmp_path)

        with patch(
            "sdd_server.mcp.tools.decompose.SpecDecomposer.decompose",
            return_value=result,
        ):
            out = await fn(ctx=ctx)

        assert out["skipped"] == [{"slug": "billing", "reason": "already_exists"}]

    async def test_coverage_pct_included(self, tmp_path: Path) -> None:
        fn = _get_tool_fn("sdd_decompose_specs")
        result = _make_result(coverage_pct=87.5)
        ctx = _make_ctx(tmp_path)

        with patch(
            "sdd_server.mcp.tools.decompose.SpecDecomposer.decompose",
            return_value=result,
        ):
            out = await fn(ctx=ctx)

        assert out["coverage_pct"] == 87.5

    async def test_exception_returns_error_dict(self, tmp_path: Path) -> None:
        fn = _get_tool_fn("sdd_decompose_specs")
        ctx = _make_ctx(tmp_path)

        with patch(
            "sdd_server.mcp.tools.decompose.SpecDecomposer.decompose",
            side_effect=RuntimeError("disk error"),
        ):
            out = await fn(ctx=ctx)

        assert "error" in out

    async def test_rate_limit_returns_rate_limited(self, tmp_path: Path) -> None:
        fn = _get_tool_fn("sdd_decompose_specs")
        cfg = RateLimitConfig(requests_per_window=0, window_seconds=60)
        configure_rate_limiter(cfg)

        try:
            out = await fn(ctx=None)
            assert out.get("error_code") == "RATE_LIMITED"
        finally:
            configure_rate_limiter(RateLimitConfig())

    async def test_dry_run_features_have_no_files_created(self, tmp_path: Path) -> None:
        fn = _get_tool_fn("sdd_decompose_specs")
        boundary = _make_boundary()
        result = _make_result(features=[boundary], dry_run=True, files_created=[])
        ctx = _make_ctx(tmp_path)

        with patch(
            "sdd_server.mcp.tools.decompose.SpecDecomposer.decompose",
            return_value=result,
        ):
            out = await fn(dry_run=True, ctx=ctx)

        assert out["features"][0]["files_created"] == []

    async def test_non_dry_run_features_have_file_paths(self, tmp_path: Path) -> None:
        fn = _get_tool_fn("sdd_decompose_specs")
        boundary = _make_boundary(slug="auth")
        result = _make_result(
            features=[boundary],
            files_created=[
                "specs/features/auth/prd.md",
                "specs/features/auth/arch.md",
                "specs/features/auth/tasks.md",
            ],
        )
        ctx = _make_ctx(tmp_path)

        with patch(
            "sdd_server.mcp.tools.decompose.SpecDecomposer.decompose",
            return_value=result,
        ):
            out = await fn(ctx=ctx)

        file_paths = out["features"][0]["files_created"]
        assert any("prd.md" in p for p in file_paths)
        assert any("arch.md" in p for p in file_paths)
        assert any("tasks.md" in p for p in file_paths)

    async def test_unassigned_acs_included(self, tmp_path: Path) -> None:
        fn = _get_tool_fn("sdd_decompose_specs")
        result = DecompositionResult(
            features=[],
            skipped=[],
            unassigned_acs=["AC-07", "AC-08"],
            coverage_pct=80.0,
            files_created=[],
            dry_run=False,
        )
        ctx = _make_ctx(tmp_path)

        with patch(
            "sdd_server.mcp.tools.decompose.SpecDecomposer.decompose",
            return_value=result,
        ):
            out = await fn(ctx=ctx)

        assert out["unassigned_acs"] == ["AC-07", "AC-08"]

    async def test_target_feature_passed_to_decomposer(self, tmp_path: Path) -> None:
        fn = _get_tool_fn("sdd_decompose_specs")
        result = _make_result()
        ctx = _make_ctx(tmp_path)

        with patch(
            "sdd_server.mcp.tools.decompose.SpecDecomposer.decompose",
            return_value=result,
        ) as mock_decompose:
            await fn(target_feature="auth", ctx=ctx)

        mock_decompose.assert_called_once_with(
            dry_run=False,
            force=False,
            target="auth",
        )

    async def test_force_flag_passed_to_decomposer(self, tmp_path: Path) -> None:
        fn = _get_tool_fn("sdd_decompose_specs")
        result = _make_result()
        ctx = _make_ctx(tmp_path)

        with patch(
            "sdd_server.mcp.tools.decompose.SpecDecomposer.decompose",
            return_value=result,
        ) as mock_decompose:
            await fn(force=True, ctx=ctx)

        mock_decompose.assert_called_once_with(
            dry_run=False,
            force=True,
            target=None,
        )
