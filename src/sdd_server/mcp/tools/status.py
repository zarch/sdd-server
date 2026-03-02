"""MCP tools: status reporting."""

from __future__ import annotations

from mcp.server.fastmcp import Context, FastMCP

from sdd_server.core.metadata import MetadataManager
from sdd_server.core.spec_manager import SpecManager
from sdd_server.utils.logging import get_logger

logger = get_logger(__name__)


def _get_managers(
    ctx: Context | None,  # type: ignore[type-arg]
) -> tuple[MetadataManager, SpecManager]:
    """Get metadata and spec managers from context."""
    if ctx and hasattr(ctx, "request_context") and ctx.request_context:
        state = ctx.request_context.lifespan_context
        return state["metadata"], state["spec_manager"]
    import os
    from pathlib import Path

    root = Path(os.getenv("SDD_PROJECT_ROOT", ".")).resolve()
    return MetadataManager(root), SpecManager(root)


def register_tools(mcp: FastMCP) -> None:
    """Register status tool on the given FastMCP instance."""

    @mcp.tool()
    async def sdd_status(
        ctx: Context | None = None,  # type: ignore[type-arg]
    ) -> dict[str, object]:
        """Return current project status: workflow state, features, bypasses, and spec issues."""
        metadata, spec_manager = _get_managers(ctx)
        state = metadata.load()
        issues = spec_manager.validate_structure()
        return {
            "workflow_state": state.workflow_state.value,
            "features": list(state.features.keys()),
            "feature_count": len(state.features),
            "bypass_count": len(state.bypasses),
            "spec_issues": issues,
            "issues_count": len(issues),
        }
