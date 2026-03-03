"""Spec path helpers."""

from __future__ import annotations

from pathlib import Path


class SpecsPaths:
    """Centralizes all path calculations for the specs directory layout."""

    def __init__(self, project_root: Path, specs_dir: str = "specs") -> None:
        self.project_root = project_root.resolve()
        self._specs_dir_name = specs_dir

    @property
    def specs_dir(self) -> Path:
        return self.project_root / self._specs_dir_name

    @property
    def prd_path(self) -> Path:
        return self.specs_dir / "prd.md"

    @property
    def arch_path(self) -> Path:
        return self.specs_dir / "arch.md"

    @property
    def tasks_path(self) -> Path:
        return self.specs_dir / "tasks.md"

    @property
    def metadata_path(self) -> Path:
        return self.specs_dir / ".metadata.json"

    @property
    def context_hints_path(self) -> Path:
        return self.specs_dir / ".context-hints"

    @property
    def recipes_dir(self) -> Path:
        return self.specs_dir / "recipes"

    def feature_dir(self, name: str) -> Path:
        return self.specs_dir / name

    def feature_prd(self, name: str) -> Path:
        return self.feature_dir(name) / "prd.md"

    def feature_arch(self, name: str) -> Path:
        return self.feature_dir(name) / "arch.md"

    def feature_tasks(self, name: str) -> Path:
        return self.feature_dir(name) / "tasks.md"

    def feature_context_hints(self, name: str) -> Path:
        return self.feature_dir(name) / ".context-hints"

    def recipe_path(self, role: str) -> Path:
        """Return the path for a Goose YAML recipe file (recipes/<role>.yaml)."""
        return self.recipes_dir / f"{role}.yaml"

    def root_spec_path(self, spec_type) -> Path:
        """Return the path for a root spec file by type."""
        from sdd_server.models.spec import SpecType

        spec_map = {
            SpecType.PRD: self.prd_path,
            SpecType.ARCH: self.arch_path,
            SpecType.TASKS: self.tasks_path,
            SpecType.CONTEXT_HINTS: self.context_hints_path,
        }
        return spec_map[spec_type]

    def feature_spec_path(self, feature: str, spec_type) -> Path:
        """Return the path for a feature spec file by type."""
        from sdd_server.models.spec import SpecType

        spec_map = {
            SpecType.PRD: self.feature_prd(feature),
            SpecType.ARCH: self.feature_arch(feature),
            SpecType.TASKS: self.feature_tasks(feature),
            SpecType.CONTEXT_HINTS: self.feature_context_hints(feature),
        }
        return spec_map[spec_type]
