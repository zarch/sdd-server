"""Spec file manager — reads, writes, and creates feature specs."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from pathlib import Path

from jinja2 import Environment, PackageLoader

from sdd_server.core.recipe_manager import ROLE_META
from sdd_server.infrastructure.exceptions import SpecNotFoundError, ValidationError
from sdd_server.infrastructure.filesystem import FileSystemClient
from sdd_server.infrastructure.security.input_validation import (
    validate_feature_name,
    validate_spec_content,
)
from sdd_server.models.spec import SpecType
from sdd_server.utils.paths import SpecsPaths

# Directories inside specs/ that are not features
_NON_FEATURE_DIRS = frozenset({"recipes"})

_SPEC_FILE_MAP: dict[SpecType, str] = {
    SpecType.PRD: "prd.md",
    SpecType.ARCH: "arch.md",
    SpecType.TASKS: "tasks.md",
    SpecType.CONTEXT_HINTS: ".context-hints",
}

_TEMPLATE_MAP: dict[SpecType, str] = {
    SpecType.PRD: "prd.md.j2",
    SpecType.ARCH: "arch.md.j2",
    SpecType.TASKS: "tasks.md.j2",
    SpecType.CONTEXT_HINTS: "context-hints.j2",
}


@dataclasses.dataclass
class SpecTemplateContext:
    """Typed context passed to Jinja2 spec templates."""

    project_name: str
    description: str
    date: str
    feature: str
    workflow_state: str
    pending_actions: list[str]
    roles: tuple[dict[str, str], ...]


class SpecManager:
    """Manages spec files under the project's specs directory."""

    def __init__(self, project_root: Path, specs_dir: str = "specs") -> None:
        self.project_root = project_root.resolve()
        self.paths = SpecsPaths(self.project_root, specs_dir)
        self._fs = FileSystemClient(self.project_root)
        self._jinja = Environment(
            loader=PackageLoader("sdd_server", "templates/specs"),
            autoescape=False,
            keep_trailing_newline=True,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _spec_path(self, spec_type: SpecType, feature: str | None) -> Path:
        filename = _SPEC_FILE_MAP[spec_type]
        if feature:
            return self.paths.feature_dir(feature) / filename
        return self.paths.specs_dir / filename

    def _render_template(self, spec_type: SpecType, context: SpecTemplateContext) -> str:
        template_name = _TEMPLATE_MAP[spec_type]
        tmpl = self._jinja.get_template(template_name)
        return tmpl.render(**dataclasses.asdict(context))

    def _register_feature(self, name: str) -> None:
        """Add feature entry to the root tasks.md (no-op if already listed)."""
        # Simple approach: append a note to tasks.md
        # The full metadata registry is handled by MetadataManager.
        pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def read_spec(self, spec_type: SpecType, feature: str | None = None) -> str:
        """Return the content of a spec file, raising SpecNotFoundError if absent."""
        path = self._spec_path(spec_type, feature)
        if not self._fs.file_exists(path):
            label = f"'{spec_type}'" + (f" (feature={feature})" if feature else "")
            raise SpecNotFoundError(f"Spec {label} not found at '{path}'")
        return self._fs.read_file(path)

    def write_spec(
        self,
        spec_type: SpecType,
        content: str,
        feature: str | None = None,
        mode: str = "overwrite",
    ) -> None:
        """Write content to a spec file.

        Args:
            spec_type: Which spec file to write.
            content: New content to write.
            feature: Feature subdirectory (None for root specs).
            mode: 'overwrite' | 'append' | 'prepend'
        """
        validate_spec_content(content)
        path = self._spec_path(spec_type, feature)
        if mode == "overwrite":
            self._fs.write_file(path, content)
        elif mode == "append":
            existing = self._fs.read_file(path) if self._fs.file_exists(path) else ""
            self._fs.write_file(path, existing + content)
        elif mode == "prepend":
            existing = self._fs.read_file(path) if self._fs.file_exists(path) else ""
            self._fs.write_file(path, content + existing)
        else:
            raise ValidationError(
                f"Invalid write mode: '{mode}'. Use overwrite, append, or prepend."
            )

    def create_feature(self, name: str, description: str = "") -> Path:
        """Create a new feature directory with all spec templates rendered.

        Returns the path to the feature directory.
        """
        from sdd_server.infrastructure.exceptions import InputValidationError as _IVE

        try:
            validate_feature_name(name)
        except _IVE as exc:
            raise ValidationError(str(exc)) from exc

        feature_dir = self.paths.feature_dir(name)
        if self._fs.directory_exists(feature_dir):
            raise ValidationError(f"Feature '{name}' already exists at '{feature_dir}'")

        self._fs.ensure_directory(feature_dir)

        ctx = SpecTemplateContext(
            project_name=self.project_root.name,
            description=description or f"Feature: {name}",
            date=datetime.now(UTC).strftime("%Y-%m-%d"),
            feature=name,
            workflow_state="uninitialized",
            pending_actions=["Complete PRD for this feature", "Create architecture spec"],
            roles=ROLE_META,
        )

        for spec_type in (SpecType.PRD, SpecType.ARCH, SpecType.TASKS, SpecType.CONTEXT_HINTS):
            rendered = self._render_template(spec_type, ctx)
            self._fs.write_file(self._spec_path(spec_type, name), rendered)

        self._register_feature(name)
        return feature_dir

    def list_features(self) -> list[str]:
        """Return the names of all feature subdirectories under specs/."""
        if not self._fs.directory_exists(self.paths.specs_dir):
            return []
        items = self._fs.list_directory(self.paths.specs_dir)
        return [
            p.name
            for p in items
            if p.is_dir() and not p.name.startswith(".") and p.name not in _NON_FEATURE_DIRS
        ]

    def validate_structure(self) -> list[str]:
        """Check that all required root spec files exist.

        Returns a list of issue strings (empty list means valid).
        """
        issues: list[str] = []
        required = [SpecType.PRD, SpecType.ARCH, SpecType.TASKS]
        for spec_type in required:
            path = self._spec_path(spec_type, None)
            if not self._fs.file_exists(path):
                issues.append(f"Missing root spec: '{path.relative_to(self.project_root)}'")
        return issues
