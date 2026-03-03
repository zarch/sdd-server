"""Tests for TaskBreakdownManager."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Generator

import pytest

from sdd_server.core.task_manager import TaskBreakdownManager
from sdd_server.models.task import Task, TaskBreakdown, TaskPriority, TaskStatus


@pytest.fixture
def temp_project(tmp_path: Path) -> Path:
    """Create a temporary project directory."""
    project = tmp_path / "project"
    project.mkdir()
    (project / "specs").mkdir()
    (project / "specs" / "features").mkdir()
    return project


@pytest.fixture
def manager(temp_project: Path) -> Generator[TaskBreakdownManager, None, None]:
    """Create a TaskBreakdownManager instance."""
    mgr = TaskBreakdownManager(temp_project)
    yield mgr


class TestTaskBreakdownManagerInit:
    """Tests for TaskBreakdownManager initialization."""

    def test_init_creates_paths(self, temp_project: Path) -> None:
        """Test that manager initializes paths correctly."""
        mgr = TaskBreakdownManager(temp_project)

        assert mgr.project_root == temp_project.resolve()
        assert mgr._breakdown_path == temp_project / ".sdd" / "tasks.json"

    def test_lazy_loading(self, manager: TaskBreakdownManager) -> None:
        """Test that breakdowns are loaded lazily."""
        assert not manager._loaded
        manager._load_breakdowns()
        assert manager._loaded


class TestBreakdownCRUD:
    """Tests for breakdown CRUD operations."""

    def test_create_breakdown(self, manager: TaskBreakdownManager) -> None:
        """Test creating a breakdown."""
        breakdown = manager.create_breakdown("auth")

        assert breakdown is not None
        assert breakdown.feature == "auth"
        assert breakdown.tasks == {}

    def test_create_project_breakdown(self, manager: TaskBreakdownManager) -> None:
        """Test creating a project-level breakdown."""
        breakdown = manager.create_breakdown(None)

        assert breakdown is not None
        assert breakdown.feature is None

    def test_create_duplicate_breakdown(self, manager: TaskBreakdownManager) -> None:
        """Test that creating duplicate breakdown raises error."""
        manager.create_breakdown("auth")

        with pytest.raises(ValueError, match="already exists"):
            manager.create_breakdown("auth")

    def test_get_breakdown(self, manager: TaskBreakdownManager) -> None:
        """Test getting a breakdown."""
        created = manager.create_breakdown("auth")
        retrieved = manager.get_breakdown("auth")

        assert retrieved is not None
        assert retrieved.feature == "auth"

    def test_get_breakdown_not_found(self, manager: TaskBreakdownManager) -> None:
        """Test getting non-existent breakdown."""
        result = manager.get_breakdown("nonexistent")

        assert result is None

    def test_get_or_create_breakdown(self, manager: TaskBreakdownManager) -> None:
        """Test get_or_create creates if needed."""
        breakdown1 = manager.get_or_create_breakdown("auth")
        assert breakdown1.feature == "auth"

        breakdown2 = manager.get_or_create_breakdown("auth")
        assert breakdown2 is breakdown1

    def test_delete_breakdown(self, manager: TaskBreakdownManager) -> None:
        """Test deleting a breakdown."""
        manager.create_breakdown("auth")

        result = manager.delete_breakdown("auth")

        assert result is True
        assert manager.get_breakdown("auth") is None

    def test_delete_breakdown_not_found(self, manager: TaskBreakdownManager) -> None:
        """Test deleting non-existent breakdown."""
        result = manager.delete_breakdown("nonexistent")

        assert result is False


class TestTaskOperations:
    """Tests for task operations."""

    def test_add_task(self, manager: TaskBreakdownManager) -> None:
        """Test adding a task."""
        task = manager.add_task(
            title="Implement login",
            feature="auth",
            priority=TaskPriority.HIGH,
        )

        assert task.id.startswith("t")
        assert task.title == "Implement login"
        assert task.priority == TaskPriority.HIGH

        breakdown = manager.get_breakdown("auth")
        assert breakdown is not None
        assert task.id in breakdown.tasks

    def test_add_task_with_dependencies(self, manager: TaskBreakdownManager) -> None:
        """Test adding task with dependencies."""
        t1 = manager.add_task(title="Task 1", feature="auth")
        t2 = manager.add_task(
            title="Task 2",
            feature="auth",
            dependencies=[t1.id],
        )

        assert t2.dependencies == [t1.id]

    def test_get_task(self, manager: TaskBreakdownManager) -> None:
        """Test getting a task."""
        created = manager.add_task(title="Test task", feature="auth")

        retrieved = manager.get_task(created.id, feature="auth")

        assert retrieved is not None
        assert retrieved.id == created.id

    def test_get_task_not_found(self, manager: TaskBreakdownManager) -> None:
        """Test getting non-existent task."""
        result = manager.get_task("nonexistent", feature="auth")

        assert result is None

    def test_find_task(self, manager: TaskBreakdownManager) -> None:
        """Test finding task across all breakdowns."""
        t1 = manager.add_task(title="Task 1", feature="auth")
        t2 = manager.add_task(title="Task 2", feature=None)

        result1 = manager.find_task(t1.id)
        result2 = manager.find_task(t2.id)

        assert result1 is not None
        assert result1[0].id == t1.id
        assert result1[1] == "auth"

        assert result2 is not None
        assert result2[0].id == t2.id
        assert result2[1] is None

    def test_find_task_not_found(self, manager: TaskBreakdownManager) -> None:
        """Test finding non-existent task."""
        result = manager.find_task("nonexistent")

        assert result is None

    def test_update_task(self, manager: TaskBreakdownManager) -> None:
        """Test updating a task."""
        task = manager.add_task(title="Original", feature="auth")

        updated = manager.update_task(
            task.id,
            feature="auth",
            title="Updated",
            priority=TaskPriority.CRITICAL,
        )

        assert updated is not None
        assert updated.title == "Updated"
        assert updated.priority == TaskPriority.CRITICAL

    def test_update_task_not_found(self, manager: TaskBreakdownManager) -> None:
        """Test updating non-existent task."""
        result = manager.update_task("nonexistent", feature="auth", title="New")

        assert result is None

    def test_set_task_status_complete(self, manager: TaskBreakdownManager) -> None:
        """Test setting task status to complete."""
        task = manager.add_task(title="Test", feature="auth")

        updated = manager.set_task_status(task.id, TaskStatus.COMPLETE, feature="auth")

        assert updated is not None
        assert updated.status == TaskStatus.COMPLETE
        assert updated.completed_at is not None

    def test_set_task_status_blocked(self, manager: TaskBreakdownManager) -> None:
        """Test setting task status to blocked."""
        task = manager.add_task(title="Test", feature="auth")

        updated = manager.set_task_status(
            task.id,
            TaskStatus.BLOCKED,
            feature="auth",
            reason="Waiting for API",
        )

        assert updated is not None
        assert updated.status == TaskStatus.BLOCKED
        assert updated.metadata.get("block_reason") == "Waiting for API"

    def test_remove_task(self, manager: TaskBreakdownManager) -> None:
        """Test removing a task."""
        task = manager.add_task(title="Test", feature="auth")

        result = manager.remove_task(task.id, feature="auth")

        assert result is True
        assert manager.get_task(task.id, feature="auth") is None

    def test_remove_task_not_found(self, manager: TaskBreakdownManager) -> None:
        """Test removing non-existent task."""
        result = manager.remove_task("nonexistent", feature="auth")

        assert result is False


class TestListTasks:
    """Tests for listing tasks."""

    def test_list_all_tasks(self, manager: TaskBreakdownManager) -> None:
        """Test listing all tasks in a breakdown."""
        manager.add_task(title="Task 1", feature="auth")
        manager.add_task(title="Task 2", feature="auth")
        manager.add_task(title="Task 3", feature="auth")

        tasks = manager.list_tasks(feature="auth")

        assert len(tasks) == 3

    def test_list_tasks_by_status(self, manager: TaskBreakdownManager) -> None:
        """Test filtering tasks by status."""
        t1 = manager.add_task(title="Task 1", feature="auth")
        manager.add_task(title="Task 2", feature="auth")
        manager.set_task_status(t1.id, TaskStatus.COMPLETE, feature="auth")

        pending = manager.list_tasks(feature="auth", status=TaskStatus.PENDING)
        complete = manager.list_tasks(feature="auth", status=TaskStatus.COMPLETE)

        assert len(pending) == 1
        assert len(complete) == 1

    def test_list_tasks_by_priority(self, manager: TaskBreakdownManager) -> None:
        """Test filtering tasks by priority."""
        manager.add_task(title="Low", feature="auth", priority=TaskPriority.LOW)
        manager.add_task(title="High", feature="auth", priority=TaskPriority.HIGH)

        high = manager.list_tasks(feature="auth", priority=TaskPriority.HIGH)

        assert len(high) == 1
        assert high[0].title == "High"

    def test_list_tasks_by_tag(self, manager: TaskBreakdownManager) -> None:
        """Test filtering tasks by tag."""
        manager.add_task(title="Tagged", feature="auth", tags=["security"])
        manager.add_task(title="Untagged", feature="auth", tags=["docs"])

        security = manager.list_tasks(feature="auth", tag="security")

        assert len(security) == 1
        assert security[0].title == "Tagged"

    def test_list_tasks_empty_breakdown(self, manager: TaskBreakdownManager) -> None:
        """Test listing tasks from non-existent breakdown."""
        tasks = manager.list_tasks(feature="nonexistent")

        assert tasks == []


class TestDependencies:
    """Tests for dependency management."""

    def test_get_task_dependencies(self, manager: TaskBreakdownManager) -> None:
        """Test getting task dependencies."""
        t1 = manager.add_task(title="Task 1", feature="auth")
        t2 = manager.add_task(title="Task 2", feature="auth")
        t3 = manager.add_task(
            title="Task 3",
            feature="auth",
            dependencies=[t1.id, t2.id],
        )

        deps = manager.get_task_dependencies(t3.id, feature="auth")

        assert len(deps) == 2
        dep_ids = {d.id for d in deps}
        assert t1.id in dep_ids
        assert t2.id in dep_ids

    def test_get_pending_dependencies(self, manager: TaskBreakdownManager) -> None:
        """Test getting pending dependencies."""
        t1 = manager.add_task(title="Task 1", feature="auth")
        t2 = manager.add_task(title="Task 2", feature="auth", dependencies=[t1.id])

        pending = manager.get_pending_dependencies(t2.id, feature="auth")

        assert pending == [t1.id]

        manager.set_task_status(t1.id, TaskStatus.COMPLETE, feature="auth")
        pending = manager.get_pending_dependencies(t2.id, feature="auth")

        assert pending == []

    def test_get_next_ready_tasks(self, manager: TaskBreakdownManager) -> None:
        """Test getting ready tasks."""
        t1 = manager.add_task(title="Task 1", feature="auth")
        t2 = manager.add_task(title="Task 2", feature="auth", dependencies=[t1.id])

        ready = manager.get_next_ready_tasks(feature="auth")

        assert len(ready) == 1
        assert ready[0].id == t1.id

        manager.set_task_status(t1.id, TaskStatus.COMPLETE, feature="auth")
        ready = manager.get_next_ready_tasks(feature="auth")

        assert len(ready) == 1
        assert ready[0].id == t2.id


class TestParsingAndSync:
    """Tests for parsing and syncing tasks.md files."""

    def test_parse_tasks_from_spec(self, manager: TaskBreakdownManager, temp_project: Path) -> None:
        """Test parsing tasks from a tasks.md file."""
        # feature_dir returns specs_dir / feature_name (not specs/features/feature_name)
        tasks_md = temp_project / "specs" / "auth" / "tasks.md"
        tasks_md.parent.mkdir(parents=True, exist_ok=True)
        tasks_md.write_text("- [ ] Implement login #t1000001\n- [x] Design API #t1000002\n- [ ] Write tests\n")

        tasks = manager.parse_tasks_from_spec("auth")

        assert len(tasks) == 3
        assert tasks[0].title == "Implement login"
        assert tasks[0].status == TaskStatus.PENDING
        assert tasks[1].status == TaskStatus.COMPLETE

    def test_parse_tasks_from_nonexistent_spec(self, manager: TaskBreakdownManager) -> None:
        """Test parsing from non-existent file."""
        tasks = manager.parse_tasks_from_spec("nonexistent")

        assert tasks == []

    def test_sync_from_spec(self, manager: TaskBreakdownManager, temp_project: Path) -> None:
        """Test syncing from tasks.md."""
        tasks_md = temp_project / "specs" / "auth" / "tasks.md"
        tasks_md.parent.mkdir(parents=True, exist_ok=True)
        tasks_md.write_text("- [ ] Task one #t2000001\n- [ ] Task two #t2000002\n")

        changes = manager.sync_from_spec("auth")

        assert changes == 2
        breakdown = manager.get_breakdown("auth")
        assert breakdown is not None
        assert len(breakdown.tasks) == 2

    def test_sync_from_spec_updates_status(self, manager: TaskBreakdownManager, temp_project: Path) -> None:
        """Test that sync updates existing task status."""
        tasks_md = temp_project / "specs" / "auth" / "tasks.md"
        tasks_md.parent.mkdir(parents=True, exist_ok=True)
        tasks_md.write_text("- [ ] Task one #t2000001")

        manager.sync_from_spec("auth")

        # Update the file to mark task complete
        tasks_md.write_text("- [x] Task one #t2000001")

        changes = manager.sync_from_spec("auth")

        assert changes == 1
        task = manager.get_task("t2000001", feature="auth")
        assert task is not None
        assert task.status == TaskStatus.COMPLETE

    def test_export_to_markdown(self, manager: TaskBreakdownManager) -> None:
        """Test exporting tasks to markdown."""
        manager.add_task(title="Task one", feature="auth")
        manager.add_task(title="Task two", feature="auth")

        result = manager.export_to_markdown("auth")

        assert "- [ ] Task one #" in result
        assert "- [ ] Task two #" in result


class TestProgress:
    """Tests for progress tracking."""

    def test_get_progress(self, manager: TaskBreakdownManager) -> None:
        """Test getting progress statistics."""
        t1 = manager.add_task(title="Task 1", feature="auth")
        manager.add_task(title="Task 2", feature="auth")
        manager.add_task(title="Task 3", feature="auth")
        manager.set_task_status(t1.id, TaskStatus.COMPLETE, feature="auth")

        progress = manager.get_progress("auth")

        assert progress["total"] == 3
        assert progress["complete"] == 1
        assert progress["pending"] == 2
        assert progress["percentage"] == pytest.approx(33.333, rel=0.01)

    def test_get_progress_empty(self, manager: TaskBreakdownManager) -> None:
        """Test progress for non-existent breakdown."""
        progress = manager.get_progress("nonexistent")

        assert progress["total"] == 0
        assert progress["percentage"] == 0.0

    def test_get_all_progress(self, manager: TaskBreakdownManager) -> None:
        """Test getting all progress."""
        manager.add_task(title="Task 1", feature="auth")
        manager.add_task(title="Task 2", feature=None)

        all_progress = manager.get_all_progress()

        assert "auth" in all_progress
        assert None in all_progress


class TestPersistence:
    """Tests for persistence."""

    def test_persists_breakdowns(self, manager: TaskBreakdownManager, temp_project: Path) -> None:
        """Test that breakdowns persist to disk."""
        manager.add_task(title="Test task", feature="auth")

        # Check file was created
        assert manager._breakdown_path.exists()

        # Check content
        content = manager._breakdown_path.read_text()
        data = json.loads(content)
        assert "auth" in data

    def test_loads_existing_breakdowns(self, temp_project: Path) -> None:
        """Test that existing breakdowns are loaded."""
        # Create data file manually
        sdd_dir = temp_project / ".sdd"
        sdd_dir.mkdir()
        tasks_file = sdd_dir / "tasks.json"

        breakdown = TaskBreakdown(feature="auth")
        data = {"auth": breakdown.model_dump()}
        tasks_file.write_text(json.dumps(data, default=str))

        manager = TaskBreakdownManager(temp_project)
        loaded = manager.get_breakdown("auth")

        assert loaded is not None
        assert loaded.feature == "auth"

    def test_survives_restart(self, temp_project: Path) -> None:
        """Test that data survives manager restart."""
        manager1 = TaskBreakdownManager(temp_project)
        task = manager1.add_task(title="Persistent task", feature="auth")

        # Create new manager
        manager2 = TaskBreakdownManager(temp_project)
        retrieved = manager2.get_task(task.id, feature="auth")

        assert retrieved is not None
        assert retrieved.title == "Persistent task"
