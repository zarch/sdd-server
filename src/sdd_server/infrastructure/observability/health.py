"""Health check infrastructure for monitoring service status.

Provides health check registration, execution, and reporting
for monitoring service health and dependencies.
"""

from __future__ import annotations

import asyncio
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence

from sdd_server.utils.logging import get_logger

logger = get_logger(__name__)


class HealthStatus(Enum):
    """Health check status levels."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a health check execution."""

    name: str
    status: HealthStatus
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    duration_ms: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)
    error: Exception | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "duration_ms": self.duration_ms,
            "details": self.details,
            "error": f"{type(self.error).__name__}: {self.error}" if self.error else None,
        }


class HealthCheck(ABC):
    """Abstract base class for health checks."""

    def __init__(
        self,
        name: str,
        description: str = "",
        timeout_seconds: float = 5.0,
        critical: bool = True,
    ) -> None:
        """Initialize health check.

        Args:
            name: Unique name for this health check
            description: Human-readable description
            timeout_seconds: Maximum time for check execution
            critical: If True, failure marks overall health as unhealthy
        """
        self.name = name
        self.description = description
        self.timeout_seconds = timeout_seconds
        self.critical = critical

    @abstractmethod
    def check(self) -> HealthCheckResult:
        """Execute the health check.

        Returns:
            HealthCheckResult with status and details
        """
        ...

    def execute(self) -> HealthCheckResult:
        """Execute health check with timing and error handling."""
        start_time = time.perf_counter()
        try:
            result = self.check()
            result.duration_ms = (time.perf_counter() - start_time) * 1000
            return result
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.exception("health_check_failed", check=self.name)
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Health check raised exception: {e}",
                duration_ms=duration_ms,
                error=e,
            )


class AsyncHealthCheck(HealthCheck):
    """Abstract base class for async health checks."""

    @abstractmethod
    async def check_async(self) -> HealthCheckResult:
        """Execute the health check asynchronously.

        Returns:
            HealthCheckResult with status and details
        """
        ...

    def check(self) -> HealthCheckResult:
        """Synchronous wrapper for async check."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # If we're in an async context, we can't use asyncio.run
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, self.check_async())
                return future.result(timeout=self.timeout_seconds)
        else:
            return asyncio.run(self._check_with_timeout())

    async def _check_with_timeout(self) -> HealthCheckResult:
        """Run check with timeout."""
        try:
            return await asyncio.wait_for(self.check_async(), timeout=self.timeout_seconds)
        except TimeoutError:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Health check timed out after {self.timeout_seconds}s",
            )


class FunctionHealthCheck(HealthCheck):
    """Health check that wraps a simple function."""

    def __init__(
        self,
        name: str,
        check_func: Callable[[], bool | HealthStatus | tuple[HealthStatus, str]],
        description: str = "",
        timeout_seconds: float = 5.0,
        critical: bool = True,
    ) -> None:
        """Initialize function health check.

        Args:
            name: Unique name for this health check
            check_func: Function that returns health status
            description: Human-readable description
            timeout_seconds: Maximum time for check execution
            critical: If True, failure marks overall health as unhealthy
        """
        super().__init__(name, description, timeout_seconds, critical)
        self._check_func = check_func

    def check(self) -> HealthCheckResult:
        """Execute the wrapped function."""
        result = self._check_func()

        if isinstance(result, bool):
            status = HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY
            message = f"Health check {'passed' if result else 'failed'}"
            return HealthCheckResult(name=self.name, status=status, message=message)

        if isinstance(result, HealthStatus):
            return HealthCheckResult(
                name=self.name,
                status=result,
                message=f"Health check returned {result.value}",
            )

        # Tuple of (status, message)
        status, message = result
        return HealthCheckResult(name=self.name, status=status, message=message)


class HealthCheckRegistry:
    """Registry for managing health checks."""

    def __init__(self, name: str = "default") -> None:
        """Initialize the registry.

        Args:
            name: Name for this registry instance
        """
        self.name = name
        self._checks: dict[str, HealthCheck] = {}
        self._lock = threading.Lock()

    def register(self, check: HealthCheck) -> None:
        """Register a health check.

        Args:
            check: HealthCheck instance to register
        """
        with self._lock:
            self._checks[check.name] = check
            logger.debug("health_check_registered", name=check.name)

    def register_function(
        self,
        name: str,
        check_func: Callable[[], bool | HealthStatus | tuple[HealthStatus, str]],
        description: str = "",
        timeout_seconds: float = 5.0,
        critical: bool = True,
    ) -> None:
        """Register a function as a health check.

        Args:
            name: Unique name for this health check
            check_func: Function that returns health status
            description: Human-readable description
            timeout_seconds: Maximum time for check execution
            critical: If True, failure marks overall health as unhealthy
        """
        check = FunctionHealthCheck(
            name=name,
            check_func=check_func,
            description=description,
            timeout_seconds=timeout_seconds,
            critical=critical,
        )
        self.register(check)

    def unregister(self, name: str) -> bool:
        """Unregister a health check.

        Args:
            name: Name of check to unregister

        Returns:
            True if check was found and removed
        """
        with self._lock:
            if name in self._checks:
                del self._checks[name]
                logger.debug("health_check_unregistered", name=name)
                return True
            return False

    def get_check(self, name: str) -> HealthCheck | None:
        """Get a registered health check by name."""
        with self._lock:
            return self._checks.get(name)

    def list_checks(self) -> list[str]:
        """List all registered check names."""
        with self._lock:
            return list(self._checks.keys())

    def run_check(self, name: str) -> HealthCheckResult | None:
        """Run a specific health check.

        Args:
            name: Name of check to run

        Returns:
            HealthCheckResult or None if check not found
        """
        check = self.get_check(name)
        if check is None:
            return None
        return check.execute()

    def run_all_checks(self) -> list[HealthCheckResult]:
        """Run all registered health checks.

        Returns:
            List of all health check results
        """
        results: list[HealthCheckResult] = []
        with self._lock:
            checks = list(self._checks.values())

        for check in checks:
            result = check.execute()
            results.append(result)
            logger.debug(
                "health_check_result",
                name=result.name,
                status=result.status.value,
                duration_ms=result.duration_ms,
            )

        return results

    def run_critical_checks(self) -> list[HealthCheckResult]:
        """Run only critical health checks.

        Returns:
            List of critical health check results
        """
        results: list[HealthCheckResult] = []
        with self._lock:
            checks = [c for c in self._checks.values() if c.critical]

        for check in checks:
            result = check.execute()
            results.append(result)

        return results

    def get_overall_status(self, results: Sequence[HealthCheckResult]) -> HealthStatus:
        """Determine overall health status from results.

        Args:
            results: List of health check results

        Returns:
            Aggregate health status
        """
        if not results:
            return HealthStatus.UNKNOWN

        has_degraded = False

        for result in results:
            check = self.get_check(result.name)
            is_critical = check.critical if check else True

            if result.status == HealthStatus.UNHEALTHY:
                # Only critical unhealthy checks affect overall status
                if is_critical:
                    return HealthStatus.UNHEALTHY
                # Non-critical unhealthy is treated as degraded
                has_degraded = True
            elif result.status == HealthStatus.DEGRADED:
                has_degraded = True

        if has_degraded:
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY

    def create_report(self) -> dict[str, Any]:
        """Create a comprehensive health report.

        Returns:
            Dictionary with overall status and all check results
        """
        results = self.run_all_checks()
        overall = self.get_overall_status(results)

        return {
            "status": overall.value,
            "timestamp": datetime.now(UTC).isoformat(),
            "checks": [r.to_dict() for r in results],
            "summary": {
                "total": len(results),
                "healthy": sum(1 for r in results if r.status == HealthStatus.HEALTHY),
                "degraded": sum(1 for r in results if r.status == HealthStatus.DEGRADED),
                "unhealthy": sum(1 for r in results if r.status == HealthStatus.UNHEALTHY),
                "unknown": sum(1 for r in results if r.status == HealthStatus.UNKNOWN),
            },
        }


# Global health check registry
health_check_registry = HealthCheckRegistry()


def run_health_checks() -> dict[str, Any]:
    """Run all health checks and return report.

    Returns:
        Health report dictionary
    """
    return health_check_registry.create_report()


# Common built-in health checks
class AlwaysHealthyCheck(HealthCheck):
    """Simple health check that always returns healthy."""

    def __init__(self, name: str = "always_healthy") -> None:
        super().__init__(name=name, description="Always returns healthy", critical=False)

    def check(self) -> HealthCheckResult:
        return HealthCheckResult(
            name=self.name,
            status=HealthStatus.HEALTHY,
            message="Basic health check passed",
        )


class FilesystemCheck(HealthCheck):
    """Check if a directory is accessible."""

    def __init__(
        self,
        path: str,
        name: str | None = None,
        check_writable: bool = False,
    ) -> None:
        super().__init__(
            name=name or f"filesystem_{path.replace('/', '_')}",
            description=f"Check filesystem access to {path}",
            critical=True,
        )
        self.path = path
        self.check_writable = check_writable

    def check(self) -> HealthCheckResult:
        import os

        path = self.path
        details: dict[str, Any] = {"path": path}

        if not os.path.exists(path):
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Path does not exist: {path}",
                details=details,
            )

        if not os.path.isdir(path):
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Path is not a directory: {path}",
                details=details,
            )

        if not os.access(path, os.R_OK):
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Path is not readable: {path}",
                details=details,
            )

        if self.check_writable and not os.access(path, os.W_OK):
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.DEGRADED,
                message=f"Path is not writable: {path}",
                details=details,
            )

        # Get disk space info
        try:
            stat = os.statvfs(path)
            free_gb = (stat.f_bavail * stat.f_frsize) / (1024**3)
            total_gb = (stat.f_blocks * stat.f_frsize) / (1024**3)
            used_percent = ((total_gb - free_gb) / total_gb * 100) if total_gb > 0 else 0

            details["free_gb"] = round(free_gb, 2)
            details["total_gb"] = round(total_gb, 2)
            details["used_percent"] = round(used_percent, 1)

            if used_percent > 95:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.DEGRADED,
                    message=f"Disk space critically low: {used_percent:.1f}% used",
                    details=details,
                )
        except OSError:
            pass  # Skip disk space check if not available

        return HealthCheckResult(
            name=self.name,
            status=HealthStatus.HEALTHY,
            message=f"Filesystem check passed for {path}",
            details=details,
        )
