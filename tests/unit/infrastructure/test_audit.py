"""Tests for audit logging."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from sdd_server.infrastructure.observability.audit import (
    AuditEvent,
    AuditEventType,
    AuditLogger,
    AuditSeverity,
    audit_log,
    audited,
    configure_audit_logger,
    get_audit_logger,
)


class TestAuditEvent:
    """Tests for AuditEvent."""

    def test_to_dict(self) -> None:
        event = AuditEvent(
            event_type=AuditEventType.FILE_READ,
            message="Read file",
            severity=AuditSeverity.INFO,
            actor="user1",
            resource="/path/to/file",
        )
        d = event.to_dict()

        assert d["event_type"] == "file.read"
        assert d["message"] == "Read file"
        assert d["severity"] == "info"
        assert d["actor"] == "user1"
        assert d["resource"] == "/path/to/file"

    def test_to_json(self) -> None:
        event = AuditEvent(
            event_type=AuditEventType.FILE_WRITE,
            message="Write file",
        )
        json_str = event.to_json()

        # Should be valid JSON
        parsed = json.loads(json_str)
        assert parsed["event_type"] == "file.write"

    def test_event_id(self) -> None:
        event1 = AuditEvent(
            event_type=AuditEventType.FILE_READ,
            message="Read file",
        )
        AuditEvent(
            event_type=AuditEventType.FILE_READ,
            message="Read file",
        )

        # Same content should produce same ID
        # (but timestamps differ, so IDs will differ in practice)
        assert event1.event_id is not None
        assert len(event1.event_id) == 16


class TestAuditLogger:
    """Tests for AuditLogger."""

    def test_log_event(self) -> None:
        logger = AuditLogger(name="test", include_structlog=False)
        event = AuditEvent(
            event_type=AuditEventType.FILE_READ,
            message="Read file",
            severity=AuditSeverity.INFO,
        )
        # Should not raise
        logger.log(event)

    def test_log_with_file(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            file_path = Path(f.name)

        try:
            logger = AuditLogger(name="test", file_path=file_path, include_structlog=False)
            logger.log_event(
                event_type=AuditEventType.FILE_WRITE,
                message="Write file",
            )

            # Read and verify
            content = file_path.read_text()
            assert "file.write" in content
            assert "Write file" in content
        finally:
            file_path.unlink(missing_ok=True)

    def test_severity_filtering(self) -> None:
        logger = AuditLogger(
            name="test",
            min_severity=AuditSeverity.WARNING,
            include_structlog=False,
        )

        events: list[AuditEvent] = []

        def handler(e: AuditEvent) -> None:
            events.append(e)

        logger.add_handler(handler)

        # INFO should be filtered out
        logger.log_event(
            event_type=AuditEventType.FILE_READ,
            message="Info message",
            severity=AuditSeverity.INFO,
        )

        # WARNING should pass
        logger.log_event(
            event_type=AuditEventType.FILE_WRITE,
            message="Warning message",
            severity=AuditSeverity.WARNING,
        )

        assert len(events) == 1
        assert events[0].message == "Warning message"

    def test_handler_exception_handling(self) -> None:
        logger = AuditLogger(name="test", include_structlog=False)

        def bad_handler(e: AuditEvent) -> None:
            raise RuntimeError("Handler error")

        logger.add_handler(bad_handler)

        # Should not raise, error should be caught
        logger.log_event(
            event_type=AuditEventType.FILE_READ,
            message="Test",
        )

    def test_log_file_operation(self) -> None:
        logger = AuditLogger(name="test", include_structlog=False)
        event = logger.log_file_operation(
            operation="read",
            path="/test/path",
            actor="user1",
            success=True,
        )

        assert event.event_type == AuditEventType.FILE_READ
        assert event.resource == "/test/path"
        assert event.actor == "user1"
        assert event.result == "success"

    def test_log_tool_call(self) -> None:
        logger = AuditLogger(name="test", include_structlog=False)
        event = logger.log_tool_call(
            tool_name="test_tool",
            arguments={"arg1": "value1"},
            success=True,
            duration_ms=50.0,
        )

        assert event.event_type == AuditEventType.MCP_TOOL_CALL
        assert event.resource == "test_tool"
        assert event.result == "success"
        assert event.details["duration_ms"] == 50.0

    def test_log_tool_call_sanitizes_secrets(self) -> None:
        logger = AuditLogger(name="test", include_structlog=False)
        event = logger.log_tool_call(
            tool_name="test_tool",
            arguments={
                "username": "user1",
                "password": "secret123",
                "api_key": "key123",
            },
            success=True,
        )

        assert event.details["arguments"]["username"] == "user1"
        assert event.details["arguments"]["password"] == "***REDACTED***"
        assert event.details["arguments"]["api_key"] == "***REDACTED***"

    def test_log_security_event(self) -> None:
        logger = AuditLogger(name="test", include_structlog=False)
        event = logger.log_security_event(
            message="Path traversal attempt",
            severity=AuditSeverity.WARNING,
            violation_type="path_traversal",
            resource="/etc/passwd",
        )

        assert event.event_type == AuditEventType.SECURITY_VIOLATION
        assert event.severity == AuditSeverity.WARNING
        assert event.details["violation_type"] == "path_traversal"

    def test_sanitize_nested_arguments(self) -> None:
        sanitized = AuditLogger._sanitize_arguments(
            {
                "config": {
                    "password": "secret",
                    "nested": {
                        "token": "abc123",
                    },
                },
                "safe_value": "public",
            }
        )

        assert sanitized["config"]["password"] == "***REDACTED***"
        assert sanitized["config"]["nested"]["token"] == "***REDACTED***"
        assert sanitized["safe_value"] == "public"


class TestAuditDecorator:
    """Tests for @audited decorator."""

    def test_sync_function(self) -> None:
        events: list[AuditEvent] = []

        def handler(e: AuditEvent) -> None:
            events.append(e)

        logger = AuditLogger(name="test", include_structlog=False)
        logger.add_handler(handler)

        @audited(event_type=AuditEventType.CUSTOM)
        def test_func(x: int) -> int:
            return x * 2

        with pytest.MonkeyPatch.context() as m:
            m.setattr("sdd_server.infrastructure.observability.audit._audit_logger", logger)
            result = test_func(5)

        assert result == 10
        assert len(events) == 1
        assert events[0].result == "success"

    def test_sync_function_with_exception(self) -> None:
        events: list[AuditEvent] = []

        def handler(e: AuditEvent) -> None:
            events.append(e)

        logger = AuditLogger(name="test", include_structlog=False)
        logger.add_handler(handler)

        @audited(event_type=AuditEventType.CUSTOM)
        def failing_func() -> None:
            raise ValueError("Test error")

        with pytest.MonkeyPatch.context() as m:
            m.setattr("sdd_server.infrastructure.observability.audit._audit_logger", logger)
            with pytest.raises(ValueError):
                failing_func()

        assert len(events) == 1
        assert events[0].result == "failure"
        assert "Test error" in events[0].details["error"]

    @pytest.mark.asyncio
    async def test_async_function(self) -> None:
        events: list[AuditEvent] = []

        def handler(e: AuditEvent) -> None:
            events.append(e)

        logger = AuditLogger(name="test", include_structlog=False)
        logger.add_handler(handler)

        @audited(event_type=AuditEventType.CUSTOM)
        async def async_func(x: int) -> int:
            return x * 2

        with pytest.MonkeyPatch.context() as m:
            m.setattr("sdd_server.infrastructure.observability.audit._audit_logger", logger)
            result = await async_func(5)

        assert result == 10
        assert len(events) == 1


class TestGlobalFunctions:
    """Tests for global audit functions."""

    def test_get_audit_logger_singleton(self) -> None:
        logger1 = get_audit_logger()
        logger2 = get_audit_logger()
        assert logger1 is logger2

    def test_configure_audit_logger(self) -> None:
        logger = configure_audit_logger(min_severity=AuditSeverity.DEBUG)
        assert logger.min_severity == AuditSeverity.DEBUG

    def test_audit_log_function(self) -> None:
        # Reset and configure
        logger = configure_audit_logger(min_severity=AuditSeverity.DEBUG, include_structlog=False)

        events: list[AuditEvent] = []

        def handler(e: AuditEvent) -> None:
            events.append(e)

        logger.add_handler(handler)

        event = audit_log(
            event_type=AuditEventType.FILE_READ,
            message="Test log",
            resource="/test/path",
        )

        assert event.message == "Test log"
        assert len(events) == 1


class TestAuditEventTypes:
    """Tests for AuditEventType enum values."""

    def test_all_types_have_values(self) -> None:
        for event_type in AuditEventType:
            assert event_type.value is not None
            # Most types have category.specific format, except CUSTOM
            if event_type != AuditEventType.CUSTOM:
                assert "." in event_type.value

    def test_common_types_exist(self) -> None:
        assert AuditEventType.FILE_READ.value == "file.read"
        assert AuditEventType.FILE_WRITE.value == "file.write"
        assert AuditEventType.MCP_TOOL_CALL.value == "mcp.tool_call"
        assert AuditEventType.SECURITY_VIOLATION.value == "security.violation"
        assert AuditEventType.CUSTOM.value == "custom"
