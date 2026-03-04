"""Workflow state models for SDD."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sdd_server.models.base import SDDBaseModel


class WorkflowState(StrEnum):
    """Feature workflow states (PRD §E1)."""

    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    SPEC_REVIEW = "spec_review"
    READY = "ready"
    IMPLEMENTING = "implementing"
    REVIEWING = "reviewing"
    BLOCKED = "blocked"
    COMPLETED = "completed"


# Valid state transitions
_TRANSITIONS: dict[WorkflowState, set[WorkflowState]] = {
    WorkflowState.UNINITIALIZED: {WorkflowState.INITIALIZING},
    WorkflowState.INITIALIZING: {WorkflowState.SPEC_REVIEW, WorkflowState.UNINITIALIZED},
    WorkflowState.SPEC_REVIEW: {WorkflowState.READY, WorkflowState.INITIALIZING},
    WorkflowState.READY: {WorkflowState.IMPLEMENTING, WorkflowState.SPEC_REVIEW},
    WorkflowState.IMPLEMENTING: {
        WorkflowState.REVIEWING,
        WorkflowState.BLOCKED,
        WorkflowState.READY,
    },
    WorkflowState.REVIEWING: {
        WorkflowState.IMPLEMENTING,
        WorkflowState.COMPLETED,
        WorkflowState.BLOCKED,
    },
    WorkflowState.BLOCKED: {
        WorkflowState.IMPLEMENTING,
        WorkflowState.REVIEWING,
        WorkflowState.READY,
    },
    WorkflowState.COMPLETED: {WorkflowState.IMPLEMENTING},
}


class StateHistory(SDDBaseModel):
    """A single state transition record."""

    from_state: WorkflowState
    to_state: WorkflowState
    timestamp: datetime
    reason: str | None = None
    actor: str | None = None


class BypassRecord(SDDBaseModel):
    """Audit record for a bypassed enforcement action."""

    timestamp: datetime
    actor: str
    reason: str
    action: str
    feature: str | None = None


class FeatureState(SDDBaseModel):
    """State machine for a single feature."""

    feature_id: str
    state: WorkflowState = WorkflowState.UNINITIALIZED
    history: list[StateHistory] = []  # noqa: RUF012
    metadata: dict[str, Any] = {}  # noqa: RUF012

    def transition_to(
        self,
        new_state: WorkflowState,
        reason: str | None = None,
        actor: str | None = None,
    ) -> None:
        """Transition to a new state, raising ValueError for invalid transitions."""
        allowed = _TRANSITIONS.get(self.state, set())
        if new_state not in allowed:
            raise ValueError(
                f"Invalid transition for feature '{self.feature_id}': "
                f"{self.state} → {new_state}. "
                f"Allowed: {', '.join(s.value for s in allowed) or 'none'}"
            )
        self.history.append(
            StateHistory(
                from_state=self.state,
                to_state=new_state,
                timestamp=datetime.now(UTC),
                reason=reason,
                actor=actor,
            )
        )
        self.state = new_state

    def can_transition_to(self, new_state: WorkflowState) -> bool:
        """Check whether a transition is valid without performing it."""
        return new_state in _TRANSITIONS.get(self.state, set())

    def get_rework_count(self) -> int:
        """Count transitions that moved backwards (e.g. reviewing → implementing)."""
        backwards = {
            (WorkflowState.REVIEWING, WorkflowState.IMPLEMENTING),
            (WorkflowState.IMPLEMENTING, WorkflowState.READY),
            (WorkflowState.SPEC_REVIEW, WorkflowState.INITIALIZING),
        }
        return sum(1 for h in self.history if (h.from_state, h.to_state) in backwards)

    def time_in_current_state(self) -> float | None:
        """Seconds spent in the current state, or None if no history."""
        if not self.history:
            return None
        return (datetime.now(UTC) - self.history[-1].timestamp).total_seconds()


class ProjectState(SDDBaseModel):
    """Project-level state, derived as a rollup from feature states."""

    features: dict[str, FeatureState] = {}  # noqa: RUF012
    bypasses: list[BypassRecord] = []  # noqa: RUF012
    metadata: dict[str, Any] = {}  # noqa: RUF012

    @property
    def workflow_state(self) -> WorkflowState:
        """Compute overall project state from all feature states."""
        if not self.features:
            return WorkflowState.UNINITIALIZED

        states = [f.state for f in self.features.values()]

        # Priority order: blocked > reviewing > implementing > spec_review >
        #                 initializing > ready > completed > uninitialized
        if any(s == WorkflowState.BLOCKED for s in states):
            return WorkflowState.BLOCKED
        if any(s == WorkflowState.REVIEWING for s in states):
            return WorkflowState.REVIEWING
        if any(s == WorkflowState.IMPLEMENTING for s in states):
            return WorkflowState.IMPLEMENTING
        if any(s == WorkflowState.SPEC_REVIEW for s in states):
            return WorkflowState.SPEC_REVIEW
        if any(s == WorkflowState.INITIALIZING for s in states):
            return WorkflowState.INITIALIZING
        if any(s == WorkflowState.READY for s in states):
            return WorkflowState.READY
        if all(s == WorkflowState.COMPLETED for s in states):
            return WorkflowState.COMPLETED
        return WorkflowState.UNINITIALIZED

    def get_feature(self, feature_id: str) -> FeatureState | None:
        return self.features.get(feature_id)

    def set_feature(self, feature_id: str, state: FeatureState) -> None:
        self.features[feature_id] = state

    def add_bypass(self, record: BypassRecord) -> None:
        self.bypasses.append(record)

    def active_bypasses(self) -> list[BypassRecord]:
        return list(self.bypasses)
