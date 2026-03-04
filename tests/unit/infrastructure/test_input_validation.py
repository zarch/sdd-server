"""Tests for input validation and sanitization."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from sdd_server.infrastructure.exceptions import InputValidationError, PathTraversalError
from sdd_server.infrastructure.security.input_validation import (
    FEATURE_NAME_PATTERN,
    InputSanitizer,
    InputValidator,
    PathValidator,
    sanitize_filename,
    sanitize_html,
    validate_feature_name,
    validate_path,
    validate_spec_content,
)


class TestInputValidator:
    """Tests for InputValidator."""

    def test_validate_string_valid(self) -> None:
        validator = InputValidator()
        result = validator.validate_string("hello", "test_field")
        assert result == "hello"

    def test_validate_string_too_short(self) -> None:
        validator = InputValidator()
        with pytest.raises(InputValidationError, match="at least"):
            validator.validate_string("ab", "test_field", min_length=5)

    def test_validate_string_too_long(self) -> None:
        validator = InputValidator(max_string_length=10)
        with pytest.raises(InputValidationError, match="at most"):
            validator.validate_string("a" * 20, "test_field")

    def test_validate_string_with_pattern(self) -> None:
        validator = InputValidator()
        # Valid
        validator.validate_string("abc123", "field", pattern=FEATURE_NAME_PATTERN)
        # Invalid
        with pytest.raises(InputValidationError, match="invalid format"):
            validator.validate_string("ABC", "field", pattern=FEATURE_NAME_PATTERN)

    def test_validate_content_valid(self) -> None:
        validator = InputValidator()
        result = validator.validate_content("Some spec content")
        assert result == "Some spec content"

    def test_validate_content_too_large(self) -> None:
        validator = InputValidator(max_content_length=100)
        with pytest.raises(InputValidationError, match="maximum size"):
            validator.validate_content("x" * 200)

    def test_validate_content_null_bytes(self) -> None:
        validator = InputValidator()
        with pytest.raises(InputValidationError, match="null bytes"):
            validator.validate_content("hello\0world")


class TestPathValidator:
    """Tests for PathValidator."""

    def test_validate_relative_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            validator = PathValidator(allowed_root=Path(tmpdir))
            result = validator.validate("subdir/file.txt")
            assert str(result).startswith(tmpdir)

    def test_validate_absolute_path_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            validator = PathValidator(allowed_root=Path(tmpdir), allow_absolute=False)
            with pytest.raises(InputValidationError, match="Absolute paths"):
                validator.validate("/etc/passwd")

    def test_validate_traversal_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            validator = PathValidator(allowed_root=Path(tmpdir))
            with pytest.raises(PathTraversalError):
                validator.validate("../../../etc/passwd")

    def test_validate_extension_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            validator = PathValidator(
                allowed_root=Path(tmpdir),
                allowed_extensions=[".md", ".txt"],
            )
            # Valid
            validator.validate("file.md")
            # Invalid
            with pytest.raises(InputValidationError, match="extension"):
                validator.validate("file.exe")

    def test_is_safe(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            validator = PathValidator(allowed_root=Path(tmpdir))
            assert validator.is_safe("file.txt")
            assert not validator.is_safe("../../../etc/passwd")

    def test_null_bytes_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            validator = PathValidator(allowed_root=Path(tmpdir))
            with pytest.raises(PathTraversalError):
                validator.validate("file\0.txt")


class TestInputSanitizer:
    """Tests for InputSanitizer."""

    def test_sanitize_filename_basic(self) -> None:
        assert InputSanitizer.sanitize_filename("hello.txt") == "hello.txt"

    def test_sanitize_filename_dangerous_chars(self) -> None:
        result = InputSanitizer.sanitize_filename('file<>:"/\\|?*.txt')
        assert "<" not in result
        assert ">" not in result
        assert ":" not in result
        assert '"' not in result
        assert "/" not in result
        assert "\\" not in result
        assert "|" not in result
        assert "?" not in result
        assert "*" not in result

    def test_sanitize_filename_null_bytes(self) -> None:
        assert InputSanitizer.sanitize_filename("file\0name.txt") == "filename.txt"

    def test_sanitize_filename_truncate(self) -> None:
        long_name = "a" * 300 + ".txt"
        result = InputSanitizer.sanitize_filename(long_name, max_length=255)
        assert len(result) <= 255

    def test_sanitize_filename_empty_fallback(self) -> None:
        assert InputSanitizer.sanitize_filename("") == "unnamed"
        assert InputSanitizer.sanitize_filename("...") == "unnamed"

    def test_sanitize_html_basic(self) -> None:
        assert InputSanitizer.sanitize_html("<p>Hello</p>") == "Hello"

    def test_sanitize_html_script_removed(self) -> None:
        result = InputSanitizer.sanitize_html("<script>alert('xss')</script>Hello")
        assert "<script>" not in result
        assert "alert" not in result

    def test_sanitize_for_log(self) -> None:
        result = InputSanitizer.sanitize_for_log("line1\nline2\ttab", max_length=100)
        assert "\n" not in result
        assert "\t" not in result

    def test_sanitize_for_log_truncate(self) -> None:
        long_text = "x" * 300
        result = InputSanitizer.sanitize_for_log(long_text, max_length=200)
        assert len(result) <= 203  # 200 + "..."
        assert result.endswith("...")


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_validate_path_function(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = validate_path("file.txt", Path(tmpdir))
            assert str(result).endswith("file.txt")

    def test_validate_feature_name_valid(self) -> None:
        assert validate_feature_name("my_feature") == "my_feature"
        assert validate_feature_name("feature-123") == "feature-123"
        assert validate_feature_name("a") == "a"

    def test_validate_feature_name_empty(self) -> None:
        with pytest.raises(InputValidationError, match="empty"):
            validate_feature_name("")

    def test_validate_feature_name_too_long(self) -> None:
        with pytest.raises(InputValidationError, match="100"):
            validate_feature_name("a" * 101)

    def test_validate_feature_name_uppercase(self) -> None:
        with pytest.raises(InputValidationError):
            validate_feature_name("MyFeature")

    def test_validate_feature_name_starts_with_number(self) -> None:
        with pytest.raises(InputValidationError):
            validate_feature_name("123feature")

    def test_validate_spec_content_valid(self) -> None:
        content = "# My Spec\n\nSome content here."
        assert validate_spec_content(content) == content

    def test_validate_spec_content_too_large(self) -> None:
        with pytest.raises(InputValidationError):
            validate_spec_content("x" * 2_000_000, max_size=1_000_000)

    def test_sanitize_filename_function(self) -> None:
        assert sanitize_filename("file<>.txt") == "file_.txt"

    def test_sanitize_html_function(self) -> None:
        assert sanitize_html("<b>bold</b>") == "bold"
