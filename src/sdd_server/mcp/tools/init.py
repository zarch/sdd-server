"""MCP tools: sdd_init and sdd_preflight."""

from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import Context, FastMCP

from sdd_server.core.initializer import ProjectInitializer
from sdd_server.core.spec_manager import SpecManager
from sdd_server.core.startup import StartupValidator
from sdd_server.infrastructure.git import GitClient
from sdd_server.infrastructure.observability.audit import AuditEventType, get_audit_logger
from sdd_server.mcp.tools._utils import check_rate_limit, format_error


def register_tools(mcp: FastMCP) -> None:
    """Register init tools on the given FastMCP instance."""

    @mcp.tool()
    async def sdd_init(
        project_name: str,
        description: str = "",
        project_root: str = "",
        ctx: Context | None = None,  # type: ignore[type-arg]
    ) -> dict[str, object]:
        """Initialize a new SDD project: create specs/ structure, render templates, install git hook.

        Args:
            project_name: Name of the project.
            description: Short project description.
            project_root: Override project root path (defaults to SDD_PROJECT_ROOT env var or cwd).
        """
        if rate_err := check_rate_limit("sdd_init"):
            return rate_err

        import os

        root = (
            Path(project_root).resolve()
            if project_root
            else Path(os.getenv("SDD_PROJECT_ROOT", ".")).resolve()
        )

        audit = get_audit_logger()
        if ctx and hasattr(ctx, "request_context") and ctx.request_context:
            state = ctx.request_context.lifespan_context
            git_client = state["git_client"]
            spec_manager = state["spec_manager"]
        else:
            git_client = GitClient(root)
            spec_manager = SpecManager(root)

        try:
            initializer = ProjectInitializer(root, spec_manager, git_client)
            initializer.init_new_project(project_name, description)

            validator = StartupValidator(root)
            report = validator.run()

            audit.log_event(
                AuditEventType.SYSTEM_STARTUP,
                message=f"Initialized project: {project_name}",
                resource=str(root),
                result="success",
            )

            warnings = [c.message for c in report.warnings]
            return {
                "success": True,
                "project_root": str(root),
                "warnings": warnings,
                "message": f"Project '{project_name}' initialized at '{root}'",
            }
        except Exception as exc:
            audit.log_event(
                AuditEventType.SYSTEM_STARTUP,
                message=f"Failed to initialize project: {project_name}",
                resource=str(root),
                result="failure",
            )
            return format_error(exc)

    @mcp.tool()
    async def sdd_preflight(
        action: str = "commit",
        ctx: Context | None = None,  # type: ignore[type-arg]
    ) -> dict[str, object]:
        """Run enforcement checks: validate spec structure, content, role reviews, and git hook.

        Checks performed:
        1. Core spec files present (prd.md, arch.md, tasks.md)       → BLOCKING
        2. Spec validation rules (content, required sections)          → BLOCKING/WARNING
        3. Role review checklist in tasks.md                          → WARNING
        4. Git pre-commit hook installed                              → WARNING

        Active bypasses (recorded via sdd bypass) suppress blocking violations for 24 h.

        Args:
            action: The action being checked (default: "commit").

        Returns:
            allowed: True only when no blocking violations remain.
            blocked: True when the action is blocked.
            violations: List of blocking violation dicts.
            warnings: List of non-blocking warning dicts.
            bypass_active: Whether an active bypass is in effect.
            bypass_reason: Reason for the active bypass (if any).
            checks_passed: Count of checks that passed.
            checks_run: Total checks run.
        """
        try:
            import os

            from sdd_server.core.enforcement import EnforcementEngine
            from sdd_server.core.metadata import MetadataManager
            from sdd_server.core.spec_validator import SpecValidator

            if ctx and hasattr(ctx, "request_context") and ctx.request_context:
                state = ctx.request_context.lifespan_context
                spec_manager: SpecManager = state["spec_manager"]
                spec_validator: SpecValidator = state["spec_validator"]
                git_client = state["git_client"]
                root = state["project_root"]
                metadata_manager: MetadataManager = state.get(
                    "metadata_manager", MetadataManager(root)
                )
            else:
                root = Path(os.getenv("SDD_PROJECT_ROOT", ".")).resolve()
                spec_manager = SpecManager(root)
                spec_validator = SpecValidator(root)
                git_client = GitClient(root)
                metadata_manager = MetadataManager(root)

            engine = EnforcementEngine(
                project_root=root,
                spec_manager=spec_manager,
                spec_validator=spec_validator,
                git_client=git_client,
                metadata_manager=metadata_manager,
            )
            report = await engine.run_async(action=action)

            return {
                "allowed": not report.blocked,
                "blocked": report.blocked,
                "violations": [v.as_dict() for v in report.violations],
                "warnings": [w.as_dict() for w in report.warnings],
                "bypass_active": report.bypass_active,
                "bypass_reason": report.bypass_reason,
                "checks_passed": report.checks_passed,
                "checks_run": report.checks_run,
            }
        except Exception as exc:
            return format_error(exc)
