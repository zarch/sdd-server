"""Unit tests for MetadataManager."""

from datetime import UTC, datetime
from pathlib import Path

from sdd_server.core.metadata import MetadataManager
from sdd_server.models.state import BypassRecord, FeatureState, ProjectState, WorkflowState


def test_load_missing_returns_empty(metadata_manager: MetadataManager) -> None:
    state = metadata_manager.load()
    assert isinstance(state, ProjectState)
    assert state.features == {}


def test_save_and_load_roundtrip(metadata_manager: MetadataManager, tmp_project: Path) -> None:
    (tmp_project / "specs").mkdir(exist_ok=True)
    state = ProjectState()
    state.set_feature("f1", FeatureState(feature_id="f1", state=WorkflowState.READY))
    metadata_manager.save(state)

    loaded = metadata_manager.load()
    assert "f1" in loaded.features
    assert loaded.features["f1"].state == WorkflowState.READY


def test_set_feature_state(metadata_manager: MetadataManager, tmp_project: Path) -> None:
    (tmp_project / "specs").mkdir(exist_ok=True)
    fs = FeatureState(feature_id="my-feature", state=WorkflowState.IMPLEMENTING)
    metadata_manager.set_feature_state("my-feature", fs)

    loaded = metadata_manager.load()
    assert loaded.features["my-feature"].state == WorkflowState.IMPLEMENTING


def test_append_bypass(metadata_manager: MetadataManager, tmp_project: Path) -> None:
    (tmp_project / "specs").mkdir(exist_ok=True)
    record = BypassRecord(
        timestamp=datetime.now(UTC),
        actor="alice",
        reason="urgent hotfix",
        action="commit",
    )
    metadata_manager.append_bypass(record)
    loaded = metadata_manager.load()
    assert len(loaded.bypasses) == 1
    assert loaded.bypasses[0].actor == "alice"
