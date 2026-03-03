"""Task breakdown manager for SDD."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sdd_server.infrastructure.filesystem import FileSystemClient
from sdd_server.models.spec import SpecType
from sdd_server.models.task import (
    Task,
    TaskBreakdown,
    TaskPriority,
    TaskStatus,
    generate_task_id,
    parse_tasks_from_markdown,
    serialize_tasks_to_markdown,
)
from sdd_server.utils.logging import get_logger
from sdd_server.utils.paths import SpecsPaths

logger = get_logger(__name__)

# Storage path for task breakdowns
TASK_BREAKDOWN_FILE = ".sdd/tasks.json"


class TaskBreakdownManager:
    """Manages task breakdowns for features and projects.

    This class provides:
    - Task parsing from tasks.md spec files
    - Task CRUD operations
    - Dependency tracking
    - Progress tracking
    - Persistence to .sdd/tasks.json
    """

    def __init__(self, project_root: Path) -> None:
        """Initialize the task breakdown manager.

        Args:
            project_root: Root directory of the project.
        """
        self.project_root = project_root.resolve()
        self._fs = FileSystemClient(self.project_root)
        self._paths = SpecsPaths(self.project_root, "specs")
        self._breakdown_path = self.project_root / TASK_BREAKDOWN_FILE
        self._breakdowns: dict[str, TaskBreakdown] = {}
        self._loaded = False

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _ensure_data_dir(self) -> None:
        """Ensure the data directory exists."""
        data_dir = self._breakdown_path.parent
        if not self._fs.directory_exists(data_dir):
            self._fs.ensure_directory(data_dir)

    def _load_breakdowns(self) -> dict[str, TaskBreakdown]:
        """Load all breakdowns from disk."""
        if self._loaded:
            return self._breakdowns

        if self._fs.file_exists(self._breakdown_path):
            try:
                content = self._fs.read_file(self._breakdown_path)
                data = __import__("json").loads(content)
                for feature, bd_data in data.items():
                    self._breakdowns[feature] = TaskBreakdown.model_validate(bd_data)
                logger.debug(
                    "Loaded task breakdowns",
                    breakdown_count=len(self._breakdowns),
                )
            except Exception as exc:
                logger.warning(
                    "Failed to load task breakdowns",
                    error=str(exc),
                )

        self._loaded = True
        return self._breakdowns

    def _save_breakdowns(self) -> None:
        """Save all breakdowns to disk."""
        self._ensure_data_dir()
        data = {f: bd.model_dump() for f, bd in self._breakdowns.items()}
        content = __import__("json").dumps(data, indent=2, default=str)
        self._fs.write_file(self._breakdown_path, content)
        logger.debug("Saved task breakdowns")

    def _get_tasks_md_path(self, feature: str | None) -> Path:
        """Get the path to a tasks.md file."""
        if feature:
            return self._paths.feature_dir(feature) / "tasks.md"
        return self._paths.specs_dir / "tasks.md"

    # ------------------------------------------------------------------
    # Public API - Breakdown management
    # ------------------------------------------------------------------

    def create_breakdown(self, feature: str | None = None) -> TaskBreakdown:
        """Create a new task breakdown.

        Args:
            feature: Feature name, or None for project-level breakdown.

        Returns:
            The created TaskBreakdown.
        """
        breakdowns = self._load_breakdowns()
        key = feature or "__project__"

        if key in breakdowns:
            raise ValueError(f"Breakdown for '{feature or 'project'}' already exists")

        breakdown = TaskBreakdown(feature=feature)
        breakdowns[key] = breakdown
        self._save_breakdowns()

        logger.info("Created task breakdown", feature=feature)
        return breakdown

    def get_breakdown(self, feature: str | None = None) -> TaskBreakdown | None:
        """Get a task breakdown.

        Args:
            feature: Feature name, or None for project-level breakdown.

        Returns:
            TaskBreakdown or None if not found.
        """
        breakdowns = self._load_breakdowns()
        key = feature or "__project__"
        return breakdowns.get(key)

    def get_or_create_breakdown(self, feature: str | None = None) -> TaskBreakdown:
        """Get or create a task breakdown.

        Args:
            feature: Feature name, or None for project-level breakdown.

        Returns:
            TaskBreakdown.
        """
        breakdown = self.get_breakdown(feature)
        if breakdown is None:
            breakdown = self.create_breakdown(feature)
        return breakdown

    def delete_breakdown(self, feature: str | None = None) -> bool:
        """Delete a task breakdown.

        Args:
            feature: Feature name, or None for project-level breakdown.

        Returns:
            True if deleted, False if not found.
        """
        breakdowns = self._load_breakdowns()
        key = feature or "__project__"
        if key in breakdowns:
            del breakdowns[key]
            self._save_breakdowns()
            logger.info("Deleted task breakdown", feature=feature)
            return True
        return False

    # ------------------------------------------------------------------
    # Public API - Task operations
    # ------------------------------------------------------------------

    def add_task(
        self,
        title: str,
        description: str = "",
        feature: str | None = None,
        priority: TaskPriority = TaskPriority.MEDIUM,
        role: str | None = None,
        dependencies: list[str] | None = None,
        tags: list[str] | None = None,
        ai_prompt: str | None = None,
    ) -> Task:
        """Add a new task to a breakdown.

        Args:
            title: Task title.
            description: Task description.
            feature: Feature to add task to.
            priority: Task priority.
            role: Associated role.
            dependencies: List of task IDs this task depends on.
            tags: List of tags.
            ai_prompt: AI prompt for task execution.

        Returns:
            The created Task.
        """
        breakdown = self.get_or_create_breakdown(feature)

        task = Task(
            id=generate_task_id(),
            title=title,
            description=description,
            priority=priority,
            role=role,
            feature=feature,
            dependencies=dependencies or [],
            tags=tags or [],
            ai_prompt=ai_prompt,
        )

        breakdown.add_task(task)
        self._save_breakdowns()

        logger.info("Added task", task_id=task.id, feature=feature)
        return task

    def get_task(self, task_id: str, feature: str | None = None) -> Task | None:
        """Get a task by ID.

        Args:
            task_id: Task ID.
            feature: Feature to search in, or None for project-level.

        Returns:
            Task or None if not found.
        """
        breakdown = self.get_breakdown(feature)
        if breakdown is None:
            return None
        return breakdown.get_task(task_id)

    def find_task(self, task_id: str) -> tuple[Task, str | None] | None:
        """Find a task across all breakdowns.

        Args:
            task_id: Task ID to find.

        Returns:
            Tuple of (Task, feature) or None if not found.
        """
        breakdowns = self._load_breakdowns()
        for key, breakdown in breakdowns.items():
            task = breakdown.get_task(task_id)
            if task:
                feature = None if key == "__project__" else key
                return (task, feature)
        return None

    def update_task(
        self,
        task_id: str,
        feature: str | None = None,
        **updates: Any,
    ) -> Task | None:
        """Update a task.

        Args:
            task_id: Task ID.
            feature: Feature the task belongs to.
            **updates: Fields to update.

        Returns:
            Updated Task or None if not found.
        """
        breakdown = self.get_breakdown(feature)
        if breakdown is None:
            return None

        task = breakdown.get_task(task_id)
        if task is None:
            return None

        # Update allowed fields
        for field in ("title", "description", "priority", "role", "dependencies", "tags", "ai_prompt", "metadata"):
            if field in updates:
                setattr(task, field, updates[field])

        task.updated_at = __import__("datetime").datetime.now(__import__("datetime").UTC)
        self._save_breakdowns()

        logger.debug("Updated task", task_id=task_id)
        return task

    def set_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        feature: str | None = None,
        reason: str | None = None,
    ) -> Task | None:
        """Set the status of a task.

        Args:
            task_id: Task ID.
            status: New status.
            feature: Feature the task belongs to.
            reason: Optional reason for status change.

        Returns:
            Updated Task or None if not found.
        """
        breakdown = self.get_breakdown(feature)
        if breakdown is None:
            return None

        task = breakdown.get_task(task_id)
        if task is None:
            return None

        task.status = status
        task.updated_at = __import__("datetime").datetime.now(__import__("datetime").UTC)

        if status == TaskStatus.COMPLETE:
            task.completed_at = task.updated_at
        elif status == TaskStatus.BLOCKED and reason:
            task.metadata["block_reason"] = reason
        elif status == TaskStatus.CANCELLED and reason:
            task.metadata["cancel_reason"] = reason

        self._save_breakdowns()

        logger.info("Set task status", task_id=task_id, status=status.value)
        return task

    def remove_task(self, task_id: str, feature: str | None = None) -> bool:
        """Remove a task from a breakdown.

        Args:
            task_id: Task ID.
            feature: Feature the task belongs to.

        Returns:
            True if removed, False if not found.
        """
        breakdown = self.get_breakdown(feature)
        if breakdown is None:
            return False

        removed = breakdown.remove_task(task_id)
        if removed:
            self._save_breakdowns()
            logger.info("Removed task", task_id=task_id)
        return removed

    def list_tasks(
        self,
        feature: str | None = None,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        tag: str | None = None,
    ) -> list[Task]:
        """List tasks with optional filters.

        Args:
            feature: Feature to list from.
            status: Filter by status.
            priority: Filter by priority.
            tag: Filter by tag.

        Returns:
            List of matching tasks.
        """
        breakdown = self.get_breakdown(feature)
        if breakdown is None:
            return []

        tasks = list(breakdown.tasks.values())

        if status is not None:
            tasks = [t for t in tasks if t.status == status]
        if priority is not None:
            tasks = [t for t in tasks if t.priority == priority]
        if tag is not None:
            tasks = [t for t in tasks if tag in t.tags]

        return tasks

    def get_next_ready_tasks(self, feature: str | None = None) -> list[Task]:
        """Get tasks that are ready to start.

        Args:
            feature: Feature to check.

        Returns:
            List of tasks that are pending and have all dependencies met.
        """
        breakdown = self.get_breakdown(feature)
        if breakdown is None:
            return []
        return breakdown.get_next_ready_tasks()

    def get_task_dependencies(self, task_id: str, feature: str | None = None) -> list[Task]:
        """Get all dependencies for a task.

        Args:
            task_id: Task ID.
            feature: Feature the task belongs to.

        Returns:
            List of dependency tasks.
        """
        breakdown = self.get_breakdown(feature)
        if breakdown is None:
            return []

        task = breakdown.get_task(task_id)
        if task is None:
            return []

        deps = []
        for dep_id in task.dependencies:
            dep_task = breakdown.get_task(dep_id)
            if dep_task:
                deps.append(dep_task)
        return deps

    def get_pending_dependencies(self, task_id: str, feature: str | None = None) -> list[str]:
        """Get IDs of dependencies that are not complete.

        Args:
            task_id: Task ID.
            feature: Feature the task belongs to.

        Returns:
            List of pending dependency IDs.
        """
        breakdown = self.get_breakdown(feature)
        if breakdown is None:
            return []
        return breakdown.get_pending_dependencies(task_id)

    # ------------------------------------------------------------------
    # Public API - Parsing and sync
    # ------------------------------------------------------------------

    def parse_tasks_from_spec(self, feature: str | None = None) -> list[Task]:
        """Parse tasks from a tasks.md spec file.

        Args:
            feature: Feature to parse from, or None for root tasks.md.

        Returns:
            List of parsed tasks.
        """
        path = self._get_tasks_md_path(feature)
        if not self._fs.file_exists(path):
            return []

        content = self._fs.read_file(path)
        tasks = parse_tasks_from_markdown(content, feature=feature)
        return tasks

    def sync_from_spec(self, feature: str | None = None) -> int:
        """Sync tasks from tasks.md spec file.

        Parses the spec file and adds any new tasks that don't already exist.
        Updates status of existing tasks based on checkbox state.

        Args:
            feature: Feature to sync, or None for project-level.

        Returns:
            Number of tasks added or updated.
        """
        parsed_tasks = self.parse_tasks_from_spec(feature)
        if not parsed_tasks:
            return 0

        breakdown = self.get_or_create_breakdown(feature)
        changes = 0

        for parsed in parsed_tasks:
            existing = breakdown.get_task(parsed.id)
            if existing is None:
                # New task
                breakdown.add_task(parsed)
                changes += 1
            elif existing.status != parsed.status:
                # Status changed
                existing.status = parsed.status
                if parsed.status == TaskStatus.COMPLETE:
                    existing.completed_at = __import__("datetime").datetime.now(
                        __import__("datetime").UTC
                    )
                existing.updated_at = __import__("datetime").datetime.now(
                    __import__("datetime").UTC
                )
                changes += 1

        if changes > 0:
            self._save_breakdowns()
            logger.info("Synced tasks from spec", feature=feature, changes=changes)

        return changes

    def sync_all_specs(self) -> dict[str | None, int]:
        """Sync all tasks.md files (root and features).

        Returns:
            Dict mapping feature name to number of changes.
        """
        results: dict[str | None, int] = {}

        # Sync root tasks.md
        results[None] = self.sync_from_spec(None)

        # Sync feature tasks.md files (features are stored as specs/<feature_name>/)
        if self._fs.directory_exists(self._paths.specs_dir):
            for item in self._fs.list_directory(self._paths.specs_dir):
                if item.is_dir():
                    feature = item.name
                    changes = self.sync_from_spec(feature)
                    if changes > 0:
                        results[feature] = changes

        return results

    def export_to_markdown(self, feature: str | None = None) -> str:
        """Export tasks to markdown format.

        Args:
            feature: Feature to export, or None for project-level.

        Returns:
            Markdown formatted task list.
        """
        breakdown = self.get_breakdown(feature)
        if breakdown is None:
            return ""

        tasks = sorted(breakdown.tasks.values(), key=lambda t: t.created_at or "")
        return serialize_tasks_to_markdown(list(tasks))

    # ------------------------------------------------------------------
    # Public API - Statistics
    # ------------------------------------------------------------------

    def get_progress(self, feature: str | None = None) -> dict[str, Any]:
        """Get progress statistics for a breakdown.

        Args:
            feature: Feature to get progress for.

        Returns:
            Dict with progress statistics.
        """
        breakdown = self.get_breakdown(feature)
        if breakdown is None:
            return {
                "feature": feature,
                "total": 0,
                "complete": 0,
                "percentage": 0.0,
                "summary": {},
            }

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
        """Get progress for all breakdowns.

        Returns:
            Dict mapping feature name to progress stats.
        """
        breakdowns = self._load_breakdowns()
        results: dict[str | None, dict[str, Any]] = {}

        for key in breakdowns:
            feature = None if key == "__project__" else key
            results[feature] = self.get_progress(feature)

        return results
