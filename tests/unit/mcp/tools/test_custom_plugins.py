"""Unit tests for MCP custom plugin tools."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from mcp.server.fastmcp import FastMCP

from sdd_server.mcp.tools import custom_plugins as cp_module
from sdd_server.models.custom_plugin import CustomPluginConfig, CustomPluginType
from sdd_server.plugins.base import RoleStage

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_tool_fn(name: str):
    app = FastMCP("test")
    cp_module.register_tools(app)
    return app._tool_manager._tools[name].fn


def _make_ctx(manager):
    ctx = MagicMock()
    ctx.request_context.lifespan_context.custom_plugin_manager = manager
    return ctx


def _make_manager(**kwargs) -> MagicMock:
    manager = MagicMock()
    for k, v in kwargs.items():
        setattr(manager, k, v)
    return manager


def _make_config(
    name: str = "test-plugin",
    plugin_type: CustomPluginType = CustomPluginType.ROLE,
    enabled: bool = True,
    instructions: str | None = None,
    recipe_template: str | None = None,
) -> CustomPluginConfig:
    return CustomPluginConfig(
        name=name,
        plugin_type=plugin_type,
        description="A test plugin",
        author="Test Author",
        version="1.0.0",
        stage=RoleStage.REVIEW,
        priority=100,
        enabled=enabled,
        instructions=instructions,
        recipe_template=recipe_template,
    )


# ---------------------------------------------------------------------------
# sdd_plugin_list
# ---------------------------------------------------------------------------


class TestSddPluginList:
    async def test_returns_no_plugins_message_when_empty(self) -> None:
        fn = _get_tool_fn("sdd_plugin_list")
        manager = _make_manager()
        manager.list_plugins.return_value = []
        ctx = _make_ctx(manager)

        output = await fn(ctx=ctx)

        assert "No custom plugins" in output

    async def test_returns_plugin_info_when_plugins_exist(self) -> None:
        fn = _get_tool_fn("sdd_plugin_list")
        config = _make_config(name="my-plugin")
        manager = _make_manager()
        manager.list_plugins.return_value = [config]
        ctx = _make_ctx(manager)

        output = await fn(ctx=ctx)

        assert "my-plugin" in output
        assert "Total" in output

    async def test_enabled_only_calls_list_enabled(self) -> None:
        fn = _get_tool_fn("sdd_plugin_list")
        manager = _make_manager()
        manager.list_enabled_plugins.return_value = []
        ctx = _make_ctx(manager)

        await fn(ctx=ctx, enabled_only=True)

        manager.list_enabled_plugins.assert_called_once()
        manager.list_plugins.assert_not_called()

    async def test_plugin_with_instructions_shows_instructions(self) -> None:
        fn = _get_tool_fn("sdd_plugin_list")
        config = _make_config(name="with-instructions", instructions="Do this thing")
        manager = _make_manager()
        manager.list_plugins.return_value = [config]
        ctx = _make_ctx(manager)

        output = await fn(ctx=ctx)

        assert "Do this thing" in output or "Instructions" in output


# ---------------------------------------------------------------------------
# sdd_plugin_create
# ---------------------------------------------------------------------------


class TestSddPluginCreate:
    async def test_creates_plugin_and_saves_to_file(self) -> None:
        fn = _get_tool_fn("sdd_plugin_create")
        config = _make_config(name="new-plugin")
        manager = _make_manager()
        manager.get_plugin_config.return_value = None  # Does not exist yet
        manager.create_plugin_config.return_value = config
        manager.save_plugin_config.return_value = Path("/project/.sdd/plugins/new-plugin.yaml")
        manager.project_root = Path("/project")
        ctx = _make_ctx(manager)

        output = await fn(ctx=ctx, name="new-plugin", plugin_type="role")

        assert "new-plugin" in output
        assert "Created" in output or "created" in output.lower()

    async def test_returns_error_if_plugin_already_exists(self) -> None:
        fn = _get_tool_fn("sdd_plugin_create")
        existing = _make_config(name="existing")
        manager = _make_manager()
        manager.get_plugin_config.return_value = existing
        ctx = _make_ctx(manager)

        output = await fn(ctx=ctx, name="existing")

        assert "already exists" in output or "❌" in output

    async def test_save_false_skips_file_save(self) -> None:
        fn = _get_tool_fn("sdd_plugin_create")
        config = _make_config(name="no-save-plugin")
        manager = _make_manager()
        manager.get_plugin_config.return_value = None
        manager.create_plugin_config.return_value = config
        ctx = _make_ctx(manager)

        output = await fn(ctx=ctx, name="no-save-plugin", save=False)

        manager.save_plugin_config.assert_not_called()
        assert "no-save-plugin" in output

    async def test_exception_in_create_returns_error(self) -> None:
        fn = _get_tool_fn("sdd_plugin_create")
        manager = _make_manager()
        manager.get_plugin_config.return_value = None
        manager.create_plugin_config.side_effect = ValueError("invalid stage")
        ctx = _make_ctx(manager)

        output = await fn(ctx=ctx, name="bad-plugin")

        assert "Failed" in output or "❌" in output

    async def test_parses_dependencies_from_comma_string(self) -> None:
        fn = _get_tool_fn("sdd_plugin_create")
        config = _make_config(name="child-plugin")
        manager = _make_manager()
        manager.get_plugin_config.return_value = None
        manager.create_plugin_config.return_value = config
        manager.save_plugin_config.return_value = Path("/project/.sdd/plugins/child-plugin.yaml")
        manager.project_root = Path("/project")
        ctx = _make_ctx(manager)

        await fn(ctx=ctx, name="child-plugin", dependencies="architect, reviewer", save=True)

        call_kwargs = manager.create_plugin_config.call_args[1]
        assert call_kwargs["dependencies"] == ["architect", "reviewer"]

    async def test_parses_extensions_from_comma_string(self) -> None:
        fn = _get_tool_fn("sdd_plugin_create")
        config = _make_config(name="ext-plugin")
        manager = _make_manager()
        manager.get_plugin_config.return_value = None
        manager.create_plugin_config.return_value = config
        manager.save_plugin_config.return_value = Path("/project/.sdd/plugins/ext-plugin.yaml")
        manager.project_root = Path("/project")
        ctx = _make_ctx(manager)

        await fn(ctx=ctx, name="ext-plugin", extensions="ext-a, ext-b", save=True)

        call_kwargs = manager.create_plugin_config.call_args[1]
        assert call_kwargs["extensions"] == ["ext-a", "ext-b"]


# ---------------------------------------------------------------------------
# sdd_plugin_show
# ---------------------------------------------------------------------------


class TestSddPluginShow:
    async def test_shows_plugin_details(self) -> None:
        fn = _get_tool_fn("sdd_plugin_show")
        config = _make_config(name="shown-plugin")
        manager = _make_manager()
        manager.get_plugin_config.return_value = config
        ctx = _make_ctx(manager)

        output = await fn(ctx=ctx, name="shown-plugin")

        assert "shown-plugin" in output

    async def test_not_found_returns_error_message(self) -> None:
        fn = _get_tool_fn("sdd_plugin_show")
        manager = _make_manager()
        manager.get_plugin_config.return_value = None
        ctx = _make_ctx(manager)

        output = await fn(ctx=ctx, name="unknown-plugin")

        assert "not found" in output or "❌" in output

    async def test_shows_recipe_template_for_role(self) -> None:
        fn = _get_tool_fn("sdd_plugin_show")
        config = _make_config(
            name="recipe-plugin",
            plugin_type=CustomPluginType.ROLE,
            recipe_template="version: '1.0'\ntitle: 'Test'\n",
        )
        manager = _make_manager()
        manager.get_plugin_config.return_value = config
        ctx = _make_ctx(manager)

        output = await fn(ctx=ctx, name="recipe-plugin")

        assert "Recipe Template" in output or "version" in output


# ---------------------------------------------------------------------------
# sdd_plugin_update
# ---------------------------------------------------------------------------


class TestSddPluginUpdate:
    async def test_updates_description(self) -> None:
        fn = _get_tool_fn("sdd_plugin_update")
        config = _make_config(name="update-me")
        manager = _make_manager()
        manager.get_plugin_config.return_value = config
        ctx = _make_ctx(manager)

        output = await fn(ctx=ctx, name="update-me", description="New description")

        assert "update-me" in output
        assert "description" in output
        manager.save_plugin_config.assert_called_once()

    async def test_plugin_not_found_returns_error(self) -> None:
        fn = _get_tool_fn("sdd_plugin_update")
        manager = _make_manager()
        manager.get_plugin_config.return_value = None
        ctx = _make_ctx(manager)

        output = await fn(ctx=ctx, name="nonexistent")

        assert "not found" in output or "❌" in output

    async def test_no_updates_provided_returns_message(self) -> None:
        fn = _get_tool_fn("sdd_plugin_update")
        config = _make_config(name="no-updates")
        manager = _make_manager()
        manager.get_plugin_config.return_value = config
        ctx = _make_ctx(manager)

        output = await fn(ctx=ctx, name="no-updates")

        assert "No updates" in output or "no updates" in output.lower()

    async def test_updates_enabled_flag(self) -> None:
        fn = _get_tool_fn("sdd_plugin_update")
        config = _make_config(name="toggle-me", enabled=True)
        manager = _make_manager()
        manager.get_plugin_config.return_value = config
        ctx = _make_ctx(manager)

        await fn(ctx=ctx, name="toggle-me", enabled=False)

        assert config.enabled is False

    async def test_updates_priority(self) -> None:
        fn = _get_tool_fn("sdd_plugin_update")
        config = _make_config(name="prio-plugin")
        manager = _make_manager()
        manager.get_plugin_config.return_value = config
        ctx = _make_ctx(manager)

        await fn(ctx=ctx, name="prio-plugin", priority=50)

        assert config.priority == 50


# ---------------------------------------------------------------------------
# sdd_plugin_delete
# ---------------------------------------------------------------------------


class TestSddPluginDelete:
    async def test_deletes_existing_plugin(self) -> None:
        fn = _get_tool_fn("sdd_plugin_delete")
        config = _make_config(name="to-delete")
        manager = _make_manager()
        manager.get_plugin_config.return_value = config
        manager.delete_plugin.return_value = True
        ctx = _make_ctx(manager)

        output = await fn(ctx=ctx, name="to-delete")

        assert "to-delete" in output
        assert "Deleted" in output or "deleted" in output.lower()

    async def test_not_found_returns_error(self) -> None:
        fn = _get_tool_fn("sdd_plugin_delete")
        manager = _make_manager()
        manager.get_plugin_config.return_value = None
        ctx = _make_ctx(manager)

        output = await fn(ctx=ctx, name="ghost-plugin")

        assert "not found" in output or "❌" in output

    async def test_delete_failure_returns_failure_message(self) -> None:
        fn = _get_tool_fn("sdd_plugin_delete")
        config = _make_config(name="fail-delete")
        manager = _make_manager()
        manager.get_plugin_config.return_value = config
        manager.delete_plugin.return_value = False
        ctx = _make_ctx(manager)

        output = await fn(ctx=ctx, name="fail-delete")

        assert "Failed" in output or "❌" in output


# ---------------------------------------------------------------------------
# sdd_plugin_enable / sdd_plugin_disable
# ---------------------------------------------------------------------------


class TestSddPluginEnableDisable:
    async def test_enables_disabled_plugin(self) -> None:
        fn = _get_tool_fn("sdd_plugin_enable")
        config = _make_config(name="enable-me", enabled=False)
        manager = _make_manager()
        manager.get_plugin_config.return_value = config
        ctx = _make_ctx(manager)

        output = await fn(ctx=ctx, name="enable-me")

        assert config.enabled is True
        assert "Enabled" in output or "enabled" in output.lower()

    async def test_enable_already_enabled_returns_message(self) -> None:
        fn = _get_tool_fn("sdd_plugin_enable")
        config = _make_config(name="already-on", enabled=True)
        manager = _make_manager()
        manager.get_plugin_config.return_value = config
        ctx = _make_ctx(manager)

        output = await fn(ctx=ctx, name="already-on")

        assert "already enabled" in output.lower()

    async def test_enable_not_found_returns_error(self) -> None:
        fn = _get_tool_fn("sdd_plugin_enable")
        manager = _make_manager()
        manager.get_plugin_config.return_value = None
        ctx = _make_ctx(manager)

        output = await fn(ctx=ctx, name="ghost")

        assert "not found" in output or "❌" in output

    async def test_disables_enabled_plugin(self) -> None:
        fn = _get_tool_fn("sdd_plugin_disable")
        config = _make_config(name="disable-me", enabled=True)
        manager = _make_manager()
        manager.get_plugin_config.return_value = config
        ctx = _make_ctx(manager)

        output = await fn(ctx=ctx, name="disable-me")

        assert config.enabled is False
        assert "Disabled" in output or "disabled" in output.lower()

    async def test_disable_already_disabled_returns_message(self) -> None:
        fn = _get_tool_fn("sdd_plugin_disable")
        config = _make_config(name="already-off", enabled=False)
        manager = _make_manager()
        manager.get_plugin_config.return_value = config
        ctx = _make_ctx(manager)

        output = await fn(ctx=ctx, name="already-off")

        assert "already disabled" in output.lower()


# ---------------------------------------------------------------------------
# sdd_plugin_load
# ---------------------------------------------------------------------------


class TestSddPluginLoad:
    async def test_returns_no_plugins_message_when_none_loaded(self) -> None:
        fn = _get_tool_fn("sdd_plugin_load")
        manager = _make_manager()
        manager.load_from_directory.return_value = []
        ctx = _make_ctx(manager)

        output = await fn(ctx=ctx)

        assert "No custom plugins" in output

    async def test_shows_loaded_plugin_names(self) -> None:
        fn = _get_tool_fn("sdd_plugin_load")
        config_a = _make_config(name="loaded-a", enabled=True)
        config_b = _make_config(name="loaded-b", enabled=False)
        manager = _make_manager()
        manager.load_from_directory.return_value = [config_a, config_b]
        ctx = _make_ctx(manager)

        output = await fn(ctx=ctx)

        assert "loaded-a" in output
        assert "loaded-b" in output
        assert "Total" in output
