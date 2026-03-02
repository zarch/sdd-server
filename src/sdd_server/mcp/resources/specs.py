"""MCP resources: expose spec files via sdd://specs/{path} URIs."""

from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import Context, FastMCP

from sdd_server.core.spec_manager import SpecManager
from sdd_server.infrastructure.exceptions import SpecNotFoundError
from sdd_server.models.spec import SpecType


def _get_spec_manager(ctx: Context | None) -> SpecManager:
    if ctx and hasattr(ctx, "request_context") and ctx.request_context:
        state = ctx.request_context.lifespan_context
        return state["spec_manager"]  # type: ignore[return-value]
    import os

    root = Path(os.getenv("SDD_PROJECT_ROOT", ".")).resolve()
    return SpecManager(root)


_SPEC_TYPE_MAP: dict[str, SpecType] = {
    "prd": SpecType.PRD,
    "arch": SpecType.ARCH,
    "tasks": SpecType.TASKS,
    "context-hints": SpecType.CONTEXT_HINTS,
}


def register_resources(mcp: FastMCP) -> None:
    """Register spec resources on the given FastMCP instance."""

    @mcp.resource("sdd://specs/{spec_type}")
    async def read_root_spec(spec_type: str, ctx: Context = None) -> str:  # type: ignore[assignment]
        """Read a root-level spec file.

        URI: sdd://specs/{spec_type}
        spec_type: prd | arch | tasks | context-hints
        """
        mgr = _get_spec_manager(ctx)
        stype = _SPEC_TYPE_MAP.get(spec_type)
        if stype is None:
            return f"Error: Unknown spec type '{spec_type}'"
        try:
            return mgr.read_spec(stype)
        except SpecNotFoundError as exc:
            return f"Error: {exc}"

    @mcp.resource("sdd://specs/features/{feature}/{spec_type}")
    async def read_feature_spec(
        feature: str,
        spec_type: str,
        ctx: Context = None,  # type: ignore[assignment]
    ) -> str:
        """Read a feature-level spec file.

        URI: sdd://specs/features/{feature}/{spec_type}
        """
        mgr = _get_spec_manager(ctx)
        stype = _SPEC_TYPE_MAP.get(spec_type)
        if stype is None:
            return f"Error: Unknown spec type '{spec_type}'"
        try:
            return mgr.read_spec(stype, feature)
        except SpecNotFoundError as exc:
            return f"Error: {exc}"
