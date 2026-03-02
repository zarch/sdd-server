"""Role engine for orchestrating role execution.

The RoleEngine manages:
- Dependency graph resolution
- Sequential and parallel role execution
- Stage progression through the workflow
- Result aggregation and reporting

Architecture reference: arch.md Section 5.1
"""

import asyncio
from datetime import datetime
from typing import Any

from sdd_server.plugins.base import (
    PluginError,
    RoleResult,
    RoleStage,
    RoleStatus,
)
from sdd_server.plugins.registry import PluginRegistry
from sdd_server.utils.logging import get_logger

logger = get_logger(__name__)


class RoleEngine:
    """Orchestrates role execution based on dependencies and stages.

    The RoleEngine coordinates running multiple role plugins in the
    correct order based on their dependencies. It supports:
    - Sequential execution for dependent roles
    - Parallel execution for independent roles at the same stage
    - Stage-based progression through the workflow
    - Result aggregation and error handling

    Usage:
        registry = PluginRegistry()
        # ... register plugins ...

        engine = RoleEngine(registry)

        # Run all roles in dependency order
        results = await engine.run_all()

        # Run specific roles
        results = await engine.run_roles(["architect", "security-analyst"])

        # Run roles for a specific stage
        results = await engine.run_stage(RoleStage.ARCHITECTURE)
    """

    def __init__(self, registry: PluginRegistry, context: dict[str, Any] | None = None) -> None:
        """Initialize the role engine.

        Args:
            registry: Plugin registry with registered roles
            context: Optional context dict passed to role plugins
        """
        self._registry = registry
        self._context = context or {}
        self._results: dict[str, RoleResult] = {}
        self._running: set[str] = set()
        self._completed: set[str] = set()
        self._failed: set[str] = set()

    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------

    @property
    def results(self) -> dict[str, RoleResult]:
        """Get all role results."""
        return self._results.copy()

    @property
    def completed_roles(self) -> set[str]:
        """Get set of completed role names."""
        return self._completed.copy()

    @property
    def failed_roles(self) -> set[str]:
        """Get set of failed role names."""
        return self._failed.copy()

    # -------------------------------------------------------------------------
    # Execution Methods
    # -------------------------------------------------------------------------

    async def run_all(
        self,
        scope: str = "all",
        target: str | None = None,
        parallel: bool = True,
    ) -> dict[str, RoleResult]:
        """Run all registered roles in dependency order.

        Args:
            scope: Review scope - "specs", "code", or "all"
            target: Optional feature name to focus on
            parallel: Whether to run independent roles in parallel

        Returns:
            Dictionary of role name to RoleResult
        """
        # Get execution order
        order = self._registry.get_execution_order()
        logger.info(
            "Starting role execution",
            roles=order,
            parallel=parallel,
        )

        # Clear previous state
        self._results.clear()
        self._running.clear()
        self._completed.clear()
        self._failed.clear()

        if parallel:
            await self._execute_parallel(order, scope, target)
        else:
            await self._execute_sequential(order, scope, target)

        logger.info(
            "Role execution complete",
            completed=len(self._completed),
            failed=len(self._failed),
        )

        return self._results

    async def run_roles(
        self,
        role_names: list[str],
        scope: str = "all",
        target: str | None = None,
        parallel: bool = True,
    ) -> dict[str, RoleResult]:
        """Run specific roles in dependency order.

        Args:
            role_names: List of role names to run
            scope: Review scope
            target: Optional feature name
            parallel: Whether to run independent roles in parallel

        Returns:
            Dictionary of role name to RoleResult
        """
        # Get execution order for specified roles
        order = self._registry.get_execution_order(role_names)
        logger.info(
            "Running specific roles",
            roles=order,
            parallel=parallel,
        )

        # Clear previous state for these roles
        for name in role_names:
            self._results.pop(name, None)
            self._completed.discard(name)
            self._failed.discard(name)

        if parallel:
            await self._execute_parallel(order, scope, target)
        else:
            await self._execute_sequential(order, scope, target)

        return {name: self._results[name] for name in role_names if name in self._results}

    async def run_stage(
        self,
        stage: RoleStage,
        scope: str = "all",
        target: str | None = None,
    ) -> dict[str, RoleResult]:
        """Run all roles for a specific stage.

        Args:
            stage: Workflow stage to run
            scope: Review scope
            target: Optional feature name

        Returns:
            Dictionary of role name to RoleResult
        """
        roles = self._registry.get_roles_by_stage(stage)
        role_names = [r.metadata.name for r in roles]

        if not role_names:
            logger.info("No roles for stage", stage=stage)
            return {}

        logger.info(
            "Running stage",
            stage=stage,
            roles=role_names,
        )

        # Run roles for this stage (they should be independent within stage)
        results = await self.run_roles(role_names, scope, target, parallel=True)

        return results

    # -------------------------------------------------------------------------
    # Execution Helpers
    # -------------------------------------------------------------------------

    async def _execute_sequential(
        self,
        order: list[str],
        scope: str,
        target: str | None,
    ) -> None:
        """Execute roles sequentially in order."""
        for name in order:
            await self._run_single_role(name, scope, target)

    async def _execute_parallel(
        self,
        order: list[str],
        scope: str,
        target: str | None,
    ) -> None:
        """Execute roles with parallel execution where possible.

        Roles are grouped by their "level" in the dependency graph.
        Roles at the same level can run in parallel.
        """
        # Build levels based on dependencies
        levels = self._build_execution_levels(order)

        for level_num, level_roles in enumerate(levels):
            logger.debug(
                "Executing level",
                level=level_num,
                roles=level_roles,
            )

            # Run all roles at this level in parallel
            tasks = [self._run_single_role(name, scope, target) for name in level_roles]
            await asyncio.gather(*tasks, return_exceptions=True)

    def _build_execution_levels(self, order: list[str]) -> list[list[str]]:
        """Build execution levels for parallel execution.

        Each level contains roles that can run in parallel because
        all their dependencies have been completed in previous levels.

        Args:
            order: Topologically sorted role names

        Returns:
            List of levels, where each level is a list of role names
        """
        levels: list[list[str]] = []
        assigned: set[str] = set()

        while len(assigned) < len(order):
            # Find roles whose dependencies are all assigned
            level: list[str] = []
            for name in order:
                if name in assigned:
                    continue
                deps = self._registry.get_role_dependencies(name)
                # Only consider dependencies in our order list
                deps_in_order = [d for d in deps if d in order]
                if all(d in assigned for d in deps_in_order):
                    level.append(name)

            if not level:
                # This shouldn't happen with valid topological order
                remaining = [n for n in order if n not in assigned]
                raise PluginError(f"Cannot build levels for: {remaining}")

            levels.append(level)
            assigned.update(level)

        return levels

    async def _run_single_role(
        self,
        name: str,
        scope: str,
        target: str | None,
    ) -> RoleResult:
        """Run a single role and record the result.

        Args:
            name: Role name
            scope: Review scope
            target: Optional feature name

        Returns:
            RoleResult from the role execution
        """
        role = self._registry.get_role(name)
        if role is None:
            raise PluginError(f"Role not found: {name}")

        self._running.add(name)
        started_at = datetime.now()

        logger.info(
            "Running role",
            role=name,
            scope=scope,
            target=target,
        )

        try:
            # Ensure role is initialized with context
            await role.initialize(self._context)

            # Run the role review
            result = await role.review(scope=scope, target=target)

            # Update result metadata
            result.started_at = started_at
            result.mark_completed(success=result.success)

            self._results[name] = result
            self._completed.add(name)

            logger.info(
                "Role completed",
                role=name,
                success=result.success,
                issues=len(result.issues),
            )

        except Exception as e:
            # Create a failed result
            result = RoleResult(
                role=name,
                status=RoleStatus.FAILED,
                success=False,
                output=f"Role execution failed: {e}",
                issues=[str(e)],
                started_at=started_at,
            )
            result.mark_completed(success=False)

            self._results[name] = result
            self._failed.add(name)

            logger.error(
                "Role failed",
                role=name,
                error=str(e),
            )

        finally:
            self._running.discard(name)

        return result

    # -------------------------------------------------------------------------
    # Status Methods
    # -------------------------------------------------------------------------

    def get_status(self) -> dict[str, Any]:
        """Get current execution status.

        Returns:
            Status dictionary with counts and role states
        """
        return {
            "running": list(self._running),
            "completed": list(self._completed),
            "failed": list(self._failed),
            "total_results": len(self._results),
            "success_count": sum(1 for r in self._results.values() if r.success),
            "failure_count": sum(1 for r in self._results.values() if not r.success),
        }

    def get_summary(self) -> str:
        """Get a human-readable summary of results.

        Returns:
            Summary string
        """
        lines = ["Role Execution Summary", "=" * 40]

        for name, result in self._results.items():
            status = "✓" if result.success else "✗"
            issues = f" ({len(result.issues)} issues)" if result.issues else ""
            lines.append(f"  {status} {name}{issues}")

        success_rate = len(self._completed) / len(self._results) * 100 if self._results else 0
        lines.append(f"\nSuccess rate: {success_rate:.0f}%")

        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # Dependency Graph Methods
    # -------------------------------------------------------------------------

    def get_dependency_graph(self) -> dict[str, list[str]]:
        """Get the role dependency graph.

        Returns:
            Dictionary mapping role name to list of dependencies
        """
        graph: dict[str, list[str]] = {}
        for name in self._registry.list_roles():
            graph[name] = self._registry.get_role_dependencies(name)
        return graph

    def get_dependents(self, role_name: str) -> list[str]:
        """Get roles that depend on a given role.

        Args:
            role_name: Role name to find dependents for

        Returns:
            List of role names that depend on the given role
        """
        dependents: list[str] = []
        for name in self._registry.list_roles():
            deps = self._registry.get_role_dependencies(name)
            if role_name in deps:
                dependents.append(name)
        return dependents
