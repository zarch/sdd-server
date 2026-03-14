"""Unit tests for mcp/tools/_utils.py."""

from __future__ import annotations

from sdd_server.infrastructure.exceptions import ErrorCode, SDDError, SpecNotFoundError
from sdd_server.infrastructure.security.rate_limiter import (
    RateLimitConfig,
    configure_rate_limiter,
)
from sdd_server.mcp.tools._utils import check_rate_limit, format_error


class TestFormatError:
    def test_plain_exception(self) -> None:
        exc = ValueError("something went wrong")
        result = format_error(exc)
        assert result == {"error": "something went wrong"}

    def test_sdd_error_includes_code_and_correlation(self) -> None:
        exc = SDDError("spec not found", code=ErrorCode.SPEC_NOT_FOUND)
        result = format_error(exc)
        assert result["error_code"] == ErrorCode.SPEC_NOT_FOUND.value
        assert "correlation_id" in result
        assert result["error"] == "spec not found"

    def test_sdd_error_with_suggestions(self) -> None:
        exc = SDDError("bad input", code=ErrorCode.VALIDATION_FAILED)
        exc.with_suggestion("Try again")
        exc.with_suggestion("Check docs")
        result = format_error(exc)
        assert result["suggestions"] == ["Try again", "Check docs"]

    def test_sdd_error_no_suggestions_key_omitted(self) -> None:
        exc = SDDError("oops", code=ErrorCode.INTERNAL_ERROR)
        result = format_error(exc)
        assert "suggestions" not in result

    def test_spec_not_found_error(self) -> None:
        exc = SpecNotFoundError("prd.md missing")
        result = format_error(exc)
        assert "error_code" in result
        assert "correlation_id" in result


class TestCheckRateLimit:
    def setup_method(self) -> None:
        # Configure a very tight rate limiter for testing
        configure_rate_limiter(RateLimitConfig(requests_per_window=2, window_seconds=60.0))

    def test_allowed_returns_none(self) -> None:
        result = check_rate_limit("test_key_allowed")
        assert result is None

    def test_exceeded_returns_error_dict(self) -> None:
        # Exhaust the limit
        check_rate_limit("test_key_exceeded")
        check_rate_limit("test_key_exceeded")
        # Third call should be rate-limited
        result = check_rate_limit("test_key_exceeded")
        assert result is not None
        assert result["error_code"] == "RATE_LIMITED"
        assert "retry_after" in result

    def teardown_method(self) -> None:
        # Restore default rate limiter
        configure_rate_limiter(RateLimitConfig())
