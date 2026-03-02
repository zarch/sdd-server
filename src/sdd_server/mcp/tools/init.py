"""MCP tools: sdd_init and sdd_preflight."""

from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import Context, FastMCP

from sdd_server.core.initializer import ProjectInitializer
from sdd_server.core.spec_manager import SpecManager
from sdd_server.core.startup import StartupValidator
from sdd_server.infrastructure.git import GitClient


def register_tools(mcp: FastMCP) -> None:
    """Register init tools on the given FastMCP instance."""

    @mcp.tool()
    async def sdd_init(
        project_name: str,
        description: str = "",
        project_root: str = "",
        ctx: Context = None,  # type: ignore[assignment]
    ) -> dict[str, object]:
        """Initialize a new SDD project: create specs/ structure, render templates, install git hook.

        Args:
            project_name: Name of the project.
            description: Short project description.
            project_root: Override project root path (defaults to SDD_PROJECT_ROOT env var or cwd).
        """
        import os

        root = (
            Path(project_root).resolve()
            if project_root
            else Path(os.getenv("SDD_PROJECT_ROOT", ".")).resolve()
        )

        git_client = GitClient(root)
        spec_manager = SpecManager(root)
        initializer = ProjectInitializer(root, spec_manager, git_client)
        initializer.init_new_project(project_name, description)

        validator = StartupValidator(root)
        report = validator.run()

        warnings = [c.message for c in report.warnings]
        return {
            "success": True,
            "project_root": str(root),
            "warnings": warnings,
            "message": f"Project '{project_name}' initialized at '{root}'",
        }

    @mcp.tool()
    async def sdd_preflight(
        ctx: Context = None,  # type: ignore[assignment]
    ) -> dict[str, object]:
        """Run preflight checks: validate spec structure and return enforcement status.

        Returns:
            allowed: Whether the operation is allowed to proceed.
            issues: List of structural issues found.
            checks_passed: Number of checks that passed.
        """
        if ctx and hasattr(ctx, "request_context") and ctx.request_context:
            state = ctx.request_context.lifespan_context
            spec_manager: SpecManager = state["spec_manager"]
        else:
            import os

            root = Path(os.getenv("SDD_PROJECT_ROOT", ".")).resolve()
            spec_manager = SpecManager(root)

        issues = spec_manager.validate_structure()
        return {
            "allowed": len(issues) == 0,
            "issues": issues,
            "checks_passed": int(len(issues) == 0),
        }
