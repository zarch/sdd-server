"""MCP tools: role-based review execution.

Tools for running and managing role-based code reviews:
- sdd_review_run: Execute role reviews
- sdd_review_status: Check review status
- sdd_review_results: Get review results
- sdd_review_list: List available roles
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import Context, FastMCP

from sdd_server.core.recipe_generator import RecipeGenerator
from sdd_server.core.role_engine import RoleEngine
from sdd_server.plugins.registry import PluginRegistry
from sdd_server.plugins.roles import BUILTIN_ROLES
from sdd_server.utils.logging import get_logger

logger = get_logger(__name__)

# Global registry and engine instances (initialized lazily)
_registry: PluginRegistry | None = None
_engine: RoleEngine | None = None
_generator: RecipeGenerator | None = None


def _get_project_root() -> Path:
    """Get the project root from environment or current directory."""
    return Path(os.getenv("SDD_PROJECT_ROOT", ".")).resolve()


def _get_registry() -> PluginRegistry:
    """Get or create the plugin registry with builtin roles."""
    global _registry
    if _registry is None:
        _registry = PluginRegistry()
        for role_class in BUILTIN_ROLES:
            role = role_class()  # type: ignore[abstract]
            _registry.register(role.metadata.name, role)
        logger.info("Initialized plugin registry", roles=_registry.list_roles())
    return _registry


def _get_engine() -> RoleEngine:
    """Get or create the role engine (context injected per-request via update_context)."""
    global _engine
    registry = _get_registry()
    if _engine is None:
        _engine = RoleEngine(registry)
    return _engine


def _get_generator() -> RecipeGenerator:
    """Get or create the recipe generator."""
    global _generator
    if _generator is None:
        _generator = RecipeGenerator(
            _get_project_root(),
            _get_registry(),
        )
    return _generator


def register_tools(mcp: FastMCP) -> None:
    """Register review tools on the given FastMCP instance."""

    @mcp.tool()
    async def sdd_review_list(
        ctx: Context | None = None,  # type: ignore[type-arg]
    ) -> dict[str, Any]:
        """List all available review roles with their metadata and dependencies.

        Returns:
            roles: List of role metadata (name, description, stage, dependencies, priority)
            count: Number of available roles
        """
        registry = _get_registry()
        roles = []

        for name in registry.list_roles():
            role = registry.get_role(name)
            if role:
                roles.append(
                    {
                        "name": role.metadata.name,
                        "version": role.metadata.version,
                        "description": role.metadata.description,
                        "stage": role.metadata.stage.value
                        if role.metadata.stage is not None
                        else "",
                        "dependencies": role.metadata.dependencies,
                        "priority": role.metadata.priority,
                    }
                )

        # Sort by priority
        roles.sort(key=lambda r: r["priority"])

        return {
            "roles": roles,
            "count": len(roles),
        }

    @mcp.tool()
    async def sdd_review_run(
        roles: list[str] | None = None,
        scope: str = "all",
        target: str | None = None,
        parallel: bool = True,
        ctx: Context | None = None,  # type: ignore[type-arg]
    ) -> dict[str, Any]:
        """Run role-based code reviews.

        Executes the specified roles (or all if not specified) in dependency order.
        Independent roles can run in parallel for faster execution.

        Args:
            roles: Optional list of role names to run. If empty, runs all roles.
            scope: Review scope - "specs", "code", or "all" (default: "all")
            target: Optional feature name to focus review on
            parallel: Whether to run independent roles in parallel (default: true)

        Returns:
            status: "started" or "completed"
            roles_run: List of roles that were executed
            results: Summary of results (if completed)
            summary: Human-readable summary
        """
        registry = _get_registry()
        engine = _get_engine()

        # Inject per-request context (ai_client from lifespan, project_root)
        run_context: dict[str, Any] = {"project_root": str(_get_project_root())}
        if ctx and hasattr(ctx, "request_context") and ctx.request_context:
            ai_client = ctx.request_context.lifespan_context.get("ai_client")
            if ai_client is not None:
                run_context["ai_client"] = ai_client
        engine.update_context(run_context)

        # Determine which roles to run
        if roles:
            # Validate role names
            available = set(registry.list_roles())
            unknown = set(roles) - available
            if unknown:
                return {
                    "status": "error",
                    "error": f"Unknown roles: {', '.join(unknown)}",
                    "available_roles": list(available),
                }
            role_names = roles
        else:
            role_names = registry.list_roles()

        logger.info(
            "Starting review run",
            roles=role_names,
            scope=scope,
            target=target,
            parallel=parallel,
        )

        try:
            # Run the roles
            results = await engine.run_roles(role_names, scope, target, parallel)

            # Build response
            role_results = {}
            for name, result in results.items():
                role_results[name] = {
                    "status": result.status.value,
                    "success": result.success,
                    "issues_count": len(result.issues),
                    "suggestions_count": len(result.suggestions),
                    "duration_seconds": result.duration_seconds,
                }

            return {
                "status": "completed",
                "roles_run": list(results.keys()),
                "results": role_results,
                "summary": engine.get_summary(),
                "engine_status": engine.get_status(),
            }

        except Exception as e:
            logger.error("Review run failed", error=str(e))
            return {
                "status": "error",
                "error": str(e),
                "roles_attempted": role_names,
            }

    @mcp.tool()
    async def sdd_review_status(
        ctx: Context | None = None,  # type: ignore[type-arg]
    ) -> dict[str, Any]:
        """Get the current status of the review engine.

        Returns information about running, completed, and failed roles.

        Returns:
            running: List of currently running role names
            completed: List of completed role names
            failed: List of failed role names
            success_rate: Percentage of successful roles
        """
        engine = _get_engine()
        status = engine.get_status()

        total = status["total_results"]
        success_count = status["success_count"]
        success_rate = (success_count / total * 100) if total > 0 else 0

        return {
            "running": status["running"],
            "completed": status["completed"],
            "failed": status["failed"],
            "total_results": total,
            "success_count": success_count,
            "failure_count": status["failure_count"],
            "success_rate": round(success_rate, 1),
            "dependency_graph": engine.get_dependency_graph(),
        }

    @mcp.tool()
    async def sdd_review_results(
        role: str | None = None,
        ctx: Context | None = None,  # type: ignore[type-arg]
    ) -> dict[str, Any]:
        """Get detailed results from role reviews.

        Args:
            role: Optional role name to get results for. If not specified, returns all results.

        Returns:
            results: Dictionary of role name to detailed results
            summary: Human-readable summary
        """
        engine = _get_engine()
        all_results = engine.results

        if role:
            if role not in all_results:
                available = list(all_results.keys())
                return {
                    "error": f"No results for role '{role}'",
                    "available_roles": available,
                }
            results = {role: all_results[role]}
        else:
            results = all_results

        # Build detailed response
        detailed_results = {}
        for name, result in results.items():
            detailed_results[name] = {
                "status": result.status.value,
                "success": result.success,
                "output": result.output,
                "issues": result.issues,
                "suggestions": result.suggestions,
                "started_at": result.started_at.isoformat() if result.started_at else None,
                "completed_at": result.completed_at.isoformat() if result.completed_at else None,
                "duration_seconds": result.duration_seconds,
            }

        return {
            "results": detailed_results,
            "summary": engine.get_summary(),
            "count": len(detailed_results),
        }

    @mcp.tool()
    async def sdd_review_reset(
        ctx: Context | None = None,  # type: ignore[type-arg]
    ) -> dict[str, Any]:
        """Reset the review engine state.

        Clears all stored results and resets the engine for a new review run.

        Returns:
            success: True if reset was successful
            message: Confirmation message
        """
        global _engine
        _engine = None

        logger.info("Review engine reset")

        return {
            "success": True,
            "message": "Review engine state has been reset",
        }

    @mcp.tool()
    async def sdd_recipes_generate(
        project_name: str,
        description: str = "",
        overwrite: bool = False,
        ctx: Context | None = None,  # type: ignore[type-arg]
    ) -> dict[str, Any]:
        """Generate Goose YAML recipes for all roles.

        Creates recipe files in specs/recipes/ for each role, using the
        role plugin templates with project context.

        Args:
            project_name: Name of the project (baked into recipes)
            description: Project description
            overwrite: Whether to overwrite existing recipes (default: false)

        Returns:
            generated: List of generated recipe paths
            count: Number of recipes generated
            validation: Validation results for each recipe
        """
        generator = _get_generator()

        try:
            paths = generator.generate_all_recipes(
                {
                    "project_name": project_name,
                    "description": description or f"Project: {project_name}",
                },
                overwrite=overwrite,
            )

            # Validate all generated recipes
            validation = generator.validate_all_recipes()

            return {
                "generated": [str(p.relative_to(_get_project_root())) for p in paths],
                "count": len(paths),
                "validation": validation,
            }

        except Exception as e:
            logger.error("Recipe generation failed", error=str(e))
            return {
                "error": str(e),
                "generated": [],
                "count": 0,
            }

    @mcp.tool()
    async def sdd_recipe_render(
        role: str,
        project_name: str,
        description: str = "",
        ctx: Context | None = None,  # type: ignore[type-arg]
    ) -> dict[str, Any]:
        """Render a single role recipe template without writing to disk.

        Args:
            role: Role name to render recipe for
            project_name: Project name for template context
            description: Project description

        Returns:
            content: Rendered YAML content
            role: Role name
            valid: Whether the YAML is valid
        """
        generator = _get_generator()

        try:
            content = generator.render_recipe(
                role,
                {
                    "project_name": project_name,
                    "description": description or f"Project: {project_name}",
                },
            )

            return {
                "role": role,
                "content": content,
                "valid": True,
            }

        except Exception as e:
            return {
                "role": role,
                "error": str(e),
                "valid": False,
            }
