"""Recipe manager — renders and writes Goose YAML recipes from Jinja2 templates.

Goose recipes are the primary format; Markdown context-hints serve as the
fallback for other AI clients.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import yaml
from jinja2 import Environment, PackageLoader

from sdd_server.infrastructure.filesystem import FileSystemClient
from sdd_server.utils.paths import SpecsPaths

ROLES: tuple[str, ...] = (
    "architect",
    "ui-designer",
    "interface-designer",
    "security-analyst",
    "edge-case-analyst",
    "senior-developer",
)

# Human-readable metadata for each role — used in spec templates
ROLE_META: tuple[dict[str, str], ...] = (
    {
        "name": "architect",
        "title": "Architect",
        "recipe": "recipes/architect.yaml",
        "purpose": "System structure, tech stack, data flow",
    },
    {
        "name": "ui-designer",
        "title": "UI/UX Designer",
        "recipe": "recipes/ui-designer.yaml",
        "purpose": "CLI commands, config, env vars, error messages",
    },
    {
        "name": "interface-designer",
        "title": "Interface Designer",
        "recipe": "recipes/interface-designer.yaml",
        "purpose": "APIs, file formats, integration contracts",
    },
    {
        "name": "security-analyst",
        "title": "Security Analyst",
        "recipe": "recipes/security-analyst.yaml",
        "purpose": "Threat model, input validation, access controls",
    },
    {
        "name": "edge-case-analyst",
        "title": "Edge Case Analyst",
        "recipe": "recipes/edge-case-analyst.yaml",
        "purpose": "Boundary conditions, failure modes, test scenarios",
    },
    {
        "name": "senior-developer",
        "title": "Senior Developer",
        "recipe": "recipes/senior-developer.yaml",
        "purpose": "KISS review, task breakdown, testing strategy",
    },
)


class RecipeManager:
    """Renders Goose YAML recipes from templates and writes them to recipes/."""

    def __init__(self, project_root: Path, specs_dir: str = "specs") -> None:
        self.project_root = project_root.resolve()
        self._paths = SpecsPaths(self.project_root, specs_dir)
        self._fs = FileSystemClient(self.project_root)
        self._jinja = Environment(
            loader=PackageLoader("sdd_server", "templates/recipes"),
            autoescape=False,
            keep_trailing_newline=True,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def render_recipe(self, role: str, context: dict[str, object]) -> str:
        """Render a single role recipe template to a YAML string.

        Args:
            role: Role name (must be one of ROLES).
            context: Jinja2 template context variables.

        Returns:
            Rendered YAML content as a string.

        Raises:
            ValueError: If the role name is unknown.
        """
        if role not in ROLES:
            raise ValueError(f"Unknown role '{role}'. Valid roles: {', '.join(ROLES)}")
        template = self._jinja.get_template(f"{role}.yaml.j2")
        result: str = template.render(**context)
        return result

    def write_recipe(self, role: str, context: dict[str, object], overwrite: bool = False) -> Path:
        """Render and write a recipe file to recipes/<role>.yaml.

        Args:
            role: Role name.
            context: Jinja2 template context variables.
            overwrite: If False (default) skip roles whose recipe already exists.

        Returns:
            Path to the written recipe file.
        """
        dest: Path = self._paths.recipe_path(role)
        if not overwrite and self._fs.file_exists(dest):
            return dest
        content = self.render_recipe(role, context)
        # Validate the rendered YAML is parseable before writing
        yaml.safe_load(content)
        self._fs.write_file(dest, content)
        return dest

    def init_recipes(
        self,
        project_name: str,
        description: str = "",
        overwrite: bool = False,
    ) -> list[Path]:
        """Render and write all role recipes for a project.

        Args:
            project_name: Project name baked into every recipe.
            description: Project description.
            overwrite: Overwrite existing recipe files.

        Returns:
            List of paths that were written.
        """
        self._fs.ensure_directory(self._paths.recipes_dir)
        ctx: dict[str, object] = {
            "project_name": project_name,
            "description": description or f"Project: {project_name}",
            "date": datetime.now(UTC).strftime("%Y-%m-%d"),
        }
        written: list[Path] = []
        for role in ROLES:
            path = self.write_recipe(role, ctx, overwrite=overwrite)
            written.append(path)
        return written

    def list_recipes(self) -> list[str]:
        """Return the names of recipe files present in recipes/."""
        recipes_dir = self._paths.recipes_dir
        if not self._fs.directory_exists(recipes_dir):
            return []
        return [p.stem for p in self._fs.list_directory(recipes_dir) if p.suffix == ".yaml"]

    def validate_recipe(self, role: str) -> list[str]:
        """Parse an existing recipe file and check required fields.

        Returns a list of issue strings (empty = valid).
        """
        dest = self._paths.recipe_path(role)
        issues: list[str] = []
        if not self._fs.file_exists(dest):
            return [f"Recipe file missing: '{dest.relative_to(self.project_root)}'"]
        try:
            data = yaml.safe_load(self._fs.read_file(dest))
        except yaml.YAMLError as exc:
            return [f"YAML parse error in '{dest.name}': {exc}"]
        for field in ("version", "title", "description", "instructions"):
            if not data.get(field):
                issues.append(f"Missing required field '{field}' in {dest.name}")
        return issues
