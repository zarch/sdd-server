"""Input validation and sanitization for security.

Provides validators and sanitizers for user inputs including paths,
filenames, feature names, and spec content.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

from sdd_server.infrastructure.exceptions import InputValidationError, PathTraversalError
from sdd_server.utils.logging import get_logger

logger = get_logger(__name__)


# Regex patterns for validation
FEATURE_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*[a-z0-9]$|^[a-z]$")
DANGEROUS_PATH_PATTERNS = [
    re.compile(r"\.\."),  # Directory traversal
    re.compile(r"~"),  # Home directory expansion
    re.compile(r"\$"),  # Environment variable expansion
    re.compile(r"%"),  # Windows environment variables
    re.compile(r"\0"),  # Null bytes
]
DANGEROUS_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
HTML_TAGS_PATTERN = re.compile(r"<[^>]+>")
SCRIPT_PATTERN = re.compile(
    r"<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>",
    re.IGNORECASE | re.DOTALL,
)


@dataclass
class ValidationError:
    """Represents a single validation error."""

    field: str
    message: str
    value: str | None = None
    constraint: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        """Convert to dictionary."""
        return {
            "field": self.field,
            "message": self.message,
            "value": self.value,
            "constraint": self.constraint,
        }


class InputValidator:
    """Validates user inputs against security constraints."""

    def __init__(
        self,
        max_string_length: int = 10000,
        max_content_length: int = 1_000_000,  # 1MB
        allowed_extensions: Sequence[str] | None = None,
    ) -> None:
        """Initialize the validator.

        Args:
            max_string_length: Maximum length for string fields
            max_content_length: Maximum length for content fields
            allowed_extensions: Allowed file extensions (with dot)
        """
        self.max_string_length = max_string_length
        self.max_content_length = max_content_length
        self.allowed_extensions = set(allowed_extensions) if allowed_extensions else None

    def validate_string(
        self,
        value: str,
        field_name: str,
        min_length: int = 0,
        max_length: int | None = None,
        pattern: re.Pattern[str] | None = None,
    ) -> str:
        """Validate a string field.

        Args:
            value: String to validate
            field_name: Name of the field for error messages
            min_length: Minimum length required
            max_length: Maximum length allowed (defaults to max_string_length)
            pattern: Optional regex pattern to match

        Returns:
            Validated string

        Raises:
            InputValidationError: If validation fails
        """
        max_len = max_length or self.max_string_length

        if len(value) < min_length:
            raise InputValidationError(
                f"{field_name} must be at least {min_length} characters",
                field=field_name,
                value=value[:50] if len(value) > 50 else value,
            )

        if len(value) > max_len:
            raise InputValidationError(
                f"{field_name} must be at most {max_len} characters",
                field=field_name,
                value=value[:50] if len(value) > 50 else value,
            )

        if pattern and not pattern.match(value):
            raise InputValidationError(
                f"{field_name} has invalid format",
                field=field_name,
                value=value[:50] if len(value) > 50 else value,
            )

        return value

    def validate_content(self, content: str, field_name: str = "content") -> str:
        """Validate content field (larger strings like specs).

        Args:
            content: Content to validate
            field_name: Name of the field

        Returns:
            Validated content

        Raises:
            InputValidationError: If validation fails
        """
        if len(content) > self.max_content_length:
            raise InputValidationError(
                f"{field_name} exceeds maximum size of {self.max_content_length} bytes",
                field=field_name,
                value=f"{len(content)} bytes",
            )

        # Check for null bytes
        if "\0" in content:
            raise InputValidationError(
                f"{field_name} contains null bytes",
                field=field_name,
                value="<contains null bytes>",
            )

        return content


class PathValidator:
    """Validates and sanitizes file paths."""

    def __init__(
        self,
        allowed_root: Path,
        allow_absolute: bool = False,
        allowed_extensions: Sequence[str] | None = None,
    ) -> None:
        """Initialize path validator.

        Args:
            allowed_root: Root directory that paths must be within
            allow_absolute: Whether to allow absolute paths
            allowed_extensions: Allowed file extensions (with dot)
        """
        self.allowed_root = allowed_root.resolve()
        self.allow_absolute = allow_absolute
        self.allowed_extensions = set(allowed_extensions) if allowed_extensions else None

    def validate(self, path: str | Path) -> Path:
        """Validate a path and return the safe resolved path.

        Args:
            path: Path to validate

        Returns:
            Resolved safe path

        Raises:
            PathTraversalError: If path is outside allowed root
            InputValidationError: If path is invalid
        """
        if isinstance(path, str):
            path = Path(path)

        # Check for dangerous patterns in string representation
        path_str = str(path)
        for pattern in DANGEROUS_PATH_PATTERNS:
            if pattern.search(path_str):
                # Log potential attack
                logger.warning(
                    "path_validation_blocked",
                    path=path_str,
                    pattern=pattern.pattern,
                )
                raise PathTraversalError(f"Path contains forbidden pattern: {pattern.pattern}")

        # Check for null bytes
        if "\0" in path_str:
            raise InputValidationError("Path contains null bytes")

        # Resolve the path
        if path.is_absolute():
            if not self.allow_absolute:
                raise InputValidationError("Absolute paths are not allowed")
            resolved = path.resolve()
        else:
            resolved = (self.allowed_root / path).resolve()

        # Ensure within allowed root
        try:
            resolved.relative_to(self.allowed_root)
        except ValueError as exc:
            raise PathTraversalError(f"Path '{path}' resolves outside allowed root") from exc

        # Check extension if specified
        if self.allowed_extensions and resolved.suffix not in self.allowed_extensions:
            raise InputValidationError(
                f"File extension '{resolved.suffix}' not allowed. "
                f"Allowed: {', '.join(self.allowed_extensions)}"
            )

        return resolved

    def is_safe(self, path: str | Path) -> bool:
        """Check if a path is safe without raising exceptions.

        Args:
            path: Path to check

        Returns:
            True if path is safe, False otherwise
        """
        try:
            self.validate(path)
            return True
        except (PathTraversalError, InputValidationError):
            return False


class InputSanitizer:
    """Sanitizes user inputs for safe storage and display."""

    @staticmethod
    def sanitize_filename(filename: str, max_length: int = 255) -> str:
        """Sanitize a filename for safe filesystem use.

        Args:
            filename: Original filename
            max_length: Maximum filename length

        Returns:
            Sanitized filename
        """
        # Remove null bytes
        filename = filename.replace("\0", "")

        # Normalize unicode
        filename = unicodedata.normalize("NFKD", filename)

        # Remove dangerous characters
        filename = DANGEROUS_FILENAME_CHARS.sub("_", filename)

        # Remove leading/trailing dots and spaces
        filename = filename.strip(". ")

        # Collapse multiple underscores
        while "__" in filename:
            filename = filename.replace("__", "_")

        # Truncate if needed
        if len(filename) > max_length:
            # Preserve extension if present
            name, ext = filename.rsplit(".", 1) if "." in filename else (filename, "")
            max_name = max_length - len(ext) - 1 if ext else max_length
            filename = f"{name[:max_name]}.{ext}" if ext else name[:max_name]

        # Fallback for empty filenames
        if not filename:
            filename = "unnamed"

        return filename

    @staticmethod
    def sanitize_html(text: str) -> str:
        """Remove HTML tags from text.

        Args:
            text: Text that may contain HTML

        Returns:
            Text with HTML tags removed
        """
        # Remove script tags first
        text = SCRIPT_PATTERN.sub("", text)
        # Remove other HTML tags
        text = HTML_TAGS_PATTERN.sub("", text)
        return text.strip()

    @staticmethod
    def sanitize_for_log(text: str, max_length: int = 200) -> str:
        """Sanitize text for safe logging.

        Args:
            text: Text to sanitize
            max_length: Maximum length to log

        Returns:
            Sanitized text safe for logging
        """
        # Remove newlines and control characters
        text = "".join(c if c.isprintable() or c == " " else " " for c in text)
        # Truncate
        if len(text) > max_length:
            text = text[:max_length] + "..."
        return text


# Convenience functions
def validate_path(
    path: str | Path,
    allowed_root: Path,
    allowed_extensions: Sequence[str] | None = None,
) -> Path:
    """Validate a path is within allowed root.

    Args:
        path: Path to validate
        allowed_root: Root directory paths must be within
        allowed_extensions: Optional allowed file extensions

    Returns:
        Resolved safe path
    """
    validator = PathValidator(
        allowed_root=allowed_root,
        allowed_extensions=allowed_extensions,
    )
    return validator.validate(path)


def validate_feature_name(name: str) -> str:
    """Validate a feature name.

    Feature names must be lowercase alphanumeric with underscores/hyphens,
    starting with a letter.

    Args:
        name: Feature name to validate

    Returns:
        Validated feature name

    Raises:
        InputValidationError: If name is invalid
    """
    if not name:
        raise InputValidationError("Feature name cannot be empty")

    if len(name) > 100:
        raise InputValidationError("Feature name must be at most 100 characters")

    if not FEATURE_NAME_PATTERN.match(name):
        raise InputValidationError(
            "Feature name must be lowercase alphanumeric with underscores/hyphens, "
            "starting with a letter",
            field="feature_name",
            value=name,
        )

    return name


def validate_spec_content(content: str, max_size: int = 1_000_000) -> str:
    """Validate spec content.

    Args:
        content: Spec content to validate
        max_size: Maximum content size in bytes

    Returns:
        Validated content

    Raises:
        InputValidationError: If content is invalid
    """
    if len(content) > max_size:
        raise InputValidationError(f"Spec content exceeds maximum size of {max_size} bytes")

    if "\0" in content:
        raise InputValidationError("Spec content contains null bytes")

    return content


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename for safe filesystem use."""
    return InputSanitizer.sanitize_filename(filename)


def sanitize_html(text: str) -> str:
    """Remove HTML tags from text."""
    return InputSanitizer.sanitize_html(text)
