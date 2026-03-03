"""Code generation models — templates and generated file metadata."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

from sdd_server.models.base import SDDBaseModel


class CodeTemplateType(str, Enum):
    """Types of code templates available for generation."""

    MODULE = "module"  # Python module scaffold
    CLASS = "class"  # Python class scaffold
    TEST = "test"  # Test file stub
    API = "api"  # API endpoint/client scaffold
    CONFIG = "config"  # Configuration file
    MODEL = "model"  # Pydantic model scaffold
    SERVICE = "service"  # Service class scaffold
    TOOL = "tool"  # MCP tool scaffold
    CUSTOM = "custom"  # User-defined template


class CodeTemplate(SDDBaseModel):
    """Represents a code template for generation.

    Templates are Jinja2 files that can be rendered with context
    to generate code files.
    """

    name: str
    """Template identifier (e.g., 'module', 'test_unit')."""

    template_type: CodeTemplateType
    """Type of template for categorization."""

    description: str
    """Human-readable description of what this template generates."""

    file_pattern: str
    """Pattern for output filename, supports Jinja2 variables.

    Example: '{{ module_name }}.py' or 'test_{{ module_name }}.py'
    """

    default_path: str
    """Default output directory relative to project root.

    Example: 'src/{{ package_name }}' or 'tests/unit'
    """

    template_content: str | None = None
    """Inline template content (for built-in templates)."""

    template_path: str | None = None
    """Path to external template file (for custom templates)."""

    required_context: list[str] = []  # noqa: RUF012
    """List of required context variables."""

    optional_context: dict[str, Any] = {}  # noqa: RUF012
    """Optional context variables with defaults."""

    def get_context_defaults(self) -> dict[str, Any]:
        """Get default values for optional context variables."""
        return dict(self.optional_context)


class GeneratedFile(SDDBaseModel):
    """Metadata about a generated code file."""

    path: Path
    """Path where the file was generated."""

    template_name: str
    """Name of the template used."""

    template_type: CodeTemplateType
    """Type of template used."""

    context: dict[str, Any]
    """Context used for generation."""

    overwritten: bool = False
    """Whether an existing file was overwritten."""

    size_bytes: int = 0
    """Size of the generated file in bytes."""

    line_count: int = 0
    """Number of lines in the generated file."""


class GenerationResult(SDDBaseModel):
    """Result of a code generation operation."""

    success: bool
    """Whether generation succeeded."""

    files: list[GeneratedFile] = []  # noqa: RUF012
    """List of generated files."""

    errors: list[str] = []  # noqa: RUF012
    """List of error messages."""

    skipped: list[str] = []  # noqa: RUF012
    """List of skipped files (e.g., already exists, no overwrite)."""

    @property
    def file_count(self) -> int:
        """Number of files generated."""
        return len(self.files)

    @property
    def total_lines(self) -> int:
        """Total lines across all generated files."""
        return sum(f.line_count for f in self.files)

    @property
    def total_bytes(self) -> int:
        """Total bytes across all generated files."""
        return sum(f.size_bytes for f in self.files)


class ScaffoldConfig(SDDBaseModel):
    """Configuration for scaffolding a new feature or module."""

    name: str
    """Name of the feature/module to scaffold."""

    description: str = ""
    """Description for docstrings and comments."""

    templates: list[CodeTemplateType] = [  # noqa: RUF012
        CodeTemplateType.MODULE,
        CodeTemplateType.TEST,
    ]
    """Types of templates to generate."""

    output_dir: str | None = None
    """Override default output directory."""

    package_name: str | None = None
    """Package name for module generation."""

    author: str = ""
    """Author name for file headers."""

    overwrite: bool = False
    """Whether to overwrite existing files."""

    dry_run: bool = False
    """If True, don't write files, just return what would be generated."""
