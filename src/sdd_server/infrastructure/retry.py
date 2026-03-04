"""Retry mechanisms for transient failures.

This module provides retry utilities with exponential backoff for operations
that may fail temporarily (file locks, network timeouts, etc.).

Example usage:
    @retry_on_exception(max_retries=3, initial_delay=0.1)
    def read_file(path: Path) -> str:
        return path.read_text()

    # Or using the retry context:
    async with retry_context("file operation", max_retries=3) as attempt:
        await perform_operation()
"""

from __future__ import annotations

import asyncio
import functools
import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, TypeVar

from sdd_server.infrastructure.exceptions import (
    ErrorCode,
    ExecutionError,
    FileSystemError,
    SDDError,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable

T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])


class RetryStrategy(Enum):
    """Strategy for retrying failed operations."""

    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIXED_DELAY = "fixed_delay"
    IMMEDIATE = "immediate"


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_retries: int = 3
    initial_delay: float = 0.1
    max_delay: float = 30.0
    backoff_multiplier: float = 2.0
    jitter: bool = True
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    retryable_exceptions: tuple[type[Exception], ...] = (
        OSError,
        IOError,
        FileSystemError,
    )

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for a given attempt number.

        Args:
            attempt: The attempt number (0-indexed).

        Returns:
            Delay in seconds before the next retry.
        """
        if self.strategy == RetryStrategy.IMMEDIATE:
            return 0.0

        if self.strategy == RetryStrategy.FIXED_DELAY:
            delay = self.initial_delay
        elif self.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = self.initial_delay * (attempt + 1)
        else:  # EXPONENTIAL_BACKOFF
            delay = self.initial_delay * (self.backoff_multiplier**attempt)

        # Apply max delay cap
        delay = min(delay, self.max_delay)

        # Add jitter to prevent thundering herd
        if self.jitter:
            delay = delay * (0.5 + random.random())

        return delay


@dataclass
class RetryResult:
    """Result of a retry operation."""

    success: bool
    result: Any = None
    error: Exception | None = None
    attempts: int = 0
    total_delay: float = 0.0
    errors: list[Exception] = field(default_factory=list)

    @property
    def retries(self) -> int:
        """Number of retries (attempts - 1)."""
        return max(0, self.attempts - 1)


class RetryExhaustedError(ExecutionError):  # type: ignore[misc]
    """Raised when all retry attempts have been exhausted."""

    def __init__(
        self,
        operation: str,
        attempts: int,
        last_error: Exception,
        errors: list[Exception],
    ) -> None:
        error_list = "\n".join(f"  - {e}" for e in errors[-3:])
        super().__init__(
            f"Operation '{operation}' failed after {attempts} attempts.\n"
            f"Last error: {last_error}\n"
            f"Recent errors:\n{error_list}",
            code=ErrorCode.EXEC_RETRY_EXHAUSTED,
            cause=last_error,
        )
        self.attempts = attempts
        self.all_errors = errors


def is_retryable_exception(
    error: Exception,
    retryable_exceptions: tuple[type[Exception], ...],
) -> bool:
    """Check if an exception is retryable.

    Args:
        error: The exception to check.
        retryable_exceptions: Tuple of exception types to retry.

    Returns:
        True if the exception should be retried.
    """
    # Check if it's a known retryable type
    if isinstance(error, retryable_exceptions):
        return True

    # Check for specific error codes that should be retried
    if isinstance(error, SDDError):
        retryable_codes = {
            ErrorCode.FS_READ_ERROR,
            ErrorCode.FS_WRITE_ERROR,
            ErrorCode.FS_DELETE_ERROR,
            ErrorCode.EXEC_TIMEOUT,
        }
        if error.code in retryable_codes:
            return True

    # Check for common transient error patterns
    error_message = str(error).lower()
    transient_patterns = [
        "resource temporarily unavailable",
        "file is locked",
        "would block",
        "timeout",
        "connection reset",
        "connection refused",
        "network is unreachable",
        "too many open files",
    ]
    return any(pattern in error_message for pattern in transient_patterns)


def sync_retry[T](
    func: Callable[..., T],
    config: RetryConfig,
    *args: Any,
    **kwargs: Any,
) -> RetryResult:
    """Execute a synchronous function with retry logic.

    Args:
        func: The function to execute.
        config: Retry configuration.
        *args: Positional arguments for the function.
        **kwargs: Keyword arguments for the function.

    Returns:
        RetryResult with the outcome.
    """
    result = RetryResult(success=False)
    errors: list[Exception] = []

    for attempt in range(config.max_retries + 1):
        result.attempts = attempt + 1

        try:
            result.result = func(*args, **kwargs)
            result.success = True
            return result
        except Exception as e:
            errors.append(e)
            result.errors = errors

            # Check if we should retry
            if attempt >= config.max_retries:
                result.error = RetryExhaustedError(
                    operation=func.__name__,
                    attempts=result.attempts,
                    last_error=e,
                    errors=errors,
                )
                return result

            if not is_retryable_exception(e, config.retryable_exceptions):
                result.error = e
                return result

            # Calculate and apply delay
            delay = config.get_delay(attempt)
            result.total_delay += delay
            time.sleep(delay)

    # Should not reach here, but just in case
    result.error = RetryExhaustedError(
        operation=func.__name__,
        attempts=result.attempts,
        last_error=errors[-1] if errors else Exception("Unknown error"),
        errors=errors,
    )
    return result


async def async_retry[T](
    func: Callable[..., Awaitable[T]],
    config: RetryConfig,
    *args: Any,
    **kwargs: Any,
) -> RetryResult:
    """Execute an async function with retry logic.

    Args:
        func: The async function to execute.
        config: Retry configuration.
        *args: Positional arguments for the function.
        **kwargs: Keyword arguments for the function.

    Returns:
        RetryResult with the outcome.
    """
    result = RetryResult(success=False)
    errors: list[Exception] = []

    for attempt in range(config.max_retries + 1):
        result.attempts = attempt + 1

        try:
            result.result = await func(*args, **kwargs)
            result.success = True
            return result
        except Exception as e:
            errors.append(e)
            result.errors = errors

            # Check if we should retry
            if attempt >= config.max_retries:
                result.error = RetryExhaustedError(
                    operation=func.__name__,
                    attempts=result.attempts,
                    last_error=e,
                    errors=errors,
                )
                return result

            if not is_retryable_exception(e, config.retryable_exceptions):
                result.error = e
                return result

            # Calculate and apply delay
            delay = config.get_delay(attempt)
            result.total_delay += delay
            await asyncio.sleep(delay)

    # Should not reach here, but just in case
    result.error = RetryExhaustedError(
        operation=func.__name__,
        attempts=result.attempts,
        last_error=errors[-1] if errors else Exception("Unknown error"),
        errors=errors,
    )
    return result


def retry_on_exception(
    max_retries: int = 3,
    initial_delay: float = 0.1,
    max_delay: float = 30.0,
    backoff_multiplier: float = 2.0,
    jitter: bool = True,
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF,
    retryable_exceptions: tuple[type[Exception], ...] | None = None,
) -> Callable[[F], F]:
    """Decorator to retry a function on transient failures.

    Args:
        max_retries: Maximum number of retry attempts.
        initial_delay: Initial delay in seconds.
        max_delay: Maximum delay cap in seconds.
        backoff_multiplier: Multiplier for exponential backoff.
        jitter: Whether to add random jitter to delays.
        strategy: Retry strategy to use.
        retryable_exceptions: Exception types to retry on.

    Returns:
        Decorated function with retry logic.

    Example:
        @retry_on_exception(max_retries=3, initial_delay=0.1)
        def read_config(path: Path) -> dict:
            return json.loads(path.read_text())
    """
    config = RetryConfig(
        max_retries=max_retries,
        initial_delay=initial_delay,
        max_delay=max_delay,
        backoff_multiplier=backoff_multiplier,
        jitter=jitter,
        strategy=strategy,
        retryable_exceptions=retryable_exceptions or (OSError, IOError),
    )

    def decorator(func: F) -> F:
        if asyncio.iscoroutinefunction(func):
            # Async function
            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                result = await async_retry(func, config, *args, **kwargs)
                if result.success:
                    return result.result
                raise RetryExhaustedError(
                    operation=func.__name__,
                    attempts=result.attempts,
                    last_error=result.error or Exception("Unknown error"),
                    errors=result.errors,
                )

            return async_wrapper  # type: ignore[return-value]
        else:
            # Sync function
            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                result = sync_retry(func, config, *args, **kwargs)
                if result.success:
                    return result.result
                raise RetryExhaustedError(
                    operation=func.__name__,
                    attempts=result.attempts,
                    last_error=result.error or Exception("Unknown error"),
                    errors=result.errors,
                )

            return sync_wrapper  # type: ignore[return-value]

    return decorator


def retry_on_file_lock(
    max_retries: int = 5,
    initial_delay: float = 0.05,
    max_delay: float = 5.0,
) -> Callable[[F], F]:
    """Specialized decorator for file lock retries.

    This is a convenience decorator specifically for file operations
    that may encounter lock contention.

    Args:
        max_retries: Maximum retries (default 5 for file locks).
        initial_delay: Initial delay (default 50ms).
        max_delay: Maximum delay (default 5s).

    Returns:
        Decorated function with file lock retry logic.
    """
    return retry_on_exception(
        max_retries=max_retries,
        initial_delay=initial_delay,
        max_delay=max_delay,
        backoff_multiplier=1.5,  # Gentler backoff for file locks
        jitter=True,
        strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        retryable_exceptions=(OSError, IOError, FileSystemError),
    )


def retry_on_timeout(
    max_retries: int = 2,
    initial_delay: float = 1.0,
    max_delay: float = 10.0,
) -> Callable[[F], F]:
    """Specialized decorator for timeout retries.

    This is a convenience decorator for operations that may timeout,
    such as network requests or long-running processes.

    Args:
        max_retries: Maximum retries (default 2 for timeouts).
        initial_delay: Initial delay (default 1s).
        max_delay: Maximum delay (default 10s).

    Returns:
        Decorated function with timeout retry logic.
    """
    return retry_on_exception(
        max_retries=max_retries,
        initial_delay=initial_delay,
        max_delay=max_delay,
        backoff_multiplier=2.0,
        jitter=True,
        strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        retryable_exceptions=(TimeoutError, asyncio.TimeoutError, OSError),
    )


class RetryContext:
    """Context manager for manual retry control.

    Use this when you need fine-grained control over retry logic.

    Example:
        with RetryContext("file read", max_retries=3) as retry:
            while retry.should_continue:
                try:
                    data = file.read()
                    retry.success(data)
                except OSError as e:
                    retry.failure(e)
    """

    def __init__(
        self,
        operation: str,
        max_retries: int = 3,
        initial_delay: float = 0.1,
        max_delay: float = 30.0,
        backoff_multiplier: float = 2.0,
        jitter: bool = True,
        strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF,
    ) -> None:
        self.operation = operation
        self.config = RetryConfig(
            max_retries=max_retries,
            initial_delay=initial_delay,
            max_delay=max_delay,
            backoff_multiplier=backoff_multiplier,
            jitter=jitter,
            strategy=strategy,
        )
        self._attempt = 0
        self._success = False
        self._result: Any = None
        self._errors: list[Exception] = []

    @property
    def attempt(self) -> int:
        """Current attempt number (1-indexed)."""
        return self._attempt

    @property
    def should_continue(self) -> bool:
        """Whether to continue retrying."""
        return not self._success and self._attempt <= self.config.max_retries

    @property
    def result(self) -> Any:
        """Get the result if successful."""
        if not self._success:
            raise ValueError("Operation was not successful")
        return self._result

    def success(self, result: Any) -> None:
        """Mark the operation as successful."""
        self._success = True
        self._result = result

    def failure(self, error: Exception) -> None:
        """Record a failure and prepare for retry.

        Args:
            error: The exception that occurred.

        Raises:
            RetryExhaustedError: If all retries are exhausted.
        """
        self._errors.append(error)

        if self._attempt >= self.config.max_retries:
            raise RetryExhaustedError(
                operation=self.operation,
                attempts=self._attempt,
                last_error=error,
                errors=self._errors,
            )

        delay = self.config.get_delay(self._attempt - 1)
        time.sleep(delay)

    def __enter__(self) -> RetryContext:
        self._attempt += 1
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        if exc_val is not None and isinstance(exc_val, Exception):
            try:
                self.failure(exc_val)
                return True  # Suppress exception, will retry
            except RetryExhaustedError:
                return False  # Let the error propagate
        return False


class AsyncRetryContext:
    """Async context manager for manual retry control.

    Example:
        async with AsyncRetryContext("api call", max_retries=3) as retry:
            while retry.should_continue:
                try:
                    response = await client.get(url)
                    retry.success(response)
                except aiohttp.ClientError as e:
                    await retry.failure(e)
    """

    def __init__(
        self,
        operation: str,
        max_retries: int = 3,
        initial_delay: float = 0.1,
        max_delay: float = 30.0,
        backoff_multiplier: float = 2.0,
        jitter: bool = True,
        strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF,
    ) -> None:
        self.operation = operation
        self.config = RetryConfig(
            max_retries=max_retries,
            initial_delay=initial_delay,
            max_delay=max_delay,
            backoff_multiplier=backoff_multiplier,
            jitter=jitter,
            strategy=strategy,
        )
        self._attempt = 0
        self._success = False
        self._result: Any = None
        self._errors: list[Exception] = []

    @property
    def attempt(self) -> int:
        """Current attempt number (1-indexed)."""
        return self._attempt

    @property
    def should_continue(self) -> bool:
        """Whether to continue retrying."""
        return not self._success and self._attempt <= self.config.max_retries

    @property
    def result(self) -> Any:
        """Get the result if successful."""
        if not self._success:
            raise ValueError("Operation was not successful")
        return self._result

    def success(self, result: Any) -> None:
        """Mark the operation as successful."""
        self._success = True
        self._result = result

    async def failure(self, error: Exception) -> None:
        """Record a failure and prepare for retry.

        Args:
            error: The exception that occurred.

        Raises:
            RetryExhaustedError: If all retries are exhausted.
        """
        self._errors.append(error)

        if self._attempt >= self.config.max_retries:
            raise RetryExhaustedError(
                operation=self.operation,
                attempts=self._attempt,
                last_error=error,
                errors=self._errors,
            )

        delay = self.config.get_delay(self._attempt - 1)
        await asyncio.sleep(delay)

    async def __aenter__(self) -> AsyncRetryContext:
        self._attempt += 1
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        if exc_val is not None and isinstance(exc_val, Exception):
            try:
                await self.failure(exc_val)
                return True  # Suppress exception, will retry
            except RetryExhaustedError:
                return False  # Let the error propagate
        return False
