"""Tests for streaming progress updates."""

import asyncio
import json
from datetime import datetime

import pytest

from sdd_server.core.streaming import (
    EventEmitter,
    EventType,
    ProgressEvent,
    create_execution_completed_event,
    create_execution_progress_event,
    create_execution_started_event,
    create_issue_found_event,
    create_result_callback,
    create_role_completed_event,
    create_role_started_event,
    create_progress_callback,
    event_stream,
    json_event_stream,
)


class TestEventType:
    """Tests for EventType enum."""

    def test_event_type_values(self) -> None:
        """Test event type enum values."""
        assert EventType.EXECUTION_STARTED.value == "execution_started"
        assert EventType.ROLE_STARTED.value == "role_started"
        assert EventType.ISSUE_FOUND.value == "issue_found"


class TestProgressEvent:
    """Tests for ProgressEvent."""

    def test_to_sse(self) -> None:
        """Test SSE format conversion."""
        event = ProgressEvent(
            event_type=EventType.ROLE_STARTED,
            message="Starting role",
            data={"role": "architect"},
        )

        sse = event.to_sse()

        assert "event: role_started" in sse
        assert "data:" in sse

    def test_to_json(self) -> None:
        """Test JSON format conversion."""
        event = ProgressEvent(
            event_type=EventType.EXECUTION_COMPLETED,
            message="Done",
            data={"count": 5},
        )

        json_str = event.to_json()
        data = json.loads(json_str)

        assert data["event"] == "execution_completed"
        assert data["message"] == "Done"
        assert data["data"]["count"] == 5

    def test_timestamp_included(self) -> None:
        """Test that timestamp is included."""
        event = ProgressEvent(
            event_type=EventType.LOG,
        )

        json_str = event.to_json()
        data = json.loads(json_str)

        assert "timestamp" in data


class TestEventEmitter:
    """Tests for EventEmitter."""

    def test_init(self) -> None:
        """Test initialization."""
        emitter = EventEmitter()
        assert len(emitter._subscribers) == 0  # Actually starts with 0

    @pytest.mark.asyncio
    async def test_subscribe_unsubscribe(self) -> None:
        """Test subscribe and unsubscribe."""
        emitter = EventEmitter()

        queue = await emitter.subscribe()
        assert queue is not None

        await emitter.unsubscribe(queue)

    @pytest.mark.asyncio
    async def test_emit_event(self) -> None:
        """Test emitting events."""
        emitter = EventEmitter()
        queue = await emitter.subscribe()

        event = ProgressEvent(event_type=EventType.LOG, message="test")
        await emitter.emit(event)

        received = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert received is not None
        assert received.message == "test"

        await emitter.unsubscribe(queue)

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self) -> None:
        """Test multiple subscribers receive events."""
        emitter = EventEmitter()
        queue1 = await emitter.subscribe()
        queue2 = await emitter.subscribe()

        event = ProgressEvent(event_type=EventType.LOG, message="broadcast")
        await emitter.emit(event)

        r1 = await asyncio.wait_for(queue1.get(), timeout=1.0)
        r2 = await asyncio.wait_for(queue2.get(), timeout=1.0)

        assert r1.message == "broadcast"
        assert r2.message == "broadcast"

        await emitter.unsubscribe(queue1)
        await emitter.unsubscribe(queue2)


class TestEventFactory:
    """Tests for event factory functions."""

    def test_create_execution_started_event(self) -> None:
        """Test execution started event creation."""
        event = create_execution_started_event(
            total_roles=5,
            role_names=["architect", "reviewer"],
            mode="parallel",
        )

        assert event.event_type == EventType.EXECUTION_STARTED
        assert "5 roles" in event.message
        assert event.data["total_roles"] == 5

    def test_create_execution_progress_event(self) -> None:
        """Test execution progress event creation."""
        event = create_execution_progress_event(
            completed=3,
            failed=1,
            total=5,
            running=["reviewer"],
        )

        assert event.event_type == EventType.EXECUTION_PROGRESS
        assert event.data["percent"] == 80.0

    def test_create_execution_completed_event(self) -> None:
        """Test execution completed event creation."""
        event = create_execution_completed_event(
            total_roles=5,
            successful=4,
            failed=1,
            duration_seconds=10.5,
        )

        assert event.event_type == EventType.EXECUTION_COMPLETED
        assert "4 successful" in event.message

    def test_create_role_started_event(self) -> None:
        """Test role started event creation."""
        event = create_role_started_event(
            role_name="architect",
            stage="architecture",
        )

        assert event.event_type == EventType.ROLE_STARTED
        assert "architect" in event.message

    def test_create_role_completed_event(self) -> None:
        """Test role completed event creation."""
        event = create_role_completed_event(
            role_name="reviewer",
            success=True,
            issue_count=2,
            duration_seconds=5.0,
        )

        assert event.event_type == EventType.ROLE_COMPLETED
        assert "completed" in event.message

    def test_create_role_failed_event(self) -> None:
        """Test role failed event creation."""
        event = create_role_completed_event(
            role_name="tester",
            success=False,
            issue_count=3,
        )

        assert event.event_type == EventType.ROLE_FAILED

    def test_create_issue_found_event(self) -> None:
        """Test issue found event creation."""
        event = create_issue_found_event(
            role_name="security",
            issue_title="XSS vulnerability",
            severity="high",
        )

        assert event.event_type == EventType.ISSUE_FOUND
        assert "security" in event.message
        assert "XSS" in event.message


class TestCallbackFactories:
    """Tests for callback factory functions."""

    @pytest.mark.asyncio
    async def test_create_progress_callback(self) -> None:
        """Test progress callback creation."""
        emitter = EventEmitter()
        queue = await emitter.subscribe()

        callback = create_progress_callback(emitter, total_roles=5)

        # Create mock progress object
        class MockProgress:
            completed_roles = 3
            failed_roles = 1
            total_roles = 5
            running_roles = ["reviewer"]

        progress = MockProgress()
        callback(progress)

        # Wait for event
        await asyncio.sleep(0.1)
        event = await asyncio.wait_for(queue.get(), timeout=1.0)

        assert event is not None
        assert event.event_type == EventType.EXECUTION_PROGRESS

        await emitter.unsubscribe(queue)

    @pytest.mark.asyncio
    async def test_create_result_callback(self) -> None:
        """Test result callback creation."""
        emitter = EventEmitter()
        queue = await emitter.subscribe()

        callback = create_result_callback(emitter)

        # Create mock result object
        class MockResult:
            role = "architect"
            success = True
            issues = ["issue1", "issue2"]
            duration_seconds = 5.0

        result = MockResult()
        callback(result)

        # Wait for events
        await asyncio.sleep(0.1)

        events = []
        while not queue.empty():
            events.append(await queue.get())

        assert len(events) >= 1
        assert any(e.event_type == EventType.ROLE_COMPLETED for e in events)

        await emitter.unsubscribe(queue)


class TestEventStreams:
    """Tests for event stream generators."""

    @pytest.mark.asyncio
    async def test_sse_event_stream(self) -> None:
        """Test SSE event stream generator."""
        emitter = EventEmitter()
        queue = await emitter.subscribe()

        # Emit some events
        await emitter.emit(ProgressEvent(event_type=EventType.LOG, message="test1"))
        await emitter.emit(ProgressEvent(event_type=EventType.EXECUTION_COMPLETED, message="done"))

        # Collect SSE output
        sse_lines = []
        async for sse in event_stream(queue, timeout_seconds=1.0):
            sse_lines.append(sse)

        assert len(sse_lines) >= 1
        assert any("event:" in line for line in sse_lines)

    @pytest.mark.asyncio
    async def test_json_event_stream(self) -> None:
        """Test JSON event stream generator."""
        emitter = EventEmitter()
        queue = await emitter.subscribe()

        # Emit events
        await emitter.emit(ProgressEvent(event_type=EventType.LOG, message="test"))
        await emitter.emit(ProgressEvent(event_type=EventType.EXECUTION_COMPLETED, message="done"))

        # Collect JSON output
        json_lines = []
        async for json_str in json_event_stream(queue, timeout_seconds=1.0):
            json_lines.append(json_str)

        assert len(json_lines) >= 1

        # Verify JSON is valid
        for line in json_lines:
            data = json.loads(line)
            assert "event" in data

    @pytest.mark.asyncio
    async def test_stream_completion_break(self) -> None:
        """Test that streams break on completion events."""
        emitter = EventEmitter()
        queue = await emitter.subscribe()

        # Emit completion event
        await emitter.emit(create_execution_completed_event(
            total_roles=1, successful=1, failed=0, duration_seconds=1.0
        ))

        # Stream should break after completion
        events = []
        async for sse in event_stream(queue, timeout_seconds=1.0):
            events.append(sse)

        # Should have received at least one event and then stopped
        assert len(events) >= 1

    @pytest.mark.asyncio
    async def test_stream_timeout_keepalive(self) -> None:
        """Test that stream sends keepalive on timeout."""
        emitter = EventEmitter()
        queue = await emitter.subscribe()

        keepalive_received = False

        async for line in event_stream(queue, timeout_seconds=0.1):
            if "keepalive" in line:
                keepalive_received = True

        # Should have received keepalive since no events were sent
        assert keepalive_received
