"""Tests for rate limiting."""

from __future__ import annotations

import time

import pytest

from sdd_server.infrastructure.security.rate_limiter import (
    InMemoryRateLimiter,
    RateLimitConfig,
    RateLimitExceeded,
    TokenBucketRateLimiter,
    configure_rate_limiter,
    get_rate_limiter,
    rate_limit,
)


class TestRateLimitConfig:
    """Tests for RateLimitConfig."""

    def test_defaults(self) -> None:
        config = RateLimitConfig()
        assert config.requests_per_window == 100
        assert config.window_seconds == 60.0
        assert config.burst_size == 100

    def test_custom_values(self) -> None:
        config = RateLimitConfig(
            requests_per_window=50,
            window_seconds=30.0,
            burst_size=75,
            key_prefix="test",
        )
        assert config.requests_per_window == 50
        assert config.window_seconds == 30.0
        assert config.burst_size == 75
        assert config.key_prefix == "test"


class TestInMemoryRateLimiter:
    """Tests for InMemoryRateLimiter."""

    def test_allows_requests_under_limit(self) -> None:
        limiter = InMemoryRateLimiter(
            config=RateLimitConfig(requests_per_window=5, window_seconds=60.0)
        )
        for _ in range(5):
            assert limiter.is_allowed("test_key")
            limiter.record_request("test_key")

    def test_blocks_requests_over_limit(self) -> None:
        limiter = InMemoryRateLimiter(
            config=RateLimitConfig(requests_per_window=3, window_seconds=60.0)
        )
        for _ in range(3):
            limiter.record_request("test_key")

        assert not limiter.is_allowed("test_key")

    def test_get_remaining(self) -> None:
        limiter = InMemoryRateLimiter(
            config=RateLimitConfig(requests_per_window=10, window_seconds=60.0)
        )
        assert limiter.get_remaining("test_key") == 10

        limiter.record_request("test_key")
        assert limiter.get_remaining("test_key") == 9

    def test_get_reset_time(self) -> None:
        limiter = InMemoryRateLimiter(
            config=RateLimitConfig(requests_per_window=2, window_seconds=10.0)
        )
        limiter.record_request("test_key")
        reset_time = limiter.get_reset_time("test_key")
        assert reset_time is not None
        assert 0 < reset_time <= 10

    def test_reset(self) -> None:
        limiter = InMemoryRateLimiter(
            config=RateLimitConfig(requests_per_window=2, window_seconds=60.0)
        )
        limiter.record_request("test_key")
        limiter.record_request("test_key")
        assert not limiter.is_allowed("test_key")

        limiter.reset("test_key")
        assert limiter.is_allowed("test_key")

    def test_check_and_record(self) -> None:
        limiter = InMemoryRateLimiter(
            config=RateLimitConfig(requests_per_window=2, window_seconds=60.0)
        )

        allowed, remaining, _ = limiter.check_and_record("test_key")
        assert allowed
        assert remaining == 1

        allowed, remaining, _ = limiter.check_and_record("test_key")
        assert allowed
        assert remaining == 0

        allowed, remaining, _ = limiter.check_and_record("test_key")
        assert not allowed
        assert remaining == 0

    def test_window_expiry(self) -> None:
        limiter = InMemoryRateLimiter(
            config=RateLimitConfig(requests_per_window=2, window_seconds=0.1)
        )
        limiter.record_request("test_key")
        limiter.record_request("test_key")
        assert not limiter.is_allowed("test_key")

        # Wait for window to expire
        time.sleep(0.15)
        assert limiter.is_allowed("test_key")

    def test_different_keys_independent(self) -> None:
        limiter = InMemoryRateLimiter(
            config=RateLimitConfig(requests_per_window=1, window_seconds=60.0)
        )
        limiter.record_request("key1")
        assert not limiter.is_allowed("key1")
        assert limiter.is_allowed("key2")


class TestTokenBucketRateLimiter:
    """Tests for TokenBucketRateLimiter."""

    def test_allows_burst(self) -> None:
        limiter = TokenBucketRateLimiter(
            config=RateLimitConfig(requests_per_window=10, burst_size=5, window_seconds=1.0)
        )
        # Should allow burst up to burst_size
        for _ in range(5):
            assert limiter.is_allowed("test_key")
            limiter.record_request("test_key")

    def test_blocks_after_burst(self) -> None:
        limiter = TokenBucketRateLimiter(
            config=RateLimitConfig(burst_size=3, requests_per_window=10, window_seconds=1.0)
        )
        for _ in range(3):
            limiter.record_request("test_key")

        assert not limiter.is_allowed("test_key")

    def test_tokens_refill(self) -> None:
        limiter = TokenBucketRateLimiter(
            config=RateLimitConfig(burst_size=2, requests_per_window=10, window_seconds=1.0),
            refill_rate=20.0,  # 20 tokens per second
        )
        # Use all tokens
        limiter.record_request("test_key")
        limiter.record_request("test_key")
        assert not limiter.is_allowed("test_key")

        # Wait for refill
        time.sleep(0.1)  # Should give us ~2 tokens
        assert limiter.is_allowed("test_key")

    def test_get_remaining(self) -> None:
        limiter = TokenBucketRateLimiter(
            config=RateLimitConfig(burst_size=10, requests_per_window=10, window_seconds=1.0)
        )
        assert limiter.get_remaining("test_key") == 10

        limiter.record_request("test_key")
        assert limiter.get_remaining("test_key") == 9


class TestRateLimitDecorator:
    """Tests for rate_limit decorator."""

    def test_rate_limit_sync_function(self) -> None:
        call_count = 0

        @rate_limit(
            key_func=lambda: "test_key",
            config=RateLimitConfig(requests_per_window=2, window_seconds=60.0),
        )
        def limited_func() -> str:
            nonlocal call_count
            call_count += 1
            return "ok"

        assert limited_func() == "ok"
        assert limited_func() == "ok"
        assert call_count == 2

        with pytest.raises(RateLimitExceeded):
            limited_func()

    @pytest.mark.asyncio
    async def test_rate_limit_async_function(self) -> None:
        call_count = 0

        @rate_limit(
            key_func=lambda: "async_test_key",
            config=RateLimitConfig(requests_per_window=2, window_seconds=60.0),
        )
        async def async_limited_func() -> str:
            nonlocal call_count
            call_count += 1
            return "ok"

        assert await async_limited_func() == "ok"
        assert await async_limited_func() == "ok"
        assert call_count == 2

        with pytest.raises(RateLimitExceeded):
            await async_limited_func()

    def test_rate_limit_default_key(self) -> None:
        @rate_limit(config=RateLimitConfig(requests_per_window=1, window_seconds=60.0))
        def my_func() -> str:
            return "ok"

        assert my_func() == "ok"

        with pytest.raises(RateLimitExceeded):
            my_func()


class TestGlobalFunctions:
    """Tests for global rate limiter functions."""

    def test_get_rate_limiter_singleton(self) -> None:
        limiter1 = get_rate_limiter()
        limiter2 = get_rate_limiter()
        assert limiter1 is limiter2

    def test_configure_rate_limiter(self) -> None:
        config = RateLimitConfig(requests_per_window=50, window_seconds=30.0)
        limiter = configure_rate_limiter(config)
        assert limiter.config.requests_per_window == 50

    def test_configure_token_bucket(self) -> None:
        config = RateLimitConfig(requests_per_window=50, window_seconds=30.0)
        limiter = configure_rate_limiter(config, use_token_bucket=True)
        assert isinstance(limiter, TokenBucketRateLimiter)


class TestRateLimitExceeded:
    """Tests for RateLimitExceeded exception."""

    def test_basic_error(self) -> None:
        error = RateLimitExceeded("Rate limit exceeded")
        # Error message includes error code prefix from SDDError
        assert "Rate limit exceeded" in str(error)

    def test_error_with_details(self) -> None:
        error = RateLimitExceeded(
            "Rate limit exceeded",
            retry_after=30.0,
            limit=100,
            window=60.0,
        )
        assert error.retry_after == 30.0
        assert error.limit == 100
        assert error.window == 60.0
