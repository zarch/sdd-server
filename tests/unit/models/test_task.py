"""Tests for task models."""

from __future__ import annotations

from datetime import UTC, datetime

from sdd_server.models.task import (
    Task,
    TaskBreakdown,
    TaskPriority,
    TaskStatus,
    generate_task_id,
    parse_tasks_from_markdown,
    serialize_tasks_to_markdown,
)


class TestTaskStatus:
    """Tests for TaskStatus enum."""

    def test_status_values(self) -> None:
        """Test status enum values."""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.IN_PROGRESS.value == "in_progress"
        assert TaskStatus.COMPLETE.value == "complete"
        assert TaskStatus.BLOCKED.value == "blocked"
        assert TaskStatus.CANCELLED.value == "cancelled"

    def test_status_count(self) -> None:
        """Test we have all expected statuses."""
        assert len(TaskStatus) == 5


class TestTaskPriority:
    """Tests for TaskPriority enum."""

    def test_priority_values(self) -> None:
        """Test priority enum values."""
        assert TaskPriority.LOW.value == "low"
        assert TaskPriority.MEDIUM.value == "medium"
        assert TaskPriority.HIGH.value == "high"
        assert TaskPriority.CRITICAL.value == "critical"

    def test_priority_count(self) -> None:
        """Test we have all expected priorities."""
        assert len(TaskPriority) == 4


class TestGenerateTaskId:
    """Tests for generate_task_id function."""

    def test_generates_unique_ids(self) -> None:
        """Test that generated IDs are unique."""
        ids = {generate_task_id() for _ in range(100)}
        assert len(ids) == 100

    def test_id_format(self) -> None:
        """Test ID format is t + 7 hex chars."""
        task_id = generate_task_id()
        assert task_id.startswith("t")
        assert len(task_id) == 8  # 't' + 7 chars
        hex_part = task_id[1:]
        assert all(c in "0123456789abcdef" for c in hex_part)


class TestTask:
    """Tests for Task model."""

    def test_create_task_minimal(self) -> None:
        """Test creating a task with minimal fields."""
        task = Task(id="t1234567", title="Test task")
        assert task.id == "t1234567"
        assert task.title == "Test task"
        assert task.status == TaskStatus.PENDING
        assert task.priority == TaskPriority.MEDIUM

    def test_create_task_full(self) -> None:
        """Test creating a task with all fields."""
        now = datetime.now(UTC)
        task = Task(
            id="tabc1234",
            title="Full task",
            description="A complete task",
            status=TaskStatus.IN_PROGRESS,
            priority=TaskPriority.HIGH,
            role="architect",
            feature="auth",
            dependencies=["tdep001"],
            tags=["security"],
            created_at=now,
            updated_at=now,
        )
        assert task.role == "architect"
        assert task.feature == "auth"

    def test_mark_in_progress(self) -> None:
        """Test marking task as in progress."""
        task = Task(id="t001", title="Test")
        task.mark_in_progress()
        assert task.status == TaskStatus.IN_PROGRESS

    def test_mark_complete(self) -> None:
        """Test marking task as complete."""
        task = Task(id="t001", title="Test")
        task.mark_complete()
        assert task.status == TaskStatus.COMPLETE
        assert task.completed_at is not None

    def test_mark_blocked(self) -> None:
        """Test marking task as blocked."""
        task = Task(id="t001", title="Test")
        task.mark_blocked("Waiting for API")
        assert task.status == TaskStatus.BLOCKED
        assert task.metadata["block_reason"] == "Waiting for API"

    def test_cancel(self) -> None:
        """Test canceling a task."""
        task = Task(id="t001", title="Test")
        task.cancel("No longer needed")
        assert task.status == TaskStatus.CANCELLED

    def test_is_done(self) -> None:
        """Test is_done check."""
        task = Task(id="t001", title="Test")
        assert not task.is_done()
        task.mark_complete()
        assert task.is_done()


class TestTaskBreakdown:
    """Tests for TaskBreakdown model."""

    def test_create_breakdown(self) -> None:
        """Test creating a breakdown."""
        breakdown = TaskBreakdown(feature="auth")
        assert breakdown.feature == "auth"
        assert breakdown.tasks == {}

    def test_add_task(self) -> None:
        """Test adding tasks."""
        breakdown = TaskBreakdown()
        task = Task(id="t001", title="Task 1")
        breakdown.add_task(task)
        assert len(breakdown.tasks) == 1

    def test_remove_task(self) -> None:
        """Test removing tasks."""
        breakdown = TaskBreakdown()
        task = Task(id="t001", title="Task 1")
        breakdown.add_task(task)
        assert breakdown.remove_task("t001") is True
        assert breakdown.remove_task("nonexistent") is False

    def test_get_pending_dependencies(self) -> None:
        """Test getting pending dependencies."""
        breakdown = TaskBreakdown()
        t1 = Task(id="t001", title="1")
        t2 = Task(id="t002", title="2", dependencies=["t001"])
        breakdown.add_task(t1)
        breakdown.add_task(t2)
        assert breakdown.get_pending_dependencies("t002") == ["t001"]

    def test_can_start(self) -> None:
        """Test can_start check."""
        breakdown = TaskBreakdown()
        t1 = Task(id="t001", title="1")
        t2 = Task(id="t002", title="2", dependencies=["t001"])
        breakdown.add_task(t1)
        breakdown.add_task(t2)
        assert breakdown.can_start("t001") is True
        assert breakdown.can_start("t002") is False

    def test_get_completion_percentage(self) -> None:
        """Test completion percentage."""
        breakdown = TaskBreakdown()
        t1 = Task(id="t001", title="1")
        t1.mark_complete()
        t2 = Task(id="t002", title="2")
        breakdown.add_task(t1)
        breakdown.add_task(t2)
        assert breakdown.get_completion_percentage() == 50.0

    def test_get_summary(self) -> None:
        """Test getting summary."""
        breakdown = TaskBreakdown()
        t1 = Task(id="t001", title="1", status=TaskStatus.PENDING)
        t2 = Task(id="t002", title="2", status=TaskStatus.COMPLETE)
        breakdown.add_task(t1)
        breakdown.add_task(t2)
        summary = breakdown.get_summary()
        assert summary["pending"] == 1
        assert summary["complete"] == 1

    def test_get_next_ready_tasks(self) -> None:
        """Test getting ready tasks."""
        breakdown = TaskBreakdown()
        t1 = Task(id="t001", title="1")
        t2 = Task(id="t002", title="2", dependencies=["t001"])
        breakdown.add_task(t1)
        breakdown.add_task(t2)
        ready = breakdown.get_next_ready_tasks()
        assert len(ready) == 1
        assert ready[0].id == "t001"


class TestParseTasksFromMarkdown:
    """Tests for parse_tasks_from_markdown function."""

    def test_parse_pending_tasks(self) -> None:
        """Test parsing pending tasks."""
        content = "- [ ] Task one\n- [ ] Task two"
        tasks = parse_tasks_from_markdown(content)
        assert len(tasks) == 2
        assert all(t.status == TaskStatus.PENDING for t in tasks)

    def test_parse_complete_tasks(self) -> None:
        """Test parsing complete tasks."""
        content = "- [x] Done task 1\n- [x] Done task 2"
        tasks = parse_tasks_from_markdown(content)
        assert len(tasks) == 2
        assert all(t.status == TaskStatus.COMPLETE for t in tasks)

    def test_parse_with_ids(self) -> None:
        """Test parsing tasks with existing IDs."""
        content = "- [ ] Task one #t1234567"
        tasks = parse_tasks_from_markdown(content)
        assert len(tasks) == 1
        assert tasks[0].id == "t1234567"

    def test_parse_generates_ids(self) -> None:
        """Test that parsing generates IDs."""
        content = "- [ ] Task without ID"
        tasks = parse_tasks_from_markdown(content)
        assert len(tasks) == 1
        assert tasks[0].id.startswith("t")
        assert len(tasks[0].id) == 8

    def test_parse_empty_content(self) -> None:
        """Test parsing empty content."""
        tasks = parse_tasks_from_markdown("")
        assert tasks == []


class TestSerializeTasksToMarkdown:
    """Tests for serialize_tasks_to_markdown function."""

    def test_serialize_pending_tasks(self) -> None:
        """Test serializing pending tasks."""
        tasks = [Task(id="t001", title="Task 1", status=TaskStatus.PENDING)]
        result = serialize_tasks_to_markdown(tasks)
        assert "- [ ] Task 1 #t001" in result

    def test_serialize_complete_tasks(self) -> None:
        """Test serializing complete tasks."""
        tasks = [Task(id="t001", title="Done", status=TaskStatus.COMPLETE)]
        result = serialize_tasks_to_markdown(tasks)
        assert "- [x] Done #t001" in result

    def test_serialize_empty_list(self) -> None:
        """Test serializing empty list."""
        result = serialize_tasks_to_markdown([])
        assert result == ""

    def test_roundtrip(self) -> None:
        """Test roundtrip parse/serialize."""
        original = "- [ ] Test task #t1234567\n- [x] Done task #t7654321"
        tasks = parse_tasks_from_markdown(original)
        result = serialize_tasks_to_markdown(tasks)
        assert result == original
