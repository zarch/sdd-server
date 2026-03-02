"""MCP tools: feature create/list."""

from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import Context, FastMCP

from sdd_server.core.spec_manager import SpecManager


def _get_spec_manager(ctx: Context | None) -> SpecManager:
    if ctx and hasattr(ctx, "request_context") and ctx.request_context:
        state = ctx.request_context.lifespan_context
        return state["spec_manager"]  # type: ignore[return-value]
    import os

    root = Path(os.getenv("SDD_PROJECT_ROOT", ".")).resolve()
    return SpecManager(root)


def register_tools(mcp: FastMCP) -> None:
    """Register feature tools on the given FastMCP instance."""

    @mcp.tool()
    async def sdd_feature_create(
        name: str,
        description: str = "",
        ctx: Context = None,  # type: ignore[assignment]
    ) -> dict[str, object]:
        """Create a new feature with spec templates.

        Args:
            name: Feature name (lowercase letters, digits, hyphens; start with letter).
            description: Short feature description.
        """
        mgr = _get_spec_manager(ctx)
        try:
            feature_dir = mgr.create_feature(name, description)
            return {
                "success": True,
                "feature": name,
                "path": str(feature_dir),
                "message": f"Feature '{name}' created at '{feature_dir}'",
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    @mcp.tool()
    async def sdd_feature_list(
        ctx: Context = None,  # type: ignore[assignment]
    ) -> dict[str, object]:
        """List all features in the project."""
        mgr = _get_spec_manager(ctx)
        features = mgr.list_features()
        return {"features": features, "count": len(features)}
