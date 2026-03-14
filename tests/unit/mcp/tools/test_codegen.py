"""Unit tests for MCP codegen tools."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from mcp.server.fastmcp import FastMCP

from sdd_server.core.code_generator import CodeGenerationError
from sdd_server.mcp.tools import codegen as codegen_module
from sdd_server.models.codegen import CodeTemplateType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_tool_fn(name: str):
    app = FastMCP("test")
    codegen_module.register_tools(app)
    return app._tool_manager._tools[name].fn


def _make_ctx(lifespan_context: dict):
    ctx = MagicMock()
    ctx.request_context.lifespan_context = lifespan_context
    return ctx


def _make_generator(**kwargs) -> MagicMock:
    gen = MagicMock()
    for k, v in kwargs.items():
        setattr(gen, k, v)
    return gen


def _make_file_result(path: str = "/out/file.py") -> MagicMock:
    result = MagicMock()
    result.path = Path(path)
    result.template_name = "module"
    result.template_type = MagicMock()
    result.template_type.value = "module"
    result.overwritten = False
    result.size_bytes = 100
    result.line_count = 10
    return result


# ---------------------------------------------------------------------------
# sdd_codegen_list_templates
# ---------------------------------------------------------------------------


class TestSddCodegenListTemplates:
    async def test_no_ctx_returns_error(self) -> None:
        fn = _get_tool_fn("sdd_codegen_list_templates")
        result = await fn(ctx=None)
        assert result["success"] is False
        assert "context" in result["error"].lower()

    async def test_missing_generator_returns_error(self) -> None:
        fn = _get_tool_fn("sdd_codegen_list_templates")
        ctx = _make_ctx({})  # no code_generator key
        result = await fn(ctx=ctx)
        assert result["success"] is False
        assert "not initialized" in result["error"].lower()

    async def test_returns_templates_list(self) -> None:
        fn = _get_tool_fn("sdd_codegen_list_templates")
        template = MagicMock()
        template.name = "module"
        template.template_type = MagicMock()
        template.template_type.value = "module"
        template.description = "Python module template"
        template.file_pattern = "{name}.py"
        template.default_path = "src/"
        template.required_context = ["module_name"]

        gen = _make_generator()
        gen.list_templates.return_value = [template]
        ctx = _make_ctx({"code_generator": gen})

        result = await fn(ctx=ctx)

        assert result["success"] is True
        assert len(result["templates"]) == 1
        assert result["templates"][0]["name"] == "module"


# ---------------------------------------------------------------------------
# sdd_codegen_generate
# ---------------------------------------------------------------------------


class TestSddCodegenGenerate:
    async def test_no_ctx_returns_error(self) -> None:
        fn = _get_tool_fn("sdd_codegen_generate")
        result = await fn(ctx=None, template_name="module")
        assert result["success"] is False

    async def test_missing_generator_returns_error(self) -> None:
        fn = _get_tool_fn("sdd_codegen_generate")
        ctx = _make_ctx({})
        result = await fn(ctx=ctx, template_name="module")
        assert result["success"] is False

    async def test_empty_template_name_returns_error(self) -> None:
        fn = _get_tool_fn("sdd_codegen_generate")
        gen = _make_generator()
        ctx = _make_ctx({"code_generator": gen})
        result = await fn(ctx=ctx, template_name="")
        assert result["success"] is False
        assert "required" in result["error"].lower()

    async def test_successful_generation_returns_file_info(self) -> None:
        fn = _get_tool_fn("sdd_codegen_generate")
        file_result = _make_file_result("/out/my_module.py")
        gen = _make_generator()
        gen.generate_from_template.return_value = file_result
        ctx = _make_ctx({"code_generator": gen})

        result = await fn(ctx=ctx, template_name="module", context={"module_name": "my_module"})

        assert result["success"] is True
        assert "file" in result
        assert result["file"]["path"] == "/out/my_module.py"

    async def test_code_generation_error_returns_failure(self) -> None:
        fn = _get_tool_fn("sdd_codegen_generate")
        gen = _make_generator()
        gen.generate_from_template.side_effect = CodeGenerationError("Template not found")
        ctx = _make_ctx({"code_generator": gen})

        result = await fn(ctx=ctx, template_name="unknown-template")

        assert result["success"] is False
        assert "Template not found" in result["error"]

    async def test_passes_output_path_to_generator(self) -> None:
        fn = _get_tool_fn("sdd_codegen_generate")
        file_result = _make_file_result("/custom/path.py")
        gen = _make_generator()
        gen.generate_from_template.return_value = file_result
        ctx = _make_ctx({"code_generator": gen})

        await fn(ctx=ctx, template_name="module", output_path="/custom/path.py")

        call_kwargs = gen.generate_from_template.call_args[1]
        assert call_kwargs["output_path"] == Path("/custom/path.py")


# ---------------------------------------------------------------------------
# sdd_codegen_preview
# ---------------------------------------------------------------------------


class TestSddCodegenPreview:
    async def test_no_ctx_returns_error(self) -> None:
        fn = _get_tool_fn("sdd_codegen_preview")
        result = await fn(ctx=None, template_name="module")
        assert result["success"] is False

    async def test_missing_generator_returns_error(self) -> None:
        fn = _get_tool_fn("sdd_codegen_preview")
        ctx = _make_ctx({})
        result = await fn(ctx=ctx, template_name="module")
        assert result["success"] is False

    async def test_empty_template_name_returns_error(self) -> None:
        fn = _get_tool_fn("sdd_codegen_preview")
        gen = _make_generator()
        ctx = _make_ctx({"code_generator": gen})
        result = await fn(ctx=ctx, template_name="")
        assert result["success"] is False

    async def test_returns_rendered_content(self) -> None:
        fn = _get_tool_fn("sdd_codegen_preview")
        gen = _make_generator()
        gen.render_preview.return_value = "# My Module\n\ndef hello(): pass\n"
        ctx = _make_ctx({"code_generator": gen})

        result = await fn(ctx=ctx, template_name="module", context={"module_name": "hello"})

        assert result["success"] is True
        assert result["template_name"] == "module"
        assert "# My Module" in result["content"]
        assert result["line_count"] >= 1

    async def test_code_generation_error_returns_failure(self) -> None:
        fn = _get_tool_fn("sdd_codegen_preview")
        gen = _make_generator()
        gen.render_preview.side_effect = CodeGenerationError("render failed")
        ctx = _make_ctx({"code_generator": gen})

        result = await fn(ctx=ctx, template_name="module")

        assert result["success"] is False
        assert "render failed" in result["error"]


# ---------------------------------------------------------------------------
# sdd_codegen_scaffold
# ---------------------------------------------------------------------------


class TestSddCodegenScaffold:
    async def test_no_ctx_returns_error(self) -> None:
        fn = _get_tool_fn("sdd_codegen_scaffold")
        result = await fn(ctx=None, name="myfeature")
        assert result["success"] is False

    async def test_missing_generator_returns_error(self) -> None:
        fn = _get_tool_fn("sdd_codegen_scaffold")
        ctx = _make_ctx({})
        result = await fn(ctx=ctx, name="myfeature")
        assert result["success"] is False

    async def test_empty_name_returns_error(self) -> None:
        fn = _get_tool_fn("sdd_codegen_scaffold")
        gen = _make_generator()
        ctx = _make_ctx({"code_generator": gen})
        result = await fn(ctx=ctx, name="")
        assert result["success"] is False
        assert "required" in result["error"].lower()

    async def test_unknown_template_type_returns_error(self) -> None:
        fn = _get_tool_fn("sdd_codegen_scaffold")
        gen = _make_generator()
        ctx = _make_ctx({"code_generator": gen})
        result = await fn(ctx=ctx, name="myfeature", templates=["__unknown_type__"])
        assert result["success"] is False
        assert "Unknown template type" in result["error"]

    async def test_successful_scaffold_returns_files(self) -> None:
        fn = _get_tool_fn("sdd_codegen_scaffold")
        file_result = _make_file_result("/src/myfeature.py")
        scaffold_result = MagicMock()
        scaffold_result.success = True
        scaffold_result.files = [file_result]
        scaffold_result.errors = []
        scaffold_result.skipped = []
        scaffold_result.file_count = 1
        scaffold_result.total_lines = 10

        gen = _make_generator()
        gen.scaffold.return_value = scaffold_result
        ctx = _make_ctx({"code_generator": gen})

        result = await fn(ctx=ctx, name="myfeature")

        assert result["success"] is True
        assert len(result["files"]) == 1
        assert result["total_files"] == 1

    async def test_exception_in_scaffold_returns_error(self) -> None:
        fn = _get_tool_fn("sdd_codegen_scaffold")
        gen = _make_generator()
        gen.scaffold.side_effect = RuntimeError("scaffold failed")
        ctx = _make_ctx({"code_generator": gen})

        result = await fn(ctx=ctx, name="myfeature")

        assert result["success"] is False
        assert "scaffold failed" in result["error"]

    async def test_default_templates_used_when_none_provided(self) -> None:
        fn = _get_tool_fn("sdd_codegen_scaffold")
        scaffold_result = MagicMock()
        scaffold_result.success = True
        scaffold_result.files = []
        scaffold_result.errors = []
        scaffold_result.skipped = []
        scaffold_result.file_count = 0
        scaffold_result.total_lines = 0

        gen = _make_generator()
        gen.scaffold.return_value = scaffold_result
        ctx = _make_ctx({"code_generator": gen})

        await fn(ctx=ctx, name="myfeature")

        call_args = gen.scaffold.call_args[0][0]
        assert CodeTemplateType.MODULE in call_args.templates
        assert CodeTemplateType.TEST in call_args.templates


# ---------------------------------------------------------------------------
# sdd_codegen_generate_from_string
# ---------------------------------------------------------------------------


class TestSddCodegenGenerateFromString:
    async def test_no_ctx_returns_error(self) -> None:
        fn = _get_tool_fn("sdd_codegen_generate_from_string")
        result = await fn(ctx=None, template_content="hello", output_path="/out.py")
        assert result["success"] is False

    async def test_missing_generator_returns_error(self) -> None:
        fn = _get_tool_fn("sdd_codegen_generate_from_string")
        ctx = _make_ctx({})
        result = await fn(ctx=ctx, template_content="hello", output_path="/out.py")
        assert result["success"] is False

    async def test_empty_template_content_returns_error(self) -> None:
        fn = _get_tool_fn("sdd_codegen_generate_from_string")
        gen = _make_generator()
        ctx = _make_ctx({"code_generator": gen})
        result = await fn(ctx=ctx, template_content="", output_path="/out.py")
        assert result["success"] is False
        assert "required" in result["error"].lower()

    async def test_empty_output_path_returns_error(self) -> None:
        fn = _get_tool_fn("sdd_codegen_generate_from_string")
        gen = _make_generator()
        ctx = _make_ctx({"code_generator": gen})
        result = await fn(ctx=ctx, template_content="hello {{ name }}", output_path="")
        assert result["success"] is False
        assert "required" in result["error"].lower()

    async def test_successful_generation_returns_file_info(self) -> None:
        fn = _get_tool_fn("sdd_codegen_generate_from_string")
        file_result = _make_file_result("/out/custom.py")
        gen = _make_generator()
        gen.generate_from_string.return_value = file_result
        ctx = _make_ctx({"code_generator": gen})

        result = await fn(
            ctx=ctx,
            template_content="# {{ name }}\n",
            context={"name": "MyModule"},
            output_path="/out/custom.py",
        )

        assert result["success"] is True
        assert result["file"]["path"] == "/out/custom.py"

    async def test_code_generation_error_returns_failure(self) -> None:
        fn = _get_tool_fn("sdd_codegen_generate_from_string")
        gen = _make_generator()
        gen.generate_from_string.side_effect = CodeGenerationError("template syntax error")
        ctx = _make_ctx({"code_generator": gen})

        result = await fn(
            ctx=ctx,
            template_content="{{ bad syntax",
            output_path="/out/file.py",
        )

        assert result["success"] is False
        assert "template syntax error" in result["error"]
