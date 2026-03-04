"""Tests for TaskBreakdownManager (read-only, tasks.md-based)."""

from __future__ import annotations

from pathlib import Path

import pytest

from sdd_server.core.task_manager import TaskBreakdownManager
from sdd_server.models.task import TaskStatus


@pytest.fixture
def temp_project(tmp_path: Path) -> Path:
    """Create a temporary project directory with a specs/ dir."""
    project = tmp_path / "project"
    project.mkdir()
    (project / "specs").mkdir()
    return project


@pytest.fixture
def manager(temp_project: Path) -> TaskBreakdownManager:
    """Create a TaskBreakdownManager instance."""
    return TaskBreakdownManager(temp_project)


def _write_tasks_md(directory: Path, content: str) -> None:
    """Helper: write tasks.md in the given directory."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "tasks.md").write_text(content)


class TestTaskBreakdownManagerInit:
    """Tests for TaskBreakdownManager initialization."""

    def test_init_sets_project_root(self, temp_project: Path) -> None:
        mgr = TaskBreakdownManager(temp_project)
        assert mgr.project_root == temp_project.resolve()

    def test_init_custom_specs_dir(self, temp_project: Path) -> None:
        mgr = TaskBreakdownManager(temp_project, specs_dir="custom-specs")
        assert mgr._paths.specs_dir == temp_project / "custom-specs"


class TestGetBreakdown:
    """Tests for get_breakdown — parses tasks.md on demand."""

    def test_returns_empty_when_no_file(self, manager: TaskBreakdownManager) -> None:
        breakdown = manager.get_breakdown("nonexistent")
        assert breakdown.feature == "nonexistent"
        assert breakdown.tasks == {}

    def test_returns_empty_root_when_no_file(self, manager: TaskBreakdownManager) -> None:
        breakdown = manager.get_breakdown(None)
        assert breakdown.feature is None
        assert breakdown.tasks == {}

    def test_parses_feature_tasks_md(
        self, manager: TaskBreakdownManager, temp_project: Path
    ) -> None:
        _write_tasks_md(
            temp_project / "specs" / "auth",
            "- [ ] Implement login #t1000001\n- [x] Design API #t1000002\n",
        )
        breakdown = manager.get_breakdown("auth")
        assert len(breakdown.tasks) == 2
        assert "t1000001" in breakdown.tasks
        assert "t1000002" in breakdown.tasks
        assert breakdown.tasks["t1000001"].status == TaskStatus.PENDING
        assert breakdown.tasks["t1000002"].status == TaskStatus.COMPLETE

    def test_parses_root_tasks_md(self, manager: TaskBreakdownManager, temp_project: Path) -> None:
        _write_tasks_md(
            temp_project / "specs",
            "- [ ] Root task #t9000001\n",
        )
        breakdown = manager.get_breakdown(None)
        assert len(breakdown.tasks) == 1
        assert "t9000001" in breakdown.tasks

    def test_reflects_file_changes(self, manager: TaskBreakdownManager, temp_project: Path) -> None:
        """get_breakdown parses fresh every call — always up-to-date."""
        tasks_md = temp_project / "specs" / "auth" / "tasks.md"
        tasks_md.parent.mkdir(parents=True, exist_ok=True)
        tasks_md.write_text("- [ ] First task #t1000001\n")

        assert len(manager.get_breakdown("auth").tasks) == 1

        tasks_md.write_text("- [ ] First task #t1000001\n- [ ] Second task #t1000002\n")

        assert len(manager.get_breakdown("auth").tasks) == 2


class TestGetTask:
    """Tests for get_task."""

    def test_returns_task_by_id(self, manager: TaskBreakdownManager, temp_project: Path) -> None:
        _write_tasks_md(
            temp_project / "specs" / "auth",
            "- [ ] Login flow #t1000001\n",
        )
        task = manager.get_task("t1000001", feature="auth")
        assert task is not None
        assert task.title == "Login flow"

    def test_returns_none_when_not_found(self, manager: TaskBreakdownManager) -> None:
        result = manager.get_task("nonexistent", feature="auth")
        assert result is None


class TestFindTask:
    """Tests for find_task — searches across all features."""

    def test_finds_in_feature(self, manager: TaskBreakdownManager, temp_project: Path) -> None:
        _write_tasks_md(
            temp_project / "specs" / "auth",
            "- [ ] Auth task #t2000001\n",
        )
        result = manager.find_task("t2000001")
        assert result is not None
        task, feature = result
        assert task.id == "t2000001"
        assert feature == "auth"

    def test_finds_in_root(self, manager: TaskBreakdownManager, temp_project: Path) -> None:
        _write_tasks_md(
            temp_project / "specs",
            "- [ ] Root task #t9000001\n",
        )
        result = manager.find_task("t9000001")
        assert result is not None
        task, feature = result
        assert task.id == "t9000001"
        assert feature is None

    def test_returns_none_when_not_found(self, manager: TaskBreakdownManager) -> None:
        result = manager.find_task("nonexistent")
        assert result is None


class TestListTasks:
    """Tests for list_tasks with filters."""

    def test_lists_all_tasks(self, manager: TaskBreakdownManager, temp_project: Path) -> None:
        _write_tasks_md(
            temp_project / "specs" / "auth",
            "- [ ] Task 1 #t1000001\n- [ ] Task 2 #t1000002\n- [x] Task 3 #t1000003\n",
        )
        tasks = manager.list_tasks(feature="auth")
        assert len(tasks) == 3

    def test_filter_by_status_pending(
        self, manager: TaskBreakdownManager, temp_project: Path
    ) -> None:
        _write_tasks_md(
            temp_project / "specs" / "auth",
            "- [ ] Pending #t1000001\n- [x] Done #t1000002\n",
        )
        pending = manager.list_tasks(feature="auth", status=TaskStatus.PENDING)
        complete = manager.list_tasks(feature="auth", status=TaskStatus.COMPLETE)
        assert len(pending) == 1
        assert len(complete) == 1

    def test_empty_for_missing_feature(self, manager: TaskBreakdownManager) -> None:
        tasks = manager.list_tasks(feature="nonexistent")
        assert tasks == []


class TestDependencies:
    """Tests for dependency queries (backed by tasks.md parsed data)."""

    def test_get_task_dependencies(self, manager: TaskBreakdownManager, temp_project: Path) -> None:
        _write_tasks_md(
            temp_project / "specs" / "auth",
            "- [ ] Base task #t1000001\n- [ ] Dependent task #t1000002\n",
        )
        # Parse tasks and manually wire dependencies via the model
        breakdown = manager.get_breakdown("auth")
        breakdown.tasks["t1000002"].dependencies = ["t1000001"]

        deps = [
            breakdown.tasks[d]
            for d in breakdown.tasks["t1000002"].dependencies
            if d in breakdown.tasks
        ]
        assert len(deps) == 1
        assert deps[0].id == "t1000001"

    def test_get_pending_dependencies(
        self, manager: TaskBreakdownManager, temp_project: Path
    ) -> None:
        """Demonstrates pending dependency check on a parsed breakdown."""
        _write_tasks_md(
            temp_project / "specs" / "auth",
            "- [ ] Task 1 #t1000001\n- [ ] Task 2 #t1000002\n",
        )
        breakdown = manager.get_breakdown("auth")
        breakdown.tasks["t1000002"].dependencies = ["t1000001"]

        pending = breakdown.get_pending_dependencies("t1000002")
        assert "t1000001" in pending

    def test_get_next_ready_tasks(self, manager: TaskBreakdownManager, temp_project: Path) -> None:
        _write_tasks_md(
            temp_project / "specs" / "auth",
            "- [ ] Task 1 #t1000001\n- [ ] Task 2 #t1000002\n",
        )
        ready = manager.get_next_ready_tasks("auth")
        # Both pending tasks with no deps are ready
        assert len(ready) == 2


class TestProgress:
    """Tests for progress statistics."""

    def test_get_progress_empty(self, manager: TaskBreakdownManager) -> None:
        progress = manager.get_progress("nonexistent")
        assert progress["total"] == 0
        assert progress["percentage"] == 0.0

    def test_get_progress(self, manager: TaskBreakdownManager, temp_project: Path) -> None:
        _write_tasks_md(
            temp_project / "specs" / "auth",
            "- [ ] Task 1 #t1000001\n- [ ] Task 2 #t1000002\n- [x] Task 3 #t1000003\n",
        )
        progress = manager.get_progress("auth")
        assert progress["total"] == 3
        assert progress["complete"] == 1
        assert progress["pending"] == 2
        assert progress["percentage"] == pytest.approx(33.333, rel=0.01)

    def test_get_all_progress_includes_root(
        self, manager: TaskBreakdownManager, temp_project: Path
    ) -> None:
        _write_tasks_md(temp_project / "specs", "- [ ] Root task #t9000001\n")
        _write_tasks_md(temp_project / "specs" / "auth", "- [x] Auth task #t1000001\n")

        all_progress = manager.get_all_progress()
        assert None in all_progress
        assert "auth" in all_progress

    def test_get_all_progress_no_files(self, manager: TaskBreakdownManager) -> None:
        all_progress = manager.get_all_progress()
        assert None in all_progress
        assert all_progress[None]["total"] == 0


class TestExportToMarkdown:
    """Tests for export_to_markdown."""

    def test_export_empty_breakdown(self, manager: TaskBreakdownManager) -> None:
        result = manager.export_to_markdown("nonexistent")
        assert result == ""

    def test_export_with_tasks(self, manager: TaskBreakdownManager, temp_project: Path) -> None:
        _write_tasks_md(
            temp_project / "specs" / "auth",
            "- [ ] Task one #t1000001\n- [x] Task two #t1000002\n",
        )
        result = manager.export_to_markdown("auth")
        assert "Task one" in result
        assert "Task two" in result
        assert "- [ ]" in result
        assert "- [x]" in result


class TestSyncAllSpecsNoOp:
    """sync_all_specs is a compatibility no-op."""

    def test_returns_empty_dict(self, manager: TaskBreakdownManager) -> None:
        result = manager.sync_all_specs()
        assert result == {}
