"""Task models."""

from __future__ import annotations

import uuid
from enum import StrEnum

from sdd_server.models.base import SDDBaseModel


class TaskStatus(StrEnum):
    """Task lifecycle status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"


def generate_task_id() -> str:
    """Generate a short unique task ID in the format t<7hexchars>."""
    return "t" + uuid.uuid4().hex[:7]


class Task(SDDBaseModel):
    """A single implementation task."""

    id: str
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    role: str | None = None
    feature: str | None = None
    ai_prompt: str | None = None
