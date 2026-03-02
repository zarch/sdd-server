"""Metadata manager — persists ProjectState to .metadata.json."""

from __future__ import annotations

import json
from pathlib import Path

from sdd_server.infrastructure.exceptions import FileSystemError
from sdd_server.models.state import BypassRecord, FeatureState, ProjectState
from sdd_server.utils.fs import atomic_write
from sdd_server.utils.paths import SpecsPaths


class MetadataManager:
    """Loads and saves ProjectState from/to .metadata.json."""

    def __init__(self, project_root: Path, specs_dir: str = "specs") -> None:
        self.project_root = project_root.resolve()
        self._paths = SpecsPaths(self.project_root, specs_dir)

    @property
    def metadata_path(self) -> Path:
        return self._paths.metadata_path

    def load(self) -> ProjectState:
        """Load ProjectState from disk. Returns empty state if file absent."""
        if not self.metadata_path.exists():
            return ProjectState()
        try:
            raw = self.metadata_path.read_text(encoding="utf-8")
            data = json.loads(raw)
            return ProjectState.model_validate(data)
        except (json.JSONDecodeError, ValueError) as exc:
            raise FileSystemError(f"Cannot parse metadata: {exc}") from exc

    def save(self, state: ProjectState) -> None:
        """Atomically write ProjectState to .metadata.json."""
        content = state.model_dump_json(indent=2)
        atomic_write(self.metadata_path, content)

    def get_feature_state(self, feature_id: str) -> FeatureState | None:
        """Return the FeatureState for the given feature ID, or None."""
        state = self.load()
        return state.get_feature(feature_id)

    def set_feature_state(self, feature_id: str, feature_state: FeatureState) -> None:
        """Persist an updated FeatureState."""
        state = self.load()
        state.set_feature(feature_id, feature_state)
        self.save(state)

    def append_bypass(self, record: BypassRecord) -> None:
        """Append a bypass record to the audit log."""
        state = self.load()
        state.add_bypass(record)
        self.save(state)
