"""MCP tools: spec read/write/list."""

from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import Context, FastMCP

from sdd_server.core.spec_manager import SpecManager
from sdd_server.infrastructure.exceptions import SDDError, SpecNotFoundError
from sdd_server.infrastructure.observability.audit import AuditEventType, get_audit_logger
from sdd_server.infrastructure.observability.metrics import get_metrics
from sdd_server.mcp.server import LifespanContext
from sdd_server.mcp.tools._utils import check_rate_limit, format_error
from sdd_server.models.spec import SpecType


def _get_spec_manager(ctx: Context | None) -> SpecManager:  # type: ignore[type-arg]
    if ctx and hasattr(ctx, "request_context") and ctx.request_context:
        state: LifespanContext = ctx.request_context.lifespan_context
        return state["spec_manager"]
    import os

    root = Path(os.getenv("SDD_PROJECT_ROOT", ".")).resolve()
    return SpecManager(root)


def register_tools(mcp: FastMCP) -> None:
    """Register spec tools on the given FastMCP instance."""

    @mcp.tool()
    async def sdd_spec_read(
        spec_type: str,
        feature: str = "",
        ctx: Context | None = None,  # type: ignore[type-arg]
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
            get_audit_logger().log_event(
                AuditEventType.FILE_READ,
                message=f"Read spec: {spec_type}" + (f"/{feature}" if feature else ""),
                resource=spec_type,
                result="success",
            )
            get_metrics().counter("sdd.tool.calls", labels={"tool": "sdd_spec_read"}).increment()
            return {"content": content, "spec_type": spec_type, "feature": feature}
        except SpecNotFoundError as exc:
            return format_error(exc)
        except Exception as exc:
            return format_error(exc)

    @mcp.tool()
    async def sdd_spec_write(
        spec_type: str,
        content: str,
        feature: str = "",
        mode: str = "overwrite",
        ctx: Context | None = None,  # type: ignore[type-arg]
    ) -> dict[str, object]:
        """Write content to a spec file.

        Args:
            spec_type: One of 'prd', 'arch', 'tasks', 'context-hints'.
            content: The content to write.
            feature: Feature name for feature-level specs (empty for root specs).
            mode: 'overwrite' | 'append' | 'prepend'
        """
        if rate_err := check_rate_limit("sdd_spec_write"):
            return rate_err

        try:
            stype = SpecType(spec_type)
        except ValueError:
            return {
                "error": f"Unknown spec type '{spec_type}'. Valid: {[s.value for s in SpecType]}"
            }

        mgr = _get_spec_manager(ctx)
        audit = get_audit_logger()
        try:
            mgr.write_spec(stype, content, feature or None, mode)
            audit.log_event(
                AuditEventType.SPEC_UPDATE,
                message=f"Wrote spec: {spec_type}" + (f"/{feature}" if feature else ""),
                resource=spec_type,
                result="success",
            )
            get_metrics().counter("sdd.tool.calls", labels={"tool": "sdd_spec_write"}).increment()
            return {"success": True, "spec_type": spec_type, "feature": feature, "mode": mode}
        except SDDError as exc:
            audit.log_event(
                AuditEventType.SPEC_UPDATE,
                message=f"Failed to write spec: {spec_type}",
                resource=spec_type,
                result="failure",
            )
            return format_error(exc)
        except Exception as exc:
            return format_error(exc)

    @mcp.tool()
    async def sdd_spec_list(
        ctx: Context | None = None,  # type: ignore[type-arg]
    ) -> dict[str, object]:
        """List all spec files in the project.

        Returns a dict describing the spec structure.
        """
        try:
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
        except Exception as exc:
            return format_error(exc)
