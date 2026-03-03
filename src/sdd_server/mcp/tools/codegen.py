"""MCP tools for code generation.

These tools allow generating implementation scaffolding from templates
via the MCP interface.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import Context, FastMCP

from sdd_server.core.code_generator import CodeGenerationError, CodeGenerator
from sdd_server.models.codegen import CodeTemplateType, ScaffoldConfig
from sdd_server.utils.logging import get_logger

logger = get_logger(__name__)


# -----------------------------------------------------------------------------
# Tool Functions
# -----------------------------------------------------------------------------


async def sdd_codegen_list_templates(
    ctx: Context | None = None,  # type: ignore[type-arg]
) -> dict[str, Any]:
    """List all available code templates.

    Returns:
        Dictionary with list of available templates
    """
    if ctx is None:
        return {"success": False, "error": "No context available"}

    try:
        generator: CodeGenerator = ctx.request_context.lifespan_context["code_generator"]
    except KeyError:
        return {"success": False, "error": "Code generator not initialized"}

    templates = generator.list_templates()
    return {
        "success": True,
        "templates": [
            {
                "name": t.name,
                "type": t.template_type.value,
                "description": t.description,
                "file_pattern": t.file_pattern,
                "default_path": t.default_path,
                "required_context": t.required_context,
            }
            for t in templates
        ],
    }


async def sdd_codegen_generate(
    ctx: Context | None = None,  # type: ignore[type-arg]
    template_name: str = "",
    context: dict[str, Any] | None = None,
    output_path: str | None = None,
    overwrite: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Generate a file from a template.

    Args:
        template_name: Name of the template to use
        context: Template context variables (e.g., {"module_name": "my_module"})
        output_path: Optional override for output path
        overwrite: Whether to overwrite existing files
        dry_run: If True, don't write the file

    Returns:
        Dictionary with generation result
    """
    if ctx is None:
        return {"success": False, "error": "No context available"}

    try:
        generator: CodeGenerator = ctx.request_context.lifespan_context["code_generator"]
    except KeyError:
        return {"success": False, "error": "Code generator not initialized"}

    if not template_name:
        return {"success": False, "error": "template_name is required"}

    context = context or {}

    try:
        output = Path(output_path) if output_path else None
        result = generator.generate_from_template(
            template_name=template_name,
            context=context,
            output_path=output,
            overwrite=overwrite,
            dry_run=dry_run,
        )

        return {
            "success": True,
            "file": {
                "path": str(result.path),
                "template_name": result.template_name,
                "template_type": result.template_type.value,
                "overwritten": result.overwritten,
                "size_bytes": result.size_bytes,
                "line_count": result.line_count,
            },
        }
    except CodeGenerationError as e:
        return {"success": False, "error": str(e)}


async def sdd_codegen_preview(
    ctx: Context | None = None,  # type: ignore[type-arg]
    template_name: str = "",
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Preview generated code without writing to disk.

    Args:
        template_name: Name of the template to use
        context: Template context variables

    Returns:
        Dictionary with rendered content
    """
    if ctx is None:
        return {"success": False, "error": "No context available"}

    try:
        generator: CodeGenerator = ctx.request_context.lifespan_context["code_generator"]
    except KeyError:
        return {"success": False, "error": "Code generator not initialized"}

    if not template_name:
        return {"success": False, "error": "template_name is required"}

    context = context or {}

    try:
        content = generator.render_preview(template_name, context)
        return {
            "success": True,
            "template_name": template_name,
            "content": content,
            "line_count": content.count("\n") + 1,
        }
    except CodeGenerationError as e:
        return {"success": False, "error": str(e)}


async def sdd_codegen_scaffold(
    ctx: Context | None = None,  # type: ignore[type-arg]
    name: str = "",
    description: str = "",
    templates: list[str] | None = None,
    output_dir: str | None = None,
    package_name: str | None = None,
    author: str = "",
    overwrite: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Scaffold a new feature or module with multiple files.

    Args:
        name: Name of the feature/module to scaffold
        description: Description for docstrings
        templates: List of template types to generate (e.g., ["module", "test"])
        output_dir: Override default output directory
        package_name: Package name for imports
        author: Author name for file headers
        overwrite: Whether to overwrite existing files
        dry_run: If True, don't write files

    Returns:
        Dictionary with generation results
    """
    if ctx is None:
        return {"success": False, "error": "No context available"}

    try:
        generator: CodeGenerator = ctx.request_context.lifespan_context["code_generator"]
    except KeyError:
        return {"success": False, "error": "Code generator not initialized"}

    if not name:
        return {"success": False, "error": "name is required"}

    # Parse template types
    template_types: list[CodeTemplateType] = []
    if templates:
        for t in templates:
            try:
                template_types.append(CodeTemplateType(t))
            except ValueError:
                return {"success": False, "error": f"Unknown template type: {t}"}
    else:
        # Default templates
        template_types = [CodeTemplateType.MODULE, CodeTemplateType.TEST]

    config = ScaffoldConfig(
        name=name,
        description=description,
        templates=template_types,
        output_dir=output_dir,
        package_name=package_name,
        author=author,
        overwrite=overwrite,
        dry_run=dry_run,
    )

    try:
        result = generator.scaffold(config)

        return {
            "success": result.success,
            "files": [
                {
                    "path": str(f.path),
                    "template_name": f.template_name,
                    "template_type": f.template_type.value,
                    "overwritten": f.overwritten,
                    "size_bytes": f.size_bytes,
                    "line_count": f.line_count,
                }
                for f in result.files
            ],
            "errors": result.errors,
            "skipped": result.skipped,
            "total_files": result.file_count,
            "total_lines": result.total_lines,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def sdd_codegen_generate_from_string(
    ctx: Context | None = None,  # type: ignore[type-arg]
    template_content: str = "",
    context: dict[str, Any] | None = None,
    output_path: str = "",
    overwrite: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Generate a file from a custom template string.

    Args:
        template_content: Jinja2 template content
        context: Template context variables
        output_path: Where to write the file
        overwrite: Whether to overwrite existing files
        dry_run: If True, don't write the file

    Returns:
        Dictionary with generation result
    """
    if ctx is None:
        return {"success": False, "error": "No context available"}

    try:
        generator: CodeGenerator = ctx.request_context.lifespan_context["code_generator"]
    except KeyError:
        return {"success": False, "error": "Code generator not initialized"}

    if not template_content:
        return {"success": False, "error": "template_content is required"}
    if not output_path:
        return {"success": False, "error": "output_path is required"}

    context = context or {}

    try:
        result = generator.generate_from_string(
            template_content=template_content,
            context=context,
            output_path=Path(output_path),
            overwrite=overwrite,
            dry_run=dry_run,
        )

        return {
            "success": True,
            "file": {
                "path": str(result.path),
                "template_name": result.template_name,
                "template_type": result.template_type.value,
                "overwritten": result.overwritten,
                "size_bytes": result.size_bytes,
                "line_count": result.line_count,
            },
        }
    except CodeGenerationError as e:
        return {"success": False, "error": str(e)}


# -----------------------------------------------------------------------------
# Registration
# -----------------------------------------------------------------------------


def register_tools(server: FastMCP) -> None:
    """Register all codegen tools with the MCP server."""
    server.tool(
        name="sdd_codegen_list_templates",
        description="List all available code templates",
    )(sdd_codegen_list_templates)

    server.tool(
        name="sdd_codegen_generate",
        description="Generate a file from a template",
    )(sdd_codegen_generate)

    server.tool(
        name="sdd_codegen_preview",
        description="Preview generated code without writing to disk",
    )(sdd_codegen_preview)

    server.tool(
        name="sdd_codegen_scaffold",
        description="Scaffold a new feature or module with multiple files",
    )(sdd_codegen_scaffold)

    server.tool(
        name="sdd_codegen_generate_from_string",
        description="Generate a file from a custom template string",
    )(sdd_codegen_generate_from_string)

    logger.debug("Registered codegen tools")


__all__ = [
    "register_tools",
    "sdd_codegen_generate",
    "sdd_codegen_generate_from_string",
    "sdd_codegen_list_templates",
    "sdd_codegen_preview",
    "sdd_codegen_scaffold",
]
