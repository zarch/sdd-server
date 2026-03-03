"""Tests for CustomPluginManager."""

from __future__ import annotations

from pathlib import Path

import pytest

from sdd_server.core.custom_plugin_manager import CustomPluginManager, DynamicRolePlugin
from sdd_server.models.custom_plugin import CustomPluginConfig, CustomPluginType
from sdd_server.plugins.base import RoleStage


class TestCustomPluginManagerInit:
    """Tests for CustomPluginManager initialization."""

    def test_init(self, tmp_path: Path):
        """Test manager initialization."""
        manager = CustomPluginManager(tmp_path)
        assert manager.project_root == tmp_path.resolve()
        assert manager.registry is not None


class TestCustomPluginManagerCreateConfig:
    """Tests for creating plugin configurations."""

    def test_create_role_config(self, tmp_path: Path):
        """Test creating a role plugin config."""
        manager = CustomPluginManager(tmp_path)
        config = manager.create_plugin_config(
            name="test-role",
            plugin_type="role",
            description="A test role",
            stage="review",
            priority=50,
        )

        assert config.name == "test-role"
        assert config.plugin_type == CustomPluginType.ROLE
        assert config.stage == RoleStage.REVIEW
        assert config.priority == 50

        # Should be in registry
        assert manager.get_plugin_config("test-role") == config

    def test_create_config_with_dependencies(self, tmp_path: Path):
        """Test creating config with dependencies."""
        manager = CustomPluginManager(tmp_path)
        config = manager.create_plugin_config(
            name="dependent-role",
            dependencies=["architect", "security-analyst"],
        )

        assert "architect" in config.dependencies
        assert "security-analyst" in config.dependencies

    def test_create_config_with_instructions(self, tmp_path: Path):
        """Test creating config with instructions."""
        manager = CustomPluginManager(tmp_path)
        config = manager.create_plugin_config(
            name="instructed-role",
            instructions="Do this, then that",
            prompt="Review the code",
        )

        assert config.instructions == "Do this, then that"
        assert config.prompt == "Review the code"


class TestCustomPluginManagerSaveLoad:
    """Tests for saving and loading plugin configurations."""

    def test_save_plugin_config(self, tmp_path: Path):
        """Test saving a plugin config to file."""
        manager = CustomPluginManager(tmp_path)
        config = CustomPluginConfig(
            name="saved-plugin",
            description="A saved plugin",
        )

        file_path = manager.save_plugin_config(config)

        assert file_path.exists()
        content = file_path.read_text()
        assert "saved-plugin" in content
        assert "A saved plugin" in content

    def test_save_to_custom_path(self, tmp_path: Path):
        """Test saving to a custom path."""
        manager = CustomPluginManager(tmp_path)
        config = CustomPluginConfig(name="custom-path-plugin")

        custom_path = tmp_path / "custom" / "my-plugin.yaml"
        file_path = manager.save_plugin_config(config, custom_path)

        assert file_path == custom_path
        assert custom_path.exists()

    def test_load_from_file_yaml(self, tmp_path: Path):
        """Test loading plugins from a YAML file."""
        plugins_file = tmp_path / "plugins.yaml"
        plugins_file.write_text("""
plugins:
  - name: yaml-plugin-1
    description: First plugin
  - name: yaml-plugin-2
    description: Second plugin
    stage: review
""")

        manager = CustomPluginManager(tmp_path)
        configs = manager.load_from_file(plugins_file)

        assert len(configs) == 2
        assert configs[0].name == "yaml-plugin-1"
        assert configs[1].name == "yaml-plugin-2"

    def test_load_from_file_single_plugin(self, tmp_path: Path):
        """Test loading a single plugin definition."""
        plugins_file = tmp_path / "single.yaml"
        plugins_file.write_text("""
name: single-plugin
description: A single plugin
stage: architecture
priority: 10
""")

        manager = CustomPluginManager(tmp_path)
        configs = manager.load_from_file(plugins_file)

        assert len(configs) == 1
        assert configs[0].name == "single-plugin"
        assert configs[0].priority == 10

    def test_load_from_file_json(self, tmp_path: Path):
        """Test loading plugins from a JSON file."""
        import json

        plugins_file = tmp_path / "plugins.json"
        plugins_file.write_text(
            json.dumps({"plugins": [{"name": "json-plugin", "description": "JSON plugin"}]})
        )

        manager = CustomPluginManager(tmp_path)
        configs = manager.load_from_file(plugins_file)

        assert len(configs) == 1
        assert configs[0].name == "json-plugin"

    def test_load_from_directory(self, tmp_path: Path):
        """Test loading plugins from a directory."""
        # Create specs/custom_plugins directory
        plugins_dir = tmp_path / "specs" / "custom_plugins"
        plugins_dir.mkdir(parents=True)

        # Create multiple plugin files
        (plugins_dir / "plugin1.yaml").write_text("name: dir-plugin-1\n")
        (plugins_dir / "plugin2.yaml").write_text("name: dir-plugin-2\n")

        manager = CustomPluginManager(tmp_path)
        loaded = manager.load_from_directory()

        assert len(loaded) == 2
        names = {p.name for p in loaded}
        assert "dir-plugin-1" in names
        assert "dir-plugin-2" in names

    def test_load_from_nonexistent_directory(self, tmp_path: Path):
        """Test loading from a nonexistent directory."""
        manager = CustomPluginManager(tmp_path)
        loaded = manager.load_from_directory()
        assert len(loaded) == 0


class TestCustomPluginManagerCreatePlugin:
    """Tests for creating plugin instances."""

    def test_create_role_plugin(self, tmp_path: Path):
        """Test creating a role plugin instance."""
        manager = CustomPluginManager(tmp_path)
        config = CustomPluginConfig(
            name="dynamic-role",
            plugin_type=CustomPluginType.ROLE,
            stage=RoleStage.REVIEW,
            priority=30,
        )

        plugin = manager.create_plugin(config)

        assert isinstance(plugin, DynamicRolePlugin)
        assert plugin.name == "dynamic-role"
        assert plugin.metadata.priority == 30

    def test_get_created_plugin(self, tmp_path: Path):
        """Test getting a created plugin."""
        manager = CustomPluginManager(tmp_path)
        config = CustomPluginConfig(name="get-test")
        manager.create_plugin(config)

        retrieved = manager.get_plugin("get-test")
        assert retrieved is not None
        assert retrieved.name == "get-test"

    def test_get_all_plugins(self, tmp_path: Path):
        """Test getting all created plugins."""
        manager = CustomPluginManager(tmp_path)
        manager.create_plugin(CustomPluginConfig(name="plugin1"))
        manager.create_plugin(CustomPluginConfig(name="plugin2"))

        all_plugins = manager.get_all_plugins()
        assert len(all_plugins) == 2
        assert "plugin1" in all_plugins
        assert "plugin2" in all_plugins


class TestDynamicRolePlugin:
    """Tests for DynamicRolePlugin class."""

    @pytest.mark.asyncio
    async def test_initialize(self, tmp_path: Path):
        """Test initializing dynamic role plugin."""
        config = CustomPluginConfig(name="init-test")
        plugin = DynamicRolePlugin(config)

        await plugin.initialize({"test": "context"})

        assert plugin.context == {"test": "context"}

    @pytest.mark.asyncio
    async def test_review(self, tmp_path: Path):
        """Test review method."""
        config = CustomPluginConfig(name="review-test")
        plugin = DynamicRolePlugin(config)

        result = await plugin.review()

        assert result.role == "review-test"
        assert result.status.value == "pending"

    def test_get_recipe_template_custom(self, tmp_path: Path):
        """Test getting custom recipe template."""
        config = CustomPluginConfig(
            name="template-test",
            recipe_template="version: custom\ninstructions: Custom",
        )
        plugin = DynamicRolePlugin(config)

        template = plugin.get_recipe_template()

        assert template == "version: custom\ninstructions: Custom"

    def test_get_recipe_template_generated(self, tmp_path: Path):
        """Test getting generated recipe template."""
        config = CustomPluginConfig(
            name="gen-template-test",
            instructions="Do the review",
            prompt="Review this",
        )
        plugin = DynamicRolePlugin(config)

        template = plugin.get_recipe_template()

        assert "version:" in template
        assert "gen-template-test" in template.lower() or "Gen Template Test" in template


class TestCustomPluginManagerDelete:
    """Tests for deleting plugins."""

    def test_delete_plugin(self, tmp_path: Path):
        """Test deleting a plugin."""
        manager = CustomPluginManager(tmp_path)
        # Create config which adds to registry
        config = manager.create_plugin_config(name="delete-test")
        # Save to file
        manager.save_plugin_config(config)
        # Create plugin instance
        manager.create_plugin(config)

        result = manager.delete_plugin("delete-test", delete_file=True)

        assert result is True
        assert manager.get_plugin_config("delete-test") is None
        assert manager.get_plugin("delete-test") is None

    def test_delete_plugin_without_file(self, tmp_path: Path):
        """Test deleting a plugin that has no file."""
        manager = CustomPluginManager(tmp_path)
        manager.create_plugin_config(name="no-file-plugin")

        result = manager.delete_plugin("no-file-plugin", delete_file=True)

        assert result is True
        assert manager.get_plugin_config("no-file-plugin") is None

    def test_delete_nonexistent_plugin(self, tmp_path: Path):
        """Test deleting a nonexistent plugin."""
        manager = CustomPluginManager(tmp_path)
        result = manager.delete_plugin("nonexistent")
        assert result is False


class TestCustomPluginManagerListing:
    """Tests for listing plugins."""

    def test_list_plugins(self, tmp_path: Path):
        """Test listing all plugins."""
        manager = CustomPluginManager(tmp_path)
        manager.create_plugin_config(name="list1")
        manager.create_plugin_config(name="list2")

        plugins = manager.list_plugins()

        assert len(plugins) == 2
        names = {p.name for p in plugins}
        assert "list1" in names
        assert "list2" in names

    def test_list_enabled_plugins(self, tmp_path: Path):
        """Test listing enabled plugins only."""
        manager = CustomPluginManager(tmp_path)
        manager.create_plugin_config(name="enabled", enabled=True)
        manager.create_plugin_config(name="disabled", enabled=False)

        enabled = manager.list_enabled_plugins()

        assert len(enabled) == 1
        assert enabled[0].name == "enabled"

    def test_get_plugin_config(self, tmp_path: Path):
        """Test getting plugin config by name."""
        manager = CustomPluginManager(tmp_path)
        manager.create_plugin_config(name="get-config", description="Test")

        config = manager.get_plugin_config("get-config")

        assert config is not None
        assert config.description == "Test"
