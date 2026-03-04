"""Tests for retry mechanisms."""

from __future__ import annotations

import pytest

from sdd_server.infrastructure.exceptions import (
    ErrorCode,
    FileSystemError,
    SDDError,
)
from sdd_server.infrastructure.retry import (
    AsyncRetryContext,
    RetryConfig,
    RetryContext,
    RetryExhaustedError,
    RetryResult,
    RetryStrategy,
    async_retry,
    is_retryable_exception,
    retry_on_exception,
    retry_on_file_lock,
    retry_on_timeout,
    sync_retry,
)


class TestRetryConfig:
    """Tests for RetryConfig."""

    def test_default_values(self) -> None:
        config = RetryConfig()
        assert config.max_retries == 3
        assert config.initial_delay == 0.1
        assert config.max_delay == 30.0
        assert config.backoff_multiplier == 2.0
        assert config.jitter is True
        assert config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF

    def test_exponential_backoff_delay(self) -> None:
        config = RetryConfig(
            initial_delay=0.1,
            backoff_multiplier=2.0,
            jitter=False,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        )
        assert config.get_delay(0) == 0.1
        assert config.get_delay(1) == 0.2
        assert config.get_delay(2) == 0.4
        assert config.get_delay(3) == 0.8

    def test_linear_backoff_delay(self) -> None:
        config = RetryConfig(
            initial_delay=0.5,
            jitter=False,
            strategy=RetryStrategy.LINEAR_BACKOFF,
        )
        assert config.get_delay(0) == 0.5
        assert config.get_delay(1) == 1.0
        assert config.get_delay(2) == 1.5

    def test_fixed_delay(self) -> None:
        config = RetryConfig(
            initial_delay=0.5,
            jitter=False,
            strategy=RetryStrategy.FIXED_DELAY,
        )
        assert config.get_delay(0) == 0.5
        assert config.get_delay(1) == 0.5
        assert config.get_delay(10) == 0.5

    def test_immediate_delay(self) -> None:
        config = RetryConfig(strategy=RetryStrategy.IMMEDIATE)
        assert config.get_delay(0) == 0.0
        assert config.get_delay(5) == 0.0

    def test_max_delay_cap(self) -> None:
        config = RetryConfig(
            initial_delay=1.0,
            max_delay=5.0,
            backoff_multiplier=10.0,
            jitter=False,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        )
        assert config.get_delay(1) == 5.0

    def test_jitter_adds_randomness(self) -> None:
        config = RetryConfig(
            initial_delay=1.0,
            jitter=True,
            strategy=RetryStrategy.FIXED_DELAY,
        )
        delays = [config.get_delay(0) for _ in range(100)]
        assert all(0.5 <= d <= 1.5 for d in delays)
        assert len(set(delays)) > 1


class TestRetryResult:
    """Tests for RetryResult."""

    def test_success_result(self) -> None:
        result = RetryResult(success=True, result="data", attempts=1)
        assert result.success is True
        assert result.result == "data"
        assert result.attempts == 1
        assert result.retries == 0

    def test_failure_result(self) -> None:
        error = ValueError("test error")
        result = RetryResult(success=False, error=error, attempts=3)
        assert result.success is False
        assert result.error == error
        assert result.attempts == 3
        assert result.retries == 2

    def test_retries_calculation(self) -> None:
        result = RetryResult(success=True, attempts=5)
        assert result.retries == 4
        result = RetryResult(success=True, attempts=1)
        assert result.retries == 0


class TestIsRetryableException:
    """Tests for is_retryable_exception function."""

    def test_retryable_by_type(self) -> None:
        assert is_retryable_exception(OSError("error"), (OSError,))
        assert is_retryable_exception(OSError("error"), (IOError,))
        assert is_retryable_exception(FileSystemError("error"), (FileSystemError,))

    def test_non_retryable_by_type(self) -> None:
        assert not is_retryable_exception(ValueError("error"), (OSError,))
        assert not is_retryable_exception(TypeError("error"), (OSError, IOError))

    def test_retryable_sdd_error_codes(self) -> None:
        error = SDDError("error", code=ErrorCode.FS_READ_ERROR)
        assert is_retryable_exception(error, ())
        error = SDDError("error", code=ErrorCode.EXEC_TIMEOUT)
        assert is_retryable_exception(error, ())

    def test_non_retryable_sdd_error_codes(self) -> None:
        error = SDDError("error", code=ErrorCode.FS_PATH_TRAVERSAL)
        assert not is_retryable_exception(error, ())
        error = SDDError("error", code=ErrorCode.PLUGIN_LOAD_FAILED)
        assert not is_retryable_exception(error, ())

    def test_retryable_by_message_pattern(self) -> None:
        assert is_retryable_exception(OSError("resource temporarily unavailable"), ())
        assert is_retryable_exception(OSError("file is locked"), ())
        assert is_retryable_exception(Exception("timeout occurred"), ())
        assert is_retryable_exception(ConnectionError("connection reset by peer"), ())

    def test_non_retryable_message(self) -> None:
        assert not is_retryable_exception(ValueError("invalid input"), ())
        assert not is_retryable_exception(FileNotFoundError("file not found"), ())


class TestSyncRetry:
    """Tests for sync_retry function."""

    def test_success_on_first_attempt(self) -> None:
        call_count = 0

        def successful_func() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        config = RetryConfig(max_retries=3)
        result = sync_retry(successful_func, config)

        assert result.success is True
        assert result.result == "success"
        assert result.attempts == 1
        assert call_count == 1

    def test_success_after_retry(self) -> None:
        call_count = 0

        def eventually_succeed() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise OSError("temporary error")
            return "success"

        config = RetryConfig(max_retries=3, initial_delay=0.001, jitter=False)
        result = sync_retry(eventually_succeed, config)

        assert result.success is True
        assert result.result == "success"
        assert result.attempts == 3
        assert len(result.errors) == 2

    def test_failure_after_max_retries(self) -> None:
        call_count = 0

        def always_fail() -> str:
            nonlocal call_count
            call_count += 1
            raise OSError("persistent error")

        config = RetryConfig(max_retries=2, initial_delay=0.001, jitter=False)
        result = sync_retry(always_fail, config)

        assert result.success is False
        assert result.attempts == 3
        assert isinstance(result.error, RetryExhaustedError)
        assert len(result.errors) == 3

    def test_non_retryable_exception(self) -> None:
        def value_error_func() -> str:
            raise ValueError("not retryable")

        config = RetryConfig(max_retries=3, retryable_exceptions=(OSError,))
        result = sync_retry(value_error_func, config)

        assert result.success is False
        assert result.attempts == 1
        assert isinstance(result.error, ValueError)

    def test_passes_arguments(self) -> None:
        def add(a: int, b: int) -> int:
            return a + b

        config = RetryConfig()
        result = sync_retry(add, config, 2, 3)

        assert result.success is True
        assert result.result == 5


class TestAsyncRetry:
    """Tests for async_retry function."""

    @pytest.mark.asyncio
    async def test_success_on_first_attempt(self) -> None:
        call_count = 0

        async def async_func() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        config = RetryConfig(max_retries=3)
        result = await async_retry(async_func, config)

        assert result.success is True
        assert result.result == "success"
        assert result.attempts == 1
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_success_after_retry(self) -> None:
        call_count = 0

        async def eventually_succeed() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise OSError("temporary error")
            return "success"

        config = RetryConfig(max_retries=3, initial_delay=0.001, jitter=False)
        result = await async_retry(eventually_succeed, config)

        assert result.success is True
        assert result.result == "success"
        assert result.attempts == 3

    @pytest.mark.asyncio
    async def test_failure_after_max_retries(self) -> None:
        call_count = 0

        async def always_fail() -> str:
            nonlocal call_count
            call_count += 1
            raise OSError("persistent error")

        config = RetryConfig(max_retries=2, initial_delay=0.001, jitter=False)
        result = await async_retry(always_fail, config)

        assert result.success is False
        assert isinstance(result.error, RetryExhaustedError)


class TestRetryOnExceptionDecorator:
    """Tests for retry_on_exception decorator."""

    def test_sync_function_success(self) -> None:
        call_count = 0

        @retry_on_exception(max_retries=3, initial_delay=0.001)
        def successful() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        result = successful()
        assert result == "success"
        assert call_count == 1

    def test_sync_function_retry(self) -> None:
        call_count = 0

        @retry_on_exception(max_retries=3, initial_delay=0.001)
        def eventually_succeed() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise OSError("temporary")
            return "success"

        result = eventually_succeed()
        assert result == "success"
        assert call_count == 2

    def test_sync_function_failure(self) -> None:
        @retry_on_exception(max_retries=2, initial_delay=0.001)
        def always_fail() -> str:
            raise OSError("persistent")

        with pytest.raises(RetryExhaustedError) as exc_info:
            always_fail()

        assert exc_info.value.attempts == 3

    def test_preserves_function_metadata(self) -> None:
        @retry_on_exception()
        def my_func() -> str:
            """My docstring."""
            return "result"

        assert my_func.__name__ == "my_func"
        assert my_func.__doc__ == "My docstring."

    @pytest.mark.asyncio
    async def test_async_function_success(self) -> None:
        call_count = 0

        @retry_on_exception(max_retries=3, initial_delay=0.001)
        async def async_successful() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        result = await async_successful()
        assert result == "success"
        assert call_count == 1


class TestRetryOnFileLock:
    """Tests for retry_on_file_lock decorator."""

    def test_file_lock_retry(self) -> None:
        call_count = 0

        @retry_on_file_lock(max_retries=3, initial_delay=0.001)
        def read_file() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise OSError("file is locked")
            return "content"

        result = read_file()
        assert result == "content"
        assert call_count == 2


class TestRetryOnTimeout:
    """Tests for retry_on_timeout decorator."""

    def test_timeout_retry(self) -> None:
        call_count = 0

        @retry_on_timeout(max_retries=2, initial_delay=0.001)
        def slow_operation() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise TimeoutError("operation timed out")
            return "done"

        result = slow_operation()
        assert result == "done"
        assert call_count == 2


class TestRetryContext:
    """Tests for RetryContext."""

    def test_success(self) -> None:
        with RetryContext("test", max_retries=3) as retry:
            assert retry.attempt == 1
            retry.success("result")

        assert retry.result == "result"
        assert retry.should_continue is False

    def test_manual_retry(self) -> None:
        call_count = 0

        with RetryContext("test", max_retries=3, initial_delay=0.001) as retry:
            while retry.should_continue:
                call_count += 1
                if call_count < 3:
                    retry.failure(OSError("error"))
                else:
                    retry.success("done")

        assert retry.result == "done"
        assert call_count == 3

    def test_exhausted_retries(self) -> None:
        with (
            pytest.raises(RetryExhaustedError),
            RetryContext("test", max_retries=2, initial_delay=0.001) as retry,
        ):
            while retry.should_continue:
                retry.failure(OSError("error"))


class TestAsyncRetryContext:
    """Tests for AsyncRetryContext."""

    @pytest.mark.asyncio
    async def test_success(self) -> None:
        async with AsyncRetryContext("test", max_retries=3) as retry:
            assert retry.attempt == 1
            retry.success("result")

        assert retry.result == "result"

    @pytest.mark.asyncio
    async def test_manual_retry(self) -> None:
        call_count = 0

        async with AsyncRetryContext("test", max_retries=3, initial_delay=0.001) as retry:
            while retry.should_continue:
                call_count += 1
                if call_count < 3:
                    await retry.failure(OSError("error"))
                else:
                    retry.success("done")

        assert retry.result == "done"
        assert call_count == 3


class TestRetryExhaustedError:
    """Tests for RetryExhaustedError."""

    def test_error_message(self) -> None:
        errors = [
            OSError("error 1"),
            OSError("error 2"),
            OSError("error 3"),
        ]
        error = RetryExhaustedError(
            operation="test_op",
            attempts=3,
            last_error=errors[-1],
            errors=errors,
        )

        assert "test_op" in str(error)
        assert "3 attempts" in str(error)
        assert "error 3" in str(error)
        assert error.attempts == 3
        assert error.all_errors == errors

    def test_error_code(self) -> None:
        error = RetryExhaustedError(
            operation="test",
            attempts=1,
            last_error=OSError("err"),
            errors=[OSError("err")],
        )
        assert error.code == ErrorCode.EXEC_RETRY_EXHAUSTED
