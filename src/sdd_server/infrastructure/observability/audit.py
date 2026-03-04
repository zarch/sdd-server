"""Audit logging for tracking key operations and security events.

Provides structured audit logging for compliance, security monitoring,
and operational tracking.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    pass

from sdd_server.utils.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class AuditEventType(Enum):
    """Types of auditable events."""

    # Authentication and authorization
    AUTH_LOGIN = "auth.login"
    AUTH_LOGOUT = "auth.logout"
    AUTH_FAILURE = "auth.failure"
    ACCESS_GRANTED = "access.granted"
    ACCESS_DENIED = "access.denied"

    # File operations
    FILE_READ = "file.read"
    FILE_WRITE = "file.write"
    FILE_DELETE = "file.delete"
    FILE_CREATE = "file.create"

    # Configuration changes
    CONFIG_CHANGE = "config.change"
    CONFIG_RELOAD = "config.reload"

    # MCP operations
    MCP_TOOL_CALL = "mcp.tool_call"
    MCP_RESOURCE_ACCESS = "mcp.resource_access"

    # Spec operations
    SPEC_CREATE = "spec.create"
    SPEC_UPDATE = "spec.update"
    SPEC_DELETE = "spec.delete"
    SPEC_VALIDATE = "spec.validate"

    # Task operations
    TASK_CREATE = "task.create"
    TASK_UPDATE = "task.update"
    TASK_COMPLETE = "task.complete"

    # Code generation
    CODE_GENERATE = "code.generate"
    CODE_REVIEW = "code.review"

    # System events
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"
    SYSTEM_ERROR = "system.error"

    # Lifecycle events
    LIFECYCLE_STATE_CHANGE = "lifecycle.state_change"

    # Security events
    SECURITY_VIOLATION = "security.violation"
    SECURITY_WARNING = "security.warning"

    # Custom event
    CUSTOM = "custom"


class AuditSeverity(Enum):
    """Severity levels for audit events."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """Represents a single audit event."""

    event_type: AuditEventType
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    severity: AuditSeverity = AuditSeverity.INFO
    actor: str | None = None  # Who performed the action
    resource: str | None = None  # What resource was affected
    action: str | None = None  # What action was taken
    result: str | None = None  # Result of the action (success/failure)
    correlation_id: str | None = None
    session_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary for serialization."""
        return {
            "event_type": self.event_type.value,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "severity": self.severity.value,
            "actor": self.actor,
            "resource": self.resource,
            "action": self.action,
            "result": self.result,
            "correlation_id": self.correlation_id,
            "session_id": self.session_id,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "details": self.details,
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        """Convert event to JSON string."""
        return json.dumps(self.to_dict())

    @property
    def event_id(self) -> str:
        """Generate a unique event ID based on content hash."""
        content = f"{self.event_type.value}:{self.timestamp.isoformat()}:{self.message}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


class AuditLogger:
    """Central audit logging system.

    Provides structured audit logging with multiple output targets
    (file, log, custom handlers).
    """

    def __init__(
        self,
        name: str = "audit",
        file_path: Path | str | None = None,
        min_severity: AuditSeverity = AuditSeverity.INFO,
        include_structlog: bool = True,
    ) -> None:
        """Initialize the audit logger.

        Args:
            name: Logger name for identification
            file_path: Optional path to write audit log file
            min_severity: Minimum severity level to log
            include_structlog: Whether to also log via structlog
        """
        self.name = name
        self.file_path = Path(file_path) if file_path else None
        self.min_severity = min_severity
        self.include_structlog = include_structlog
        self._lock = threading.Lock()
        self._handlers: list[Callable[[AuditEvent], None]] = []

        # Severity order for filtering
        self._severity_order = {
            AuditSeverity.DEBUG: 0,
            AuditSeverity.INFO: 1,
            AuditSeverity.WARNING: 2,
            AuditSeverity.ERROR: 3,
            AuditSeverity.CRITICAL: 4,
        }

    def add_handler(self, handler: Callable[[AuditEvent], None]) -> None:
        """Add a custom event handler.

        Args:
            handler: Function to call with each audit event
        """
        with self._lock:
            self._handlers.append(handler)

    def remove_handler(self, handler: Callable[[AuditEvent], None]) -> bool:
        """Remove a custom event handler.

        Args:
            handler: Handler to remove

        Returns:
            True if handler was found and removed
        """
        with self._lock:
            try:
                self._handlers.remove(handler)
                return True
            except ValueError:
                return False

    def _should_log(self, severity: AuditSeverity) -> bool:
        """Check if severity level should be logged."""
        return self._severity_order.get(severity, 0) >= self._severity_order.get(
            self.min_severity, 1
        )

    def log(self, event: AuditEvent) -> None:
        """Log an audit event.

        Args:
            event: AuditEvent to log
        """
        if not self._should_log(event.severity):
            return

        # Log to structlog
        if self.include_structlog:
            log_method = getattr(logger, event.severity.value, logger.info)
            log_method(
                f"audit.{event.event_type.value}",
                event_id=event.event_id,
                message=event.message,
                actor=event.actor,
                resource=event.resource,
                action=event.action,
                result=event.result,
                correlation_id=event.correlation_id,
                **event.details,
            )

        # Log to file
        if self.file_path:
            self._write_to_file(event)

        # Call custom handlers
        with self._lock:
            handlers = list(self._handlers)

        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(
                    "audit_handler_error",
                    handler=str(handler),
                    error=str(e),
                )

    def _write_to_file(self, event: AuditEvent) -> None:
        """Write event to audit log file."""
        if self.file_path is None:
            return
        try:
            with self._lock, self.file_path.open("a", encoding="utf-8") as f:
                f.write(event.to_json() + "\n")
        except Exception as e:
            logger.error("audit_file_write_error", error=str(e))

    # Convenience methods for common event types
    def log_event(
        self,
        event_type: AuditEventType,
        message: str,
        severity: AuditSeverity = AuditSeverity.INFO,
        **kwargs: Any,
    ) -> AuditEvent:
        """Create and log an audit event.

        Args:
            event_type: Type of event
            message: Human-readable message
            severity: Event severity
            **kwargs: Additional event fields

        Returns:
            The created event
        """
        event = AuditEvent(
            event_type=event_type,
            message=message,
            severity=severity,
            **kwargs,
        )
        self.log(event)
        return event

    def log_file_operation(
        self,
        operation: str,
        path: str,
        actor: str | None = None,
        success: bool = True,
        details: dict[str, Any] | None = None,
    ) -> AuditEvent:
        """Log a file system operation.

        Args:
            operation: Operation type (read, write, delete, create)
            path: File path affected
            actor: Who performed the operation
            success: Whether operation succeeded
            details: Additional details

        Returns:
            The created event
        """
        event_type_map = {
            "read": AuditEventType.FILE_READ,
            "write": AuditEventType.FILE_WRITE,
            "delete": AuditEventType.FILE_DELETE,
            "create": AuditEventType.FILE_CREATE,
        }
        event_type = event_type_map.get(operation.lower(), AuditEventType.CUSTOM)

        return self.log_event(
            event_type=event_type,
            message=f"File {operation}: {path}",
            resource=path,
            action=operation,
            actor=actor,
            result="success" if success else "failure",
            severity=AuditSeverity.INFO if success else AuditSeverity.WARNING,
            details=details or {},
        )

    def log_tool_call(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        actor: str | None = None,
        success: bool = True,
        duration_ms: float | None = None,
        correlation_id: str | None = None,
    ) -> AuditEvent:
        """Log an MCP tool call.

        Args:
            tool_name: Name of the tool called
            arguments: Tool arguments (sanitized)
            actor: Who called the tool
            success: Whether call succeeded
            duration_ms: Call duration in milliseconds
            correlation_id: Request correlation ID

        Returns:
            The created event
        """
        details: dict[str, Any] = {"tool_name": tool_name}
        if arguments:
            details["arguments"] = self._sanitize_arguments(arguments)
        if duration_ms is not None:
            details["duration_ms"] = duration_ms

        return self.log_event(
            event_type=AuditEventType.MCP_TOOL_CALL,
            message=f"Tool call: {tool_name}",
            resource=tool_name,
            action="call",
            actor=actor,
            result="success" if success else "failure",
            correlation_id=correlation_id,
            severity=AuditSeverity.INFO if success else AuditSeverity.WARNING,
            details=details,
        )

    def log_security_event(
        self,
        message: str,
        severity: AuditSeverity = AuditSeverity.WARNING,
        violation_type: str | None = None,
        resource: str | None = None,
        actor: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditEvent:
        """Log a security-related event.

        Args:
            message: Human-readable message
            severity: Event severity
            violation_type: Type of security violation
            resource: Affected resource
            actor: Who triggered the event
            details: Additional details

        Returns:
            The created event
        """
        event_details = details or {}
        if violation_type:
            event_details["violation_type"] = violation_type

        return self.log_event(
            event_type=AuditEventType.SECURITY_VIOLATION,
            message=message,
            severity=severity,
            resource=resource,
            actor=actor,
            details=event_details,
        )

    @staticmethod
    def _sanitize_arguments(args: dict[str, Any]) -> dict[str, Any]:
        """Sanitize arguments to remove sensitive data."""
        sensitive_keys = {
            "password",
            "secret",
            "token",
            "api_key",
            "apikey",
            "credential",
            "auth",
        }

        sanitized: dict[str, Any] = {}
        for key, value in args.items():
            key_lower = key.lower()
            if any(sensitive in key_lower for sensitive in sensitive_keys):
                sanitized[key] = "***REDACTED***"
            elif isinstance(value, dict):
                sanitized[key] = AuditLogger._sanitize_arguments(value)
            else:
                sanitized[key] = value

        return sanitized


# Global audit logger instance
_audit_logger: AuditLogger | None = None
_audit_lock = threading.Lock()


def get_audit_logger() -> AuditLogger:
    """Get the global audit logger instance."""
    global _audit_logger
    with _audit_lock:
        if _audit_logger is None:
            _audit_logger = AuditLogger()
        return _audit_logger


def configure_audit_logger(
    file_path: Path | str | None = None,
    min_severity: AuditSeverity = AuditSeverity.INFO,
    include_structlog: bool = True,
) -> AuditLogger:
    """Configure the global audit logger.

    Args:
        file_path: Optional path for audit log file
        min_severity: Minimum severity to log
        include_structlog: Whether to also log via structlog

    Returns:
        Configured audit logger
    """
    global _audit_logger
    with _audit_lock:
        _audit_logger = AuditLogger(
            file_path=file_path,
            min_severity=min_severity,
            include_structlog=include_structlog,
        )
        return _audit_logger


def audit_log(
    event_type: AuditEventType,
    message: str,
    severity: AuditSeverity = AuditSeverity.INFO,
    **kwargs: Any,
) -> AuditEvent:
    """Convenience function to log an audit event.

    Args:
        event_type: Type of event
        message: Human-readable message
        severity: Event severity
        **kwargs: Additional event fields

    Returns:
        The created event
    """
    return get_audit_logger().log_event(
        event_type=event_type,
        message=message,
        severity=severity,
        **kwargs,
    )


def audited(
    event_type: AuditEventType = AuditEventType.CUSTOM,
    resource_arg: str | None = None,
    include_args: bool = False,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to automatically audit function calls.

    Args:
        event_type: Type of audit event
        resource_arg: Name of argument to use as resource
        include_args: Whether to include function arguments in details

    Returns:
        Decorated function
    """
    import functools

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            import time

            start = time.perf_counter()
            success = True
            result = None
            error = None

            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                error = e
                raise
            finally:
                duration = (time.perf_counter() - start) * 1000
                details = {"duration_ms": duration, "function": func.__name__}

                if include_args:
                    details["args"] = str(args)[:200]
                    details["kwargs"] = str(kwargs)[:200]

                if error:
                    details["error"] = str(error)

                resource = None
                if resource_arg and resource_arg in kwargs:
                    resource = str(kwargs[resource_arg])

                audit_log(
                    event_type=event_type,
                    message=f"Function call: {func.__name__}",
                    resource=resource,
                    action=func.__name__,
                    result="success" if success else "failure",
                    severity=AuditSeverity.INFO if success else AuditSeverity.WARNING,
                    details=details,
                )

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            import time

            start = time.perf_counter()
            success = True
            result = None
            error = None

            try:
                result = await func(*args, **kwargs)  # type: ignore[misc]
                return result
            except Exception as e:
                success = False
                error = e
                raise
            finally:
                duration = (time.perf_counter() - start) * 1000
                details = {"duration_ms": duration, "function": func.__name__}

                if include_args:
                    details["args"] = str(args)[:200]
                    details["kwargs"] = str(kwargs)[:200]

                if error:
                    details["error"] = str(error)

                resource = None
                if resource_arg and resource_arg in kwargs:
                    resource = str(kwargs[resource_arg])

                audit_log(
                    event_type=event_type,
                    message=f"Function call: {func.__name__}",
                    resource=resource,
                    action=func.__name__,
                    result="success" if success else "failure",
                    severity=AuditSeverity.INFO if success else AuditSeverity.WARNING,
                    details=details,
                )

        if inspect.iscoroutinefunction(func):
            return async_wrapper  # type: ignore[return-value]
        return sync_wrapper

    return decorator
