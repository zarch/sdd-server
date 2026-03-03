"""Feature lifecycle models for SDD."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sdd_server.models.base import SDDBaseModel


class LifecycleState(StrEnum):
    """Feature lifecycle states.

    Lifecycle flow:
    PLANNED → IN_PROGRESS → REVIEW → COMPLETE → ARCHIVED
              ↑              ↓
              └──────────────┘ (rework loop)
    """

    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    COMPLETE = "complete"
    ARCHIVED = "archived"


# Valid lifecycle state transitions
_LIFECYCLE_TRANSITIONS: dict[LifecycleState, set[LifecycleState]] = {
    LifecycleState.PLANNED: {
        LifecycleState.IN_PROGRESS,
        LifecycleState.ARCHIVED,  # Cancel before starting
    },
    LifecycleState.IN_PROGRESS: {
        LifecycleState.REVIEW,
        LifecycleState.PLANNED,  # Back to planning
        LifecycleState.ARCHIVED,  # Cancel
    },
    LifecycleState.REVIEW: {
        LifecycleState.COMPLETE,
        LifecycleState.IN_PROGRESS,  # Rework needed
        LifecycleState.ARCHIVED,  # Cancel during review
    },
    LifecycleState.COMPLETE: {
        LifecycleState.ARCHIVED,
        LifecycleState.REVIEW,  # Re-open for issues
    },
    LifecycleState.ARCHIVED: set(),  # Terminal state
}


class LifecycleTransition(SDDBaseModel):
    """Record of a lifecycle state transition."""

    from_state: LifecycleState
    to_state: LifecycleState
    timestamp: datetime
    reason: str | None = None
    actor: str | None = None
    metadata: dict[str, Any] = {}  # noqa: RUF012


class FeatureLifecycle(SDDBaseModel):
    """Lifecycle state machine for a single feature."""

    feature_id: str
    state: LifecycleState = LifecycleState.PLANNED
    history: list[LifecycleTransition] = []  # noqa: RUF012
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        if self.created_at is None:
            self.created_at = datetime.now(UTC)
        if self.updated_at is None:
            self.updated_at = self.created_at

    def transition_to(
        self,
        new_state: LifecycleState,
        reason: str | None = None,
        actor: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> LifecycleTransition:
        """Transition to a new state.

        Args:
            new_state: Target lifecycle state.
            reason: Optional reason for the transition.
            actor: Optional actor who initiated the transition.
            metadata: Optional additional metadata.

        Returns:
            The created LifecycleTransition record.

        Raises:
            ValueError: If the transition is invalid.
        """
        allowed = _LIFECYCLE_TRANSITIONS.get(self.state, set())
        if new_state not in allowed:
            raise ValueError(
                f"Invalid lifecycle transition for feature '{self.feature_id}': "
                f"{self.state} → {new_state}. "
                f"Allowed: {', '.join(s.value for s in allowed) or 'none'}"
            )

        transition = LifecycleTransition(
            from_state=self.state,
            to_state=new_state,
            timestamp=datetime.now(UTC),
            reason=reason,
            actor=actor,
            metadata=metadata or {},
        )
        self.history.append(transition)
        self.state = new_state
        self.updated_at = datetime.now(UTC)
        return transition

    def can_transition_to(self, new_state: LifecycleState) -> bool:
        """Check whether a transition is valid without performing it."""
        return new_state in _LIFECYCLE_TRANSITIONS.get(self.state, set())

    def get_allowed_transitions(self) -> list[LifecycleState]:
        """Get list of states this feature can transition to."""
        return list(_LIFECYCLE_TRANSITIONS.get(self.state, set()))

    def time_in_current_state(self) -> float | None:
        """Get seconds spent in current state, or None if no history."""
        if not self.history:
            if self.created_at:
                return (datetime.now(UTC) - self.created_at).total_seconds()
            return None
        last_transition = self.history[-1]
        return (datetime.now(UTC) - last_transition.timestamp).total_seconds()

    def get_transition_count(self) -> int:
        """Get total number of transitions."""
        return len(self.history)

    def get_rework_count(self) -> int:
        """Get number of times the feature went from REVIEW back to IN_PROGRESS."""
        return sum(
            1
            for t in self.history
            if t.from_state == LifecycleState.REVIEW and t.to_state == LifecycleState.IN_PROGRESS
        )


class ProjectLifecycle(SDDBaseModel):
    """Project-level lifecycle state aggregating all features."""

    features: dict[str, FeatureLifecycle] = {}  # noqa: RUF012
    metadata: dict[str, Any] = {}  # noqa: RUF012

    def add_feature(self, feature_id: str) -> FeatureLifecycle:
        """Add a new feature in PLANNED state."""
        if feature_id in self.features:
            raise ValueError(f"Feature '{feature_id}' already exists")
        lifecycle = FeatureLifecycle(feature_id=feature_id)
        self.features[feature_id] = lifecycle
        return lifecycle

    def get_feature(self, feature_id: str) -> FeatureLifecycle | None:
        """Get a feature's lifecycle state."""
        return self.features.get(feature_id)

    def remove_feature(self, feature_id: str) -> bool:
        """Remove a feature. Returns True if found and removed."""
        if feature_id in self.features:
            del self.features[feature_id]
            return True
        return False

    def get_features_by_state(self, state: LifecycleState) -> list[str]:
        """Get all features in a specific state."""
        return [fid for fid, f in self.features.items() if f.state == state]

    def get_summary(self) -> dict[LifecycleState, int]:
        """Get count of features in each state."""
        summary: dict[LifecycleState, int] = {s: 0 for s in LifecycleState}
        for feature in self.features.values():
            summary[feature.state] += 1
        return summary

    @property
    def overall_state(self) -> LifecycleState | None:
        """Compute overall project lifecycle state.

        Priority: IN_PROGRESS > REVIEW > PLANNED > COMPLETE > ARCHIVED
        Returns None if no features.
        """
        if not self.features:
            return None

        states = [f.state for f in self.features.values()]

        # Priority order for "active" states
        if any(s == LifecycleState.IN_PROGRESS for s in states):
            return LifecycleState.IN_PROGRESS
        if any(s == LifecycleState.REVIEW for s in states):
            return LifecycleState.REVIEW
        if any(s == LifecycleState.PLANNED for s in states):
            return LifecycleState.PLANNED
        if any(s == LifecycleState.COMPLETE for s in states):
            return LifecycleState.COMPLETE
        if all(s == LifecycleState.ARCHIVED for s in states):
            return LifecycleState.ARCHIVED
        return None
