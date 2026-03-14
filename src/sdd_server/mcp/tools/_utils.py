"""Shared helpers for MCP tool handlers."""

from __future__ import annotations

from sdd_server.infrastructure.exceptions import SDDError
from sdd_server.infrastructure.security.rate_limiter import get_rate_limiter


def format_error(exc: Exception) -> dict[str, object]:
    """Return a structured error dict; includes error_code and correlation_id for SDDError."""
    if isinstance(exc, SDDError):
        result: dict[str, object] = {
            "error": exc.message,
            "error_code": exc.code.value,
            "correlation_id": exc.context.correlation_id,
        }
        if exc.context.suggestions:
            result["suggestions"] = exc.context.suggestions
        return result
    return {"error": str(exc)}


def check_rate_limit(key: str) -> dict[str, object] | None:
    """Return an error dict if the key is rate-limited, else None."""
    limiter = get_rate_limiter()
    allowed, _remaining, reset_time = limiter.check_and_record(key)
    if not allowed:
        return {
            "error": "Rate limit exceeded",
            "error_code": "RATE_LIMITED",
            "retry_after": reset_time,
        }
    return None
