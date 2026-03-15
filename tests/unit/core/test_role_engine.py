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

    # Register in dependency order (spec-linter must come before architect)
    for name in [
        "spec-linter",
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

        # Should have 7 results
        assert len(results) == 7

        # All roles should be completed
        assert len(engine.completed_roles) == 7
        assert len(engine.failed_roles) == 0

    @pytest.mark.asyncio
    async def test_run_all_parallel(self, registry_with_roles: PluginRegistry) -> None:
        """Test running all roles in parallel."""
        engine = RoleEngine(registry_with_roles)

        results = await engine.run_all(parallel=True)

        # Should have 7 results
        assert len(results) == 7

        # All roles should be completed
        assert len(engine.completed_roles) == 7

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
        assert status["total_results"] == 7
        assert len(status["completed"]) == 7
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

        # Spec-linter has no dependencies (first in chain)
        assert graph["spec-linter"] == []
        # Architect depends on spec-linter
        assert graph["architect"] == ["spec-linter"]

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

        # First level should only have spec-linter (no dependencies)
        assert "spec-linter" in levels[0]
        # Architect is in the second level (depends on spec-linter)
        assert "architect" in levels[1]

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

        # Verify all 7 roles completed
        assert len(results) == 7

        # In sequential mode, roles run in topological order
        # Spec-linter is always first (no dependencies, priority 5)
        result_names = list(results.keys())
        assert result_names[0] == "spec-linter"
        # Architect follows spec-linter
        assert result_names.index("architect") > result_names.index("spec-linter")

    @pytest.mark.asyncio
    async def test_update_context_merges_values(self, registry_with_roles: PluginRegistry) -> None:
        """update_context() merges keys into engine context."""
        engine = RoleEngine(registry_with_roles, context={"project_root": "/initial"})
        engine.update_context({"project_root": "/updated", "extra": "value"})

        assert engine._context["project_root"] == "/updated"
        assert engine._context["extra"] == "value"

    @pytest.mark.asyncio
    async def test_update_context_does_not_clear_existing(
        self, registry_with_roles: PluginRegistry
    ) -> None:
        """update_context() is additive, not a full replacement."""
        engine = RoleEngine(registry_with_roles, context={"existing_key": "kept"})
        engine.update_context({"new_key": "added"})

        assert engine._context["existing_key"] == "kept"
        assert engine._context["new_key"] == "added"

    @pytest.mark.asyncio
    async def test_update_context_propagates_to_roles(
        self, registry_with_roles: PluginRegistry
    ) -> None:
        """Context injected via update_context() reaches role.initialize()."""
        from unittest.mock import AsyncMock, patch

        engine = RoleEngine(registry_with_roles)
        engine.update_context({"project_root": "/test/project"})

        # Run just the architect role so it calls initialize with our context
        with patch.object(
            registry_with_roles.get_role("architect"),
            "initialize",
            new_callable=AsyncMock,
        ) as mock_init:
            mock_init.return_value = None
            # Patch review too so it doesn't crash
            with patch.object(
                registry_with_roles.get_role("architect"),
                "review",
                new_callable=AsyncMock,
            ) as mock_review:
                from datetime import datetime

                from sdd_server.plugins.base import RoleResult, RoleStatus

                mock_review.return_value = RoleResult(
                    role="architect",
                    status=RoleStatus.COMPLETED,
                    success=True,
                    output="mocked",
                    started_at=datetime.now(),
                )
                await engine.run_roles(["architect"])

            mock_init.assert_called_once()
            ctx_passed = mock_init.call_args[0][0]
            assert ctx_passed.get("project_root") == "/test/project"
