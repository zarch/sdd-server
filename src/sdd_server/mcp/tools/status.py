"""MCP tools: status reporting."""

from __future__ import annotations

from mcp.server.fastmcp import Context, FastMCP

from sdd_server.core.metadata import MetadataManager
from sdd_server.core.spec_manager import SpecManager
from sdd_server.core.task_manager import TaskBreakdownManager
from sdd_server.utils.logging import get_logger

logger = get_logger(__name__)


def _get_managers(
    ctx: Context | None,  # type: ignore[type-arg]
) -> tuple[MetadataManager, SpecManager, TaskBreakdownManager]:
    """Get managers from lifespan context or construct fresh instances."""
    if ctx and hasattr(ctx, "request_context") and ctx.request_context:
        state = ctx.request_context.lifespan_context
        return state["metadata"], state["spec_manager"], state["task_manager"]
    import os
    from pathlib import Path

    root = Path(os.getenv("SDD_PROJECT_ROOT", ".")).resolve()
    return MetadataManager(root), SpecManager(root), TaskBreakdownManager(root)


def register_tools(mcp: FastMCP) -> None:
    """Register status tool on the given FastMCP instance."""

    @mcp.tool()
    async def sdd_status(
        ctx: Context | None = None,  # type: ignore[type-arg]
    ) -> dict[str, object]:
        """Return current project status: workflow state, features, task progress, and spec issues."""
        metadata, spec_manager, task_manager = _get_managers(ctx)
        state = metadata.load()
        issues = spec_manager.validate_structure()

        # Aggregate task progress across root and all features
        all_progress = task_manager.get_all_progress()
        task_summary: dict[str, object] = {}
        for feature, progress in all_progress.items():
            key = feature if feature is not None else "__root__"
            task_summary[key] = {
                "total": progress["total"],
                "complete": progress["complete"],
                "percentage": progress["percentage"],
            }

        # Per-feature workflow state
        feature_states = {name: fs.state.value for name, fs in state.features.items()}

        return {
            "workflow_state": state.workflow_state.value,
            "features": list(state.features.keys()),
            "feature_count": len(state.features),
            "feature_states": feature_states,
            "bypass_count": len(state.bypasses),
            "spec_issues": issues,
            "issues_count": len(issues),
            "task_progress": task_summary,
        }
