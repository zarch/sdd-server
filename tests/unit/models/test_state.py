"""Unit tests for workflow state models."""

from datetime import UTC, datetime

import pytest

from sdd_server.models.state import (
    BypassRecord,
    FeatureState,
    ProjectState,
    WorkflowState,
)


def test_workflow_state_values() -> None:
    assert WorkflowState.UNINITIALIZED == "uninitialized"
    assert WorkflowState.COMPLETED == "completed"
    assert len(WorkflowState) == 8


def test_feature_state_valid_transition() -> None:
    fs = FeatureState(feature_id="f1")
    fs.transition_to(WorkflowState.INITIALIZING)
    assert fs.state == WorkflowState.INITIALIZING
    assert len(fs.history) == 1
    assert fs.history[0].from_state == WorkflowState.UNINITIALIZED


def test_feature_state_invalid_transition() -> None:
    fs = FeatureState(feature_id="f1")
    with pytest.raises(ValueError, match="Invalid transition"):
        fs.transition_to(WorkflowState.COMPLETED)


def test_can_transition_to() -> None:
    fs = FeatureState(feature_id="f1")
    assert fs.can_transition_to(WorkflowState.INITIALIZING) is True
    assert fs.can_transition_to(WorkflowState.COMPLETED) is False


def test_project_state_rollup_empty() -> None:
    ps = ProjectState()
    assert ps.workflow_state == WorkflowState.UNINITIALIZED


def test_project_state_rollup_blocked() -> None:
    ps = ProjectState()
    ps.set_feature("f1", FeatureState(feature_id="f1", state=WorkflowState.IMPLEMENTING))
    ps.set_feature("f2", FeatureState(feature_id="f2", state=WorkflowState.BLOCKED))
    assert ps.workflow_state == WorkflowState.BLOCKED


def test_project_state_rollup_completed() -> None:
    ps = ProjectState()
    ps.set_feature("f1", FeatureState(feature_id="f1", state=WorkflowState.COMPLETED))
    ps.set_feature("f2", FeatureState(feature_id="f2", state=WorkflowState.COMPLETED))
    assert ps.workflow_state == WorkflowState.COMPLETED


def test_project_state_add_bypass() -> None:
    ps = ProjectState()
    record = BypassRecord(
        timestamp=datetime.now(UTC),
        actor="test",
        reason="hotfix",
        action="commit",
    )
    ps.add_bypass(record)
    assert len(ps.active_bypasses()) == 1
