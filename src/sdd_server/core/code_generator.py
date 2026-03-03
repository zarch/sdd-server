"""Code generator — generates implementation scaffolding from templates.

The CodeGenerator creates Python code files by:
1. Loading Jinja2 templates from the templates/code directory
2. Building context from feature specs and user input
3. Rendering templates and writing to the appropriate location
4. Tracking generated files for reporting

Architecture reference: arch.md Section 5.3 (Code Generation)
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, PackageLoader, Template

from sdd_server.infrastructure.filesystem import FileSystemClient
from sdd_server.models.codegen import (
    CodeTemplate,
    CodeTemplateType,
    GeneratedFile,
    GenerationResult,
    ScaffoldConfig,
)
from sdd_server.utils.logging import get_logger
from sdd_server.utils.paths import SpecsPaths

logger = get_logger(__name__)


class CodeGenerationError(Exception):
    """Raised when code generation fails."""

    pass


# Built-in template definitions
BUILTIN_TEMPLATES: dict[str, CodeTemplate] = {
    "module": CodeTemplate(
        name="module",
        template_type=CodeTemplateType.MODULE,
        description="Python module scaffold with classes and functions",
        file_pattern="{{ module_name }}.py",
        default_path="src/{{ package_name }}",
        template_path="module.py.j2",
        required_context=["module_name"],
        optional_context={
            "description": "",
            "author": "",
            "classes": [],
            "functions": [],
            "imports": [],
        },
    ),
    "test": CodeTemplate(
        name="test",
        template_type=CodeTemplateType.TEST,
        description="Unit test file scaffold",
        file_pattern="test_{{ module_name }}.py",
        default_path="tests/unit",
        template_path="test.py.j2",
        required_context=["module_name"],
        optional_context={
            "description": "",
            "author": "",
            "import_path": "",
            "classes": [],
            "functions": [],
        },
    ),
    "model": CodeTemplate(
        name="model",
        template_type=CodeTemplateType.MODEL,
        description="Pydantic model scaffold",
        file_pattern="{{ class_name | lower }}.py",
        default_path="src/{{ package_name }}/models",
        template_path="model.py.j2",
        required_context=["class_name"],
        optional_context={
            "description": "",
            "author": "",
            "models": [],
        },
    ),
    "service": CodeTemplate(
        name="service",
        template_type=CodeTemplateType.SERVICE,
        description="Service class scaffold with filesystem integration",
        file_pattern="{{ service_name | lower }}.py",
        default_path="src/{{ package_name }}/core",
        template_path="service.py.j2",
        required_context=["service_name"],
        optional_context={
            "description": "",
            "author": "",
            "methods": [],
            "init_args": [],
            "helpers": [],
            "imports": [],
        },
    ),
    "tool": CodeTemplate(
        name="tool",
        template_type=CodeTemplateType.TOOL,
        description="MCP tool scaffold with FastMCP integration",
        file_pattern="{{ tool_name | lower }}.py",
        default_path="src/{{ package_name }}/mcp/tools",
        template_path="tool.py.j2",
        required_context=["tool_name"],
        optional_context={
            "description": "",
            "author": "",
            "tools": [],
        },
    ),
    "config_yaml": CodeTemplate(
        name="config_yaml",
        template_type=CodeTemplateType.CONFIG,
        description="YAML configuration file",
        file_pattern="{{ config_name | lower }}.yaml",
        default_path="config",
        template_path="config.yaml.j2",
        required_context=["config_name"],
        optional_context={
            "description": "",
            "project_name": "",
            "sections": [],
        },
    ),
    "config_ini": CodeTemplate(
        name="config_ini",
        template_type=CodeTemplateType.CONFIG,
        description="INI configuration file",
        file_pattern="{{ config_name | lower }}.ini",
        default_path="config",
        template_path="config.ini.j2",
        required_context=["config_name"],
        optional_context={
            "description": "",
            "project_name": "",
            "sections": [],
        },
    ),
}


class CodeGenerator:
    """Generates code files from Jinja2 templates.

    The CodeGenerator creates implementation scaffolding by combining
    templates with context. It supports:
    - Multiple template types (module, test, model, service, tool, config)
    - Custom templates via template_path
    - Dry-run mode for previewing generated code
    - Overwrite protection

    Usage:
        generator = CodeGenerator(project_root=Path("/project"))

        # Generate a module
        result = generator.generate_from_template(
            template_name="module",
            context={"module_name": "my_module", "description": "My module"},
        )

        # Scaffold a full feature
        result = generator.scaffold(ScaffoldConfig(
            name="my_feature",
            templates=[CodeTemplateType.MODULE, CodeTemplateType.TEST],
        ))
    """

    def __init__(
        self,
        project_root: Path,
        specs_dir: str = "specs",
    ) -> None:
        """Initialize the code generator.

        Args:
            project_root: Project root directory
            specs_dir: Name of the specs directory
        """
        self.project_root = project_root.resolve()
        self._paths = SpecsPaths(self.project_root, specs_dir)
        self._fs = FileSystemClient(self.project_root)
        self._jinja = Environment(
            loader=PackageLoader("sdd_server", "templates/code"),
            autoescape=False,
            keep_trailing_newline=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self._templates = dict(BUILTIN_TEMPLATES)

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def list_templates(self) -> list[CodeTemplate]:
        """List all available templates."""
        return list(self._templates.values())

    def get_template(self, name: str) -> CodeTemplate | None:
        """Get a template by name."""
        return self._templates.get(name)

    def register_template(self, template: CodeTemplate) -> None:
        """Register a custom template."""
        self._templates[template.name] = template
        logger.debug("Registered template", name=template.name)

    def generate_from_template(
        self,
        template_name: str,
        context: dict[str, Any],
        output_path: Path | None = None,
        overwrite: bool = False,
        dry_run: bool = False,
    ) -> GeneratedFile:
        """Generate a file from a named template.

        Args:
            template_name: Name of the template to use
            context: Template context variables
            output_path: Optional override for output path
            overwrite: Whether to overwrite existing files
            dry_run: If True, don't write the file

        Returns:
            GeneratedFile with metadata

        Raises:
            CodeGenerationError: If generation fails
        """
        template = self._templates.get(template_name)
        if template is None:
            raise CodeGenerationError(f"Template not found: {template_name}")

        return self._generate(template, context, output_path, overwrite, dry_run)

    def generate_from_string(
        self,
        template_content: str,
        context: dict[str, Any],
        output_path: Path,
        overwrite: bool = False,
        dry_run: bool = False,
    ) -> GeneratedFile:
        """Generate a file from a template string.

        Args:
            template_content: Jinja2 template content
            context: Template context variables
            output_path: Where to write the file
            overwrite: Whether to overwrite existing files
            dry_run: If True, don't write the file

        Returns:
            GeneratedFile with metadata
        """
        # Create a temporary template definition
        template = CodeTemplate(
            name="inline",
            template_type=CodeTemplateType.CUSTOM,
            description="Inline template",
            file_pattern=output_path.name,
            default_path=str(output_path.parent),
            template_content=template_content,
            required_context=[],
        )

        return self._generate(template, context, output_path, overwrite, dry_run)

    def scaffold(
        self,
        config: ScaffoldConfig,
        extra_context: dict[str, Any] | None = None,
    ) -> GenerationResult:
        """Scaffold a new feature or module with multiple files.

        Args:
            config: Scaffold configuration
            extra_context: Additional context variables

        Returns:
            GenerationResult with all generated files
        """
        result = GenerationResult(success=True)
        base_context = self._build_scaffold_context(config, extra_context)

        for template_type in config.templates:
            template = self._find_template_by_type(template_type)
            if template is None:
                result.errors.append(f"No template found for type: {template_type}")
                continue

            try:
                generated = self._generate(
                    template,
                    {**base_context, **self._type_specific_context(template_type, config)},
                    None,
                    config.overwrite,
                    config.dry_run,
                )
                result.files.append(generated)
                logger.info(
                    "Generated file",
                    template=template.name,
                    path=str(generated.path),
                )
            except CodeGenerationError as e:
                result.errors.append(str(e))
                logger.error("Generation failed", template=template.name, error=str(e))

        result.success = len(result.errors) == 0
        return result

    def render_preview(
        self,
        template_name: str,
        context: dict[str, Any],
    ) -> str:
        """Render a template without writing to disk.

        Args:
            template_name: Name of the template
            context: Template context variables

        Returns:
            Rendered content as string
        """
        template = self._templates.get(template_name)
        if template is None:
            raise CodeGenerationError(f"Template not found: {template_name}")

        full_context = self._prepare_context(template, context)
        return self._render_template(template, full_context)

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    def _generate(
        self,
        template: CodeTemplate,
        context: dict[str, Any],
        output_path: Path | None,
        overwrite: bool,
        dry_run: bool,
    ) -> GeneratedFile:
        """Generate a file from a template definition."""
        # Validate required context
        self._validate_context(template, context)

        # Prepare full context
        full_context = self._prepare_context(template, context)

        # Determine output path
        if output_path is None:
            output_path = self._resolve_output_path(template, full_context)

        # Check if file exists
        exists = self._fs.file_exists(output_path)
        if exists and not overwrite:
            return GeneratedFile(
                path=output_path,
                template_name=template.name,
                template_type=template.template_type,
                context=full_context,
                overwritten=False,
                size_bytes=0,
                line_count=0,
            )

        # Render template
        content = self._render_template(template, full_context)

        # Write file if not dry run
        if not dry_run:
            self._fs.ensure_directory(output_path.parent)
            self._fs.write_file(output_path, content)
            logger.info("Generated file", path=str(output_path))

        # Count lines and bytes
        line_count = content.count("\n") + 1 if content else 0
        size_bytes = len(content.encode("utf-8"))

        return GeneratedFile(
            path=output_path,
            template_name=template.name,
            template_type=template.template_type,
            context=full_context,
            overwritten=exists and overwrite,
            size_bytes=size_bytes,
            line_count=line_count,
        )

    def _validate_context(
        self,
        template: CodeTemplate,
        context: dict[str, Any],
    ) -> None:
        """Validate that required context variables are present."""
        missing = []
        for key in template.required_context:
            if key not in context:
                missing.append(key)

        if missing:
            raise CodeGenerationError(
                f"Missing required context for template '{template.name}': {missing}"
            )

    def _prepare_context(
        self,
        template: CodeTemplate,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Prepare full context with defaults."""
        full_context = {
            **template.get_context_defaults(),
            **context,
            "date": context.get("date", datetime.now(UTC).strftime("%Y-%m-%d")),
            "project_name": context.get("project_name", self.project_root.name),
        }
        return full_context

    def _resolve_output_path(
        self,
        template: CodeTemplate,
        context: dict[str, Any],
    ) -> Path:
        """Resolve the output path for a generated file."""
        # Render the directory pattern
        dir_pattern = template.default_path
        dir_template = Template(dir_pattern)
        dir_str: str = dir_template.render(**context)

        # Render the filename pattern
        file_pattern = template.file_pattern
        file_template = Template(file_pattern)
        file_str: str = file_template.render(**context)

        return self.project_root / dir_str / file_str

    def _render_template(
        self,
        template: CodeTemplate,
        context: dict[str, Any],
    ) -> str:
        """Render a template with context."""
        try:
            if template.template_content:
                jinja_template = self._jinja.from_string(template.template_content)
            elif template.template_path:
                jinja_template = self._jinja.get_template(template.template_path)
            else:
                raise CodeGenerationError(f"Template '{template.name}' has no content or path")

            return str(jinja_template.render(**context))
        except Exception as e:
            raise CodeGenerationError(f"Failed to render template '{template.name}': {e}") from e

    def _find_template_by_type(self, template_type: CodeTemplateType) -> CodeTemplate | None:
        """Find a template by type."""
        for template in self._templates.values():
            if template.template_type == template_type:
                return template
        return None

    def _build_scaffold_context(
        self,
        config: ScaffoldConfig,
        extra_context: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Build context for scaffolding."""
        context: dict[str, Any] = {
            "name": config.name,
            "module_name": config.name.lower().replace("-", "_"),
            "class_name": "".join(word.capitalize() for word in config.name.split("_")),
            "service_name": "".join(word.capitalize() for word in config.name.split("_"))
            + "Service",
            "tool_name": "".join(word.capitalize() for word in config.name.split("_")),
            "description": config.description,
            "author": config.author,
            "project_name": self.project_root.name,
            "date": datetime.now(UTC).strftime("%Y-%m-%d"),
        }

        if config.package_name:
            context["package_name"] = config.package_name
        else:
            context["package_name"] = self.project_root.name.replace("-", "_")

        if extra_context:
            context.update(extra_context)

        return context

    def _type_specific_context(
        self,
        template_type: CodeTemplateType,
        config: ScaffoldConfig,
    ) -> dict[str, Any]:
        """Get type-specific context for a template type."""
        context: dict[str, Any] = {}

        if template_type == CodeTemplateType.TEST:
            # Set import path for tests
            package = config.package_name or self.project_root.name.replace("-", "_")
            context["import_path"] = f"{package}.{config.name.lower().replace('-', '_')}"

        return context
