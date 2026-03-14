"""SDD exception hierarchy with error codes and context.

This module provides a comprehensive exception hierarchy for the SDD server:
- Error codes for programmatic handling
- Correlation IDs for request tracing
- Context information for debugging
- Actionable error messages with guidance

Error Code Format: SDD_<DOMAIN>_<SPECIFIC>
Example: SDD_FS_PATH_TRAVERSAL, SDD_PLUGIN_LOAD_FAILED
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    """Error codes for programmatic error handling.

    Format: SDD_<DOMAIN>_<SPECIFIC_ERROR>
    """

    # Filesystem errors (SDD_FS_*)
    FS_PATH_TRAVERSAL = "SDD_FS_PATH_TRAVERSAL"
    FS_FILE_NOT_FOUND = "SDD_FS_FILE_NOT_FOUND"
    FS_READ_ERROR = "SDD_FS_READ_ERROR"
    FS_WRITE_ERROR = "SDD_FS_WRITE_ERROR"
    FS_DELETE_ERROR = "SDD_FS_DELETE_ERROR"
    FS_PERMISSION_DENIED = "SDD_FS_PERMISSION_DENIED"

    # Git errors (SDD_GIT_*)
    GIT_NOT_A_REPO = "SDD_GIT_NOT_A_REPO"
    GIT_OPERATION_FAILED = "SDD_GIT_OPERATION_FAILED"
    GIT_COMMIT_FAILED = "SDD_GIT_COMMIT_FAILED"
    GIT_BRANCH_ERROR = "SDD_GIT_BRANCH_ERROR"

    # Spec errors (SDD_SPEC_*)
    SPEC_NOT_FOUND = "SDD_SPEC_NOT_FOUND"
    SPEC_PARSE_ERROR = "SDD_SPEC_PARSE_ERROR"
    SPEC_VALIDATION_FAILED = "SDD_SPEC_VALIDATION_FAILED"
    SPEC_WRITE_FAILED = "SDD_SPEC_WRITE_FAILED"

    # Plugin errors (SDD_PLUGIN_*)
    PLUGIN_LOAD_FAILED = "SDD_PLUGIN_LOAD_FAILED"
    PLUGIN_VALIDATION_FAILED = "SDD_PLUGIN_VALIDATION_FAILED"
    PLUGIN_NOT_FOUND = "SDD_PLUGIN_NOT_FOUND"
    PLUGIN_DEPENDENCY_ERROR = "SDD_PLUGIN_DEPENDENCY_ERROR"
    PLUGIN_EXECUTION_FAILED = "SDD_PLUGIN_EXECUTION_FAILED"

    # Validation errors (SDD_VALIDATION_*)
    VALIDATION_FAILED = "SDD_VALIDATION_FAILED"
    VALIDATION_RULE_VIOLATION = "SDD_VALIDATION_RULE_VIOLATION"

    # Execution errors (SDD_EXEC_*)
    EXEC_RECIPE_NOT_FOUND = "SDD_EXEC_RECIPE_NOT_FOUND"
    EXEC_GOOSE_NOT_FOUND = "SDD_EXEC_GOOSE_NOT_FOUND"
    EXEC_TIMEOUT = "SDD_EXEC_TIMEOUT"
    EXEC_CANCELLED = "SDD_EXEC_CANCELLED"
    EXEC_FAILED = "SDD_EXEC_FAILED"
    EXEC_RETRY_EXHAUSTED = "SDD_EXEC_RETRY_EXHAUSTED"

    # Configuration errors (SDD_CONFIG_*)
    CONFIG_INVALID = "SDD_CONFIG_INVALID"
    CONFIG_MISSING_REQUIRED = "SDD_CONFIG_MISSING_REQUIRED"
    CONFIG_FILE_ERROR = "SDD_CONFIG_FILE_ERROR"

    # Security errors (SDD_SEC_*)
    SEC_UNAUTHORIZED = "SDD_SEC_UNAUTHORIZED"
    SEC_PATH_VIOLATION = "SDD_SEC_PATH_VIOLATION"
    SEC_INPUT_VALIDATION = "SDD_SEC_INPUT_VALIDATION"

    # Enforcement errors (SDD_ENF_*)
    ENF_BLOCKED = "SDD_ENF_BLOCKED"
    ENF_BYPASS_EXPIRED = "SDD_ENF_BYPASS_EXPIRED"

    # General errors (SDD_*)
    INTERNAL_ERROR = "SDD_INTERNAL_ERROR"
    NOT_INITIALIZED = "SDD_NOT_INITIALIZED"
    ALREADY_EXISTS = "SDD_ALREADY_EXISTS"


@dataclass
class ErrorContext:
    """Context information for error tracking and debugging."""

    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    operation: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    suggestions: list[str] = field(default_factory=list)
    cause: Exception | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert context to dictionary for serialization."""
        return {
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp.isoformat(),
            "operation": self.operation,
            "details": self.details,
            "suggestions": self.suggestions,
            "cause": str(self.cause) if self.cause else None,
        }


class SDDError(Exception):
    """Base exception for all SDD errors.

    Provides error codes, context for debugging, and actionable guidance.
    """

    def __init__(
        self,
        message: str,
        code: ErrorCode = ErrorCode.INTERNAL_ERROR,
        context: ErrorContext | None = None,
        *,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.context = context or ErrorContext()
        if cause and not self.context.cause:
            self.context.cause = cause

    @property
    def correlation_id(self) -> str:
        """Get the correlation ID for this error."""
        return self.context.correlation_id

    def with_operation(self, operation: str) -> SDDError:
        """Add operation context to the error."""
        self.context.operation = operation
        return self

    def with_details(self, **kwargs: Any) -> SDDError:
        """Add details to the error context."""
        self.context.details.update(kwargs)
        return self

    def with_suggestion(self, suggestion: str) -> SDDError:
        """Add a suggestion for resolving the error."""
        self.context.suggestions.append(suggestion)
        return self

    def to_dict(self) -> dict[str, Any]:
        """Convert error to dictionary for API responses."""
        return {
            "error": self.code.value,
            "message": self.message,
            "correlation_id": self.correlation_id,
            "context": self.context.to_dict(),
        }

    def __str__(self) -> str:
        """Return formatted error message with context."""
        parts = [f"[{self.code.value}] {self.message}"]
        if self.context.correlation_id:
            parts.append(f"  Correlation ID: {self.context.correlation_id}")
        if self.context.suggestions:
            parts.append("  Suggestions:")
            for s in self.context.suggestions:
                parts.append(f"    - {s}")
        return "\n".join(parts)


# =============================================================================
# Filesystem Errors
# =============================================================================


class FileSystemError(SDDError):
    """File system operation failed."""

    def __init__(
        self,
        message: str,
        path: str | None = None,
        code: ErrorCode = ErrorCode.FS_READ_ERROR,
        context: ErrorContext | None = None,
        *,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, code, context, cause=cause)
        if path:
            self.context.details["path"] = path


class PathTraversalError(FileSystemError):
    """Attempted path traversal outside allowed root."""

    def __init__(
        self,
        message: str,
        path: str | None = None,
        allowed_root: str | None = None,
        *,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(
            message,
            path=path,
            code=ErrorCode.FS_PATH_TRAVERSAL,
            cause=cause,
        )
        if allowed_root:
            self.context.details["allowed_root"] = allowed_root
        self.context.suggestions.extend(
            [
                "Ensure the path is within the project directory",
                "Avoid using '..' or absolute paths that escape the project root",
            ]
        )


class FileNotFoundError_(FileSystemError):
    """File not found (underscore suffix to avoid shadowing builtin)."""

    def __init__(
        self,
        message: str,
        path: str | None = None,
        *,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(
            message,
            path=path,
            code=ErrorCode.FS_FILE_NOT_FOUND,
            cause=cause,
        )
        self.context.suggestions.extend(
            [
                "Verify the file path is correct",
                "Check if the file has been deleted or moved",
            ]
        )


# =============================================================================
# Git Errors
# =============================================================================


class GitError(SDDError):
    """Git operation failed."""

    def __init__(
        self,
        message: str,
        operation: str | None = None,
        code: ErrorCode = ErrorCode.GIT_OPERATION_FAILED,
        context: ErrorContext | None = None,
        *,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, code, context, cause=cause)
        if operation:
            self.context.operation = operation


class GitNotARepoError(GitError):
    """Directory is not a git repository."""

    def __init__(
        self,
        message: str = "Not a git repository",
        path: str | None = None,
        *,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(
            message,
            operation="git_check",
            code=ErrorCode.GIT_NOT_A_REPO,
            cause=cause,
        )
        if path:
            self.context.details["path"] = path
        self.context.suggestions.extend(
            [
                "Run 'git init' to initialize a repository",
                "Ensure you're in the correct project directory",
            ]
        )


# =============================================================================
# Spec Errors
# =============================================================================


class SpecNotFoundError(SDDError):
    """Requested spec file does not exist."""

    def __init__(
        self,
        message: str,
        spec_type: str | None = None,
        feature: str | None = None,
        *,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, code=ErrorCode.SPEC_NOT_FOUND, cause=cause)
        if spec_type:
            self.context.details["spec_type"] = spec_type
        if feature:
            self.context.details["feature"] = feature
        self.context.suggestions.extend(
            [
                "Run 'sdd init' to create initial spec files",
                "Check if the feature name is correct",
            ]
        )


class SpecParseError(SDDError):
    """Failed to parse spec file."""

    def __init__(
        self,
        message: str,
        spec_type: str | None = None,
        path: str | None = None,
        *,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, code=ErrorCode.SPEC_PARSE_ERROR, cause=cause)
        if spec_type:
            self.context.details["spec_type"] = spec_type
        if path:
            self.context.details["path"] = path
        self.context.suggestions.extend(
            [
                "Check the spec file for syntax errors",
                "Ensure YAML/markdown formatting is correct",
            ]
        )


# =============================================================================
# Validation Errors
# =============================================================================


class ValidationError(SDDError):
    """Validation failed."""

    def __init__(
        self,
        message: str,
        issues: list[str] | None = None,
        code: ErrorCode = ErrorCode.VALIDATION_FAILED,
        context: ErrorContext | None = None,
        *,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, code, context, cause=cause)
        if issues:
            self.context.details["issues"] = issues


class EnforcementError(SDDError):
    """Enforcement check failed."""

    def __init__(
        self,
        message: str,
        rule: str | None = None,
        *,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, code=ErrorCode.VALIDATION_RULE_VIOLATION, cause=cause)
        if rule:
            self.context.details["rule"] = rule


# =============================================================================
# Execution Errors
# =============================================================================


class ExecutionError(SDDError):
    """Base class for execution-related errors."""

    def __init__(
        self,
        message: str,
        code: ErrorCode = ErrorCode.EXEC_FAILED,
        context: ErrorContext | None = None,
        *,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, code, context, cause=cause)


class RecipeNotFoundError(ExecutionError):
    """Recipe file not found."""

    def __init__(
        self,
        message: str,
        recipe_path: str | None = None,
        *,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, code=ErrorCode.EXEC_RECIPE_NOT_FOUND, cause=cause)
        if recipe_path:
            self.context.details["recipe_path"] = recipe_path
        self.context.suggestions.extend(
            [
                "Verify the recipe file exists",
                "Check if the recipe name is correct",
            ]
        )


class GooseNotFoundError(ExecutionError):
    """Goose CLI not found on system."""

    def __init__(
        self,
        message: str = "Goose CLI not found",
        goose_path: str | None = None,
        *,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, code=ErrorCode.EXEC_GOOSE_NOT_FOUND, cause=cause)
        if goose_path:
            self.context.details["goose_path"] = goose_path
        self.context.suggestions.extend(
            [
                "Install Goose CLI: https://github.com/block/goose",
                "Ensure 'goose' is in your PATH",
            ]
        )


class ExecutionTimeoutError(ExecutionError):
    """Execution timed out."""

    def __init__(
        self,
        message: str,
        timeout_seconds: float | None = None,
        *,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, code=ErrorCode.EXEC_TIMEOUT, cause=cause)
        if timeout_seconds:
            self.context.details["timeout_seconds"] = timeout_seconds
        self.context.suggestions.extend(
            [
                "Increase the timeout duration",
                "Check for slow operations or infinite loops",
            ]
        )


class ExecutionCancelledError(ExecutionError):
    """Execution was cancelled."""

    def __init__(
        self,
        message: str = "Execution was cancelled",
        *,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, code=ErrorCode.EXEC_CANCELLED, cause=cause)


# =============================================================================
# Plugin Errors
# =============================================================================


class PluginError(SDDError):
    """Base exception for plugin-related errors."""

    def __init__(
        self,
        message: str,
        plugin_name: str | None = None,
        code: ErrorCode = ErrorCode.PLUGIN_EXECUTION_FAILED,
        context: ErrorContext | None = None,
        *,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, code, context, cause=cause)
        if plugin_name:
            self.context.details["plugin_name"] = plugin_name


class PluginLoadError(PluginError):
    """Failed to load a plugin."""

    def __init__(
        self,
        message: str,
        plugin_name: str | None = None,
        *,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(
            message,
            plugin_name=plugin_name,
            code=ErrorCode.PLUGIN_LOAD_FAILED,
            cause=cause,
        )
        self.context.suggestions.extend(
            [
                "Check the plugin configuration",
                "Verify all plugin dependencies are installed",
            ]
        )


class PluginValidationError(PluginError):
    """Plugin validation failed."""

    def __init__(
        self,
        message: str,
        plugin_name: str | None = None,
        validation_errors: list[str] | None = None,
        *,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(
            message,
            plugin_name=plugin_name,
            code=ErrorCode.PLUGIN_VALIDATION_FAILED,
            cause=cause,
        )
        if validation_errors:
            self.context.details["validation_errors"] = validation_errors


class PluginNotFoundError(PluginError):
    """Plugin not found."""

    def __init__(
        self,
        message: str,
        plugin_name: str | None = None,
        *,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(
            message,
            plugin_name=plugin_name,
            code=ErrorCode.PLUGIN_NOT_FOUND,
            cause=cause,
        )
        self.context.suggestions.extend(
            [
                "Check the plugin name spelling",
                "Use 'sdd plugin list' to see available plugins",
            ]
        )


# =============================================================================
# Configuration Errors
# =============================================================================


class ConfigurationError(SDDError):
    """Configuration-related error."""

    def __init__(
        self,
        message: str,
        config_key: str | None = None,
        code: ErrorCode = ErrorCode.CONFIG_INVALID,
        context: ErrorContext | None = None,
        *,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, code, context, cause=cause)
        if config_key:
            self.context.details["config_key"] = config_key


# =============================================================================
# Security Errors
# =============================================================================


class SecurityError(SDDError):
    """Security-related error."""

    def __init__(
        self,
        message: str,
        code: ErrorCode = ErrorCode.SEC_UNAUTHORIZED,
        context: ErrorContext | None = None,
        *,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, code, context, cause=cause)


class InputValidationError(SecurityError):
    """Input validation failed for security reasons."""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        value: str | None = None,
        *,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(
            message,
            code=ErrorCode.SEC_INPUT_VALIDATION,
            cause=cause,
        )
        if field:
            self.context.details["field"] = field
        if value:
            # Truncate potentially sensitive values
            self.context.details["value"] = value[:50] + "..." if len(value) > 50 else value


class NotInitializedError(SDDError):
    """Error when a component is used before initialization."""

    def __init__(
        self,
        component: str,
        *,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(
            f"{component} has not been initialized. Call initialize() first.",
            code=ErrorCode.NOT_INITIALIZED,
            cause=cause,
        )
        self.context.details["component"] = component


class AlreadyInitializedError(SDDError):
    """Error when a component is initialized twice."""

    def __init__(
        self,
        component: str,
        *,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(
            f"{component} has already been initialized.",
            code=ErrorCode.ALREADY_EXISTS,
            cause=cause,
        )
        self.context.details["component"] = component
