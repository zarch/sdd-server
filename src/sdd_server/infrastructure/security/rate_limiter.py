"""Rate limiting for API protection.

Provides rate limiting implementations including token bucket and
sliding window algorithms.
"""

from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar

if TYPE_CHECKING:
    pass

from sdd_server.infrastructure.exceptions import ErrorCode, ExecutionError
from sdd_server.utils.logging import get_logger

logger = get_logger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


class RateLimitExceeded(ExecutionError):  # type: ignore[misc]
    """Raised when rate limit is exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: float | None = None,
        limit: int | None = None,
        window: float | None = None,
    ) -> None:
        """Initialize rate limit error.

        Args:
            message: Error message
            retry_after: Seconds until retry is allowed
            limit: The rate limit that was exceeded
            window: The time window in seconds
        """
        details: dict[str, Any] = {}
        if retry_after is not None:
            details["retry_after"] = retry_after
        if limit is not None:
            details["limit"] = limit
        if window is not None:
            details["window"] = window

        super().__init__(
            message,
            code=ErrorCode.EXEC_TIMEOUT,  # Reuse existing error code
            context=details,
        )
        self.retry_after = retry_after
        self.limit = limit
        self.window = window


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    requests_per_window: int = 100
    window_seconds: float = 60.0
    burst_size: int | None = None  # For token bucket, defaults to requests_per_window
    key_prefix: str = ""

    def __post_init__(self) -> None:
        """Set defaults."""
        if self.burst_size is None:
            self.burst_size = self.requests_per_window


class RateLimiter(ABC):
    """Abstract base class for rate limiters."""

    @abstractmethod
    def is_allowed(self, key: str) -> bool:
        """Check if request is allowed for the given key.

        Args:
            key: Identifier for the client/resource

        Returns:
            True if request is allowed, False if rate limited
        """
        ...

    @abstractmethod
    def record_request(self, key: str) -> None:
        """Record a request for the given key.

        Args:
            key: Identifier for the client/resource
        """
        ...

    @abstractmethod
    def get_remaining(self, key: str) -> int:
        """Get remaining requests allowed for the key.

        Args:
            key: Identifier for the client/resource

        Returns:
            Number of remaining requests allowed
        """
        ...

    @abstractmethod
    def get_reset_time(self, key: str) -> float | None:
        """Get seconds until rate limit resets.

        Args:
            key: Identifier for the client/resource

        Returns:
            Seconds until reset, or None if not rate limited
        """
        ...

    @abstractmethod
    def reset(self, key: str) -> None:
        """Reset rate limit for a key.

        Args:
            key: Identifier to reset
        """
        ...

    def check_and_record(self, key: str) -> tuple[bool, int, float | None]:
        """Check if allowed and record if so.

        Args:
            key: Identifier for the client/resource

        Returns:
            Tuple of (is_allowed, remaining, reset_time)
        """
        if self.is_allowed(key):
            self.record_request(key)
            remaining = self.get_remaining(key)
            reset_time = self.get_reset_time(key)
            return True, remaining, reset_time
        else:
            remaining = 0
            reset_time = self.get_reset_time(key)
            return False, remaining, reset_time


class InMemoryRateLimiter(RateLimiter):
    """In-memory rate limiter using sliding window.

    This is suitable for single-process applications. For distributed
    systems, use a Redis-backed implementation.
    """

    def __init__(self, config: RateLimitConfig | None = None) -> None:
        """Initialize rate limiter.

        Args:
            config: Rate limit configuration
        """
        self.config = config or RateLimitConfig()
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def _get_full_key(self, key: str) -> str:
        """Get full key with prefix."""
        prefix = self.config.key_prefix
        return f"{prefix}:{key}" if prefix else key

    def _cleanup_old_requests(self, key: str, now: float) -> None:
        """Remove requests outside the current window."""
        cutoff = now - self.config.window_seconds
        self._requests[key] = [t for t in self._requests[key] if t > cutoff]

    def is_allowed(self, key: str) -> bool:
        """Check if request is allowed."""
        full_key = self._get_full_key(key)
        now = time.time()

        with self._lock:
            self._cleanup_old_requests(full_key, now)
            count = len(self._requests[full_key])
            return count < self.config.requests_per_window

    def record_request(self, key: str) -> None:
        """Record a request."""
        full_key = self._get_full_key(key)
        now = time.time()

        with self._lock:
            self._requests[full_key].append(now)

    def get_remaining(self, key: str) -> int:
        """Get remaining requests."""
        full_key = self._get_full_key(key)
        now = time.time()

        with self._lock:
            self._cleanup_old_requests(full_key, now)
            count = len(self._requests[full_key])
            return max(0, self.config.requests_per_window - count)

    def get_reset_time(self, key: str) -> float | None:
        """Get seconds until oldest request expires."""
        full_key = self._get_full_key(key)
        now = time.time()

        with self._lock:
            self._cleanup_old_requests(full_key, now)
            if not self._requests[full_key]:
                return None

            oldest = min(self._requests[full_key])
            reset_at = oldest + self.config.window_seconds
            return max(0, reset_at - now)

    def reset(self, key: str) -> None:
        """Reset rate limit for a key."""
        full_key = self._get_full_key(key)
        with self._lock:
            self._requests[full_key] = []


class TokenBucketRateLimiter(RateLimiter):
    """Token bucket rate limiter.

    Allows for burst traffic up to burst_size, then enforces steady rate.
    """

    def __init__(
        self,
        config: RateLimitConfig | None = None,
        refill_rate: float | None = None,
    ) -> None:
        """Initialize token bucket rate limiter.

        Args:
            config: Rate limit configuration
            refill_rate: Tokens per second (defaults to requests/window)
        """
        self.config = config or RateLimitConfig()
        self.refill_rate = refill_rate or (
            self.config.requests_per_window / self.config.window_seconds
        )
        self._buckets: dict[str, tuple[float, float]] = {}  # key -> (tokens, last_refill)
        self._lock = threading.Lock()

    def _get_full_key(self, key: str) -> str:
        """Get full key with prefix."""
        prefix = self.config.key_prefix
        return f"{prefix}:{key}" if prefix else key

    def _refill(self, key: str, now: float) -> None:
        """Refill tokens based on elapsed time."""
        if key not in self._buckets:
            self._buckets[key] = (
                float(self.config.burst_size or self.config.requests_per_window),
                now,
            )
            return

        tokens, last_refill = self._buckets[key]
        elapsed = now - last_refill
        new_tokens = elapsed * self.refill_rate
        max_tokens = self.config.burst_size or self.config.requests_per_window
        self._buckets[key] = (min(max_tokens, tokens + new_tokens), now)

    def is_allowed(self, key: str) -> bool:
        """Check if request is allowed (has tokens)."""
        full_key = self._get_full_key(key)
        now = time.time()

        with self._lock:
            self._refill(full_key, now)
            tokens, _ = self._buckets[full_key]
            return tokens >= 1.0

    def record_request(self, key: str) -> None:
        """Consume a token."""
        full_key = self._get_full_key(key)
        now = time.time()

        with self._lock:
            self._refill(full_key, now)
            tokens, last_refill = self._buckets[full_key]
            self._buckets[full_key] = (tokens - 1.0, last_refill)

    def get_remaining(self, key: str) -> int:
        """Get remaining tokens."""
        full_key = self._get_full_key(key)
        now = time.time()

        with self._lock:
            self._refill(full_key, now)
            tokens, _ = self._buckets[full_key]
            return int(tokens)

    def get_reset_time(self, key: str) -> float | None:
        """Get time until one token is available."""
        full_key = self._get_full_key(key)
        now = time.time()

        with self._lock:
            self._refill(full_key, now)
            tokens, _ = self._buckets[full_key]
            if tokens >= 1.0:
                return None
            # Time until one token is refilled
            return (1.0 - tokens) / self.refill_rate

    def reset(self, key: str) -> None:
        """Reset bucket for a key."""
        full_key = self._get_full_key(key)
        with self._lock:
            if full_key in self._buckets:
                del self._buckets[full_key]


# Global rate limiter
_rate_limiter: RateLimiter | None = None
_rate_limiter_lock = threading.Lock()


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance."""
    global _rate_limiter
    with _rate_limiter_lock:
        if _rate_limiter is None:
            _rate_limiter = InMemoryRateLimiter()
        return _rate_limiter


def configure_rate_limiter(
    config: RateLimitConfig,
    use_token_bucket: bool = False,
) -> RateLimiter:
    """Configure the global rate limiter.

    Args:
        config: Rate limit configuration
        use_token_bucket: Use token bucket algorithm

    Returns:
        Configured rate limiter
    """
    global _rate_limiter
    with _rate_limiter_lock:
        if use_token_bucket:
            _rate_limiter = TokenBucketRateLimiter(config)
        else:
            _rate_limiter = InMemoryRateLimiter(config)
        return _rate_limiter


def rate_limit(
    key_func: Callable[..., str] | None = None,
    config: RateLimitConfig | None = None,
    raise_on_limit: bool = True,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator to rate limit function calls.

    Args:
        key_func: Function to extract rate limit key from args
        config: Rate limit configuration
        raise_on_limit: Raise RateLimitExceeded or return None

    Returns:
        Decorated function
    """
    limiter = InMemoryRateLimiter(config)

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            # Get key
            key = key_func(*args, **kwargs) if key_func else func.__name__

            allowed, remaining, reset_time = limiter.check_and_record(key)

            if not allowed:
                logger.warning(
                    "rate_limit_exceeded",
                    function=func.__name__,
                    key=key,
                    remaining=remaining,
                )
                if raise_on_limit:
                    raise RateLimitExceeded(
                        f"Rate limit exceeded for {func.__name__}",
                        retry_after=reset_time,
                        limit=limiter.config.requests_per_window,
                        window=limiter.config.window_seconds,
                    )
                # This is unreachable if raise_on_limit is True, but mypy needs it
                raise RateLimitExceeded("Rate limit exceeded")

            return func(*args, **kwargs)

        @wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            # Get key
            key = key_func(*args, **kwargs) if key_func else func.__name__

            allowed, remaining, reset_time = limiter.check_and_record(key)

            if not allowed:
                logger.warning(
                    "rate_limit_exceeded",
                    function=func.__name__,
                    key=key,
                    remaining=remaining,
                )
                if raise_on_limit:
                    raise RateLimitExceeded(
                        f"Rate limit exceeded for {func.__name__}",
                        retry_after=reset_time,
                        limit=limiter.config.requests_per_window,
                        window=limiter.config.window_seconds,
                    )
                raise RateLimitExceeded("Rate limit exceeded")

            return await func(*args, **kwargs)  # type: ignore[misc,no-any-return]

        import inspect

        if inspect.iscoroutinefunction(func):
            return async_wrapper  # type: ignore[return-value]
        return sync_wrapper

    return decorator
