"""Unit tests for mcp/tools/health.py."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from sdd_server.infrastructure.observability.health import (
    AlwaysHealthyCheck,
    HealthCheckRegistry,
    HealthStatus,
)


@pytest.fixture()
def isolated_registry() -> HealthCheckRegistry:
    """Return a fresh registry (not the global one)."""
    return HealthCheckRegistry(name="test")


def test_sdd_health_check_returns_status(isolated_registry: HealthCheckRegistry) -> None:
    isolated_registry.register(AlwaysHealthyCheck("basic"))
    report = isolated_registry.create_report()
    assert report["status"] == HealthStatus.HEALTHY.value
    checks = report["checks"]
    assert len(checks) == 1
    assert checks[0]["name"] == "basic"
    assert checks[0]["status"] == HealthStatus.HEALTHY.value


def test_sdd_health_check_empty_registry() -> None:
    reg = HealthCheckRegistry(name="empty")
    report = reg.create_report()
    assert report["status"] == HealthStatus.UNKNOWN.value
    assert report["checks"] == []


def test_filesystem_check_healthy(tmp_path: Path) -> None:
    from sdd_server.infrastructure.observability.health import FilesystemCheck

    check = FilesystemCheck(str(tmp_path), name="test_fs")
    result = check.execute()
    assert result.status == HealthStatus.HEALTHY


def test_filesystem_check_missing_path() -> None:
    from sdd_server.infrastructure.observability.health import FilesystemCheck

    check = FilesystemCheck("/nonexistent/path/xyz", name="missing")
    result = check.execute()
    assert result.status == HealthStatus.UNHEALTHY


async def _run_tool() -> dict[str, object]:
    """Helper to call the health tool logic directly."""
    from sdd_server.infrastructure.observability.health import health_check_registry

    report = health_check_registry.create_report()
    return {
        "status": report["status"],
        "checks": [
            {"name": c["name"], "status": c["status"], "message": c["message"]}
            for c in report["checks"]
        ],
    }


def test_health_tool_shape() -> None:
    result = asyncio.run(_run_tool())
    assert "status" in result
    assert "checks" in result
    assert isinstance(result["checks"], list)
