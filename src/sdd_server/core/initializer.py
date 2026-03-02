"""Project initializer — creates or updates a project's spec structure."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sdd_server.core.metadata import MetadataManager
from sdd_server.core.recipe_manager import ROLE_META, RecipeManager
from sdd_server.core.spec_manager import SpecManager
from sdd_server.infrastructure.filesystem import FileSystemClient
from sdd_server.infrastructure.git import GitClient
from sdd_server.models.spec import SpecType
from sdd_server.models.state import FeatureState, ProjectState, WorkflowState
from sdd_server.utils.paths import SpecsPaths


class ProjectInitializer:
    """Initializes or bootstraps a project's SDD spec structure."""

    def __init__(
        self,
        project_root: Path,
        spec_manager: SpecManager,
        git_client: GitClient,
        specs_dir: str = "specs",
    ) -> None:
        self.project_root = project_root.resolve()
        self.spec_manager = spec_manager
        self.git_client = git_client
        self._paths = SpecsPaths(self.project_root, specs_dir)
        self._fs = FileSystemClient(self.project_root)
        self._metadata = MetadataManager(self.project_root, specs_dir)
        self._recipes = RecipeManager(self.project_root, specs_dir)

    def init_new_project(self, name: str, description: str = "") -> None:
        """Create full specs/ structure, render templates, install git hook, write metadata."""
        self._fs.ensure_directory(self._paths.specs_dir)
        self._fs.ensure_directory(self._paths.recipes_dir)

        from jinja2 import Environment, PackageLoader

        jinja = Environment(
            loader=PackageLoader("sdd_server", "templates/specs"),
            autoescape=False,
            keep_trailing_newline=True,
        )

        ctx = {
            "project_name": name,
            "description": description or f"Project: {name}",
            "date": datetime.now(UTC).strftime("%Y-%m-%d"),
            "feature": None,
            "workflow_state": WorkflowState.UNINITIALIZED,
            "roles": ROLE_META,
            "pending_actions": [
                "Complete the PRD (prd.md)",
                "Run role reviews via Goose recipes (see recipes/)",
                "Create initial tasks (tasks.md)",
            ],
        }

        for spec_type in (SpecType.PRD, SpecType.ARCH, SpecType.TASKS, SpecType.CONTEXT_HINTS):
            from sdd_server.core.spec_manager import _SPEC_FILE_MAP, _TEMPLATE_MAP

            template_name = _TEMPLATE_MAP[spec_type]
            filename = _SPEC_FILE_MAP[spec_type]
            tmpl = jinja.get_template(template_name)
            rendered = tmpl.render(**ctx)
            self._fs.write_file(self._paths.specs_dir / filename, rendered)

        # Write initial metadata
        root_feature = FeatureState(feature_id="__root__", state=WorkflowState.UNINITIALIZED)
        state = ProjectState(
            features={"__root__": root_feature},
            metadata={"project_name": name, "description": description},
        )
        self._metadata.save(state)

        # Render Goose YAML recipes (primary format for role invocation)
        self._recipes.init_recipes(name, description)

        # Install git pre-commit hook
        if self.git_client.is_repo() and not self.git_client.is_hook_installed("pre-commit"):
            self.git_client.install_hook("pre-commit")

    def init_existing_project(self) -> None:
        """Create any missing spec files from templates while preserving existing ones."""
        self._fs.ensure_directory(self._paths.specs_dir)

        from jinja2 import Environment, PackageLoader

        from sdd_server.core.spec_manager import _SPEC_FILE_MAP, _TEMPLATE_MAP

        jinja = Environment(
            loader=PackageLoader("sdd_server", "templates/specs"),
            autoescape=False,
            keep_trailing_newline=True,
        )

        ctx = {
            "project_name": self.project_root.name,
            "description": "Existing project — fill in details",
            "date": datetime.now(UTC).strftime("%Y-%m-%d"),
            "feature": None,
            "workflow_state": WorkflowState.UNINITIALIZED,
            "roles": ROLE_META,
            "pending_actions": [
                "Review and update existing specs",
                "Run role reviews via Goose recipes (see recipes/)",
            ],
        }

        for spec_type in (SpecType.PRD, SpecType.ARCH, SpecType.TASKS, SpecType.CONTEXT_HINTS):
            filename = _SPEC_FILE_MAP[spec_type]
            target = self._paths.specs_dir / filename
            if not self._fs.file_exists(target):
                template_name = _TEMPLATE_MAP[spec_type]
                tmpl = jinja.get_template(template_name)
                rendered = tmpl.render(**ctx)
                self._fs.write_file(target, rendered)

        # Render missing Goose recipes (skip existing to preserve customisations)
        self._recipes.init_recipes(self.project_root.name, overwrite=False)

        # Initialize metadata if absent
        if not self._metadata.metadata_path.exists():
            state = ProjectState()
            self._metadata.save(state)
