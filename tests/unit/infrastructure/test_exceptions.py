"""Tests for the enhanced exception hierarchy."""

from sdd_server.infrastructure.exceptions import (
    ConfigurationError,
    EnforcementError,
    ErrorCode,
    ErrorContext,
    ExecutionCancelledError,
    ExecutionTimeoutError,
    FileNotFoundError_,
    FileSystemError,
    GitError,
    GitNotARepoError,
    GooseNotFoundError,
    InputValidationError,
    PathTraversalError,
    PluginError,
    PluginLoadError,
    PluginNotFoundError,
    PluginValidationError,
    RecipeNotFoundError,
    SDDError,
    SecurityError,
    SpecNotFoundError,
    SpecParseError,
    ValidationError,
)


class TestErrorCode:
    """Tests for ErrorCode enum."""

    def test_error_code_is_string(self) -> None:
        """Error codes should be strings."""
        assert isinstance(ErrorCode.FS_PATH_TRAVERSAL.value, str)

    def test_error_code_format(self) -> None:
        """Error codes should follow SDD_<DOMAIN>_<SPECIFIC> format."""
        for code in ErrorCode:
            assert code.value.startswith("SDD_")
            parts = code.value.split("_")
            assert len(parts) >= 2

    def test_filesystem_error_codes(self) -> None:
        """Filesystem error codes should have FS domain."""
        fs_codes = [
            ErrorCode.FS_PATH_TRAVERSAL,
            ErrorCode.FS_FILE_NOT_FOUND,
            ErrorCode.FS_READ_ERROR,
            ErrorCode.FS_WRITE_ERROR,
            ErrorCode.FS_DELETE_ERROR,
            ErrorCode.FS_PERMISSION_DENIED,
        ]
        for code in fs_codes:
            assert code.value.startswith("SDD_FS_")


class TestErrorContext:
    """Tests for ErrorContext dataclass."""

    def test_default_context(self) -> None:
        """Default context should have auto-generated correlation ID."""
        ctx = ErrorContext()
        assert ctx.correlation_id is not None
        assert len(ctx.correlation_id) == 8
        assert ctx.operation is None
        assert ctx.details == {}
        assert ctx.suggestions == []

    def test_context_to_dict(self) -> None:
        """Context should serialize to dict."""
        ctx = ErrorContext(
            correlation_id="abc123",
            operation="test_op",
            details={"key": "value"},
            suggestions=["Try this"],
        )
        d = ctx.to_dict()
        assert d["correlation_id"] == "abc123"
        assert d["operation"] == "test_op"
        assert d["details"] == {"key": "value"}
        assert d["suggestions"] == ["Try this"]
        assert "timestamp" in d


class TestSDDError:
    """Tests for base SDDError class."""

    def test_basic_error(self) -> None:
        """Basic error should have message and code."""
        err = SDDError("Test error")
        assert err.message == "Test error"
        assert err.code == ErrorCode.INTERNAL_ERROR
        assert err.correlation_id is not None

    def test_error_with_code(self) -> None:
        """Error should accept custom code."""
        err = SDDError("Test error", code=ErrorCode.VALIDATION_FAILED)
        assert err.code == ErrorCode.VALIDATION_FAILED

    def test_error_with_context(self) -> None:
        """Error should accept custom context."""
        ctx = ErrorContext(correlation_id="custom123")
        err = SDDError("Test error", context=ctx)
        assert err.correlation_id == "custom123"

    def test_error_with_cause(self) -> None:
        """Error should store cause exception."""
        original = ValueError("original error")
        err = SDDError("Wrapped error", cause=original)
        assert err.context.cause == original

    def test_with_operation(self) -> None:
        """with_operation should set operation in context."""
        err = SDDError("Test").with_operation("file_read")
        assert err.context.operation == "file_read"

    def test_with_details(self) -> None:
        """with_details should add to context details."""
        err = SDDError("Test").with_details(path="/tmp/file", line=42)
        assert err.context.details["path"] == "/tmp/file"
        assert err.context.details["line"] == 42

    def test_with_suggestion(self) -> None:
        """with_suggestion should add suggestion."""
        err = SDDError("Test").with_suggestion("Try again")
        assert "Try again" in err.context.suggestions

    def test_to_dict(self) -> None:
        """to_dict should produce API-ready dict."""
        err = SDDError(
            "Test error",
            code=ErrorCode.VALIDATION_FAILED,
        ).with_details(key="value")
        d = err.to_dict()
        assert d["error"] == "SDD_VALIDATION_FAILED"
        assert d["message"] == "Test error"
        assert "correlation_id" in d
        assert "context" in d

    def test_str_format(self) -> None:
        """String representation should be formatted nicely."""
        err = SDDError(
            "Test error",
            code=ErrorCode.FS_FILE_NOT_FOUND,
        ).with_suggestion("Check the path")
        s = str(err)
        assert "[SDD_FS_FILE_NOT_FOUND]" in s
        assert "Test error" in s
        assert "Correlation ID:" in s
        assert "Suggestions:" in s
        assert "- Check the path" in s


class TestFileSystemErrors:
    """Tests for filesystem-related errors."""

    def test_filesystem_error(self) -> None:
        """FileSystemError should include path in details."""
        err = FileSystemError("Cannot read file", path="/tmp/test")
        assert err.code == ErrorCode.FS_READ_ERROR
        assert err.context.details["path"] == "/tmp/test"

    def test_path_traversal_error(self) -> None:
        """PathTraversalError should have suggestions."""
        err = PathTraversalError(
            "Path escapes root",
            path="../../../etc/passwd",
            allowed_root="/project",
        )
        assert err.code == ErrorCode.FS_PATH_TRAVERSAL
        assert err.context.details["path"] == "../../../etc/passwd"
        assert err.context.details["allowed_root"] == "/project"
        assert len(err.context.suggestions) >= 2

    def test_file_not_found_error(self) -> None:
        """FileNotFoundError_ should have suggestions."""
        err = FileNotFoundError_("File missing", path="/tmp/missing")
        assert err.code == ErrorCode.FS_FILE_NOT_FOUND
        assert len(err.context.suggestions) >= 2


class TestGitErrors:
    """Tests for git-related errors."""

    def test_git_error(self) -> None:
        """GitError should accept operation."""
        err = GitError("Git failed", operation="commit")
        assert err.code == ErrorCode.GIT_OPERATION_FAILED
        assert err.context.operation == "commit"

    def test_git_not_a_repo_error(self) -> None:
        """GitNotARepoError should have suggestions."""
        err = GitNotARepoError(path="/tmp")
        assert err.code == ErrorCode.GIT_NOT_A_REPO
        assert err.context.details["path"] == "/tmp"
        assert "git init" in err.context.suggestions[0].lower()


class TestSpecErrors:
    """Tests for spec-related errors."""

    def test_spec_not_found_error(self) -> None:
        """SpecNotFoundError should include spec type and feature."""
        err = SpecNotFoundError(
            "PRD not found",
            spec_type="prd",
            feature="auth",
        )
        assert err.code == ErrorCode.SPEC_NOT_FOUND
        assert err.context.details["spec_type"] == "prd"
        assert err.context.details["feature"] == "auth"

    def test_spec_parse_error(self) -> None:
        """SpecParseError should include path."""
        err = SpecParseError(
            "Invalid YAML",
            spec_type="arch",
            path="/specs/arch.md",
        )
        assert err.code == ErrorCode.SPEC_PARSE_ERROR
        assert err.context.details["spec_type"] == "arch"
        assert err.context.details["path"] == "/specs/arch.md"


class TestValidationErrors:
    """Tests for validation-related errors."""

    def test_validation_error(self) -> None:
        """ValidationError should include issues."""
        err = ValidationError(
            "Validation failed",
            issues=["Missing field", "Invalid format"],
        )
        assert err.code == ErrorCode.VALIDATION_FAILED
        assert err.context.details["issues"] == ["Missing field", "Invalid format"]

    def test_enforcement_error(self) -> None:
        """EnforcementError should include rule."""
        err = EnforcementError("Rule violated", rule="no-hardcoded-secrets")
        assert err.code == ErrorCode.VALIDATION_RULE_VIOLATION
        assert err.context.details["rule"] == "no-hardcoded-secrets"


class TestExecutionErrors:
    """Tests for execution-related errors."""

    def test_recipe_not_found_error(self) -> None:
        """RecipeNotFoundError should include path."""
        err = RecipeNotFoundError("Recipe missing", recipe_path="/recipes/test.yaml")
        assert err.code == ErrorCode.EXEC_RECIPE_NOT_FOUND
        assert err.context.details["recipe_path"] == "/recipes/test.yaml"

    def test_goose_not_found_error(self) -> None:
        """GooseNotFoundError should have install suggestions."""
        err = GooseNotFoundError(goose_path="/usr/local/bin/goose")
        assert err.code == ErrorCode.EXEC_GOOSE_NOT_FOUND
        assert err.context.details["goose_path"] == "/usr/local/bin/goose"
        assert any("install" in s.lower() for s in err.context.suggestions)

    def test_execution_timeout_error(self) -> None:
        """ExecutionTimeoutError should include timeout value."""
        err = ExecutionTimeoutError("Timed out", timeout_seconds=30.0)
        assert err.code == ErrorCode.EXEC_TIMEOUT
        assert err.context.details["timeout_seconds"] == 30.0

    def test_execution_cancelled_error(self) -> None:
        """ExecutionCancelledError should have default message."""
        err = ExecutionCancelledError()
        assert err.code == ErrorCode.EXEC_CANCELLED
        assert "cancelled" in err.message.lower()


class TestPluginErrors:
    """Tests for plugin-related errors."""

    def test_plugin_error(self) -> None:
        """PluginError should include plugin name."""
        err = PluginError("Plugin failed", plugin_name="test-plugin")
        assert err.code == ErrorCode.PLUGIN_EXECUTION_FAILED
        assert err.context.details["plugin_name"] == "test-plugin"

    def test_plugin_load_error(self) -> None:
        """PluginLoadError should have suggestions."""
        err = PluginLoadError("Failed to load", plugin_name="broken-plugin")
        assert err.code == ErrorCode.PLUGIN_LOAD_FAILED
        assert len(err.context.suggestions) >= 2

    def test_plugin_validation_error(self) -> None:
        """PluginValidationError should include validation errors."""
        err = PluginValidationError(
            "Invalid plugin",
            plugin_name="bad-plugin",
            validation_errors=["Missing name", "Invalid version"],
        )
        assert err.code == ErrorCode.PLUGIN_VALIDATION_FAILED
        assert err.context.details["validation_errors"] == ["Missing name", "Invalid version"]

    def test_plugin_not_found_error(self) -> None:
        """PluginNotFoundError should have suggestions."""
        err = PluginNotFoundError("Not found", plugin_name="missing-plugin")
        assert err.code == ErrorCode.PLUGIN_NOT_FOUND
        assert any("list" in s.lower() for s in err.context.suggestions)


class TestConfigurationErrors:
    """Tests for configuration-related errors."""

    def test_configuration_error(self) -> None:
        """ConfigurationError should include config key."""
        err = ConfigurationError("Invalid config", config_key="timeout")
        assert err.code == ErrorCode.CONFIG_INVALID
        assert err.context.details["config_key"] == "timeout"


class TestSecurityErrors:
    """Tests for security-related errors."""

    def test_security_error(self) -> None:
        """SecurityError should have security code."""
        err = SecurityError("Unauthorized")
        assert err.code == ErrorCode.SEC_UNAUTHORIZED

    def test_input_validation_error(self) -> None:
        """InputValidationError should include field and truncated value."""
        err = InputValidationError(
            "Invalid input",
            field="username",
            value="a" * 100,  # 100 chars
        )
        assert err.code == ErrorCode.SEC_INPUT_VALIDATION
        assert err.context.details["field"] == "username"
        # Value should be truncated
        assert len(err.context.details["value"]) == 53  # 50 + "..."

    def test_input_validation_short_value(self) -> None:
        """Short values should not be truncated."""
        err = InputValidationError("Invalid", field="x", value="short")
        assert err.context.details["value"] == "short"
