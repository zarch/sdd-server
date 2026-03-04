"""Task breakdown manager for SDD — reads tasks from tasks.md spec files.

State of truth is always tasks.md (git-tracked). This manager is read-only:
mutations are performed by writing to tasks.md via sdd_spec_write.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sdd_server.infrastructure.filesystem import FileSystemClient
from sdd_server.models.task import (
    Task,
    TaskBreakdown,
    TaskPriority,
    TaskStatus,
    parse_tasks_from_markdown,
    serialize_tasks_to_markdown,
)
from sdd_server.utils.logging import get_logger
from sdd_server.utils.paths import SpecsPaths

logger = get_logger(__name__)


class TaskBreakdownManager:
    """Reads task breakdowns from tasks.md spec files.

    Tasks are stored exclusively in tasks.md (the git-tracked spec file).
    This manager parses them on demand — there is no internal database.

    Mutations (add, update, remove) are intentionally not supported here;
    use the sdd_spec_write MCP tool to modify tasks.md directly.
    """

    def __init__(self, project_root: Path, specs_dir: str = "specs") -> None:
        """Initialize the task breakdown manager.

        Args:
            project_root: Root directory of the project.
            specs_dir: Name of the specs directory (default: "specs").
        """
        self.project_root = project_root.resolve()
        self._fs = FileSystemClient(self.project_root)
        self._paths = SpecsPaths(self.project_root, specs_dir)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_tasks_md_path(self, feature: str | None) -> Path:
        """Return the path to the tasks.md file for a feature or root."""
        if feature:
            return self._paths.feature_dir(feature) / "tasks.md"
        return self._paths.specs_dir / "tasks.md"

    # ------------------------------------------------------------------
    # Public API — read operations
    # ------------------------------------------------------------------

    def get_breakdown(self, feature: str | None = None) -> TaskBreakdown:
        """Parse and return a TaskBreakdown from the relevant tasks.md.

        Args:
            feature: Feature name, or None for the project-level tasks.md.

        Returns:
            TaskBreakdown populated from tasks.md (empty if file absent).
        """
        path = self._get_tasks_md_path(feature)
        if not self._fs.file_exists(path):
            return TaskBreakdown(feature=feature)

        content = self._fs.read_file(path)
        tasks = parse_tasks_from_markdown(content, feature=feature)

        breakdown = TaskBreakdown(feature=feature)
        for task in tasks:
            breakdown.add_task(task)

        logger.debug(
            "parsed_tasks_from_spec",
            feature=feature,
            count=len(tasks),
        )
        return breakdown

    def get_task(self, task_id: str, feature: str | None = None) -> Task | None:
        """Get a single task by ID from the relevant tasks.md.

        Args:
            task_id: Task ID.
            feature: Feature to search in, or None for project-level.

        Returns:
            Task or None if not found.
        """
        return self.get_breakdown(feature).get_task(task_id)

    def find_task(self, task_id: str) -> tuple[Task, str | None] | None:
        """Search for a task across all features and the root tasks.md.

        Args:
            task_id: Task ID to find.

        Returns:
            (Task, feature_name) tuple or None if not found.
        """
        # Check root
        task = self.get_task(task_id, feature=None)
        if task:
            return (task, None)

        # Check all features
        if self._fs.directory_exists(self._paths.specs_dir):
            for item in self._fs.list_directory(self._paths.specs_dir):
                if item.is_dir() and not item.name.startswith("."):
                    task = self.get_task(task_id, feature=item.name)
                    if task:
                        return (task, item.name)
        return None

    def list_tasks(
        self,
        feature: str | None = None,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        tag: str | None = None,
    ) -> list[Task]:
        """List tasks from tasks.md with optional filters.

        Args:
            feature: Feature to list from, or None for root tasks.md.
            status: Filter by status.
            priority: Filter by priority.
            tag: Filter by tag.

        Returns:
            List of matching tasks.
        """
        tasks = list(self.get_breakdown(feature).tasks.values())

        if status is not None:
            tasks = [t for t in tasks if t.status == status]
        if priority is not None:
            tasks = [t for t in tasks if t.priority == priority]
        if tag is not None:
            tasks = [t for t in tasks if tag in t.tags]

        return tasks

    def get_next_ready_tasks(self, feature: str | None = None) -> list[Task]:
        """Return tasks that are pending and have all dependencies met.

        Args:
            feature: Feature to check, or None for root.

        Returns:
            List of ready tasks.
        """
        return self.get_breakdown(feature).get_next_ready_tasks()

    def get_task_dependencies(self, task_id: str, feature: str | None = None) -> list[Task]:
        """Return dependency tasks for a given task.

        Args:
            task_id: Task ID.
            feature: Feature the task belongs to.

        Returns:
            List of dependency Task objects.
        """
        breakdown = self.get_breakdown(feature)
        task = breakdown.get_task(task_id)
        if task is None:
            return []
        return [breakdown.tasks[dep] for dep in task.dependencies if dep in breakdown.tasks]

    def get_pending_dependencies(self, task_id: str, feature: str | None = None) -> list[str]:
        """Return IDs of dependencies that are not yet complete.

        Args:
            task_id: Task ID.
            feature: Feature the task belongs to.

        Returns:
            List of pending dependency IDs.
        """
        return self.get_breakdown(feature).get_pending_dependencies(task_id)

    # ------------------------------------------------------------------
    # Public API — statistics
    # ------------------------------------------------------------------

    def get_progress(self, feature: str | None = None) -> dict[str, Any]:
        """Return progress statistics for a breakdown.

        Args:
            feature: Feature to report on.

        Returns:
            Dict with total, complete, percentage, and per-status counts.
        """
        breakdown = self.get_breakdown(feature)
        summary = breakdown.get_summary()
        total = len(breakdown.tasks)
        complete = summary.get(TaskStatus.COMPLETE.value, 0)

        return {
            "feature": feature,
            "total": total,
            "complete": complete,
            "in_progress": summary.get(TaskStatus.IN_PROGRESS.value, 0),
            "pending": summary.get(TaskStatus.PENDING.value, 0),
            "blocked": summary.get(TaskStatus.BLOCKED.value, 0),
            "cancelled": summary.get(TaskStatus.CANCELLED.value, 0),
            "percentage": breakdown.get_completion_percentage(),
            "summary": summary,
        }

    def get_all_progress(self) -> dict[str | None, dict[str, Any]]:
        """Return progress for root tasks.md and all feature tasks.md files.

        Returns:
            Dict mapping feature name (None = root) to progress stats.
        """
        results: dict[str | None, dict[str, Any]] = {}
        results[None] = self.get_progress(None)

        if self._fs.directory_exists(self._paths.specs_dir):
            for item in self._fs.list_directory(self._paths.specs_dir):
                if item.is_dir() and not item.name.startswith("."):
                    feature = item.name
                    feature_tasks_path = self._get_tasks_md_path(feature)
                    if self._fs.file_exists(feature_tasks_path):
                        results[feature] = self.get_progress(feature)

        return results

    def export_to_markdown(self, feature: str | None = None) -> str:
        """Export the current task breakdown as a markdown checkbox list.

        Args:
            feature: Feature to export, or None for root.

        Returns:
            Markdown-formatted task list.
        """
        breakdown = self.get_breakdown(feature)
        tasks = sorted(
            breakdown.tasks.values(),
            key=lambda t: t.created_at or datetime.min.replace(tzinfo=UTC),
        )
        return serialize_tasks_to_markdown(list(tasks))

    # ------------------------------------------------------------------
    # Compatibility stub (previously synced from spec; now a no-op)
    # ------------------------------------------------------------------

    def sync_all_specs(self) -> dict[str | None, int]:
        """No-op — tasks are always read directly from tasks.md.

        Retained for API compatibility. Returns an empty dict.
        """
        return {}
