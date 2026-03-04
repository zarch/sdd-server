"""Tests for health check infrastructure."""

from __future__ import annotations

import tempfile

from sdd_server.infrastructure.observability.health import (
    AlwaysHealthyCheck,
    FilesystemCheck,
    FunctionHealthCheck,
    HealthCheckRegistry,
    HealthCheckResult,
    HealthStatus,
    health_check_registry,
    run_health_checks,
)


class TestHealthCheckResult:
    """Tests for HealthCheckResult."""

    def test_to_dict(self) -> None:
        result = HealthCheckResult(
            name="test_check",
            status=HealthStatus.HEALTHY,
            message="All good",
            duration_ms=10.5,
            details={"key": "value"},
        )
        d = result.to_dict()

        assert d["name"] == "test_check"
        assert d["status"] == "healthy"
        assert d["message"] == "All good"
        assert d["duration_ms"] == 10.5
        assert d["details"] == {"key": "value"}
        assert d["error"] is None

    def test_to_dict_with_error(self) -> None:
        result = HealthCheckResult(
            name="test_check",
            status=HealthStatus.UNHEALTHY,
            message="Failed",
            error=RuntimeError("Something went wrong"),
        )
        d = result.to_dict()
        assert "RuntimeError" in d["error"]


class TestFunctionHealthCheck:
    """Tests for FunctionHealthCheck."""

    def test_bool_true_returns_healthy(self) -> None:
        check = FunctionHealthCheck(name="bool_check", check_func=lambda: True)
        result = check.execute()

        assert result.status == HealthStatus.HEALTHY
        assert "passed" in result.message.lower()

    def test_bool_false_returns_unhealthy(self) -> None:
        check = FunctionHealthCheck(name="bool_check", check_func=lambda: False)
        result = check.execute()

        assert result.status == HealthStatus.UNHEALTHY
        assert "failed" in result.message.lower()

    def test_status_return(self) -> None:
        check = FunctionHealthCheck(
            name="status_check",
            check_func=lambda: HealthStatus.DEGRADED,
        )
        result = check.execute()

        assert result.status == HealthStatus.DEGRADED

    def test_tuple_return(self) -> None:
        check = FunctionHealthCheck(
            name="tuple_check",
            check_func=lambda: (HealthStatus.UNHEALTHY, "Disk full"),
        )
        result = check.execute()

        assert result.status == HealthStatus.UNHEALTHY
        assert result.message == "Disk full"

    def test_exception_handling(self) -> None:
        def raise_error() -> bool:
            raise ValueError("Test error")

        check = FunctionHealthCheck(name="error_check", check_func=raise_error)
        result = check.execute()

        assert result.status == HealthStatus.UNHEALTHY
        assert result.error is not None


class TestHealthCheckRegistry:
    """Tests for HealthCheckRegistry."""

    def test_register_and_list(self) -> None:
        registry = HealthCheckRegistry(name="test_registry")
        check = AlwaysHealthyCheck(name="check1")
        registry.register(check)

        assert "check1" in registry.list_checks()

    def test_unregister(self) -> None:
        registry = HealthCheckRegistry(name="test_registry")
        check = AlwaysHealthyCheck(name="check1")
        registry.register(check)
        registry.unregister("check1")

        assert "check1" not in registry.list_checks()

    def test_register_function(self) -> None:
        registry = HealthCheckRegistry(name="test_registry")
        registry.register_function("func_check", lambda: True)

        assert "func_check" in registry.list_checks()

    def test_run_check(self) -> None:
        registry = HealthCheckRegistry(name="test_registry")
        registry.register_function("check1", lambda: True)
        result = registry.run_check("check1")

        assert result is not None
        assert result.status == HealthStatus.HEALTHY

    def test_run_check_not_found(self) -> None:
        registry = HealthCheckRegistry(name="test_registry")
        result = registry.run_check("nonexistent")

        assert result is None

    def test_run_all_checks(self) -> None:
        registry = HealthCheckRegistry(name="test_registry")
        registry.register_function("check1", lambda: True)
        registry.register_function("check2", lambda: False)

        results = registry.run_all_checks()
        assert len(results) == 2

    def test_get_overall_status_all_healthy(self) -> None:
        registry = HealthCheckRegistry(name="test_registry")
        registry.register_function("check1", lambda: True, critical=True)
        registry.register_function("check2", lambda: True, critical=True)

        results = registry.run_all_checks()
        status = registry.get_overall_status(results)

        assert status == HealthStatus.HEALTHY

    def test_get_overall_status_critical_unhealthy(self) -> None:
        registry = HealthCheckRegistry(name="test_registry")
        registry.register_function("check1", lambda: True, critical=True)
        registry.register_function("check2", lambda: False, critical=True)

        results = registry.run_all_checks()
        status = registry.get_overall_status(results)

        assert status == HealthStatus.UNHEALTHY

    def test_get_overall_status_non_critical_unhealthy(self) -> None:
        registry = HealthCheckRegistry(name="test_registry")
        registry.register_function("check1", lambda: True, critical=True)
        registry.register_function("check2", lambda: False, critical=False)

        results = registry.run_all_checks()
        status = registry.get_overall_status(results)

        # Non-critical failure is treated as degraded, not unhealthy
        assert status == HealthStatus.DEGRADED

    def test_get_overall_status_degraded(self) -> None:
        registry = HealthCheckRegistry(name="test_registry")
        registry.register_function("check1", lambda: HealthStatus.DEGRADED, critical=True)

        results = registry.run_all_checks()
        status = registry.get_overall_status(results)

        assert status == HealthStatus.DEGRADED

    def test_create_report(self) -> None:
        registry = HealthCheckRegistry(name="test_registry")
        registry.register_function("check1", lambda: True, critical=True)

        report = registry.create_report()

        assert report["status"] == "healthy"
        assert report["summary"]["total"] == 1
        assert report["summary"]["healthy"] == 1
        assert len(report["checks"]) == 1


class TestAlwaysHealthyCheck:
    """Tests for AlwaysHealthyCheck."""

    def test_always_healthy(self) -> None:
        check = AlwaysHealthyCheck()
        result = check.execute()

        assert result.status == HealthStatus.HEALTHY
        assert not check.critical  # Should be non-critical


class TestFilesystemCheck:
    """Tests for FilesystemCheck."""

    def test_existing_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            check = FilesystemCheck(path=tmpdir)
            result = check.execute()

            assert result.status == HealthStatus.HEALTHY
            assert "free_gb" in result.details

    def test_nonexistent_path(self) -> None:
        check = FilesystemCheck(path="/nonexistent/path/12345")
        result = check.execute()

        assert result.status == HealthStatus.UNHEALTHY
        assert "does not exist" in result.message.lower()

    def test_file_not_directory(self) -> None:
        with tempfile.NamedTemporaryFile() as tmpfile:
            check = FilesystemCheck(path=tmpfile.name)
            result = check.execute()

            assert result.status == HealthStatus.UNHEALTHY
            assert "not a directory" in result.message.lower()

    def test_writable_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            check = FilesystemCheck(path=tmpdir, check_writable=True)
            result = check.execute()

            # Should be healthy if writable
            assert result.status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED)


class TestGlobalRegistry:
    """Tests for global health check registry."""

    def test_global_registry_exists(self) -> None:
        assert health_check_registry is not None

    def test_run_health_checks(self) -> None:
        # Register a test check
        health_check_registry.register_function("_test_global_check", lambda: True, critical=False)

        report = run_health_checks()

        assert "status" in report
        assert "checks" in report
        assert "summary" in report

        # Clean up
        health_check_registry.unregister("_test_global_check")
