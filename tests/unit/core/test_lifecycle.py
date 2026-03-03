"""Tests for FeatureLifecycleManager."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest

from sdd_server.core.lifecycle import LIFECYCLE_FILE, FeatureLifecycleManager
from sdd_server.models.lifecycle import (
    LifecycleState,
)


class TestFeatureLifecycleManager:
    """Tests for FeatureLifecycleManager class."""

    @pytest.fixture
    def temp_project_root(self, tmp_path: Path) -> Path:
        """Create a temporary project root directory."""
        return tmp_path / "project"

    @pytest.fixture
    def manager(self, temp_project_root: Path) -> Generator[FeatureLifecycleManager]:
        """Create a lifecycle manager with temp directory."""
        temp_project_root.mkdir(parents=True, exist_ok=True)
        yield FeatureLifecycleManager(temp_project_root)

    def test_init(self, temp_project_root: Path) -> None:
        """Test manager initialization."""
        manager = FeatureLifecycleManager(temp_project_root)
        assert manager.project_root == temp_project_root.resolve()
        assert manager._lifecycle_path == temp_project_root / LIFECYCLE_FILE

    def test_create_feature(self, manager: FeatureLifecycleManager) -> None:
        """Test creating a feature lifecycle."""
        lifecycle = manager.create_feature("test-feature")
        assert lifecycle.feature_id == "test-feature"
        assert lifecycle.state == LifecycleState.PLANNED
        assert lifecycle.created_at is not None

    def test_create_feature_with_initial_state(self, manager: FeatureLifecycleManager) -> None:
        """Test creating a feature with a specific initial state."""
        lifecycle = manager.create_feature("test-feature", initial_state=LifecycleState.IN_PROGRESS)
        assert lifecycle.state == LifecycleState.IN_PROGRESS

    def test_create_duplicate_feature(self, manager: FeatureLifecycleManager) -> None:
        """Test creating a duplicate feature raises error."""
        manager.create_feature("test-feature")
        with pytest.raises(ValueError, match="already exists"):
            manager.create_feature("test-feature")

    def test_get_feature(self, manager: FeatureLifecycleManager) -> None:
        """Test getting a feature."""
        manager.create_feature("test-feature")
        lifecycle = manager.get_feature("test-feature")
        assert lifecycle is not None
        assert lifecycle.feature_id == "test-feature"
        assert manager.get_feature("nonexistent") is None

    def test_transition_feature(self, manager: FeatureLifecycleManager) -> None:
        """Test transitioning a feature."""
        manager.create_feature("test-feature")
        transition = manager.transition_feature(
            "test-feature",
            LifecycleState.IN_PROGRESS,
            reason="Starting work",
            actor="developer",
        )
        assert transition.from_state == LifecycleState.PLANNED
        assert transition.to_state == LifecycleState.IN_PROGRESS
        assert transition.reason == "Starting work"
        assert transition.actor == "developer"

        lifecycle = manager.get_feature("test-feature")
        assert lifecycle is not None
        assert lifecycle.state == LifecycleState.IN_PROGRESS

    def test_transition_invalid(self, manager: FeatureLifecycleManager) -> None:
        """Test invalid transition raises error."""
        manager.create_feature("test-feature")
        with pytest.raises(ValueError, match="Invalid lifecycle transition"):
            manager.transition_feature("test-feature", LifecycleState.COMPLETE)

    def test_transition_nonexistent(self, manager: FeatureLifecycleManager) -> None:
        """Test transitioning nonexistent feature raises error."""
        with pytest.raises(ValueError, match="not found"):
            manager.transition_feature("nonexistent", LifecycleState.IN_PROGRESS)

    def test_can_transition(self, manager: FeatureLifecycleManager) -> None:
        """Test checking if transition is valid."""
        manager.create_feature("test-feature")
        assert manager.can_transition("test-feature", LifecycleState.IN_PROGRESS) is True
        assert manager.can_transition("test-feature", LifecycleState.COMPLETE) is False
        assert manager.can_transition("nonexistent", LifecycleState.PLANNED) is False

    def test_get_allowed_transitions(self, manager: FeatureLifecycleManager) -> None:
        """Test getting allowed transitions."""
        manager.create_feature("test-feature")
        allowed = manager.get_allowed_transitions("test-feature")
        assert LifecycleState.IN_PROGRESS in allowed
        assert LifecycleState.ARCHIVED in allowed

    def test_get_allowed_transitions_nonexistent(self, manager: FeatureLifecycleManager) -> None:
        """Test getting allowed transitions for nonexistent feature."""
        with pytest.raises(ValueError, match="not found"):
            manager.get_allowed_transitions("nonexistent")

    def test_list_features(self, manager: FeatureLifecycleManager) -> None:
        """Test listing all features."""
        manager.create_feature("feature-1")
        manager.create_feature("feature-2")
        manager.create_feature("feature-3")

        features = manager.list_features()
        assert set(features) == {"feature-1", "feature-2", "feature-3"}

    def test_list_features_by_state(self, manager: FeatureLifecycleManager) -> None:
        """Test listing features filtered by state."""
        manager.create_feature("planned-1")
        manager.create_feature("planned-2")
        manager.create_feature("progress-1")
        manager.transition_feature("progress-1", LifecycleState.IN_PROGRESS)

        planned = manager.list_features(state=LifecycleState.PLANNED)
        assert set(planned) == {"planned-1", "planned-2"}

        in_progress = manager.list_features(state=LifecycleState.IN_PROGRESS)
        assert in_progress == ["progress-1"]

    def test_get_summary(self, manager: FeatureLifecycleManager) -> None:
        """Test getting state summary."""
        manager.create_feature("f1")
        manager.create_feature("f2")
        manager.create_feature("f3")
        manager.transition_feature("f1", LifecycleState.IN_PROGRESS)

        summary = manager.get_summary()
        assert summary["planned"] == 2
        assert summary["in_progress"] == 1
        assert summary["complete"] == 0

    def test_remove_feature(self, manager: FeatureLifecycleManager) -> None:
        """Test removing a feature."""
        manager.create_feature("test-feature")
        assert manager.remove_feature("test-feature") is True
        assert manager.get_feature("test-feature") is None
        assert manager.remove_feature("nonexistent") is False

    def test_archive_feature_complete(self, manager: FeatureLifecycleManager) -> None:
        """Test archiving a completed feature."""
        manager.create_feature("test-feature")
        manager.transition_feature("test-feature", LifecycleState.IN_PROGRESS)
        manager.transition_feature("test-feature", LifecycleState.REVIEW)
        manager.transition_feature("test-feature", LifecycleState.COMPLETE)

        result = manager.archive_feature("test-feature", reason="Done")
        assert result is True
        lifecycle = manager.get_feature("test-feature")
        assert lifecycle is not None
        assert lifecycle.state == LifecycleState.ARCHIVED

    def test_archive_feature_planned(self, manager: FeatureLifecycleManager) -> None:
        """Test archiving from planned state."""
        manager.create_feature("test-feature")
        result = manager.archive_feature("test-feature", reason="Cancelled")
        assert result is True
        lifecycle = manager.get_feature("test-feature")
        assert lifecycle is not None
        assert lifecycle.state == LifecycleState.ARCHIVED

    def test_archive_feature_nonexistent(self, manager: FeatureLifecycleManager) -> None:
        """Test archiving nonexistent feature."""
        assert manager.archive_feature("nonexistent") is False

    def test_get_feature_history(self, manager: FeatureLifecycleManager) -> None:
        """Test getting feature history."""
        manager.create_feature("test-feature")
        manager.transition_feature("test-feature", LifecycleState.IN_PROGRESS)
        manager.transition_feature("test-feature", LifecycleState.REVIEW)

        history = manager.get_feature_history("test-feature")
        assert len(history) == 2
        assert history[0].from_state == LifecycleState.PLANNED
        assert history[0].to_state == LifecycleState.IN_PROGRESS
        assert history[1].from_state == LifecycleState.IN_PROGRESS
        assert history[1].to_state == LifecycleState.REVIEW

    def test_get_feature_history_nonexistent(self, manager: FeatureLifecycleManager) -> None:
        """Test getting history for nonexistent feature."""
        with pytest.raises(ValueError, match="not found"):
            manager.get_feature_history("nonexistent")

    def test_get_feature_metrics(self, manager: FeatureLifecycleManager) -> None:
        """Test getting feature metrics."""
        manager.create_feature("test-feature")
        manager.transition_feature("test-feature", LifecycleState.IN_PROGRESS)
        manager.transition_feature("test-feature", LifecycleState.REVIEW)
        manager.transition_feature("test-feature", LifecycleState.IN_PROGRESS)  # Rework

        metrics = manager.get_feature_metrics("test-feature")
        assert metrics["feature_id"] == "test-feature"
        assert metrics["current_state"] == "in_progress"
        assert metrics["transition_count"] == 3
        assert metrics["rework_count"] == 1
        assert "time_in_current_state_seconds" in metrics
        assert "created_at" in metrics
        assert "updated_at" in metrics
        assert len(metrics["allowed_transitions"]) > 0

    def test_get_feature_metrics_nonexistent(self, manager: FeatureLifecycleManager) -> None:
        """Test getting metrics for nonexistent feature."""
        with pytest.raises(ValueError, match="not found"):
            manager.get_feature_metrics("nonexistent")

    def test_get_project_state(self, manager: FeatureLifecycleManager) -> None:
        """Test getting overall project state."""
        assert manager.get_project_state() is None

        manager.create_feature("f1")
        manager.create_feature("f2")
        manager.transition_feature("f1", LifecycleState.IN_PROGRESS)

        assert manager.get_project_state() == LifecycleState.IN_PROGRESS

    def test_persistence(self, manager: FeatureLifecycleManager) -> None:
        """Test that lifecycle state is persisted."""
        manager.create_feature("test-feature")
        manager.transition_feature("test-feature", LifecycleState.IN_PROGRESS)

        # Create a new manager to load from disk
        new_manager = FeatureLifecycleManager(manager.project_root)
        lifecycle = new_manager.get_feature("test-feature")
        assert lifecycle is not None
        assert lifecycle.state == LifecycleState.IN_PROGRESS
        assert len(lifecycle.history) == 1

    def test_sync_with_spec_manager(self, manager: FeatureLifecycleManager) -> None:
        """Test syncing with spec manager features."""
        spec_features = ["feature-1", "feature-2", "feature-3"]

        added = manager.sync_with_spec_manager(spec_features)
        assert added == 3

        # Sync again - should add nothing
        added = manager.sync_with_spec_manager(spec_features)
        assert added == 0

        # All features should exist
        for feature_id in spec_features:
            lifecycle = manager.get_feature(feature_id)
            assert lifecycle is not None
            assert lifecycle.state == LifecycleState.PLANNED

    def test_sync_preserves_existing(self, manager: FeatureLifecycleManager) -> None:
        """Test that sync preserves existing feature state."""
        manager.create_feature("existing-feature")
        manager.transition_feature("existing-feature", LifecycleState.IN_PROGRESS)

        # Sync with list that includes existing feature
        manager.sync_with_spec_manager(["existing-feature", "new-feature"])

        # Existing feature should keep its state
        lifecycle = manager.get_feature("existing-feature")
        assert lifecycle is not None
        assert lifecycle.state == LifecycleState.IN_PROGRESS

        # New feature should be planned
        new_lifecycle = manager.get_feature("new-feature")
        assert new_lifecycle is not None
        assert new_lifecycle.state == LifecycleState.PLANNED

    def test_corrupted_file_recovery(self, temp_project_root: Path) -> None:
        """Test recovery from corrupted lifecycle file."""
        # Create a corrupted file
        lifecycle_path = temp_project_root / LIFECYCLE_FILE
        lifecycle_path.parent.mkdir(parents=True, exist_ok=True)
        lifecycle_path.write_text("not valid json")

        # Should recover gracefully
        manager = FeatureLifecycleManager(temp_project_root)
        assert manager.list_features() == []

        # Should be able to create features
        manager.create_feature("test-feature")
        assert manager.get_feature("test-feature") is not None


class TestFeatureLifecycleManagerIntegration:
    """Integration tests for FeatureLifecycleManager."""

    @pytest.fixture
    def temp_project_root(self, tmp_path: Path) -> Path:
        """Create a temporary project root directory."""
        return tmp_path / "project"

    @pytest.fixture
    def manager(self, temp_project_root: Path) -> Generator[FeatureLifecycleManager]:
        """Create a lifecycle manager with temp directory."""
        temp_project_root.mkdir(parents=True, exist_ok=True)
        yield FeatureLifecycleManager(temp_project_root)

    def test_full_workflow(self, manager: FeatureLifecycleManager) -> None:
        """Test a complete feature lifecycle workflow."""
        # Create feature
        lifecycle = manager.create_feature("auth-feature")
        assert lifecycle.state == LifecycleState.PLANNED

        # Start work
        manager.transition_feature("auth-feature", LifecycleState.IN_PROGRESS)
        assert manager.get_feature("auth-feature").state == LifecycleState.IN_PROGRESS

        # Submit for review
        manager.transition_feature("auth-feature", LifecycleState.REVIEW)
        assert manager.get_feature("auth-feature").state == LifecycleState.REVIEW

        # Rework needed
        manager.transition_feature(
            "auth-feature", LifecycleState.IN_PROGRESS, reason="Security issues found"
        )
        assert manager.get_feature("auth-feature").state == LifecycleState.IN_PROGRESS

        # Resubmit
        manager.transition_feature("auth-feature", LifecycleState.REVIEW)
        assert manager.get_feature("auth-feature").state == LifecycleState.REVIEW

        # Approved
        manager.transition_feature("auth-feature", LifecycleState.COMPLETE)
        assert manager.get_feature("auth-feature").state == LifecycleState.COMPLETE

        # Archive
        manager.archive_feature("auth-feature")
        assert manager.get_feature("auth-feature").state == LifecycleState.ARCHIVED

        # Check metrics
        metrics = manager.get_feature_metrics("auth-feature")
        assert metrics["transition_count"] == 6  # 6 transitions in this flow
        assert metrics["rework_count"] == 1

    def test_multiple_features_with_different_states(
        self, manager: FeatureLifecycleManager
    ) -> None:
        """Test managing multiple features in different states."""
        # Create multiple features
        manager.create_feature("feature-1")
        manager.create_feature("feature-2")
        manager.create_feature("feature-3")
        manager.create_feature("feature-4")

        # Progress to different states
        manager.transition_feature("feature-1", LifecycleState.IN_PROGRESS)
        manager.transition_feature("feature-2", LifecycleState.IN_PROGRESS)
        manager.transition_feature("feature-2", LifecycleState.REVIEW)
        manager.transition_feature("feature-3", LifecycleState.IN_PROGRESS)
        manager.transition_feature("feature-3", LifecycleState.REVIEW)
        manager.transition_feature("feature-3", LifecycleState.COMPLETE)

        # feature-4 stays in PLANNED

        # Check summary
        summary = manager.get_summary()
        assert summary["planned"] == 1  # feature-4
        assert summary["in_progress"] == 1  # feature-1
        assert summary["review"] == 1  # feature-2
        assert summary["complete"] == 1  # feature-3

        # Check overall state - IN_PROGRESS has priority
        assert manager.get_project_state() == LifecycleState.IN_PROGRESS

        # Complete in-progress feature
        manager.transition_feature("feature-1", LifecycleState.REVIEW)
        # Now REVIEW has priority
        assert manager.get_project_state() == LifecycleState.REVIEW
