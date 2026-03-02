"""Tests for RoleEngine."""

import pytest

from sdd_server.core.role_engine import RoleEngine
from sdd_server.plugins import (
    PluginLoader,
    PluginRegistry,
    RoleStage,
)


@pytest.fixture
async def registry_with_roles() -> PluginRegistry:
    """Set up a registry with all built-in roles."""
    loader = PluginLoader()
    await loader.discover_plugins()
    registry = PluginRegistry()

    # Register in dependency order
    for name in [
        "architect",
        "ui-designer",
        "interface-designer",
        "security-analyst",
        "edge-case-analyst",
        "senior-developer",
    ]:
        plugin = await loader.load_plugin(name)
        registry.register(name, plugin)

    return registry


class TestRoleEngine:
    """Tests for RoleEngine class."""

    @pytest.mark.asyncio
    async def test_engine_creation(self, registry_with_roles: PluginRegistry) -> None:
        """Test creating a RoleEngine."""
        engine = RoleEngine(registry_with_roles)
        assert engine.completed_roles == set()
        assert engine.failed_roles == set()

    @pytest.mark.asyncio
    async def test_run_all_sequential(self, registry_with_roles: PluginRegistry) -> None:
        """Test running all roles sequentially."""
        engine = RoleEngine(registry_with_roles)

        results = await engine.run_all(parallel=False)

        # Should have 6 results
        assert len(results) == 6

        # All roles should be completed
        assert len(engine.completed_roles) == 6
        assert len(engine.failed_roles) == 0

    @pytest.mark.asyncio
    async def test_run_all_parallel(self, registry_with_roles: PluginRegistry) -> None:
        """Test running all roles in parallel."""
        engine = RoleEngine(registry_with_roles)

        results = await engine.run_all(parallel=True)

        # Should have 6 results
        assert len(results) == 6

        # All roles should be completed
        assert len(engine.completed_roles) == 6

    @pytest.mark.asyncio
    async def test_run_specific_roles(self, registry_with_roles: PluginRegistry) -> None:
        """Test running specific roles."""
        engine = RoleEngine(registry_with_roles)

        results = await engine.run_roles(["architect", "ui-designer"])

        assert len(results) == 2
        assert "architect" in results
        assert "ui-designer" in results

    @pytest.mark.asyncio
    async def test_run_stage(self, registry_with_roles: PluginRegistry) -> None:
        """Test running a specific stage."""
        engine = RoleEngine(registry_with_roles)

        results = await engine.run_stage(RoleStage.ARCHITECTURE)

        # Only architect is in ARCHITECTURE stage
        assert len(results) == 1
        assert "architect" in results

    @pytest.mark.asyncio
    async def test_get_status(self, registry_with_roles: PluginRegistry) -> None:
        """Test getting execution status."""
        engine = RoleEngine(registry_with_roles)

        await engine.run_all()

        status = engine.get_status()
        assert status["total_results"] == 6
        assert len(status["completed"]) == 6
        assert len(status["failed"]) == 0

    @pytest.mark.asyncio
    async def test_get_summary(self, registry_with_roles: PluginRegistry) -> None:
        """Test getting execution summary."""
        engine = RoleEngine(registry_with_roles)

        await engine.run_all()

        summary = engine.get_summary()
        assert "Role Execution Summary" in summary
        assert "architect" in summary

    @pytest.mark.asyncio
    async def test_get_dependency_graph(self, registry_with_roles: PluginRegistry) -> None:
        """Test getting dependency graph."""
        engine = RoleEngine(registry_with_roles)

        graph = engine.get_dependency_graph()

        # Architect has no dependencies
        assert graph["architect"] == []

        # UI Designer depends on architect
        assert "architect" in graph["ui-designer"]

    @pytest.mark.asyncio
    async def test_get_dependents(self, registry_with_roles: PluginRegistry) -> None:
        """Test getting dependents of a role."""
        engine = RoleEngine(registry_with_roles)

        dependents = engine.get_dependents("architect")

        # Multiple roles depend on architect
        assert "ui-designer" in dependents
        assert "interface-designer" in dependents
        assert "security-analyst" in dependents

    @pytest.mark.asyncio
    async def test_build_execution_levels(self, registry_with_roles: PluginRegistry) -> None:
        """Test building execution levels for parallel execution."""
        engine = RoleEngine(registry_with_roles)

        order = registry_with_roles.get_execution_order()
        levels = engine._build_execution_levels(order)

        # First level should only have architect (no dependencies)
        assert "architect" in levels[0]

        # Last level should have senior-developer (most dependencies)
        assert "senior-developer" in levels[-1]

    @pytest.mark.asyncio
    async def test_execution_order_respects_dependencies(
        self, registry_with_roles: PluginRegistry
    ) -> None:
        """Test that execution order respects dependencies."""
        engine = RoleEngine(registry_with_roles)

        # Run and collect order
        results = await engine.run_all(parallel=False)

        # Verify all 6 roles completed
        assert len(results) == 6

        # In sequential mode, roles run in topological order
        # Architect is always first
        result_names = list(results.keys())
        assert result_names[0] == "architect"
