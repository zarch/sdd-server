"""Tests for codegen models."""

from __future__ import annotations

from pathlib import Path

import pytest

from sdd_server.models.codegen import (
    CodeTemplate,
    CodeTemplateType,
    GeneratedFile,
    GenerationResult,
    ScaffoldConfig,
)


class TestCodeTemplateType:
    """Tests for CodeTemplateType enum."""

    def test_all_types_exist(self) -> None:
        """All expected template types should exist."""
        expected = {
            "module",
            "class",
            "test",
            "api",
            "config",
            "model",
            "service",
            "tool",
            "custom",
        }
        actual = {t.value for t in CodeTemplateType}
        assert expected == actual

    def test_from_string(self) -> None:
        """Should create from string value."""
        assert CodeTemplateType("module") == CodeTemplateType.MODULE
        assert CodeTemplateType("test") == CodeTemplateType.TEST

    def test_invalid_type_raises(self) -> None:
        """Invalid type should raise ValueError."""
        with pytest.raises(ValueError):
            CodeTemplateType("invalid")


class TestCodeTemplate:
    """Tests for CodeTemplate model."""

    def test_minimal_template(self) -> None:
        """Should create with minimal required fields."""
        template = CodeTemplate(
            name="test",
            template_type=CodeTemplateType.MODULE,
            description="Test template",
            file_pattern="test.py",
            default_path="src",
        )
        assert template.name == "test"
        assert template.template_type == CodeTemplateType.MODULE
        assert template.required_context == []
        assert template.optional_context == {}

    def test_full_template(self) -> None:
        """Should create with all fields."""
        template = CodeTemplate(
            name="full",
            template_type=CodeTemplateType.CUSTOM,
            description="Full template",
            file_pattern="{{ name }}.py",
            default_path="src/{{ package }}",
            template_content="# {{ name }}",
            template_path=None,
            required_context=["name"],
            optional_context={"author": "Unknown", "description": ""},
        )
        assert template.name == "full"
        assert template.template_content == "# {{ name }}"
        assert len(template.required_context) == 1

    def test_get_context_defaults(self) -> None:
        """Should return copy of optional context."""
        template = CodeTemplate(
            name="test",
            template_type=CodeTemplateType.MODULE,
            description="Test",
            file_pattern="test.py",
            default_path="src",
            optional_context={"author": "Test", "version": "1.0"},
        )
        defaults = template.get_context_defaults()
        assert defaults == {"author": "Test", "version": "1.0"}
        # Should be a copy
        defaults["new"] = "value"
        assert "new" not in template.optional_context


class TestGeneratedFile:
    """Tests for GeneratedFile model."""

    def test_minimal_file(self) -> None:
        """Should create with minimal fields."""
        gf = GeneratedFile(
            path=Path("test.py"),
            template_name="module",
            template_type=CodeTemplateType.MODULE,
            context={},
        )
        assert gf.path == Path("test.py")
        assert not gf.overwritten
        assert gf.size_bytes == 0
        assert gf.line_count == 0

    def test_full_file(self) -> None:
        """Should create with all fields."""
        gf = GeneratedFile(
            path=Path("src/module.py"),
            template_name="module",
            template_type=CodeTemplateType.MODULE,
            context={"module_name": "test"},
            overwritten=True,
            size_bytes=1024,
            line_count=50,
        )
        assert gf.overwritten
        assert gf.size_bytes == 1024
        assert gf.line_count == 50


class TestGenerationResult:
    """Tests for GenerationResult model."""

    def test_empty_result(self) -> None:
        """Should create empty result."""
        result = GenerationResult(success=True)
        assert result.success
        assert result.file_count == 0
        assert result.total_lines == 0
        assert result.total_bytes == 0

    def test_with_files(self) -> None:
        """Should calculate totals correctly."""
        result = GenerationResult(
            success=True,
            files=[
                GeneratedFile(
                    path=Path("a.py"),
                    template_name="module",
                    template_type=CodeTemplateType.MODULE,
                    context={},
                    size_bytes=100,
                    line_count=10,
                ),
                GeneratedFile(
                    path=Path("b.py"),
                    template_name="module",
                    template_type=CodeTemplateType.MODULE,
                    context={},
                    size_bytes=200,
                    line_count=20,
                ),
            ],
        )
        assert result.file_count == 2
        assert result.total_lines == 30
        assert result.total_bytes == 300

    def test_with_errors(self) -> None:
        """Should track errors."""
        result = GenerationResult(
            success=False,
            errors=["Missing template", "Invalid context"],
        )
        assert not result.success
        assert len(result.errors) == 2

    def test_with_skipped(self) -> None:
        """Should track skipped files."""
        result = GenerationResult(
            success=True,
            skipped=["existing.py", "protected.py"],
        )
        assert len(result.skipped) == 2


class TestScaffoldConfig:
    """Tests for ScaffoldConfig model."""

    def test_minimal_config(self) -> None:
        """Should create with minimal fields."""
        config = ScaffoldConfig(name="my_feature")
        assert config.name == "my_feature"
        assert config.description == ""
        assert config.templates == [CodeTemplateType.MODULE, CodeTemplateType.TEST]
        assert not config.overwrite
        assert not config.dry_run

    def test_full_config(self) -> None:
        """Should create with all fields."""
        config = ScaffoldConfig(
            name="auth",
            description="Authentication module",
            templates=[CodeTemplateType.MODULE, CodeTemplateType.TEST, CodeTemplateType.MODEL],
            output_dir="custom",
            package_name="myapp",
            author="Developer",
            overwrite=True,
            dry_run=True,
        )
        assert config.name == "auth"
        assert config.description == "Authentication module"
        assert len(config.templates) == 3
        assert config.output_dir == "custom"
        assert config.package_name == "myapp"
        assert config.author == "Developer"
        assert config.overwrite
        assert config.dry_run

    def test_template_types(self) -> None:
        """Should accept all template types."""
        all_types = list(CodeTemplateType)
        config = ScaffoldConfig(
            name="test",
            templates=all_types,
        )
        assert len(config.templates) == len(all_types)
