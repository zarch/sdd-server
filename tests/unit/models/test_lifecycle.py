"""Tests for feature lifecycle models."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from sdd_server.models.lifecycle import (
    FeatureLifecycle,
    LifecycleState,
    LifecycleTransition,
    ProjectLifecycle,
)


class TestLifecycleState:
    """Tests for LifecycleState enum."""

    def test_all_states_exist(self) -> None:
        """Test that all expected states exist."""
        expected = {"planned", "in_progress", "review", "complete", "archived"}
        actual = {s.value for s in LifecycleState}
        assert actual == expected

    def test_state_values_are_strings(self) -> None:
        """Test that all state values are strings."""
        for state in LifecycleState:
            assert isinstance(state.value, str)


class TestLifecycleTransition:
    """Tests for LifecycleTransition model."""

    def test_create_transition(self) -> None:
        """Test creating a transition record."""
        now = datetime.now(UTC)
        transition = LifecycleTransition(
            from_state=LifecycleState.PLANNED,
            to_state=LifecycleState.IN_PROGRESS,
            timestamp=now,
            reason="Starting implementation",
            actor="developer",
        )
        assert transition.from_state == LifecycleState.PLANNED
        assert transition.to_state == LifecycleState.IN_PROGRESS
        assert transition.timestamp == now
        assert transition.reason == "Starting implementation"
        assert transition.actor == "developer"

    def test_transition_defaults(self) -> None:
        """Test transition default values."""
        transition = LifecycleTransition(
            from_state=LifecycleState.PLANNED,
            to_state=LifecycleState.IN_PROGRESS,
            timestamp=datetime.now(UTC),
        )
        assert transition.reason is None
        assert transition.actor is None
        assert transition.metadata == {}


class TestFeatureLifecycle:
    """Tests for FeatureLifecycle model."""

    def test_create_lifecycle(self) -> None:
        """Test creating a feature lifecycle."""
        lifecycle = FeatureLifecycle(feature_id="test-feature")
        assert lifecycle.feature_id == "test-feature"
        assert lifecycle.state == LifecycleState.PLANNED
        assert lifecycle.history == []

    def test_created_at_auto_set(self) -> None:
        """Test that created_at is auto-set."""
        with patch("sdd_server.models.lifecycle.datetime") as mock_dt:
            fixed_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
            mock_dt.now.return_value = fixed_time
            lifecycle = FeatureLifecycle(feature_id="test")
            assert lifecycle.created_at == fixed_time
            assert lifecycle.updated_at == fixed_time

    def test_valid_transition(self) -> None:
        """Test a valid state transition."""
        lifecycle = FeatureLifecycle(feature_id="test")
        transition = lifecycle.transition_to(
            LifecycleState.IN_PROGRESS,
            reason="Starting work",
        )
        assert lifecycle.state == LifecycleState.IN_PROGRESS
        assert len(lifecycle.history) == 1
        assert transition.from_state == LifecycleState.PLANNED
        assert transition.to_state == LifecycleState.IN_PROGRESS
        assert transition.reason == "Starting work"

    def test_invalid_transition(self) -> None:
        """Test that invalid transitions raise ValueError."""
        lifecycle = FeatureLifecycle(feature_id="test")
        # Cannot go from PLANNED to COMPLETE directly
        with pytest.raises(ValueError, match="Invalid lifecycle transition"):
            lifecycle.transition_to(LifecycleState.COMPLETE)

    def test_can_transition_to(self) -> None:
        """Test checking if transition is valid."""
        lifecycle = FeatureLifecycle(feature_id="test")
        assert lifecycle.can_transition_to(LifecycleState.IN_PROGRESS) is True
        assert lifecycle.can_transition_to(LifecycleState.COMPLETE) is False
        assert lifecycle.can_transition_to(LifecycleState.ARCHIVED) is True

    def test_get_allowed_transitions(self) -> None:
        """Test getting allowed transitions."""
        lifecycle = FeatureLifecycle(feature_id="test")
        allowed = lifecycle.get_allowed_transitions()
        assert LifecycleState.IN_PROGRESS in allowed
        assert LifecycleState.ARCHIVED in allowed
        assert LifecycleState.COMPLETE not in allowed

    def test_time_in_current_state_no_history(self) -> None:
        """Test time in state with no history."""
        lifecycle = FeatureLifecycle(feature_id="test")
        # Just verify the method returns a non-negative value
        time_spent = lifecycle.time_in_current_state()
        assert time_spent is not None
        assert time_spent >= 0

    def test_get_transition_count(self) -> None:
        """Test counting transitions."""
        lifecycle = FeatureLifecycle(feature_id="test")
        assert lifecycle.get_transition_count() == 0
        lifecycle.transition_to(LifecycleState.IN_PROGRESS)
        assert lifecycle.get_transition_count() == 1
        lifecycle.transition_to(LifecycleState.REVIEW)
        assert lifecycle.get_transition_count() == 2

    def test_get_rework_count(self) -> None:
        """Test counting rework cycles."""
        lifecycle = FeatureLifecycle(feature_id="test")
        assert lifecycle.get_rework_count() == 0

        # Normal flow: PLANNED -> IN_PROGRESS -> REVIEW -> COMPLETE
        lifecycle.transition_to(LifecycleState.IN_PROGRESS)
        lifecycle.transition_to(LifecycleState.REVIEW)
        assert lifecycle.get_rework_count() == 0

        # Rework: REVIEW -> IN_PROGRESS
        lifecycle.transition_to(LifecycleState.IN_PROGRESS)
        assert lifecycle.get_rework_count() == 1

        # Another rework cycle
        lifecycle.transition_to(LifecycleState.REVIEW)
        lifecycle.transition_to(LifecycleState.IN_PROGRESS)
        assert lifecycle.get_rework_count() == 2

    def test_full_lifecycle_flow(self) -> None:
        """Test a complete lifecycle flow."""
        lifecycle = FeatureLifecycle(feature_id="test")

        # PLANNED -> IN_PROGRESS
        lifecycle.transition_to(LifecycleState.IN_PROGRESS)
        assert lifecycle.state == LifecycleState.IN_PROGRESS

        # IN_PROGRESS -> REVIEW
        lifecycle.transition_to(LifecycleState.REVIEW)
        assert lifecycle.state == LifecycleState.REVIEW

        # REVIEW -> IN_PROGRESS (rework)
        lifecycle.transition_to(LifecycleState.IN_PROGRESS)
        assert lifecycle.state == LifecycleState.IN_PROGRESS

        # IN_PROGRESS -> REVIEW (second attempt)
        lifecycle.transition_to(LifecycleState.REVIEW)
        assert lifecycle.state == LifecycleState.REVIEW

        # REVIEW -> COMPLETE
        lifecycle.transition_to(LifecycleState.COMPLETE)
        assert lifecycle.state == LifecycleState.COMPLETE

        # COMPLETE -> ARCHIVED
        lifecycle.transition_to(LifecycleState.ARCHIVED)
        assert lifecycle.state == LifecycleState.ARCHIVED

        # ARCHIVED is terminal - no transitions allowed
        assert lifecycle.get_allowed_transitions() == []
        assert lifecycle.get_transition_count() == 6  # 6 transitions in this flow

    def test_cancel_from_planned(self) -> None:
        """Test cancelling from planned state."""
        lifecycle = FeatureLifecycle(feature_id="test")
        lifecycle.transition_to(LifecycleState.ARCHIVED, reason="Cancelled")
        assert lifecycle.state == LifecycleState.ARCHIVED

    def test_cancel_from_in_progress(self) -> None:
        """Test cancelling from in_progress state."""
        lifecycle = FeatureLifecycle(feature_id="test")
        lifecycle.transition_to(LifecycleState.IN_PROGRESS)
        lifecycle.transition_to(LifecycleState.ARCHIVED, reason="Cancelled")
        assert lifecycle.state == LifecycleState.ARCHIVED

    def test_reopen_completed(self) -> None:
        """Test reopening a completed feature."""
        lifecycle = FeatureLifecycle(feature_id="test")
        lifecycle.transition_to(LifecycleState.IN_PROGRESS)
        lifecycle.transition_to(LifecycleState.REVIEW)
        lifecycle.transition_to(LifecycleState.COMPLETE)

        # Reopen for review
        lifecycle.transition_to(LifecycleState.REVIEW, reason="Bug found")
        assert lifecycle.state == LifecycleState.REVIEW


class TestProjectLifecycle:
    """Tests for ProjectLifecycle model."""

    def test_empty_project(self) -> None:
        """Test empty project state."""
        project = ProjectLifecycle()
        assert project.features == {}
        assert project.overall_state is None
        assert project.get_summary() == {s: 0 for s in LifecycleState}

    def test_add_feature(self) -> None:
        """Test adding a feature."""
        project = ProjectLifecycle()
        lifecycle = project.add_feature("feature-1")
        assert lifecycle.feature_id == "feature-1"
        assert lifecycle.state == LifecycleState.PLANNED
        assert "feature-1" in project.features

    def test_add_duplicate_feature(self) -> None:
        """Test adding a duplicate feature raises error."""
        project = ProjectLifecycle()
        project.add_feature("feature-1")
        with pytest.raises(ValueError, match="already exists"):
            project.add_feature("feature-1")

    def test_get_feature(self) -> None:
        """Test getting a feature."""
        project = ProjectLifecycle()
        project.add_feature("feature-1")
        lifecycle = project.get_feature("feature-1")
        assert lifecycle is not None
        assert lifecycle.feature_id == "feature-1"
        assert project.get_feature("nonexistent") is None

    def test_remove_feature(self) -> None:
        """Test removing a feature."""
        project = ProjectLifecycle()
        project.add_feature("feature-1")
        assert project.remove_feature("feature-1") is True
        assert "feature-1" not in project.features
        assert project.remove_feature("nonexistent") is False

    def test_get_features_by_state(self) -> None:
        """Test filtering features by state."""
        project = ProjectLifecycle()
        project.add_feature("planned-1")
        project.add_feature("planned-2")
        project.add_feature("progress-1")
        project.features["progress-1"].transition_to(LifecycleState.IN_PROGRESS)

        planned = project.get_features_by_state(LifecycleState.PLANNED)
        assert set(planned) == {"planned-1", "planned-2"}

        in_progress = project.get_features_by_state(LifecycleState.IN_PROGRESS)
        assert in_progress == ["progress-1"]

    def test_get_summary(self) -> None:
        """Test getting state summary."""
        project = ProjectLifecycle()
        project.add_feature("f1")
        project.add_feature("f2")
        project.add_feature("f3")
        project.features["f1"].transition_to(LifecycleState.IN_PROGRESS)

        summary = project.get_summary()
        assert summary[LifecycleState.PLANNED] == 2
        assert summary[LifecycleState.IN_PROGRESS] == 1
        assert summary[LifecycleState.COMPLETE] == 0

    def test_overall_state_in_progress(self) -> None:
        """Test overall state when any feature is in progress."""
        project = ProjectLifecycle()
        project.add_feature("f1")
        project.add_feature("f2")
        project.features["f1"].transition_to(LifecycleState.IN_PROGRESS)
        # f2 is still PLANNED, but overall is IN_PROGRESS
        assert project.overall_state == LifecycleState.IN_PROGRESS

    def test_overall_state_review(self) -> None:
        """Test overall state when any feature is in review."""
        project = ProjectLifecycle()
        project.add_feature("f1")
        project.features["f1"].transition_to(LifecycleState.IN_PROGRESS)
        project.features["f1"].transition_to(LifecycleState.REVIEW)
        assert project.overall_state == LifecycleState.REVIEW

    def test_overall_state_complete(self) -> None:
        """Test overall state when features are complete."""
        project = ProjectLifecycle()
        project.add_feature("f1")
        project.features["f1"].transition_to(LifecycleState.IN_PROGRESS)
        project.features["f1"].transition_to(LifecycleState.REVIEW)
        project.features["f1"].transition_to(LifecycleState.COMPLETE)
        assert project.overall_state == LifecycleState.COMPLETE

    def test_overall_state_archived(self) -> None:
        """Test overall state when all features are archived."""
        project = ProjectLifecycle()
        project.add_feature("f1")
        project.features["f1"].transition_to(LifecycleState.ARCHIVED)
        assert project.overall_state == LifecycleState.ARCHIVED

    def test_overall_state_priority(self) -> None:
        """Test overall state priority order."""
        # IN_PROGRESS > REVIEW > PLANNED > COMPLETE > ARCHIVED
        project = ProjectLifecycle()

        # Add one feature in each state
        project.add_feature("complete")
        project.features["complete"].transition_to(LifecycleState.IN_PROGRESS)
        project.features["complete"].transition_to(LifecycleState.REVIEW)
        project.features["complete"].transition_to(LifecycleState.COMPLETE)

        project.add_feature("planned")

        project.add_feature("progress")
        project.features["progress"].transition_to(LifecycleState.IN_PROGRESS)

        # IN_PROGRESS takes priority
        assert project.overall_state == LifecycleState.IN_PROGRESS

        # Complete the in-progress feature
        project.features["progress"].transition_to(LifecycleState.REVIEW)
        # REVIEW takes priority
        assert project.overall_state == LifecycleState.REVIEW
