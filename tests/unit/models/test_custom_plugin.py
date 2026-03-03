"""Tests for custom plugin models."""

from __future__ import annotations

from sdd_server.models.custom_plugin import (
    CustomPluginConfig,
    CustomPluginFile,
    CustomPluginRegistry,
    CustomPluginType,
)
from sdd_server.plugins.base import RoleStage


class TestCustomPluginType:
    """Tests for CustomPluginType enum."""

    def test_plugin_type_values(self):
        """Test plugin type enum values."""
        assert CustomPluginType.ROLE == "role"
        assert CustomPluginType.VALIDATOR == "validator"
        assert CustomPluginType.GENERATOR == "generator"
        assert CustomPluginType.HOOK == "hook"


class TestCustomPluginConfig:
    """Tests for CustomPluginConfig model."""

    def test_create_minimal_config(self):
        """Test creating a minimal plugin config."""
        config = CustomPluginConfig(name="test-plugin")
        assert config.name == "test-plugin"
        assert config.version == "1.0.0"
        assert config.plugin_type == CustomPluginType.ROLE
        assert config.enabled is True

    def test_create_role_config(self):
        """Test creating a role plugin config."""
        config = CustomPluginConfig(
            name="custom-reviewer",
            plugin_type=CustomPluginType.ROLE,
            description="A custom reviewer role",
            stage=RoleStage.REVIEW,
            priority=50,
            dependencies=["architect"],
            instructions="Review the code for best practices",
        )
        assert config.name == "custom-reviewer"
        assert config.stage == RoleStage.REVIEW
        assert config.priority == 50
        assert "architect" in config.dependencies
        assert config.instructions == "Review the code for best practices"

    def test_create_with_extensions(self):
        """Test creating config with extensions."""
        config = CustomPluginConfig(
            name="my-plugin",
            extensions=["developer", "filesystem"],
        )
        assert "developer" in config.extensions
        assert "filesystem" in config.extensions

    def test_create_with_recipe_template(self):
        """Test creating config with recipe template."""
        config = CustomPluginConfig(
            name="templated-plugin",
            recipe_template="version: 1.0.0\ninstructions: Test",
        )
        assert config.recipe_template is not None
        assert "version:" in config.recipe_template

    def test_create_hook_config(self):
        """Test creating a hook plugin config."""
        config = CustomPluginConfig(
            name="pre-commit-hook",
            plugin_type=CustomPluginType.HOOK,
            hook_events=["pre_review", "post_review"],
        )
        assert config.plugin_type == CustomPluginType.HOOK
        assert "pre_review" in config.hook_events


class TestCustomPluginFile:
    """Tests for CustomPluginFile model."""

    def test_create_file(self):
        """Test creating a plugin file model."""
        plugin_file = CustomPluginFile(
            path="/path/to/plugins.yaml",
            plugins=[
                CustomPluginConfig(name="plugin1"),
                CustomPluginConfig(name="plugin2"),
            ],
        )
        assert plugin_file.path == "/path/to/plugins.yaml"
        assert len(plugin_file.plugins) == 2

    def test_file_with_errors(self):
        """Test plugin file with errors."""
        plugin_file = CustomPluginFile(
            path="/path/to/invalid.yaml",
            errors=["Invalid YAML syntax", "Missing required field"],
        )
        assert len(plugin_file.errors) == 2


class TestCustomPluginRegistry:
    """Tests for CustomPluginRegistry model."""

    def test_empty_registry(self):
        """Test empty registry."""
        registry = CustomPluginRegistry()
        assert len(registry.plugins) == 0
        assert len(registry.list_plugins()) == 0

    def test_add_plugin(self):
        """Test adding a plugin to registry."""
        registry = CustomPluginRegistry()
        config = CustomPluginConfig(name="test-plugin")

        registry.add_plugin(config)

        assert "test-plugin" in registry.plugins
        assert registry.get_plugin("test-plugin") == config

    def test_remove_plugin(self):
        """Test removing a plugin from registry."""
        registry = CustomPluginRegistry()
        config = CustomPluginConfig(name="test-plugin")
        registry.add_plugin(config)

        result = registry.remove_plugin("test-plugin")

        assert result is True
        assert "test-plugin" not in registry.plugins

    def test_remove_nonexistent_plugin(self):
        """Test removing a plugin that doesn't exist."""
        registry = CustomPluginRegistry()
        result = registry.remove_plugin("nonexistent")
        assert result is False

    def test_get_plugin(self):
        """Test getting a plugin by name."""
        registry = CustomPluginRegistry()
        config = CustomPluginConfig(name="my-plugin", description="Test")
        registry.add_plugin(config)

        retrieved = registry.get_plugin("my-plugin")
        assert retrieved is not None
        assert retrieved.description == "Test"

    def test_get_nonexistent_plugin(self):
        """Test getting a nonexistent plugin."""
        registry = CustomPluginRegistry()
        assert registry.get_plugin("nonexistent") is None

    def test_list_plugins(self):
        """Test listing all plugins."""
        registry = CustomPluginRegistry()
        registry.add_plugin(CustomPluginConfig(name="plugin1"))
        registry.add_plugin(CustomPluginConfig(name="plugin2"))

        plugins = registry.list_plugins()
        assert len(plugins) == 2
        names = {p.name for p in plugins}
        assert "plugin1" in names
        assert "plugin2" in names

    def test_list_enabled_plugins(self):
        """Test listing enabled plugins only."""
        registry = CustomPluginRegistry()
        registry.add_plugin(CustomPluginConfig(name="enabled-plugin", enabled=True))
        registry.add_plugin(CustomPluginConfig(name="disabled-plugin", enabled=False))

        enabled = registry.list_enabled_plugins()
        assert len(enabled) == 1
        assert enabled[0].name == "enabled-plugin"

    def test_plugin_files_tracking(self):
        """Test tracking plugin files."""
        registry = CustomPluginRegistry()
        registry.plugin_files.append("/path/to/plugins1.yaml")
        registry.plugin_files.append("/path/to/plugins2.yaml")

        assert len(registry.plugin_files) == 2
