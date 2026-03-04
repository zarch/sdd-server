"""Task models."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sdd_server.models.base import SDDBaseModel


class TaskStatus(StrEnum):
    """Task lifecycle status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class TaskPriority(StrEnum):
    """Task priority levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


def generate_task_id() -> str:
    """Generate a short unique task ID in the format t<7hexchars>."""
    return "t" + uuid.uuid4().hex[:7]


class Task(SDDBaseModel):
    """A single implementation task."""

    id: str
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.MEDIUM
    role: str | None = None
    feature: str | None = None
    ai_prompt: str | None = None
    dependencies: list[str] = []  # noqa: RUF012
    tags: list[str] = []  # noqa: RUF012
    created_at: datetime | None = None
    updated_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: dict[str, Any] = {}  # noqa: RUF012

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        if self.created_at is None:
            self.created_at = datetime.now(UTC)
        if self.updated_at is None:
            self.updated_at = self.created_at

    def mark_in_progress(self) -> None:
        """Mark task as in progress."""
        self.status = TaskStatus.IN_PROGRESS
        self.updated_at = datetime.now(UTC)

    def mark_complete(self) -> None:
        """Mark task as complete."""
        self.status = TaskStatus.COMPLETE
        self.completed_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)

    def mark_blocked(self, reason: str | None = None) -> None:
        """Mark task as blocked."""
        self.status = TaskStatus.BLOCKED
        self.updated_at = datetime.now(UTC)
        if reason:
            self.metadata["block_reason"] = reason

    def cancel(self, reason: str | None = None) -> None:
        """Cancel the task."""
        self.status = TaskStatus.CANCELLED
        self.updated_at = datetime.now(UTC)
        if reason:
            self.metadata["cancel_reason"] = reason

    def is_done(self) -> bool:
        """Check if task is in a terminal state."""
        return self.status in (TaskStatus.COMPLETE, TaskStatus.CANCELLED)


class TaskBreakdown(SDDBaseModel):
    """A collection of tasks for a feature or project."""

    feature: str | None = None
    tasks: dict[str, Task] = {}  # noqa: RUF012
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        if self.created_at is None:
            self.created_at = datetime.now(UTC)
        if self.updated_at is None:
            self.updated_at = self.created_at

    def add_task(self, task: Task) -> None:
        """Add a task to the breakdown."""
        self.tasks[task.id] = task
        self.updated_at = datetime.now(UTC)

    def remove_task(self, task_id: str) -> bool:
        """Remove a task from the breakdown."""
        if task_id in self.tasks:
            del self.tasks[task_id]
            self.updated_at = datetime.now(UTC)
            return True
        return False

    def get_task(self, task_id: str) -> Task | None:
        """Get a task by ID."""
        return self.tasks.get(task_id)

    def get_tasks_by_status(self, status: TaskStatus) -> list[Task]:
        """Get all tasks with a specific status."""
        return [t for t in self.tasks.values() if t.status == status]

    def get_pending_dependencies(self, task_id: str) -> list[str]:
        """Get list of pending dependency IDs for a task."""
        task = self.get_task(task_id)
        if task is None:
            return []
        pending = []
        for dep_id in task.dependencies:
            dep_task = self.get_task(dep_id)
            if dep_task is None or not dep_task.is_done():
                pending.append(dep_id)
        return pending

    def can_start(self, task_id: str) -> bool:
        """Check if all dependencies are complete."""
        return len(self.get_pending_dependencies(task_id)) == 0

    def get_completion_percentage(self) -> float:
        """Get percentage of completed tasks."""
        if not self.tasks:
            return 0.0
        completed = sum(1 for t in self.tasks.values() if t.status == TaskStatus.COMPLETE)
        return (completed / len(self.tasks)) * 100

    def get_summary(self) -> dict[str, int]:
        """Get count of tasks by status."""
        summary: dict[str, int] = {s.value: 0 for s in TaskStatus}
        for task in self.tasks.values():
            summary[task.status.value] += 1
        return summary

    def get_next_ready_tasks(self) -> list[Task]:
        """Get tasks that are pending and have all dependencies met."""
        ready = []
        for task in self.tasks.values():
            if task.status == TaskStatus.PENDING and self.can_start(task.id):
                ready.append(task)
        return ready


# Regex patterns for parsing tasks.md files
_TASK_PATTERN = re.compile(r"^\s*-\s*\[([ x])\]\s*(.+?)\s*(?:#([a-z0-9-]+))?\s*$", re.MULTILINE)

_ID_PATTERN = re.compile(r"^t[0-9a-f]{7}$", re.IGNORECASE)


def parse_tasks_from_markdown(content: str, feature: str | None = None) -> list[Task]:
    """Parse tasks from a markdown file content.

    Supports formats:
    - [ ] Task title
    - [x] Completed task title
    - [ ] Task title #t1234567

    Args:
        content: Markdown content to parse.
        feature: Optional feature to associate with tasks.

    Returns:
        List of Task objects parsed from the content.
    """
    tasks = []

    for match in _TASK_PATTERN.finditer(content):
        checked, title, task_id = match.groups()

        # Generate ID if not present
        if not task_id or not _ID_PATTERN.match(task_id):
            task_id = generate_task_id()

        status = TaskStatus.COMPLETE if checked.lower() == "x" else TaskStatus.PENDING

        task = Task(
            id=task_id,
            title=title.strip(),
            status=status,
            feature=feature,
        )
        tasks.append(task)

    return tasks


def serialize_tasks_to_markdown(tasks: list[Task]) -> str:
    """Serialize tasks to markdown format.

    Args:
        tasks: List of tasks to serialize.

    Returns:
        Markdown formatted task list.
    """
    lines = []
    for task in tasks:
        checkbox = "[x]" if task.status == TaskStatus.COMPLETE else "[ ]"
        line = f"- {checkbox} {task.title} #{task.id}"
        lines.append(line)
    return "\n".join(lines)
