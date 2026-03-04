"""Role execution pipeline with parallel execution and progress tracking.

The execution module provides:
- Concurrency-controlled parallel execution
- Progress callbacks for monitoring
- Graceful cancellation support
- Enhanced result aggregation and reporting

Architecture reference: arch.md Section 5.3
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from sdd_server.plugins.base import (
    RoleResult,
    RoleStage,
    RoleStatus,
)
from sdd_server.plugins.registry import PluginRegistry
from sdd_server.utils.logging import get_logger

logger = get_logger(__name__)

# Type aliases
ProgressCallback = Callable[["ExecutionProgress"], None]
ResultCallback = Callable[[str, RoleResult], None]


class ExecutionMode(StrEnum):
    """Execution mode for the pipeline."""

    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    AUTO = "auto"  # Parallel with concurrency control


class FailureStrategy(StrEnum):
    """How to handle role failures during execution."""

    CONTINUE = "continue"  # Continue running other roles
    STOP = "stop"  # Stop execution on first failure
    STOP_STAGE = "stop-stage"  # Stop current stage but continue others


@dataclass
class ExecutionProgress:
    """Progress information for execution pipeline."""

    total_roles: int
    completed_roles: int = 0
    failed_roles: int = 0
    running_roles: list[str] = field(default_factory=list)
    current_stage: str | None = None
    started_at: datetime = field(default_factory=datetime.now)
    estimated_remaining_seconds: float | None = None

    @property
    def progress_percent(self) -> float:
        """Calculate progress percentage."""
        if self.total_roles == 0:
            return 100.0
        processed = self.completed_roles + self.failed_roles
        return (processed / self.total_roles) * 100

    @property
    def elapsed_seconds(self) -> float:
        """Calculate elapsed time in seconds."""
        return (datetime.now() - self.started_at).total_seconds()

    @property
    def is_complete(self) -> bool:
        """Check if execution is complete."""
        processed = self.completed_roles + self.failed_roles
        return processed >= self.total_roles and len(self.running_roles) == 0


@dataclass
class ExecutionConfig:
    """Configuration for the execution pipeline."""

    mode: ExecutionMode = ExecutionMode.AUTO
    max_concurrent: int = 4
    failure_strategy: FailureStrategy = FailureStrategy.CONTINUE
    timeout_seconds: float | None = None
    progress_callback: ProgressCallback | None = None
    result_callback: ResultCallback | None = None
    include_stages: list[RoleStage] | None = None
    exclude_stages: list[RoleStage] | None = None


@dataclass
class ExecutionReport:
    """Comprehensive execution report."""

    started_at: datetime
    completed_at: datetime | None = None
    total_duration_seconds: float | None = None
    results: dict[str, RoleResult] = field(default_factory=dict)
    success_count: int = 0
    failure_count: int = 0
    skipped_count: int = 0
    stages_executed: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        total = self.success_count + self.failure_count
        if total == 0:
            return 100.0
        return (self.success_count / total) * 100

    def to_dict(self) -> dict[str, Any]:
        """Convert report to dictionary for serialization."""
        return {
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "total_duration_seconds": self.total_duration_seconds,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "skipped_count": self.skipped_count,
            "success_rate": self.success_rate,
            "stages_executed": self.stages_executed,
            "errors": self.errors,
            "roles": {
                name: {
                    "success": result.success,
                    "status": result.status,
                    "issues_count": len(result.issues),
                    "duration_seconds": result.duration_seconds,
                }
                for name, result in self.results.items()
            },
        }


class ExecutionPipeline:
    """Advanced execution pipeline for role plugins.

    The ExecutionPipeline provides enhanced execution capabilities:
    - Concurrency control with semaphores
    - Progress tracking and callbacks
    - Configurable failure handling
    - Timeout support
    - Stage filtering
    - Comprehensive reporting
    """

    def __init__(
        self,
        registry: PluginRegistry,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the execution pipeline.

        Args:
            registry: Plugin registry with registered roles
            context: Optional context dict passed to role plugins
        """
        self._registry = registry
        self._context = context or {}
        self._cancel_event = asyncio.Event()
        self._progress = ExecutionProgress(total_roles=0)
        self._results: dict[str, RoleResult] = {}
        self._config = ExecutionConfig()

    @property
    def progress(self) -> ExecutionProgress:
        """Get current execution progress."""
        return self._progress

    @property
    def results(self) -> dict[str, RoleResult]:
        """Get all role results."""
        return self._results.copy()

    @property
    def is_cancelled(self) -> bool:
        """Check if execution has been cancelled."""
        return self._cancel_event.is_set()

    async def execute(
        self,
        config: ExecutionConfig | None = None,
        scope: str = "all",
        target: str | None = None,
    ) -> ExecutionReport:
        """Execute all roles with the given configuration.

        Args:
            config: Execution configuration (uses defaults if None)
            scope: Review scope - "specs", "code", or "all"
            target: Optional feature name to focus on

        Returns:
            ExecutionReport with comprehensive results
        """
        self._config = config or ExecutionConfig()
        # Check if already cancelled before clearing
        was_cancelled = self._cancel_event.is_set()
        self._cancel_event.clear()
        if was_cancelled:
            self._cancel_event.set()  # Preserve cancelled state

        role_names = self._get_filtered_roles()
        self._progress = ExecutionProgress(total_roles=len(role_names))
        self._results.clear()

        report = ExecutionReport(started_at=datetime.now())

        logger.info(
            "Starting execution pipeline",
            mode=self._config.mode,
            roles=role_names,
            max_concurrent=self._config.max_concurrent,
        )

        try:
            levels = self._build_execution_levels(role_names)

            if self._config.mode == ExecutionMode.SEQUENTIAL:
                await self._execute_sequential(levels, scope, target, report)
            else:
                await self._execute_parallel(levels, scope, target, report)

        except asyncio.CancelledError:
            logger.info("Execution cancelled")
            report.errors.append("Execution cancelled by user")

        finally:
            report.completed_at = datetime.now()
            report.total_duration_seconds = (
                report.completed_at - report.started_at
            ).total_seconds()
            report.results = self._results.copy()

            for result in self._results.values():
                if result.status == RoleStatus.COMPLETED:
                    if result.success:
                        report.success_count += 1
                    else:
                        report.failure_count += 1
                elif result.status in (RoleStatus.SKIPPED, RoleStatus.FAILED):
                    report.failure_count += 1

        logger.info(
            "Execution complete",
            success=report.success_count,
            failed=report.failure_count,
            duration=report.total_duration_seconds,
        )

        return report

    def cancel(self) -> None:
        """Cancel the current execution."""
        logger.info("Cancellation requested")
        self._cancel_event.set()

    def _get_filtered_roles(self) -> list[str]:
        """Get role names filtered by stage configuration."""
        all_roles = self._registry.list_roles()

        if self._config.include_stages:
            filtered: list[str] = []
            for name in all_roles:
                role = self._registry.get_role(name)
                if role and role.metadata.stage in self._config.include_stages:
                    filtered.append(name)
            return filtered

        if self._config.exclude_stages:
            filtered_results: list[str] = []
            for name in all_roles:
                role = self._registry.get_role(name)
                if role and role.metadata.stage not in self._config.exclude_stages:
                    filtered_results.append(name)
            return filtered_results

        return list(all_roles)

    def _build_execution_levels(self, role_names: list[str]) -> list[list[str]]:
        """Build execution levels for parallel execution."""
        levels: list[list[str]] = []
        assigned: set[str] = set()

        while len(assigned) < len(role_names):
            level: list[str] = []
            for name in role_names:
                if name in assigned:
                    continue
                deps = self._registry.get_role_dependencies(name)
                deps_in_scope = [d for d in deps if d in role_names]
                if all(d in assigned for d in deps_in_scope):
                    level.append(name)

            if not level:
                remaining = [n for n in role_names if n not in assigned]
                logger.error("Cannot build levels", remaining=remaining)
                break

            levels.append(level)
            assigned.update(level)

        return levels

    async def _execute_sequential(
        self,
        levels: list[list[str]],
        scope: str,
        target: str | None,
        report: ExecutionReport,
    ) -> None:
        """Execute roles sequentially level by level."""
        for level_roles in levels:
            if self.is_cancelled:
                break

            for name in level_roles:
                if self.is_cancelled:
                    break

                result = await self._run_role(name, scope, target)

                if not result.success and self._config.failure_strategy == FailureStrategy.STOP:
                    logger.info("Stopping execution due to failure", role=name)
                    self._skip_remaining(levels, level_roles, name, report)
                    return

    async def _execute_parallel(
        self,
        levels: list[list[str]],
        scope: str,
        target: str | None,
        report: ExecutionReport,
    ) -> None:
        """Execute roles with parallel execution and concurrency control."""
        semaphore = asyncio.Semaphore(self._config.max_concurrent)

        for level_idx, level_roles in enumerate(levels):
            if self.is_cancelled:
                break

            self._progress.current_stage = f"Level {level_idx + 1}"
            self._progress.running_roles = level_roles.copy()
            self._notify_progress()

            tasks = [
                self._run_role_with_semaphore(semaphore, name, scope, target)
                for name in level_roles
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for name, result in zip(level_roles, results, strict=False):
                if isinstance(result, Exception):
                    logger.error("Role execution error", role=name, error=str(result))
                    report.errors.append(f"{name}: {result}")
                    continue

                if (
                    isinstance(result, RoleResult)
                    and not result.success
                    and self._config.failure_strategy == FailureStrategy.STOP
                ):
                    logger.info("Stopping execution due to failure", role=name)
                    self.cancel()
                    break

            if self.is_cancelled:
                self._skip_remaining(
                    levels, level_roles, level_roles[-1] if level_roles else "", report
                )

    async def _run_role_with_semaphore(
        self,
        semaphore: asyncio.Semaphore,
        name: str,
        scope: str,
        target: str | None,
    ) -> RoleResult:
        """Run a role with semaphore for concurrency control."""
        async with semaphore:
            return await self._run_role(name, scope, target)

    async def _run_role(
        self,
        name: str,
        scope: str,
        target: str | None,
    ) -> RoleResult:
        """Run a single role and track progress."""
        if self.is_cancelled:
            return self._create_skipped_result(name, "Execution cancelled")

        role = self._registry.get_role(name)
        if role is None:
            return self._create_failed_result(name, f"Role not found: {name}")

        started_at = datetime.now()
        self._progress.running_roles = [name]
        self._notify_progress()

        logger.info("Running role", role=name, scope=scope, target=target)

        try:
            if self._config.timeout_seconds:
                result = await asyncio.wait_for(
                    self._execute_role(role, scope, target),
                    timeout=self._config.timeout_seconds,
                )
            else:
                result = await self._execute_role(role, scope, target)

            result.started_at = started_at
            result.mark_completed(success=result.success)

            self._results[name] = result

            if result.success:
                self._progress.completed_roles += 1
            else:
                self._progress.failed_roles += 1

            if self._config.result_callback:
                self._config.result_callback(name, result)

            logger.info(
                "Role completed",
                role=name,
                success=result.success,
                issues=len(result.issues),
            )

            return result

        except TimeoutError:
            result = self._create_failed_result(
                name, f"Role timed out after {self._config.timeout_seconds}s"
            )
            result.started_at = started_at
            result.mark_completed(success=False)
            self._results[name] = result
            self._progress.failed_roles += 1
            return result

        except Exception as e:
            result = self._create_failed_result(name, str(e))
            result.started_at = started_at
            result.mark_completed(success=False)
            self._results[name] = result
            self._progress.failed_roles += 1
            logger.error("Role failed", role=name, error=str(e))
            return result

    async def _execute_role(
        self,
        role: Any,
        scope: str,
        target: str | None,
    ) -> RoleResult:
        """Execute a role plugin."""
        await role.initialize(self._context)
        result: RoleResult = await role.review(scope=scope, target=target)
        return result

    def _skip_remaining(
        self,
        levels: list[list[str]],
        current_level: list[str],
        after_role: str,
        report: ExecutionReport,
    ) -> None:
        """Skip remaining roles after cancellation or failure."""
        skip = False
        for level_roles in levels:
            for name in level_roles:
                if skip and name not in self._results:
                    result = self._create_skipped_result(name, "Skipped due to earlier failure")
                    self._results[name] = result
                    report.skipped_count += 1
                if name == after_role:
                    skip = True

    def _create_skipped_result(self, name: str, reason: str) -> RoleResult:
        """Create a skipped result."""
        return RoleResult(
            role=name,
            status=RoleStatus.SKIPPED,
            success=False,
            output=reason,
            issues=[],
            started_at=datetime.now(),
        )

    def _create_failed_result(self, name: str, error: str) -> RoleResult:
        """Create a failed result."""
        return RoleResult(
            role=name,
            status=RoleStatus.FAILED,
            success=False,
            output=error,
            issues=[error],
            started_at=datetime.now(),
        )

    def _notify_progress(self) -> None:
        """Notify progress callback if configured."""
        if self._config.progress_callback:
            self._config.progress_callback(self._progress)
