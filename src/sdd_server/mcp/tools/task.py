"""MCP tools for task management."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context, FastMCP

from sdd_server.core.task_manager import TaskBreakdownManager
from sdd_server.models.task import TaskPriority, TaskStatus
from sdd_server.utils.logging import get_logger

logger = get_logger(__name__)


def _get_manager(ctx: Context | None) -> TaskBreakdownManager:  # type: ignore[type-arg]
    """Get the task breakdown manager from context or create standalone."""
    if ctx and hasattr(ctx, "request_context") and ctx.request_context:
        state = ctx.request_context.lifespan_context
        mgr: TaskBreakdownManager = state["task_manager"]
        return mgr
    import os
    from pathlib import Path

    root = Path(os.getenv("SDD_PROJECT_ROOT", ".")).resolve()
    return TaskBreakdownManager(root)


async def sdd_task_add(
    ctx: Context | None,  # type: ignore[type-arg]
    title: str,
    description: str = "",
    feature: str | None = None,
    priority: str = "medium",
    role: str | None = None,
    dependencies: list[str] | None = None,
    tags: list[str] | None = None,
    ai_prompt: str | None = None,
) -> dict[str, Any]:
    """Add a new task.

    Args:
        title: Task title.
        description: Task description.
        feature: Feature to add task to (optional).
        priority: Task priority (low, medium, high, critical).
        role: Associated role for the task.
        dependencies: List of task IDs this task depends on.
        tags: List of tags for categorization.
        ai_prompt: AI prompt for task execution.

    Returns:
        Not supported message — tasks are managed via tasks.md directly.
    """
    return {
        "status": "not_supported",
        "message": (
            "Adding tasks programmatically is not supported. "
            "Tasks are managed by editing tasks.md directly."
        ),
    }


async def sdd_task_get(
    ctx: Context | None,  # type: ignore[type-arg]
    task_id: str,
    feature: str | None = None,
) -> dict[str, Any] | None:
    """Get a task by ID.

    Args:
        task_id: Task ID.
        feature: Feature to search in (optional, searches all if not provided).

    Returns:
        Task details or None if not found.
    """
    manager = _get_manager(ctx)

    if feature is not None:
        task = manager.get_task(task_id, feature=feature)
    else:
        result = manager.find_task(task_id)
        if result is None:
            return None
        task, _ = result

    return task.model_dump() if task else None


async def sdd_task_update(
    ctx: Context | None,  # type: ignore[type-arg]
    task_id: str,
    feature: str | None = None,
    title: str | None = None,
    description: str | None = None,
    priority: str | None = None,
    role: str | None = None,
    dependencies: list[str] | None = None,
    tags: list[str] | None = None,
    ai_prompt: str | None = None,
) -> dict[str, Any]:
    """Update a task.

    Args:
        task_id: Task ID.
        feature: Feature the task belongs to.
        title: New title.
        description: New description.
        priority: New priority.
        role: New role.
        dependencies: New dependencies list.
        tags: New tags list.
        ai_prompt: New AI prompt.

    Returns:
        Not supported message — tasks are managed via tasks.md directly.
    """
    return {
        "status": "not_supported",
        "task_id": task_id,
        "message": (
            "Updating tasks programmatically is not supported. "
            "Tasks are managed by editing tasks.md directly."
        ),
    }


async def sdd_task_set_status(
    ctx: Context | None,  # type: ignore[type-arg]
    task_id: str,
    status: str,
    feature: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    """Set the status of a task.

    Args:
        task_id: Task ID.
        status: New status (pending, in_progress, complete, blocked, cancelled).
        feature: Feature the task belongs to.
        reason: Optional reason for status change.

    Returns:
        Not supported message — tasks are managed via tasks.md directly.
    """
    return {
        "status": "not_supported",
        "task_id": task_id,
        "message": (
            "Setting task status programmatically is not supported. "
            "Tasks are managed by editing tasks.md directly."
        ),
    }


async def sdd_task_remove(
    ctx: Context | None,  # type: ignore[type-arg]
    task_id: str,
    feature: str | None = None,
) -> dict[str, str]:
    """Remove a task.

    Args:
        task_id: Task ID.
        feature: Feature the task belongs to.

    Returns:
        Not supported message — tasks are managed via tasks.md directly.
    """
    return {
        "status": "not_supported",
        "task_id": task_id,
        "message": (
            "Removing tasks programmatically is not supported. "
            "Tasks are managed by editing tasks.md directly."
        ),
    }


async def sdd_task_list(
    ctx: Context | None,  # type: ignore[type-arg]
    feature: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    tag: str | None = None,
) -> list[dict[str, Any]]:
    """List tasks with optional filters.

    Args:
        feature: Feature to list from.
        status: Filter by status.
        priority: Filter by priority.
        tag: Filter by tag.

    Returns:
        List of matching tasks.
    """
    manager = _get_manager(ctx)

    status_enum = TaskStatus(status.lower()) if status else None
    priority_enum = TaskPriority(priority.lower()) if priority else None

    tasks = manager.list_tasks(
        feature=feature,
        status=status_enum,
        priority=priority_enum,
        tag=tag,
    )

    return [t.model_dump() for t in tasks]


async def sdd_task_ready(
    ctx: Context | None,  # type: ignore[type-arg]
    feature: str | None = None,
) -> list[dict[str, Any]]:
    """Get tasks that are ready to start.

    Returns tasks that are pending and have all dependencies met.

    Args:
        feature: Feature to check.

    Returns:
        List of ready tasks.
    """
    manager = _get_manager(ctx)
    tasks = manager.get_next_ready_tasks(feature=feature)
    return [t.model_dump() for t in tasks]


async def sdd_task_dependencies(
    ctx: Context | None,  # type: ignore[type-arg]
    task_id: str,
    feature: str | None = None,
) -> dict[str, Any]:
    """Get dependency information for a task.

    Args:
        task_id: Task ID.
        feature: Feature the task belongs to.

    Returns:
        Dependency information including all dependencies and pending ones.
    """
    manager = _get_manager(ctx)

    deps = manager.get_task_dependencies(task_id, feature=feature)
    pending = manager.get_pending_dependencies(task_id, feature=feature)

    return {
        "task_id": task_id,
        "dependencies": [d.model_dump() for d in deps],
        "pending_ids": pending,
        "can_start": len(pending) == 0,
    }


async def sdd_task_progress(
    ctx: Context | None,  # type: ignore[type-arg]
    feature: str | None = None,
) -> dict[str, Any]:
    """Get progress statistics.

    Args:
        feature: Feature to get progress for (all if not provided).

    Returns:
        Progress statistics.
    """
    manager = _get_manager(ctx)

    if feature is not None:
        return manager.get_progress(feature)
    return {"features": manager.get_all_progress()}


async def sdd_task_sync(
    ctx: Context | None,  # type: ignore[type-arg]
    feature: str | None = None,
) -> dict[str, Any]:
    """Sync tasks from tasks.md spec file.

    Args:
        feature: Feature to sync (all if not provided).

    Returns:
        Sync results.
    """
    manager = _get_manager(ctx)

    if feature is not None:
        # sync_from_spec no longer exists; fall back to syncing all specs
        results = manager.sync_all_specs()
        return {
            "feature": feature,
            "message": ("Per-feature sync is not supported; synced all specs instead."),
            "results": {str(k): v for k, v in results.items()},
        }

    results = manager.sync_all_specs()
    return {"results": {str(k): v for k, v in results.items()}}


async def sdd_task_export(
    ctx: Context | None,  # type: ignore[type-arg]
    feature: str | None = None,
) -> dict[str, str]:
    """Export tasks to markdown format.

    Args:
        feature: Feature to export.

    Returns:
        Markdown formatted task list.
    """
    manager = _get_manager(ctx)
    markdown = manager.export_to_markdown(feature=feature)
    return {"markdown": markdown}


def register_tools(server: FastMCP) -> None:
    """Register all task tools with the server."""
    server.tool()(sdd_task_add)
    server.tool()(sdd_task_get)
    server.tool()(sdd_task_update)
    server.tool()(sdd_task_set_status)
    server.tool()(sdd_task_remove)
    server.tool()(sdd_task_list)
    server.tool()(sdd_task_ready)
    server.tool()(sdd_task_dependencies)
    server.tool()(sdd_task_progress)
    server.tool()(sdd_task_sync)
    server.tool()(sdd_task_export)


# For backwards compatibility
TASK_TOOLS = [
    sdd_task_add,
    sdd_task_get,
    sdd_task_update,
    sdd_task_set_status,
    sdd_task_remove,
    sdd_task_list,
    sdd_task_ready,
    sdd_task_dependencies,
    sdd_task_progress,
    sdd_task_sync,
    sdd_task_export,
]
