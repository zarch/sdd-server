"""MCP tools: feature lifecycle management."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context, FastMCP

from sdd_server.core.lifecycle import FeatureLifecycleManager
from sdd_server.models.lifecycle import LifecycleState
from sdd_server.utils.logging import get_logger

logger = get_logger(__name__)


def _get_lifecycle_manager(ctx: Context | None) -> FeatureLifecycleManager:  # type: ignore[type-arg]
    """Get lifecycle manager from context or create standalone."""
    if ctx and hasattr(ctx, "request_context") and ctx.request_context:
        state = ctx.request_context.lifespan_context
        mgr: FeatureLifecycleManager = state["lifecycle_manager"]
        return mgr
    import os
    from pathlib import Path

    root = Path(os.getenv("SDD_PROJECT_ROOT", ".")).resolve()
    return FeatureLifecycleManager(root)


def _lifecycle_to_dict(lifecycle: Any) -> dict[str, Any]:
    """Convert a FeatureLifecycle to a dictionary for JSON response."""
    return {
        "feature_id": lifecycle.feature_id,
        "state": lifecycle.state.value,
        "created_at": lifecycle.created_at.isoformat() if lifecycle.created_at else None,
        "updated_at": lifecycle.updated_at.isoformat() if lifecycle.updated_at else None,
        "transition_count": len(lifecycle.history),
        "allowed_transitions": [s.value for s in lifecycle.get_allowed_transitions()],
    }


def register_tools(mcp: FastMCP) -> None:
    """Register lifecycle tools on the given FastMCP instance."""

    @mcp.tool()
    async def sdd_lifecycle_create(
        feature_id: str,
        initial_state: str = "planned",
        ctx: Context | None = None,  # type: ignore[type-arg]
    ) -> dict[str, Any]:
        """Create a new feature lifecycle.

        Args:
            feature_id: Unique identifier for the feature.
            initial_state: Initial state (planned, in_progress, review, complete, archived).
        """
        mgr = _get_lifecycle_manager(ctx)
        try:
            state = LifecycleState(initial_state)
            lifecycle = mgr.create_feature(feature_id, initial_state=state)
            return {
                "success": True,
                "lifecycle": _lifecycle_to_dict(lifecycle),
            }
        except ValueError as exc:
            return {"success": False, "error": str(exc)}

    @mcp.tool()
    async def sdd_lifecycle_get(
        feature_id: str,
        ctx: Context | None = None,  # type: ignore[type-arg]
    ) -> dict[str, Any]:
        """Get lifecycle state for a feature.

        Args:
            feature_id: Feature identifier.
        """
        mgr = _get_lifecycle_manager(ctx)
        lifecycle = mgr.get_feature(feature_id)
        if lifecycle is None:
            return {"success": False, "error": f"Feature '{feature_id}' not found"}
        return {
            "success": True,
            "lifecycle": _lifecycle_to_dict(lifecycle),
        }

    @mcp.tool()
    async def sdd_lifecycle_transition(
        feature_id: str,
        new_state: str,
        reason: str | None = None,
        actor: str | None = None,
        ctx: Context | None = None,  # type: ignore[type-arg]
    ) -> dict[str, Any]:
        """Transition a feature to a new lifecycle state.

        Args:
            feature_id: Feature identifier.
            new_state: Target state (planned, in_progress, review, complete, archived).
            reason: Optional reason for the transition.
            actor: Optional actor who initiated the transition.
        """
        mgr = _get_lifecycle_manager(ctx)
        try:
            target_state = LifecycleState(new_state)
            transition = mgr.transition_feature(
                feature_id=feature_id,
                new_state=target_state,
                reason=reason,
                actor=actor,
            )
            lifecycle = mgr.get_feature(feature_id)
            return {
                "success": True,
                "transition": {
                    "from_state": transition.from_state.value,
                    "to_state": transition.to_state.value,
                    "timestamp": transition.timestamp.isoformat(),
                    "reason": transition.reason,
                    "actor": transition.actor,
                },
                "lifecycle": _lifecycle_to_dict(lifecycle) if lifecycle else None,
            }
        except ValueError as exc:
            return {"success": False, "error": str(exc)}

    @mcp.tool()
    async def sdd_lifecycle_list(
        state: str | None = None,
        ctx: Context | None = None,  # type: ignore[type-arg]
    ) -> dict[str, Any]:
        """List all features with their lifecycle states.

        Args:
            state: Optional state filter (planned, in_progress, review, complete, archived).
        """
        mgr = _get_lifecycle_manager(ctx)
        filter_state = LifecycleState(state) if state else None
        features = mgr.list_features(state=filter_state)
        lifecycles = []
        for feature_id in features:
            lifecycle = mgr.get_feature(feature_id)
            if lifecycle:
                lifecycles.append(_lifecycle_to_dict(lifecycle))
        return {
            "success": True,
            "features": lifecycles,
            "count": len(lifecycles),
            "filter": state,
        }

    @mcp.tool()
    async def sdd_lifecycle_summary(
        ctx: Context | None = None,  # type: ignore[type-arg]
    ) -> dict[str, Any]:
        """Get summary of features in each lifecycle state."""
        mgr = _get_lifecycle_manager(ctx)
        summary = mgr.get_summary()
        project_state = mgr.get_project_state()
        return {
            "success": True,
            "summary": summary,
            "project_state": project_state.value if project_state else None,
            "total_features": sum(summary.values()),
        }

    @mcp.tool()
    async def sdd_lifecycle_history(
        feature_id: str,
        ctx: Context | None = None,  # type: ignore[type-arg]
    ) -> dict[str, Any]:
        """Get transition history for a feature.

        Args:
            feature_id: Feature identifier.
        """
        mgr = _get_lifecycle_manager(ctx)
        try:
            history = mgr.get_feature_history(feature_id)
            return {
                "success": True,
                "feature_id": feature_id,
                "history": [
                    {
                        "from_state": t.from_state.value,
                        "to_state": t.to_state.value,
                        "timestamp": t.timestamp.isoformat(),
                        "reason": t.reason,
                        "actor": t.actor,
                    }
                    for t in history
                ],
            }
        except ValueError as exc:
            return {"success": False, "error": str(exc)}

    @mcp.tool()
    async def sdd_lifecycle_metrics(
        feature_id: str,
        ctx: Context | None = None,  # type: ignore[type-arg]
    ) -> dict[str, Any]:
        """Get metrics for a feature lifecycle.

        Args:
            feature_id: Feature identifier.
        """
        mgr = _get_lifecycle_manager(ctx)
        try:
            metrics = mgr.get_feature_metrics(feature_id)
            return {"success": True, "metrics": metrics}
        except ValueError as exc:
            return {"success": False, "error": str(exc)}

    @mcp.tool()
    async def sdd_lifecycle_archive(
        feature_id: str,
        reason: str | None = None,
        ctx: Context | None = None,  # type: ignore[type-arg]
    ) -> dict[str, Any]:
        """Archive a feature.

        Args:
            feature_id: Feature identifier.
            reason: Optional reason for archiving.
        """
        mgr = _get_lifecycle_manager(ctx)
        result = mgr.archive_feature(feature_id, reason=reason)
        if result:
            lifecycle = mgr.get_feature(feature_id)
            return {
                "success": True,
                "archived": True,
                "lifecycle": _lifecycle_to_dict(lifecycle) if lifecycle else None,
            }
        return {"success": False, "error": f"Feature '{feature_id}' not found"}

    @mcp.tool()
    async def sdd_lifecycle_can_transition(
        feature_id: str,
        target_state: str,
        ctx: Context | None = None,  # type: ignore[type-arg]
    ) -> dict[str, Any]:
        """Check if a transition is valid without performing it.

        Args:
            feature_id: Feature identifier.
            target_state: Target state to check.
        """
        mgr = _get_lifecycle_manager(ctx)
        try:
            new_state = LifecycleState(target_state)
            can_transition = mgr.can_transition(feature_id, new_state)
            allowed = mgr.get_allowed_transitions(feature_id)
            return {
                "success": True,
                "can_transition": can_transition,
                "current_allowed_transitions": [s.value for s in allowed],
            }
        except ValueError as exc:
            return {"success": False, "error": str(exc)}
