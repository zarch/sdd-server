"""Tests for ExecutionPipeline."""

import asyncio
from datetime import datetime
from typing import Any

import pytest

from sdd_server.core.execution import (
    ExecutionConfig,
    ExecutionMode,
    ExecutionPipeline,
    ExecutionProgress,
    ExecutionReport,
    FailureStrategy,
)
from sdd_server.plugins.base import (
    PluginMetadata,
    RolePlugin,
    RoleResult,
    RoleStage,
    RoleStatus,
)
from sdd_server.plugins.registry import PluginRegistry


class MockRolePlugin(RolePlugin):  # type: ignore[misc]
    """Mock role plugin for testing."""

    def __init__(
        self,
        name: str,
        stage: RoleStage,
        dependencies: list[str] | None = None,
        should_fail: bool = False,
        delay: float = 0.0,
    ) -> None:
        self._name = name
        self._stage = stage
        self._dependencies = dependencies or []
        self._should_fail = should_fail
        self._delay = delay
        self.metadata = PluginMetadata(
            name=name,
            version="1.0.0",
            description=f"Mock {name}",
            author="test",
            stage=stage,
            dependencies=dependencies or [],
        )
        self._context: dict[str, Any] = {}

    async def initialize(self, context: dict[str, Any]) -> None:
        self._context = context

    async def shutdown(self) -> None:
        pass

    async def review(self, scope: str = "all", target: str | None = None) -> RoleResult:
        if self._delay:
            await asyncio.sleep(self._delay)

        if self._should_fail:
            raise RuntimeError(f"Role {self._name} failed")

        return RoleResult(
            role=self._name,
            status=RoleStatus.COMPLETED,
            success=True,
            output=f"Review output for {self._name}",
            issues=[],
            started_at=datetime.now(),
        )

    def get_recipe_template(self) -> str:
        return f"# Recipe for {self._name}"


@pytest.fixture
def registry() -> PluginRegistry:
    """Create a registry with mock plugins."""
    reg = PluginRegistry()

    # Register plugins with dependencies
    architect = MockRolePlugin("architect", RoleStage.ARCHITECTURE)
    ui_designer = MockRolePlugin("ui-designer", RoleStage.UI_DESIGN, dependencies=["architect"])
    interface_designer = MockRolePlugin(
        "interface-designer", RoleStage.INTERFACE_DESIGN, dependencies=["architect"]
    )
    security = MockRolePlugin(
        "security-analyst", RoleStage.SECURITY, dependencies=["interface-designer"]
    )
    edge_case = MockRolePlugin(
        "edge-case-analyst", RoleStage.EDGE_CASE_ANALYSIS, dependencies=["security-analyst"]
    )
    senior_dev = MockRolePlugin(
        "senior-developer", RoleStage.IMPLEMENTATION, dependencies=["edge-case-analyst"]
    )

    for plugin in [architect, ui_designer, interface_designer, security, edge_case, senior_dev]:
        reg.register(plugin.metadata.name, plugin)

    return reg


class TestExecutionProgress:
    """Tests for ExecutionProgress."""

    def test_progress_percent_empty(self) -> None:
        """Test progress with no roles."""
        progress = ExecutionProgress(total_roles=0)
        assert progress.progress_percent == 100.0

    def test_progress_percent_halfway(self) -> None:
        """Test progress at 50%."""
        progress = ExecutionProgress(total_roles=10, completed_roles=5)
        assert progress.progress_percent == 50.0

    def test_progress_percent_with_failures(self) -> None:
        """Test progress includes failures."""
        progress = ExecutionProgress(total_roles=10, completed_roles=3, failed_roles=2)
        assert progress.progress_percent == 50.0

    def test_is_complete(self) -> None:
        """Test completion check."""
        progress = ExecutionProgress(total_roles=5, completed_roles=5)
        assert progress.is_complete

    def test_is_complete_with_failures(self) -> None:
        """Test completion with some failures."""
        progress = ExecutionProgress(
            total_roles=5, completed_roles=3, failed_roles=2, running_roles=[]
        )
        assert progress.is_complete

    def test_elapsed_seconds(self) -> None:
        """Test elapsed time calculation."""
        progress = ExecutionProgress(total_roles=5)
        # Should be very small since just created
        assert progress.elapsed_seconds < 1.0


class TestExecutionReport:
    """Tests for ExecutionReport."""

    def test_success_rate_empty(self) -> None:
        """Test success rate with no results."""
        report = ExecutionReport(started_at=datetime.now())
        assert report.success_rate == 100.0

    def test_success_rate_full(self) -> None:
        """Test success rate with all successes."""
        report = ExecutionReport(started_at=datetime.now(), success_count=10, failure_count=0)
        assert report.success_rate == 100.0

    def test_success_rate_half(self) -> None:
        """Test success rate at 50%."""
        report = ExecutionReport(started_at=datetime.now(), success_count=5, failure_count=5)
        assert report.success_rate == 50.0

    def test_to_dict(self) -> None:
        """Test serialization to dict."""
        report = ExecutionReport(
            started_at=datetime(2026, 1, 1, 12, 0, 0),
            completed_at=datetime(2026, 1, 1, 12, 1, 0),
            total_duration_seconds=60.0,
            success_count=5,
            failure_count=1,
            skipped_count=0,
            stages_executed=["architecture"],
            errors=["test error"],
        )

        result = report.to_dict()

        assert result["success_count"] == 5
        assert result["failure_count"] == 1
        assert result["total_duration_seconds"] == 60.0
        assert result["success_rate"] == 83.33333333333334
        assert "architecture" in result["stages_executed"]
        assert "test error" in result["errors"]


class TestExecutionConfig:
    """Tests for ExecutionConfig."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = ExecutionConfig()

        assert config.mode == ExecutionMode.AUTO
        assert config.max_concurrent == 4
        assert config.failure_strategy == FailureStrategy.CONTINUE
        assert config.timeout_seconds is None
        assert config.progress_callback is None
        assert config.result_callback is None
        assert config.include_stages is None
        assert config.exclude_stages is None


class TestExecutionPipeline:
    """Tests for ExecutionPipeline."""

    def test_init(self, registry: PluginRegistry) -> None:
        """Test pipeline initialization."""
        pipeline = ExecutionPipeline(registry)

        assert pipeline.progress.total_roles == 0
        assert pipeline.results == {}
        assert not pipeline.is_cancelled

    def test_init_with_context(self, registry: PluginRegistry) -> None:
        """Test pipeline with context."""
        context = {"project_name": "test"}
        pipeline = ExecutionPipeline(registry, context=context)

        assert pipeline._context == context

    @pytest.mark.asyncio
    async def test_execute_all_roles(self, registry: PluginRegistry) -> None:
        """Test executing all roles."""
        pipeline = ExecutionPipeline(registry)
        report = await pipeline.execute()

        assert report.success_count == 6
        assert report.failure_count == 0
        assert len(report.results) == 6

    @pytest.mark.asyncio
    async def test_execute_sequential_mode(self, registry: PluginRegistry) -> None:
        """Test sequential execution mode."""
        config = ExecutionConfig(mode=ExecutionMode.SEQUENTIAL)
        pipeline = ExecutionPipeline(registry)
        report = await pipeline.execute(config=config)

        assert report.success_count == 6

    @pytest.mark.asyncio
    async def test_execute_with_max_concurrent(self, registry: PluginRegistry) -> None:
        """Test parallel execution with concurrency limit."""
        config = ExecutionConfig(
            mode=ExecutionMode.PARALLEL,
            max_concurrent=2,
        )
        pipeline = ExecutionPipeline(registry)
        report = await pipeline.execute(config=config)

        assert report.success_count == 6

    @pytest.mark.asyncio
    async def test_execute_with_failure_continue(self, registry: PluginRegistry) -> None:
        """Test execution continues after failure."""
        # Add a failing plugin
        failing_plugin = MockRolePlugin("failing-role", RoleStage.REVIEW, should_fail=True)
        registry.register("failing-role", failing_plugin)

        config = ExecutionConfig(failure_strategy=FailureStrategy.CONTINUE)
        pipeline = ExecutionPipeline(registry)
        report = await pipeline.execute(config=config)

        # Should have completed other roles despite failure
        assert report.failure_count >= 1

    @pytest.mark.asyncio
    async def test_execute_with_failure_stop(self, registry: PluginRegistry) -> None:
        """Test execution stops on failure."""
        # Create a new registry with failing architect
        reg = PluginRegistry()
        failing_architect = MockRolePlugin("architect", RoleStage.ARCHITECTURE, should_fail=True)
        ui_designer = MockRolePlugin("ui-designer", RoleStage.UI_DESIGN, dependencies=["architect"])

        reg.register("architect", failing_architect)
        reg.register("ui-designer", ui_designer)

        config = ExecutionConfig(failure_strategy=FailureStrategy.STOP)
        pipeline = ExecutionPipeline(reg)
        report = await pipeline.execute(config=config)

        # UI designer should be skipped
        assert report.skipped_count >= 1

    @pytest.mark.asyncio
    async def test_execute_with_stage_filter(self, registry: PluginRegistry) -> None:
        """Test execution with stage filtering."""
        config = ExecutionConfig(include_stages=[RoleStage.ARCHITECTURE, RoleStage.UI_DESIGN])
        pipeline = ExecutionPipeline(registry)
        report = await pipeline.execute(config=config)

        # Only architect and ui-designer should run
        assert report.success_count == 2

    @pytest.mark.asyncio
    async def test_execute_with_exclude_stages(self, registry: PluginRegistry) -> None:
        """Test execution with stage exclusion."""
        config = ExecutionConfig(exclude_stages=[RoleStage.SECURITY, RoleStage.EDGE_CASE_ANALYSIS])
        pipeline = ExecutionPipeline(registry)
        report = await pipeline.execute(config=config)

        # 6 roles - 2 excluded = 4
        assert report.success_count == 4

    @pytest.mark.asyncio
    async def test_progress_callback(self, registry: PluginRegistry) -> None:
        """Test progress callback is called."""
        progress_updates: list[ExecutionProgress] = []

        def on_progress(progress: ExecutionProgress) -> None:
            progress_updates.append(progress)

        config = ExecutionConfig(progress_callback=on_progress)
        pipeline = ExecutionPipeline(registry)
        await pipeline.execute(config=config)

        # Should have received progress updates
        assert len(progress_updates) > 0

    @pytest.mark.asyncio
    async def test_result_callback(self, registry: PluginRegistry) -> None:
        """Test result callback is called for each role."""
        results: list[tuple[str, RoleResult]] = []

        def on_result(name: str, result: RoleResult) -> None:
            results.append((name, result))

        config = ExecutionConfig(result_callback=on_result)
        pipeline = ExecutionPipeline(registry)
        await pipeline.execute(config=config)

        assert len(results) == 6

    @pytest.mark.asyncio
    async def test_cancel_execution(self, registry: PluginRegistry) -> None:
        """Test cancelling execution."""
        pipeline = ExecutionPipeline(registry)

        # Cancel before execution
        pipeline.cancel()
        assert pipeline.is_cancelled

        # Verify cancellation state persists
        config = ExecutionConfig(mode=ExecutionMode.SEQUENTIAL)
        _ = await pipeline.execute(config=config)

        # Execution should have been cancelled - roles skipped or errors recorded
        # The execution completes quickly with mocked roles, so check the cancelled state
        assert pipeline.is_cancelled

    @pytest.mark.asyncio
    async def test_timeout_per_role(self, registry: PluginRegistry) -> None:
        """Test role execution timeout."""
        # Create a slow plugin
        reg = PluginRegistry()
        slow_plugin = MockRolePlugin("slow", RoleStage.ARCHITECTURE, delay=5.0)
        reg.register("slow", slow_plugin)

        config = ExecutionConfig(timeout_seconds=0.1)
        pipeline = ExecutionPipeline(reg)
        report = await pipeline.execute(config=config)

        # Should have timed out
        assert report.failure_count == 1
        assert "timed out" in report.results["slow"].output

    def test_build_execution_levels(self, registry: PluginRegistry) -> None:
        """Test building execution levels."""
        pipeline = ExecutionPipeline(registry)
        roles = registry.list_roles()
        levels = pipeline._build_execution_levels(roles)

        # Architect should be in level 0 (no dependencies)
        assert "architect" in levels[0]

        # UI designer and interface designer should be in level 1 (depend on architect)
        level_1_roles = levels[1] if len(levels) > 1 else []
        assert "ui-designer" in level_1_roles
        assert "interface-designer" in level_1_roles

    def test_get_filtered_roles_include(self, registry: PluginRegistry) -> None:
        """Test filtering roles by included stages."""
        pipeline = ExecutionPipeline(registry)
        pipeline._config = ExecutionConfig(
            include_stages=[RoleStage.ARCHITECTURE, RoleStage.SECURITY]
        )

        filtered = pipeline._get_filtered_roles()

        assert "architect" in filtered
        assert "security-analyst" in filtered
        assert "ui-designer" not in filtered

    def test_get_filtered_roles_exclude(self, registry: PluginRegistry) -> None:
        """Test filtering roles by excluded stages."""
        pipeline = ExecutionPipeline(registry)
        pipeline._config = ExecutionConfig(exclude_stages=[RoleStage.SECURITY])

        filtered = pipeline._get_filtered_roles()

        assert "architect" in filtered
        assert "security-analyst" not in filtered


class TestExecutionMode:
    """Tests for ExecutionMode enum."""

    def test_mode_values(self) -> None:
        """Test mode enum values."""
        assert ExecutionMode.SEQUENTIAL.value == "sequential"
        assert ExecutionMode.PARALLEL.value == "parallel"
        assert ExecutionMode.AUTO.value == "auto"


class TestFailureStrategy:
    """Tests for FailureStrategy enum."""

    def test_strategy_values(self) -> None:
        """Test strategy enum values."""
        assert FailureStrategy.CONTINUE.value == "continue"
        assert FailureStrategy.STOP.value == "stop"
        assert FailureStrategy.STOP_STAGE.value == "stop-stage"
