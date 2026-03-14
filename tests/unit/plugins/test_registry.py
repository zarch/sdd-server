"""Unit tests for PluginRegistry."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from sdd_server.plugins.base import (
    PluginError,
    PluginMetadata,
    RolePlugin,
    RoleResult,
    RoleStage,
    RoleStatus,
)
from sdd_server.plugins.registry import PluginRegistry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_role(
    name: str,
    stage: RoleStage = RoleStage.REVIEW,
    priority: int = 100,
    dependencies: list[str] | None = None,
) -> RolePlugin:
    """Create a minimal RolePlugin with given metadata."""
    _meta = PluginMetadata(
        name=name,
        version="1.0.0",
        description="Test role",
        author="Test",
        priority=priority,
        stage=stage,
        dependencies=dependencies or [],
    )

    class _Role(RolePlugin):
        metadata = _meta

        async def review(self, scope: str = "all", target: str | None = None) -> RoleResult:
            return RoleResult(
                role=self.name,
                status=RoleStatus.COMPLETED,
                success=True,
                output="ok",
                started_at=datetime.now(),
            )

        def get_recipe_template(self) -> str:
            return 'version: "1.0.0"\n'

    return _Role()


@pytest.fixture
def registry() -> PluginRegistry:
    return PluginRegistry()


@pytest.fixture
def populated_registry(registry: PluginRegistry) -> PluginRegistry:
    registry.register("architect", _make_role("architect", RoleStage.ARCHITECTURE, priority=10))
    registry.register("reviewer", _make_role("reviewer", RoleStage.REVIEW, priority=50))
    return registry


# ---------------------------------------------------------------------------
# register / unregister
# ---------------------------------------------------------------------------


class TestRegisterUnregister:
    def test_register_adds_plugin(self, registry: PluginRegistry) -> None:
        role = _make_role("my-role")
        registry.register("my-role", role)
        assert registry.has_plugin("my-role")

    def test_register_duplicate_raises(self, registry: PluginRegistry) -> None:
        role = _make_role("my-role")
        registry.register("my-role", role)
        with pytest.raises(PluginError, match="already registered"):
            registry.register("my-role", _make_role("my-role"))

    def test_register_plugin_without_metadata_raises(self, registry: PluginRegistry) -> None:
        plugin = MagicMock(spec=[])  # no metadata attribute
        with pytest.raises(PluginError, match="no metadata"):
            registry.register("bad", plugin)

    def test_unregister_removes_plugin(self, populated_registry: PluginRegistry) -> None:
        result = populated_registry.unregister("architect")
        assert result is not None
        assert not populated_registry.has_plugin("architect")

    def test_unregister_removes_from_roles(self, populated_registry: PluginRegistry) -> None:
        populated_registry.unregister("architect")
        assert not populated_registry.has_role("architect")

    def test_unregister_unknown_returns_none(self, registry: PluginRegistry) -> None:
        result = registry.unregister("__nonexistent__")
        assert result is None

    def test_register_role_adds_to_roles(self, registry: PluginRegistry) -> None:
        role = _make_role("my-role")
        registry.register("my-role", role)
        assert registry.has_role("my-role")


# ---------------------------------------------------------------------------
# get_role / list_roles / count_roles
# ---------------------------------------------------------------------------


class TestRoleAccess:
    def test_get_role_returns_role(self, populated_registry: PluginRegistry) -> None:
        role = populated_registry.get_role("architect")
        assert role is not None
        assert role.name == "architect"

    def test_get_role_unknown_returns_none(self, registry: PluginRegistry) -> None:
        result = registry.get_role("__nonexistent__")
        assert result is None

    def test_list_roles_returns_all_role_names(self, populated_registry: PluginRegistry) -> None:
        roles = populated_registry.list_roles()
        assert set(roles) == {"architect", "reviewer"}

    def test_count_roles_matches_registered_count(self, populated_registry: PluginRegistry) -> None:
        assert populated_registry.count_roles() == 2

    def test_count_roles_zero_when_empty(self, registry: PluginRegistry) -> None:
        assert registry.count_roles() == 0


# ---------------------------------------------------------------------------
# get_roles_by_stage
# ---------------------------------------------------------------------------


class TestGetRolesByStage:
    def test_returns_roles_for_stage(self, populated_registry: PluginRegistry) -> None:
        roles = populated_registry.get_roles_by_stage(RoleStage.REVIEW)
        assert len(roles) == 1
        assert roles[0].name == "reviewer"

    def test_returns_empty_for_unused_stage(self, populated_registry: PluginRegistry) -> None:
        roles = populated_registry.get_roles_by_stage(RoleStage.SECURITY)
        assert roles == []

    def test_roles_sorted_by_priority(self, registry: PluginRegistry) -> None:
        registry.register("high-prio", _make_role("high-prio", RoleStage.REVIEW, priority=10))
        registry.register("low-prio", _make_role("low-prio", RoleStage.REVIEW, priority=90))
        roles = registry.get_roles_by_stage(RoleStage.REVIEW)
        assert roles[0].name == "high-prio"
        assert roles[1].name == "low-prio"


# ---------------------------------------------------------------------------
# get_dependency_graph via get_execution_order
# ---------------------------------------------------------------------------


class TestExecutionOrder:
    def test_execution_order_respects_dependencies(self, registry: PluginRegistry) -> None:
        registry.register("a", _make_role("a", RoleStage.ARCHITECTURE, priority=10))
        registry.register("b", _make_role("b", RoleStage.REVIEW, priority=20, dependencies=["a"]))
        order = registry.get_execution_order(["a", "b"])
        assert order.index("a") < order.index("b")

    def test_execution_order_no_deps_is_sorted_by_priority(self, registry: PluginRegistry) -> None:
        registry.register("r1", _make_role("r1", RoleStage.REVIEW, priority=5))
        registry.register("r2", _make_role("r2", RoleStage.REVIEW, priority=1))
        order = registry.get_execution_order(["r1", "r2"])
        assert order.index("r2") < order.index("r1")

    def test_circular_dependency_raises(self, registry: PluginRegistry) -> None:
        # Register x and y without mutual deps first (so they pass validation),
        # then manually plant circular deps in the metadata after registration.
        role_x = _make_role("x", RoleStage.REVIEW, priority=10)
        role_y = _make_role("y", RoleStage.REVIEW, priority=20)
        registry.register("x", role_x)
        registry.register("y", role_y)
        # Plant circular dependencies directly
        role_x.metadata.dependencies.append("y")
        role_y.metadata.dependencies.append("x")
        with pytest.raises(PluginError, match="Circular dependency"):
            registry.get_execution_order(["x", "y"])


# ---------------------------------------------------------------------------
# clear
# ---------------------------------------------------------------------------


class TestClear:
    def test_clear_resets_all_state(self, populated_registry: PluginRegistry) -> None:
        populated_registry.clear()
        assert populated_registry.count_plugins() == 0
        assert populated_registry.count_roles() == 0
        assert populated_registry.list_plugins() == []
        assert populated_registry.list_roles() == []

    def test_can_register_again_after_clear(self, populated_registry: PluginRegistry) -> None:
        populated_registry.clear()
        populated_registry.register("new-role", _make_role("new-role"))
        assert populated_registry.has_plugin("new-role")


# ---------------------------------------------------------------------------
# list_metadata / get_metadata / get_roles_info
# ---------------------------------------------------------------------------


class TestMetadataAccess:
    def test_get_metadata_returns_metadata(self, populated_registry: PluginRegistry) -> None:
        meta = populated_registry.get_metadata("architect")
        assert meta is not None
        assert meta.name == "architect"

    def test_get_metadata_unknown_returns_none(self, registry: PluginRegistry) -> None:
        assert registry.get_metadata("__nonexistent__") is None

    def test_list_metadata_returns_all(self, populated_registry: PluginRegistry) -> None:
        metas = populated_registry.list_metadata()
        assert len(metas) == 2

    def test_get_roles_info_shape(self, populated_registry: PluginRegistry) -> None:
        info = populated_registry.get_roles_info()
        assert len(info) == 2
        for item in info:
            assert "name" in item
            assert "stage" in item
            assert "priority" in item


# ---------------------------------------------------------------------------
# Dependency validation on registration
# ---------------------------------------------------------------------------


class TestDependencyValidation:
    def test_missing_dependency_raises(self, registry: PluginRegistry) -> None:
        role = _make_role("needs-missing", dependencies=["does-not-exist"])
        with pytest.raises(PluginError, match="missing dependencies"):
            registry.register("needs-missing", role)

    def test_registered_dependency_passes(self, registry: PluginRegistry) -> None:
        dep = _make_role("dep-role")
        registry.register("dep-role", dep)
        child = _make_role("child-role", dependencies=["dep-role"])
        # Should not raise
        registry.register("child-role", child)
        assert registry.has_plugin("child-role")
