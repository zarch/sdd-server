"""Observability infrastructure: metrics, tracing, health checks, and audit logging."""

from sdd_server.infrastructure.observability.audit import (
    AuditEvent,
    AuditEventType,
    AuditLogger,
    audit_log,
    get_audit_logger,
)
from sdd_server.infrastructure.observability.health import (
    HealthCheck,
    HealthCheckRegistry,
    HealthCheckResult,
    HealthStatus,
    health_check_registry,
    run_health_checks,
)
from sdd_server.infrastructure.observability.metrics import (
    Counter,
    Gauge,
    Histogram,
    MetricsCollector,
    Timer,
    get_metrics,
    metric_counter,
    metric_timer,
)

__all__ = [
    # Audit logging
    "AuditEvent",
    "AuditEventType",
    "AuditLogger",
    # Metrics
    "Counter",
    "Gauge",
    # Health checks
    "HealthCheck",
    "HealthCheckRegistry",
    "HealthCheckResult",
    "HealthStatus",
    "Histogram",
    "MetricsCollector",
    "Timer",
    "audit_log",
    "get_audit_logger",
    "get_metrics",
    "health_check_registry",
    "metric_counter",
    "metric_timer",
    "run_health_checks",
]
