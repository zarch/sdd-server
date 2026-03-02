"""Unit tests for task models."""

import re

from sdd_server.models.task import Task, TaskStatus, generate_task_id


def test_generate_task_id_format() -> None:
    tid = generate_task_id()
    assert re.match(r"^t[0-9a-f]{7}$", tid), f"Bad task ID: {tid!r}"


def test_generate_task_id_unique() -> None:
    # 7 hex chars = 28 bits; collision probability for 100 items is negligible
    ids = {generate_task_id() for _ in range(100)}
    assert len(ids) == 100


def test_task_defaults() -> None:
    task = Task(id=generate_task_id(), title="Implement auth")
    assert task.status == TaskStatus.PENDING
    assert task.role is None
    assert task.feature is None


def test_task_status_assignment() -> None:
    task = Task(id=generate_task_id(), title="Test")
    task.status = TaskStatus.IN_PROGRESS
    assert task.status == TaskStatus.IN_PROGRESS


def test_task_status_values() -> None:
    assert TaskStatus.PENDING == "pending"
    assert TaskStatus.IN_PROGRESS == "in_progress"
    assert TaskStatus.COMPLETE == "complete"
