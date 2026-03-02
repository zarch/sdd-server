"""Recipe generator — dynamically generates recipes from role plugins.

The RecipeGenerator creates Goose YAML recipes by:
1. Getting recipe templates from role plugins
2. Injecting context (project name, dependencies, previous results)
3. Rendering the templates with Jinja2
4. Validating and writing the output

Architecture reference: arch.md Section 5.2
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment

from sdd_server.infrastructure.filesystem import FileSystemClient
from sdd_server.plugins.base import RolePlugin, RoleResult
from sdd_server.plugins.registry import PluginRegistry
from sdd_server.utils.logging import get_logger
from sdd_server.utils.paths import SpecsPaths

logger = get_logger(__name__)


class RecipeGenerationError(Exception):
    """Raised when recipe generation fails."""

    pass


class RecipeGenerator:
    """Generates Goose YAML recipes from role plugins with context injection.

    The RecipeGenerator creates dynamic recipes by combining role plugin
    templates with project context. It supports:
    - Template inheritance and customization
    - Context injection from previous role results
    - Dependency-aware template variables
    - Validation of generated recipes

    Usage:
        registry = PluginRegistry()
        # ... register plugins ...

        generator = RecipeGenerator(
            project_root=Path("/project"),
            registry=registry,
        )

        # Generate a single recipe
        recipe = generator.generate_recipe("architect", context={"project_name": "MyApp"})

        # Generate all recipes
        paths = generator.generate_all_recipes(context={"project_name": "MyApp"})

        # Generate with previous results for context injection
        results = await engine.run_all()
        paths = generator.generate_all_recipes(
            context={"project_name": "MyApp"},
            previous_results=results,
        )
    """

    def __init__(
        self,
        project_root: Path,
        registry: PluginRegistry,
        specs_dir: str = "specs",
    ) -> None:
        """Initialize the recipe generator.

        Args:
            project_root: Project root directory
            registry: Plugin registry with registered roles
            specs_dir: Name of the specs directory
        """
        self.project_root = project_root.resolve()
        self._registry = registry
        self._paths: SpecsPaths = SpecsPaths(self.project_root, specs_dir)
        self._fs: FileSystemClient = FileSystemClient(self.project_root)
        self._jinja: Environment = Environment(
            autoescape=False,
            keep_trailing_newline=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def generate_recipe(
        self,
        role_name: str,
        context: dict[str, Any],
        previous_results: dict[str, RoleResult] | None = None,
        overwrite: bool = False,
    ) -> Path:
        """Generate and write a recipe for a specific role.

        Args:
            role_name: Name of the role to generate recipe for
            context: Base context variables (project_name, description, etc.)
            previous_results: Optional results from previous role executions
            overwrite: Whether to overwrite existing recipe file

        Returns:
            Path to the generated recipe file

        Raises:
            RecipeGenerationError: If generation fails
        """
        role = self._registry.get_role(role_name)
        if role is None:
            raise RecipeGenerationError(f"Role not found: {role_name}")

        dest: Path = self._paths.recipe_path(role_name)

        # Check if file exists and overwrite is False
        if not overwrite and self._fs.file_exists(dest):
            logger.debug("Recipe exists, skipping", role=role_name, path=str(dest))
            return dest

        # Build the full context
        full_context = self._build_context(role, context, previous_results)

        # Get and render the template
        try:
            template_content = role.get_recipe_template()
            template = self._jinja.from_string(template_content)
            rendered = str(template.render(**full_context))
        except Exception as e:
            raise RecipeGenerationError(
                f"Failed to render template for role '{role_name}': {e}"
            ) from e

        # Validate the rendered YAML
        try:
            yaml.safe_load(rendered)
        except yaml.YAMLError as e:
            raise RecipeGenerationError(
                f"Generated invalid YAML for role '{role_name}': {e}"
            ) from e

        # Write the recipe file
        self._fs.ensure_directory(self._paths.recipes_dir)
        self._fs.write_file(dest, rendered)

        logger.info("Generated recipe", role=role_name, path=str(dest))
        return dest

    def generate_all_recipes(
        self,
        context: dict[str, Any],
        previous_results: dict[str, RoleResult] | None = None,
        overwrite: bool = False,
    ) -> list[Path]:
        """Generate recipes for all registered roles in dependency order.

        Args:
            context: Base context variables
            previous_results: Optional results from previous role executions
            overwrite: Whether to overwrite existing recipe files

        Returns:
            List of paths to generated recipe files
        """
        # Get roles in execution order
        order = self._registry.get_execution_order()
        logger.info("Generating recipes", roles=order, count=len(order))

        self._fs.ensure_directory(self._paths.recipes_dir)

        written: list[Path] = []
        for role_name in order:
            try:
                path = self.generate_recipe(
                    role_name,
                    context,
                    previous_results,
                    overwrite,
                )
                written.append(path)
            except RecipeGenerationError as e:
                logger.error("Failed to generate recipe", role=role_name, error=str(e))
                raise

        return written

    def render_recipe(
        self,
        role_name: str,
        context: dict[str, Any],
        previous_results: dict[str, RoleResult] | None = None,
    ) -> str:
        """Render a recipe template without writing to disk.

        Args:
            role_name: Name of the role
            context: Base context variables
            previous_results: Optional results from previous role executions

        Returns:
            Rendered YAML content as string

        Raises:
            RecipeGenerationError: If rendering fails
        """
        role = self._registry.get_role(role_name)
        if role is None:
            raise RecipeGenerationError(f"Role not found: {role_name}")

        # Build the full context
        full_context = self._build_context(role, context, previous_results)

        # Get and render the template
        try:
            template_content = role.get_recipe_template()
            template = self._jinja.from_string(template_content)
            return str(template.render(**full_context))
        except Exception as e:
            raise RecipeGenerationError(
                f"Failed to render template for role '{role_name}': {e}"
            ) from e

    def get_recipe_context(
        self,
        role_name: str,
        base_context: dict[str, Any],
        previous_results: dict[str, RoleResult] | None = None,
    ) -> dict[str, Any]:
        """Get the full context that would be used for recipe generation.

        This is useful for debugging or inspecting what variables are
        available to the template.

        Args:
            role_name: Name of the role
            base_context: Base context variables
            previous_results: Optional results from previous role executions

        Returns:
            Full context dictionary
        """
        role = self._registry.get_role(role_name)
        if role is None:
            raise RecipeGenerationError(f"Role not found: {role_name}")

        return self._build_context(role, base_context, previous_results)

    # -------------------------------------------------------------------------
    # Context Building
    # -------------------------------------------------------------------------

    def _build_context(
        self,
        role: RolePlugin,
        base_context: dict[str, Any],
        previous_results: dict[str, RoleResult] | None = None,
    ) -> dict[str, Any]:
        """Build the full template context for a role.

        The context includes:
        - Base context (project_name, description, etc.)
        - Role metadata (name, version, dependencies)
        - Previous results from dependency roles
        - Date and time

        Args:
            role: Role plugin instance
            base_context: Base context variables
            previous_results: Results from previous role executions

        Returns:
            Complete context dictionary for template rendering
        """
        context = dict(base_context)

        # Add standard context variables
        context.setdefault("date", datetime.now(UTC).strftime("%Y-%m-%d"))
        context.setdefault("timestamp", datetime.now(UTC).isoformat())

        # Add role metadata
        context["role_name"] = role.metadata.name
        context["role_version"] = role.metadata.version
        context["role_description"] = role.metadata.description
        context["role_stage"] = role.metadata.stage.value
        context["role_priority"] = role.metadata.priority
        context["role_dependencies"] = role.metadata.dependencies

        # Add dependency results for context injection
        if previous_results:
            context["dependency_results"] = self._get_dependency_results(role, previous_results)
            context["previous_issues"] = self._aggregate_previous_issues(role, previous_results)
            context["previous_suggestions"] = self._aggregate_previous_suggestions(
                role, previous_results
            )
        else:
            context["dependency_results"] = {}
            context["previous_issues"] = []
            context["previous_suggestions"] = []

        return context

    def _get_dependency_results(
        self,
        role: RolePlugin,
        previous_results: dict[str, RoleResult],
    ) -> dict[str, dict[str, Any]]:
        """Get results from dependency roles as template context.

        Args:
            role: Role plugin instance
            previous_results: All previous results

        Returns:
            Dictionary mapping dependency name to its result summary
        """
        dep_results: dict[str, dict[str, Any]] = {}

        for dep_name in role.metadata.dependencies:
            if dep_name in previous_results:
                result = previous_results[dep_name]
                dep_results[dep_name] = {
                    "success": result.success,
                    "status": result.status.value,
                    "output": result.output,
                    "issues": result.issues,
                    "suggestions": result.suggestions,
                    "duration_seconds": result.duration_seconds,
                }

        return dep_results

    def _aggregate_previous_issues(
        self,
        role: RolePlugin,
        previous_results: dict[str, RoleResult],
    ) -> list[str]:
        """Aggregate issues from dependency roles.

        Args:
            role: Role plugin instance
            previous_results: All previous results

        Returns:
            List of issues from all dependencies
        """
        issues: list[str] = []

        for dep_name in role.metadata.dependencies:
            if dep_name in previous_results:
                issues.extend(previous_results[dep_name].issues)

        return issues

    def _aggregate_previous_suggestions(
        self,
        role: RolePlugin,
        previous_results: dict[str, RoleResult],
    ) -> list[str]:
        """Aggregate suggestions from dependency roles.

        Args:
            role: Role plugin instance
            previous_results: All previous results

        Returns:
            List of suggestions from all dependencies
        """
        suggestions: list[str] = []

        for dep_name in role.metadata.dependencies:
            if dep_name in previous_results:
                suggestions.extend(previous_results[dep_name].suggestions)

        return suggestions

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------

    def validate_recipe(self, role_name: str) -> list[str]:
        """Validate an existing recipe file.

        Args:
            role_name: Name of the role to validate

        Returns:
            List of validation issues (empty = valid)
        """
        dest = self._paths.recipe_path(role_name)
        issues: list[str] = []

        if not self._fs.file_exists(dest):
            return [f"Recipe file missing: '{dest.relative_to(self.project_root)}'"]

        try:
            content = self._fs.read_file(dest)
            data = yaml.safe_load(content)
        except yaml.YAMLError as exc:
            return [f"YAML parse error in '{dest.name}': {exc}"]

        # Check required fields
        for field in ("version", "title", "description", "instructions"):
            if not data.get(field):
                issues.append(f"Missing required field '{field}' in {dest.name}")

        return issues

    def validate_all_recipes(self) -> dict[str, list[str]]:
        """Validate all registered role recipes.

        Returns:
            Dictionary mapping role name to list of issues
        """
        results: dict[str, list[str]] = {}

        for role_name in self._registry.list_roles():
            results[role_name] = self.validate_recipe(role_name)

        return results
