"""Streaming progress updates for role executions.

This module provides functionality for streaming progress events
from role executions via Server-Sent Events (SSE) and async queues.
"""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, AsyncIterator, Callable

from sdd_server.plugins.base import RoleStatus
from sdd_server.utils.logging import get_logger

logger = get_logger(__name__)


class EventType(StrEnum):
    """Types of progress events."""

    # Execution lifecycle
    EXECUTION_STARTED = "execution_started"
    EXECUTION_PROGRESS = "execution_progress"
    EXECUTION_COMPLETED = "execution_completed"
    EXECUTION_FAILED = "execution_failed"
    EXECUTION_CANCELLED = "execution_cancelled"

    # Role lifecycle
    ROLE_STARTED = "role_started"
    ROLE_PROGRESS = "role_progress"
    ROLE_COMPLETED = "role_completed"
    ROLE_FAILED = "role_failed"
    ROLE_SKIPPED = "role_skipped"

    # Issue events
    ISSUE_FOUND = "issue_found"

    # Log events
    LOG = "log"


@dataclass
class ProgressEvent:
    """A progress event for streaming."""

    event_type: EventType
    timestamp: datetime = field(default_factory=datetime.now)
    data: dict[str, Any] = field(default_factory=dict)
    message: str | None = None

    def to_sse(self) -> str:
        """Convert to Server-Sent Events format.

        Returns:
            SSE formatted string
        """
        lines: list[str] = []
        lines.append(f"event: {self.event_type.value}")

        if self.message:
            lines.append(f"data: {json.dumps({'message': self.message})}")

        if self.data:
            lines.append(f"data: {json.dumps(self.data)}")

        lines.append("")
        lines.append("")
        return "\n".join(lines)

    def to_json(self) -> str:
        """Convert to JSON string.

        Returns:
            JSON formatted string
        """
        return json.dumps({
            "event": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "message": self.message,
            "data": self.data,
        })


class EventEmitter:
    """Emits progress events to subscribers via async queues."""

    def __init__(self, max_queue_size: int = 100) -> None:
        """Initialize the event emitter.

        Args:
            max_queue_size: Maximum events to queue per subscriber
        """
        self._subscribers: list[asyncio.Queue[ProgressEvent]] = []
        self._max_queue_size = max_queue_size
        self._lock = asyncio.Lock()

    async def subscribe(self) -> "asyncio.Queue[ProgressEvent]":
        """Subscribe to events.

        Returns:
            Queue that will receive events
        """
        queue: asyncio.Queue[ProgressEvent] = asyncio.Queue(maxsize=self._max_queue_size)
        async with self._lock:
            self._subscribers.append(queue)
        logger.debug("New subscriber added", total=len(self._subscribers))
        return queue

    async def unsubscribe(self, queue: "asyncio.Queue[ProgressEvent]") -> None:
        """Unsubscribe from events.

        Args:
            queue: Queue to remove
        """
        async with self._lock:
            if queue in self._subscribers:
                self._subscribers.remove(queue)
        logger.debug("Subscriber removed", total=len(self._subscribers))

    async def emit(self, event: ProgressEvent) -> None:
        """Emit an event to all subscribers.

        Args:
            event: Event to emit
        """
        async with self._lock:
            subscribers = self._subscribers.copy()

        if not subscribers:
            return

        # Send to all subscribers, drop if queue full
        for queue in subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("Dropped event for slow subscriber", event=event.event_type)

        logger.debug(
            "Event emitted",
            event_type=event.event_type.value,
            subscribers=len(subscribers),
        )

    async def emit_simple(
        self,
        event_type: EventType,
        message: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Emit a simple event.

        Args:
            event_type: Type of event
            message: Optional message
            data: Optional data dict
        """
        event = ProgressEvent(
            event_type=event_type,
            message=message,
            data=data or {},
        )
        await self.emit(event)

    def subscriber_count(self) -> int:
        """Get current subscriber count.

        Returns:
            Number of subscribers
        """
        return len(self._subscribers)

    async def clear(self) -> None:
        """Clear all subscribers."""
        async with self._lock:
            self._subscribers.clear()


async def event_stream(
    queue: "asyncio.Queue[ProgressEvent]",
    timeout_seconds: float | None = None,
) -> AsyncIterator[str]:
    """Generate SSE stream from event queue.

    Args:
        queue: Queue to read events from
        timeout_seconds: Optional timeout for waiting for events

    Yields:
        SSE formatted strings
    """
    while True:
        try:
            if timeout_seconds:
                event = await asyncio.wait_for(queue.get(), timeout=timeout_seconds)
            else:
                event = await queue.get()

            yield event.to_sse()

            # Check for completion events
            if event.event_type in (
                EventType.EXECUTION_COMPLETED,
                EventType.EXECUTION_FAILED,
                EventType.EXECUTION_CANCELLED,
            ):
                break

        except asyncio.TimeoutError:
            # Send keepalive comment
            yield ": keepalive\n\n"
        except asyncio.CancelledError:
            break


async def json_event_stream(
    queue: "asyncio.Queue[ProgressEvent]",
    timeout_seconds: float | None = None,
) -> AsyncIterator[str]:
    """Generate JSON stream from event queue.

    Args:
        queue: Queue to read events from
        timeout_seconds: Optional timeout for waiting for events

    Yields:
        JSON formatted strings with newlines
    """
    while True:
        try:
            if timeout_seconds:
                event = await asyncio.wait_for(queue.get(), timeout=timeout_seconds)
            else:
                event = await queue.get()

            yield event.to_json() + "\n"

            # Check for completion events
            if event.event_type in (
                EventType.EXECUTION_COMPLETED,
                EventType.EXECUTION_FAILED,
                EventType.EXECUTION_CANCELLED,
            ):
                break

        except asyncio.TimeoutError:
            # Skip keepalive for JSON stream
            continue
        except asyncio.CancelledError:
            break


# Helper functions for creating common events

def create_execution_started_event(
    total_roles: int,
    role_names: list[str],
    mode: str = "parallel",
) -> ProgressEvent:
    """Create execution started event."""
    return ProgressEvent(
        event_type=EventType.EXECUTION_STARTED,
        message=f"Starting execution of {total_roles} roles",
        data={
            "total_roles": total_roles,
            "role_names": role_names,
            "mode": mode,
        },
    )


def create_execution_progress_event(
    completed: int,
    failed: int,
    total: int,
    running: list[str] | None = None,
) -> ProgressEvent:
    """Create execution progress event."""
    percent = (completed + failed) / total * 100 if total > 0 else 100
    return ProgressEvent(
        event_type=EventType.EXECUTION_PROGRESS,
        message=f"Progress: {completed}/{total} roles completed ({percent:.0f}%)",
        data={
            "completed": completed,
            "failed": failed,
            "total": total,
            "percent": round(percent, 1),
            "running": running or [],
        },
    )


def create_execution_completed_event(
    total_roles: int,
    successful: int,
    failed: int,
    duration_seconds: float,
) -> ProgressEvent:
    """Create execution completed event."""
    return ProgressEvent(
        event_type=EventType.EXECUTION_COMPLETED,
        message=f"Execution completed: {successful} successful, {failed} failed",
        data={
            "total_roles": total_roles,
            "successful": successful,
            "failed": failed,
            "duration_seconds": round(duration_seconds, 2),
        },
    )


def create_role_started_event(
    role_name: str,
    stage: str | None = None,
) -> ProgressEvent:
    """Create role started event."""
    return ProgressEvent(
        event_type=EventType.ROLE_STARTED,
        message=f"Starting role: {role_name}",
        data={
            "role": role_name,
            "stage": stage,
        },
    )


def create_role_completed_event(
    role_name: str,
    success: bool,
    issue_count: int,
    duration_seconds: float | None = None,
) -> ProgressEvent:
    """Create role completed event."""
    status = "completed" if success else "failed"
    return ProgressEvent(
        event_type=EventType.ROLE_COMPLETED if success else EventType.ROLE_FAILED,
        message=f"Role {role_name} {status} with {issue_count} issues",
        data={
            "role": role_name,
            "success": success,
            "issue_count": issue_count,
            "duration_seconds": duration_seconds,
        },
    )


def create_issue_found_event(
    role_name: str,
    issue_title: str,
    severity: str = "medium",
) -> ProgressEvent:
    """Create issue found event."""
    return ProgressEvent(
        event_type=EventType.ISSUE_FOUND,
        message=f"Issue found by {role_name}: {issue_title[:50]}",
        data={
            "role": role_name,
            "issue": issue_title,
            "severity": severity,
        },
    )


# Callback factory for integration with ExecutionPipeline

def create_progress_callback(
    emitter: EventEmitter,
    total_roles: int,
) -> Callable[[Any], None]:
    """Create a progress callback for ExecutionPipeline.

    Args:
        emitter: EventEmitter to send events to
        total_roles: Total number of roles

    Returns:
        Callback function for ExecutionConfig.progress_callback
    """

    def callback(progress: Any) -> None:
        """Progress callback that emits events."""
        event = create_execution_progress_event(
            completed=progress.completed_roles,
            failed=progress.failed_roles,
            total=progress.total_roles,
            running=progress.running_roles,
        )
        # Create task but don't await - fire and forget
        asyncio.create_task(emitter.emit(event))

    return callback


def create_result_callback(
    emitter: EventEmitter,
) -> Callable[[Any], None]:
    """Create a result callback for ExecutionPipeline.

    Args:
        emitter: EventEmitter to send events to

    Returns:
        Callback function for ExecutionConfig.result_callback
    """

    def callback(result: Any) -> None:
        """Result callback that emits events."""
        event = create_role_completed_event(
            role_name=result.role,
            success=result.success,
            issue_count=len(result.issues) if hasattr(result, "issues") else 0,
            duration_seconds=result.duration_seconds,
        )
        asyncio.create_task(emitter.emit(event))

        # Also emit issue events
        if hasattr(result, "issues"):
            for issue in result.issues:
                issue_event = create_issue_found_event(
                    role_name=result.role,
                    issue_title=issue,
                )
                asyncio.create_task(emitter.emit(issue_event))

    return callback
