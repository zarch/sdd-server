"""MCP tools: spec read/write/list."""

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


def register_tools(mcp: FastMCP) -> None:
    """Register spec tools on the given FastMCP instance."""

    @mcp.tool()
    async def sdd_spec_read(
        spec_type: str,
        feature: str = "",
        ctx: Context = None,  # type: ignore[assignment]
    ) -> dict[str, object]:
        """Read the content of a spec file.

        Args:
            spec_type: One of 'prd', 'arch', 'tasks', 'context-hints'.
            feature: Feature name for feature-level specs (empty for root specs).
        """
        try:
            stype = SpecType(spec_type)
        except ValueError:
            return {
                "error": f"Unknown spec type '{spec_type}'. Valid: {[s.value for s in SpecType]}"
            }

        mgr = _get_spec_manager(ctx)
        try:
            content = mgr.read_spec(stype, feature or None)
            return {"content": content, "spec_type": spec_type, "feature": feature}
        except SpecNotFoundError as exc:
            return {"error": str(exc)}

    @mcp.tool()
    async def sdd_spec_write(
        spec_type: str,
        content: str,
        feature: str = "",
        mode: str = "overwrite",
        ctx: Context = None,  # type: ignore[assignment]
    ) -> dict[str, object]:
        """Write content to a spec file.

        Args:
            spec_type: One of 'prd', 'arch', 'tasks', 'context-hints'.
            content: The content to write.
            feature: Feature name for feature-level specs (empty for root specs).
            mode: 'overwrite' | 'append' | 'prepend'
        """
        try:
            stype = SpecType(spec_type)
        except ValueError:
            return {
                "error": f"Unknown spec type '{spec_type}'. Valid: {[s.value for s in SpecType]}"
            }

        mgr = _get_spec_manager(ctx)
        try:
            mgr.write_spec(stype, content, feature or None, mode)
            return {"success": True, "spec_type": spec_type, "feature": feature, "mode": mode}
        except Exception as exc:
            return {"error": str(exc)}

    @mcp.tool()
    async def sdd_spec_list(
        ctx: Context = None,  # type: ignore[assignment]
    ) -> dict[str, object]:
        """List all spec files in the project.

        Returns a dict describing the spec structure.
        """
        mgr = _get_spec_manager(ctx)
        features = mgr.list_features()
        issues = mgr.validate_structure()

        structure: dict[str, object] = {
            "root": {
                "prd": mgr.paths.prd_path.exists(),
                "arch": mgr.paths.arch_path.exists(),
                "tasks": mgr.paths.tasks_path.exists(),
                "context_hints": mgr.paths.context_hints_path.exists(),
            },
            "features": features,
            "issues": issues,
        }
        return structure
