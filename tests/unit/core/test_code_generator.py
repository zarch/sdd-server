"""Tests for CodeGenerator core class."""

from __future__ import annotations

from pathlib import Path

import pytest

from sdd_server.core.code_generator import (
    BUILTIN_TEMPLATES,
    CodeGenerationError,
    CodeGenerator,
)
from sdd_server.models.codegen import (
    CodeTemplate,
    CodeTemplateType,
    ScaffoldConfig,
)


class TestCodeGeneratorInit:
    """Tests for CodeGenerator initialization."""

    def test_init_with_defaults(self, tmp_path: Path) -> None:
        """Should initialize with default settings."""
        generator = CodeGenerator(tmp_path)
        assert generator.project_root == tmp_path.resolve()
        assert generator._templates == BUILTIN_TEMPLATES

    def test_init_with_custom_specs_dir(self, tmp_path: Path) -> None:
        """Should accept custom specs directory."""
        generator = CodeGenerator(tmp_path, specs_dir="custom_specs")
        assert generator.project_root == tmp_path.resolve()


class TestCodeGeneratorTemplates:
    """Tests for template management."""

    def test_list_templates(self, tmp_path: Path) -> None:
        """Should list all available templates."""
        generator = CodeGenerator(tmp_path)
        templates = generator.list_templates()
        assert len(templates) >= 7  # At least 7 built-in templates

        names = [t.name for t in templates]
        assert "module" in names
        assert "test" in names
        assert "model" in names
        assert "service" in names
        assert "tool" in names

    def test_get_template_existing(self, tmp_path: Path) -> None:
        """Should get existing template."""
        generator = CodeGenerator(tmp_path)
        template = generator.get_template("module")
        assert template is not None
        assert template.name == "module"
        assert template.template_type == CodeTemplateType.MODULE

    def test_get_template_missing(self, tmp_path: Path) -> None:
        """Should return None for missing template."""
        generator = CodeGenerator(tmp_path)
        template = generator.get_template("nonexistent")
        assert template is None

    def test_register_template(self, tmp_path: Path) -> None:
        """Should register custom template."""
        generator = CodeGenerator(tmp_path)
        custom = CodeTemplate(
            name="custom",
            template_type=CodeTemplateType.CUSTOM,
            description="Custom template",
            file_pattern="{{ name }}.py",
            default_path="custom",
            template_content="# {{ name }}",
        )
        generator.register_template(custom)

        retrieved = generator.get_template("custom")
        assert retrieved is not None
        assert retrieved.name == "custom"


class TestCodeGeneratorGenerate:
    """Tests for code generation."""

    def test_generate_module_basic(self, tmp_path: Path) -> None:
        """Should generate a basic module."""
        generator = CodeGenerator(tmp_path)
        result = generator.generate_from_template(
            template_name="module",
            context={"module_name": "my_module"},
        )

        assert result.path.exists()
        assert result.template_name == "module"
        assert result.template_type == CodeTemplateType.MODULE
        assert not result.overwritten
        assert result.line_count > 0
        assert result.size_bytes > 0

        content = result.path.read_text()
        assert "my_module" in content
        assert "from __future__ import annotations" in content

    def test_generate_module_with_description(self, tmp_path: Path) -> None:
        """Should include description in generated module."""
        generator = CodeGenerator(tmp_path)
        result = generator.generate_from_template(
            template_name="module",
            context={
                "module_name": "auth",
                "description": "Authentication module",
            },
        )

        content = result.path.read_text()
        assert "Authentication module" in content

    def test_generate_test(self, tmp_path: Path) -> None:
        """Should generate a test file."""
        generator = CodeGenerator(tmp_path)
        result = generator.generate_from_template(
            template_name="test",
            context={"module_name": "auth"},
        )

        assert result.path.exists()
        assert result.path.name == "test_auth.py"
        assert "import pytest" in result.path.read_text()

    def test_generate_model(self, tmp_path: Path) -> None:
        """Should generate a Pydantic model file."""
        generator = CodeGenerator(tmp_path)
        result = generator.generate_from_template(
            template_name="model",
            context={"class_name": "User"},
        )

        assert result.path.exists()
        content = result.path.read_text()
        assert "from pydantic import Field" in content
        assert "class User(SDDBaseModel)" in content

    def test_generate_service(self, tmp_path: Path) -> None:
        """Should generate a service file."""
        generator = CodeGenerator(tmp_path)
        result = generator.generate_from_template(
            template_name="service",
            context={"service_name": "Auth"},
        )

        assert result.path.exists()
        content = result.path.read_text()
        assert "class AuthService" in content
        assert "AuthServiceError" in content

    def test_generate_tool(self, tmp_path: Path) -> None:
        """Should generate an MCP tool file."""
        generator = CodeGenerator(tmp_path)
        result = generator.generate_from_template(
            template_name="tool",
            context={"tool_name": "Auth"},
        )

        assert result.path.exists()
        content = result.path.read_text()
        assert "from mcp.server.fastmcp import Context, FastMCP" in content
        assert "register_tools" in content

    def test_generate_config_yaml(self, tmp_path: Path) -> None:
        """Should generate a YAML config file."""
        generator = CodeGenerator(tmp_path)
        result = generator.generate_from_template(
            template_name="config_yaml",
            context={"config_name": "settings"},
        )

        assert result.path.exists()
        assert result.path.suffix == ".yaml"
        assert "SDD:" in result.path.read_text()

    def test_generate_config_ini(self, tmp_path: Path) -> None:
        """Should generate an INI config file."""
        generator = CodeGenerator(tmp_path)
        result = generator.generate_from_template(
            template_name="config_ini",
            context={"config_name": "settings"},
        )

        assert result.path.exists()
        assert result.path.suffix == ".ini"
        assert "[sdd]" in result.path.read_text()

    def test_generate_with_missing_required_context(self, tmp_path: Path) -> None:
        """Should raise error for missing required context."""
        generator = CodeGenerator(tmp_path)
        with pytest.raises(CodeGenerationError) as exc_info:
            generator.generate_from_template(
                template_name="module",
                context={},  # Missing module_name
            )
        assert "module_name" in str(exc_info.value)

    def test_generate_with_invalid_template(self, tmp_path: Path) -> None:
        """Should raise error for invalid template."""
        generator = CodeGenerator(tmp_path)
        with pytest.raises(CodeGenerationError) as exc_info:
            generator.generate_from_template(
                template_name="nonexistent",
                context={},
            )
        assert "not found" in str(exc_info.value)

    def test_generate_no_overwrite(self, tmp_path: Path) -> None:
        """Should not overwrite existing file by default."""
        generator = CodeGenerator(tmp_path)

        # First generation
        generator.generate_from_template(
            template_name="module",
            context={"module_name": "test"},
        )

        # Second generation - should not overwrite
        result = generator.generate_from_template(
            template_name="module",
            context={"module_name": "test"},
        )
        assert not result.overwritten

    def test_generate_with_overwrite(self, tmp_path: Path) -> None:
        """Should overwrite when requested."""
        generator = CodeGenerator(tmp_path)

        # First generation
        generator.generate_from_template(
            template_name="module",
            context={"module_name": "test"},
        )

        # Second generation with overwrite
        result = generator.generate_from_template(
            template_name="module",
            context={"module_name": "test"},
            overwrite=True,
        )
        assert result.overwritten

    def test_generate_dry_run(self, tmp_path: Path) -> None:
        """Should not write file in dry-run mode."""
        generator = CodeGenerator(tmp_path)
        result = generator.generate_from_template(
            template_name="module",
            context={"module_name": "test"},
            dry_run=True,
        )

        # File should not exist
        assert not result.path.exists()
        # But we should still get metadata
        assert result.line_count > 0

    def test_generate_with_custom_output_path(self, tmp_path: Path) -> None:
        """Should use custom output path."""
        generator = CodeGenerator(tmp_path)
        custom_path = tmp_path / "custom" / "my_file.py"
        result = generator.generate_from_template(
            template_name="module",
            context={"module_name": "test"},
            output_path=custom_path,
        )

        assert result.path == custom_path
        assert custom_path.exists()


class TestCodeGeneratorGenerateFromString:
    """Tests for generating from template string."""

    def test_generate_from_string_basic(self, tmp_path: Path) -> None:
        """Should generate from inline template."""
        generator = CodeGenerator(tmp_path)
        result = generator.generate_from_string(
            template_content="# {{ name }}\nprint('Hello, {{ name }}!')",
            context={"name": "World"},
            output_path=tmp_path / "hello.py",
        )

        assert result.path.exists()
        content = result.path.read_text()
        assert "# World" in content
        assert "Hello, World!" in content

    def test_generate_from_string_with_overwrite(self, tmp_path: Path) -> None:
        """Should overwrite existing file."""
        generator = CodeGenerator(tmp_path)
        output_path = tmp_path / "test.py"

        # First generation
        generator.generate_from_string(
            template_content="first",
            context={},
            output_path=output_path,
        )
        assert output_path.read_text() == "first"

        # Second with overwrite
        result = generator.generate_from_string(
            template_content="second",
            context={},
            output_path=output_path,
            overwrite=True,
        )
        assert result.overwritten
        assert output_path.read_text() == "second"


class TestCodeGeneratorScaffold:
    """Tests for scaffolding multiple files."""

    def test_scaffold_default_templates(self, tmp_path: Path) -> None:
        """Should scaffold with default templates."""
        generator = CodeGenerator(tmp_path)
        config = ScaffoldConfig(name="auth")
        result = generator.scaffold(config)

        assert result.success
        assert result.file_count == 2  # module + test

        paths = [f.path.name for f in result.files]
        assert any("auth" in p for p in paths)
        assert any("test" in p for p in paths)

    def test_scaffold_custom_templates(self, tmp_path: Path) -> None:
        """Should scaffold with specified templates."""
        generator = CodeGenerator(tmp_path)
        config = ScaffoldConfig(
            name="user",
            templates=[CodeTemplateType.MODULE, CodeTemplateType.MODEL],
        )
        result = generator.scaffold(config)

        assert result.success
        assert result.file_count == 2

    def test_scaffold_with_description(self, tmp_path: Path) -> None:
        """Should include description in generated files."""
        generator = CodeGenerator(tmp_path)
        config = ScaffoldConfig(
            name="auth",
            description="Authentication module",
            templates=[CodeTemplateType.MODULE],
        )
        result = generator.scaffold(config)

        content = result.files[0].path.read_text()
        assert "Authentication module" in content

    def test_scaffold_dry_run(self, tmp_path: Path) -> None:
        """Should not write files in dry-run mode."""
        generator = CodeGenerator(tmp_path)
        config = ScaffoldConfig(
            name="test",
            dry_run=True,
        )
        result = generator.scaffold(config)

        assert result.success
        # Files should not exist
        for f in result.files:
            assert not f.path.exists()

    def test_scaffold_with_package_name(self, tmp_path: Path) -> None:
        """Should use custom package name."""
        generator = CodeGenerator(tmp_path)
        config = ScaffoldConfig(
            name="auth",
            package_name="myapp",
            templates=[CodeTemplateType.MODULE],
        )
        result = generator.scaffold(config)

        assert result.success
        assert "myapp" in str(result.files[0].path)

    def test_scaffold_invalid_template_type(self, tmp_path: Path) -> None:
        """Should report error for invalid template type."""
        generator = CodeGenerator(tmp_path)
        # Use a template type that has no registered template
        config = ScaffoldConfig(
            name="test",
            templates=[CodeTemplateType.API],  # No api template registered
        )
        result = generator.scaffold(config)

        # Should have error about missing template
        assert len(result.errors) > 0
        assert "No template found" in result.errors[0]


class TestCodeGeneratorPreview:
    """Tests for preview mode."""

    def test_preview_module(self, tmp_path: Path) -> None:
        """Should preview module without writing."""
        generator = CodeGenerator(tmp_path)
        content = generator.render_preview(
            template_name="module",
            context={"module_name": "preview"},
        )

        assert "preview" in content
        assert "from __future__ import annotations" in content

    def test_preview_test(self, tmp_path: Path) -> None:
        """Should preview test file."""
        generator = CodeGenerator(tmp_path)
        content = generator.render_preview(
            template_name="test",
            context={"module_name": "auth"},
        )

        assert "import pytest" in content
        assert "Test" in content  # Test class name

    def test_preview_missing_template(self, tmp_path: Path) -> None:
        """Should raise error for missing template."""
        generator = CodeGenerator(tmp_path)
        with pytest.raises(CodeGenerationError):
            generator.render_preview(
                template_name="nonexistent",
                context={},
            )


class TestBuiltInTemplates:
    """Tests for built-in template definitions."""

    def test_builtin_templates_complete(self) -> None:
        """All built-in templates should have required fields."""
        for name, template in BUILTIN_TEMPLATES.items():
            assert template.name == name
            assert template.description
            assert template.file_pattern
            assert template.default_path
            assert template.required_context is not None
            assert template.template_path is not None

    def test_module_template_context(self) -> None:
        """Module template should require module_name."""
        template = BUILTIN_TEMPLATES["module"]
        assert "module_name" in template.required_context

    def test_test_template_context(self) -> None:
        """Test template should require module_name."""
        template = BUILTIN_TEMPLATES["test"]
        assert "module_name" in template.required_context

    def test_service_template_context(self) -> None:
        """Service template should require service_name."""
        template = BUILTIN_TEMPLATES["service"]
        assert "service_name" in template.required_context

    def test_tool_template_context(self) -> None:
        """Tool template should require tool_name."""
        template = BUILTIN_TEMPLATES["tool"]
        assert "tool_name" in template.required_context
