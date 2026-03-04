"""MCP tools: feature create and list."""

from __future__ import annotations

from mcp.server.fastmcp import Context, FastMCP

from sdd_server.core.spec_manager import SpecManager
from sdd_server.infrastructure.exceptions import ValidationError
from sdd_server.mcp.server import LifespanContext


def _get_spec_manager(ctx: Context | None) -> SpecManager:  # type: ignore[type-arg]
    if ctx and hasattr(ctx, "request_context") and ctx.request_context:
        state: LifespanContext = ctx.request_context.lifespan_context
        return state["spec_manager"]
    import os
    from pathlib import Path

    root = Path(os.getenv("SDD_PROJECT_ROOT", ".")).resolve()
    return SpecManager(root)


def register_tools(mcp: FastMCP) -> None:
    """Register feature tools on the given FastMCP instance."""

    @mcp.tool()
    async def sdd_feature_create(
        name: str,
        description: str = "",
        ctx: Context | None = None,  # type: ignore[type-arg]
    ) -> dict[str, object]:
        """Create a new feature subdirectory under specs/<name>.

        Args:
            name: Feature name (lowercase, hyphens allowed).
            description: Short feature description.
        """
        mgr = _get_spec_manager(ctx)
        try:
            feature_dir = mgr.create_feature(name, description)
            return {
                "success": True,
                "feature": name,
                "path": str(feature_dir),
            }
        except ValidationError as exc:
            return {"error": str(exc)}

    @mcp.tool()
    async def sdd_feature_list(
        ctx: Context | None = None,  # type: ignore[type-arg]
    ) -> dict[str, object]:
        """List all features in the project."""
        mgr = _get_spec_manager(ctx)
        features = mgr.list_features()
        return {"features": features, "count": len(features)}
