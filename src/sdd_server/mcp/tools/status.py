"""MCP tool: sdd_status."""

from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import Context, FastMCP

from sdd_server.core.metadata import MetadataManager
from sdd_server.core.spec_manager import SpecManager


def register_tools(mcp: FastMCP) -> None:
    """Register status tools on the given FastMCP instance."""

    @mcp.tool()
    async def sdd_status(
        ctx: Context = None,  # type: ignore[assignment]
    ) -> dict[str, object]:
        """Return the current project state including workflow state and bypasses.

        Returns a JSON-serializable representation of ProjectState.
        """
        if ctx and hasattr(ctx, "request_context") and ctx.request_context:
            lifespan_ctx = ctx.request_context.lifespan_context
            metadata: MetadataManager = lifespan_ctx["metadata"]
            spec_manager: SpecManager = lifespan_ctx["spec_manager"]
        else:
            import os

            root = Path(os.getenv("SDD_PROJECT_ROOT", ".")).resolve()
            metadata = MetadataManager(root)
            spec_manager = SpecManager(root)

        state = metadata.load()
        issues = spec_manager.validate_structure()

        return {
            "workflow_state": state.workflow_state.value,
            "features": {
                fid: {
                    "state": fs.state.value,
                    "history_count": len(fs.history),
                }
                for fid, fs in state.features.items()
            },
            "bypasses": [
                {
                    "timestamp": b.timestamp.isoformat(),
                    "actor": b.actor,
                    "reason": b.reason,
                    "action": b.action,
                    "feature": b.feature,
                }
                for b in state.active_bypasses()
            ],
            "spec_issues": issues,
            "metadata": state.metadata,
        }
