"""Feature lifecycle manager for SDD."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sdd_server.infrastructure.filesystem import FileSystemClient
from sdd_server.models.lifecycle import (
    FeatureLifecycle,
    LifecycleState,
    LifecycleTransition,
    ProjectLifecycle,
)
from sdd_server.utils.logging import get_logger

logger = get_logger(__name__)

# Default lifecycle file path
LIFECYCLE_FILE = ".sdd/lifecycle.json"


class FeatureLifecycleManager:
    """Manages feature lifecycle states and transitions.

    This class provides the core business logic for feature lifecycle management,
    including state transitions, validation, and persistence.
    """

    def __init__(self, project_root: Path) -> None:
        """Initialize the lifecycle manager.

        Args:
            project_root: Root directory of the project.
        """
        self.project_root = project_root.resolve()
        self._fs = FileSystemClient(self.project_root)
        self._lifecycle_path = self.project_root / LIFECYCLE_FILE
        self._project_lifecycle: ProjectLifecycle | None = None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _ensure_lifecycle_dir(self) -> None:
        """Ensure the lifecycle directory exists."""
        lifecycle_dir = self._lifecycle_path.parent
        if not self._fs.directory_exists(lifecycle_dir):
            self._fs.ensure_directory(lifecycle_dir)

    def _load_project_lifecycle(self) -> ProjectLifecycle:
        """Load project lifecycle from disk, or create new if not exists."""
        if self._project_lifecycle is not None:
            return self._project_lifecycle

        if self._fs.file_exists(self._lifecycle_path):
            try:
                content = self._fs.read_file(self._lifecycle_path)
                data = __import__("json").loads(content)
                self._project_lifecycle = ProjectLifecycle.model_validate(data)
                logger.debug(
                    "Loaded lifecycle state",
                    feature_count=len(self._project_lifecycle.features),
                )
            except Exception as exc:
                logger.warning(
                    "Failed to load lifecycle state, creating new",
                    error=str(exc),
                )
                self._project_lifecycle = ProjectLifecycle()
        else:
            self._project_lifecycle = ProjectLifecycle()

        return self._project_lifecycle

    def _save_project_lifecycle(self) -> None:
        """Save project lifecycle to disk."""
        if self._project_lifecycle is None:
            return

        self._ensure_lifecycle_dir()
        content = self._project_lifecycle.model_dump_json(indent=2)
        self._fs.write_file(self._lifecycle_path, content)
        logger.debug("Saved lifecycle state")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_feature(
        self,
        feature_id: str,
        initial_state: LifecycleState = LifecycleState.PLANNED,
    ) -> FeatureLifecycle:
        """Create a new feature lifecycle.

        Args:
            feature_id: Unique identifier for the feature.
            initial_state: Initial lifecycle state (default: PLANNED).

        Returns:
            The created FeatureLifecycle.

        Raises:
            ValueError: If feature already exists.
        """
        project = self._load_project_lifecycle()

        if feature_id in project.features:
            raise ValueError(f"Feature '{feature_id}' already exists")

        lifecycle = FeatureLifecycle(
            feature_id=feature_id,
            state=initial_state,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        project.features[feature_id] = lifecycle
        self._save_project_lifecycle()

        logger.info(
            "Created feature lifecycle",
            feature_id=feature_id,
            initial_state=initial_state.value,
        )
        return lifecycle

    def get_feature(self, feature_id: str) -> FeatureLifecycle | None:
        """Get a feature's lifecycle state.

        Args:
            feature_id: Feature identifier.

        Returns:
            FeatureLifecycle or None if not found.
        """
        project = self._load_project_lifecycle()
        return project.features.get(feature_id)

    def transition_feature(
        self,
        feature_id: str,
        new_state: LifecycleState,
        reason: str | None = None,
        actor: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> LifecycleTransition:
        """Transition a feature to a new lifecycle state.

        Args:
            feature_id: Feature identifier.
            new_state: Target lifecycle state.
            reason: Optional reason for the transition.
            actor: Optional actor who initiated the transition.
            metadata: Optional additional metadata.

        Returns:
            The created LifecycleTransition record.

        Raises:
            ValueError: If feature not found or transition is invalid.
        """
        project = self._load_project_lifecycle()

        if feature_id not in project.features:
            raise ValueError(f"Feature '{feature_id}' not found")

        lifecycle = project.features[feature_id]
        transition = lifecycle.transition_to(
            new_state=new_state,
            reason=reason,
            actor=actor,
            metadata=metadata,
        )
        self._save_project_lifecycle()

        logger.info(
            "Transitioned feature lifecycle",
            feature_id=feature_id,
            from_state=transition.from_state.value,
            to_state=new_state.value,
            reason=reason,
        )
        return transition

    def can_transition(self, feature_id: str, new_state: LifecycleState) -> bool:
        """Check if a transition is valid.

        Args:
            feature_id: Feature identifier.
            new_state: Target lifecycle state.

        Returns:
            True if transition is valid, False otherwise.
        """
        lifecycle = self.get_feature(feature_id)
        if lifecycle is None:
            return False
        return lifecycle.can_transition_to(new_state)  # type: ignore[no-any-return]

    def get_allowed_transitions(self, feature_id: str) -> list[LifecycleState]:
        """Get list of states a feature can transition to.

        Args:
            feature_id: Feature identifier.

        Returns:
            List of valid target states.

        Raises:
            ValueError: If feature not found.
        """
        lifecycle = self.get_feature(feature_id)
        if lifecycle is None:
            raise ValueError(f"Feature '{feature_id}' not found")
        return lifecycle.get_allowed_transitions()  # type: ignore[no-any-return]

    def list_features(self, state: LifecycleState | None = None) -> list[str]:
        """List all features, optionally filtered by state.

        Args:
            state: Optional state filter.

        Returns:
            List of feature IDs.
        """
        project = self._load_project_lifecycle()
        if state is None:
            return list(project.features.keys())
        return project.get_features_by_state(state)  # type: ignore[no-any-return]

    def get_summary(self) -> dict[str, int]:
        """Get count of features in each lifecycle state.

        Returns:
            Dict mapping state name to count.
        """
        project = self._load_project_lifecycle()
        summary = project.get_summary()
        return {state.value: count for state, count in summary.items()}

    def remove_feature(self, feature_id: str) -> bool:
        """Remove a feature lifecycle.

        Args:
            feature_id: Feature identifier.

        Returns:
            True if feature was removed, False if not found.
        """
        project = self._load_project_lifecycle()
        removed = project.remove_feature(feature_id)
        if removed:
            self._save_project_lifecycle()
            logger.info("Removed feature lifecycle", feature_id=feature_id)
        return removed  # type: ignore[no-any-return]

    def archive_feature(self, feature_id: str, reason: str | None = None) -> bool:
        """Archive a completed feature.

        This transitions the feature to ARCHIVED state if valid.
        Otherwise, removes it from tracking.

        Args:
            feature_id: Feature identifier.
            reason: Optional reason for archiving.

        Returns:
            True if archived or removed, False if not found.
        """
        lifecycle = self.get_feature(feature_id)
        if lifecycle is None:
            return False

        if lifecycle.can_transition_to(LifecycleState.ARCHIVED):
            self.transition_feature(
                feature_id=feature_id,
                new_state=LifecycleState.ARCHIVED,
                reason=reason,
            )
            return True

        # If can't transition to archived, just remove
        return self.remove_feature(feature_id)

    def get_feature_history(self, feature_id: str) -> list[LifecycleTransition]:
        """Get transition history for a feature.

        Args:
            feature_id: Feature identifier.

        Returns:
            List of transitions, oldest first.

        Raises:
            ValueError: If feature not found.
        """
        lifecycle = self.get_feature(feature_id)
        if lifecycle is None:
            raise ValueError(f"Feature '{feature_id}' not found")
        return list(lifecycle.history)

    def get_feature_metrics(self, feature_id: str) -> dict[str, Any]:
        """Get metrics for a feature.

        Args:
            feature_id: Feature identifier.

        Returns:
            Dict with metrics including transition count, rework count,
            time in current state, etc.

        Raises:
            ValueError: If feature not found.
        """
        lifecycle = self.get_feature(feature_id)
        if lifecycle is None:
            raise ValueError(f"Feature '{feature_id}' not found")

        return {
            "feature_id": feature_id,
            "current_state": lifecycle.state.value,
            "transition_count": lifecycle.get_transition_count(),
            "rework_count": lifecycle.get_rework_count(),
            "time_in_current_state_seconds": lifecycle.time_in_current_state(),
            "created_at": lifecycle.created_at.isoformat() if lifecycle.created_at else None,
            "updated_at": lifecycle.updated_at.isoformat() if lifecycle.updated_at else None,
            "allowed_transitions": [s.value for s in lifecycle.get_allowed_transitions()],
        }

    def get_project_state(self) -> LifecycleState | None:
        """Get overall project lifecycle state.

        Returns:
            Overall state or None if no features.
        """
        project = self._load_project_lifecycle()
        return project.overall_state

    def sync_with_spec_manager(self, spec_features: list[str]) -> int:
        """Sync lifecycle state with features from spec manager.

        Creates lifecycle entries for features that exist in specs
        but not in lifecycle tracking.

        Args:
            spec_features: List of feature IDs from spec manager.

        Returns:
            Number of new features added.
        """
        project = self._load_project_lifecycle()
        existing = set(project.features.keys())
        new_features = set(spec_features) - existing

        added = 0
        for feature_id in new_features:
            project.add_feature(feature_id)
            added += 1
            logger.info("Synced new feature", feature_id=feature_id)

        if added > 0:
            self._save_project_lifecycle()

        return added
