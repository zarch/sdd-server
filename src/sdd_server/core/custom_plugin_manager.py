"""Custom plugin manager for user-defined plugins.

This module provides functionality to:
- Load custom plugins from YAML/JSON configuration files
- Create plugin instances from configuration
- Manage custom plugin lifecycle
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from sdd_server.infrastructure.filesystem import FileSystemClient
from sdd_server.models.custom_plugin import (
    CustomPluginConfig,
    CustomPluginRegistry,
    CustomPluginType,
)
from sdd_server.plugins.base import (
    BasePlugin,
    PluginError,
    PluginMetadata,
    RolePlugin,
    RoleResult,
    RoleStage,
    RoleStatus,
)
from sdd_server.utils.logging import get_logger

logger = get_logger(__name__)


class DynamicRolePlugin(RolePlugin):
    """A role plugin created from configuration.

    This class allows creating role plugins dynamically from
    CustomPluginConfig without writing Python code.
    """

    def __init__(self, config: CustomPluginConfig) -> None:
        """Initialize the dynamic role plugin.

        Args:
            config: Plugin configuration
        """
        super().__init__()
        self._config = config
        self.metadata = PluginMetadata(
            name=config.name,
            version=config.version,
            description=config.description,
            author=config.author,
            priority=config.priority,
            stage=config.stage or RoleStage.REVIEW,
            dependencies=config.dependencies,
        )

    async def initialize(self, context: dict[str, Any]) -> None:
        """Initialize the plugin with context."""
        await super().initialize(context)
        logger.info("Initialized custom role plugin", name=self._config.name)

    async def review(
        self,
        scope: str = "all",
        target: str | None = None,
    ) -> RoleResult:
        """Perform the role review.

        Args:
            scope: Review scope
            target: Optional feature target

        Returns:
            RoleResult with findings
        """
        started_at = datetime.now()

        # The actual review is performed by the AI client
        # This returns a placeholder result
        return RoleResult(
            role=self.name,
            status=RoleStatus.PENDING,
            success=False,
            output=f"Custom role '{self.name}' review pending - run with AI client",
            issues=[],
            suggestions=[
                f"Run the {self.name} recipe to perform the review",
                "Check the plugin configuration for details",
            ],
            started_at=started_at,
        )

    def get_recipe_template(self) -> str:
        """Return the recipe template for this plugin."""
        if self._config.recipe_template:
            return self._config.recipe_template

        # Generate a default recipe template
        return self._generate_default_recipe()

    def _generate_default_recipe(self) -> str:
        """Generate a default recipe template from configuration."""
        extensions_yaml = (
            "\n".join(f"  - type: builtin\n    name: {ext}" for ext in self._config.extensions)
            or "  - type: builtin\n    name: developer"
        )

        deps_yaml = ""
        if self._config.dependencies:
            deps_list = ", ".join(self._config.dependencies)
            deps_yaml = f"\n  Dependencies: {deps_list}"

        return f"""version: "1.0.0"
title: "{self._config.name.title()} — {{{{ project_name }}}}"
description: "{self._config.description}"

instructions: |
  {self._config.instructions or f"You are the {self._config.name} role for this project."}
{deps_yaml}

prompt: |
  {self._config.prompt or f"Perform the {self._config.name} review for this project."}

extensions:
{extensions_yaml}

parameters:
  - key: feature
    input_type: string
    requirement: optional
    default: ""
    description: Feature to focus on

response:
  json_schema:
    type: object
    properties:
      success:
        type: boolean
      issues_found:
        type: integer
      suggestions:
        type: array
        items:
          type: string
    required:
      - success

retry:
  max_retries: 2
  timeout_seconds: 300
"""


class CustomPluginManager:
    """Manager for custom plugins.

    This class handles:
    - Loading custom plugins from configuration files
    - Creating plugin instances from configuration
    - Managing the custom plugin registry
    """

    CUSTOM_PLUGINS_DIR = "custom_plugins"
    CUSTOM_PLUGINS_FILE = "custom_plugins.yaml"

    def __init__(
        self,
        project_root: Path,
        specs_dir: str = "specs",
    ) -> None:
        """Initialize the custom plugin manager.

        Args:
            project_root: Project root directory
            specs_dir: Specs directory name
        """
        self.project_root = project_root.resolve()
        self._specs_dir = specs_dir
        self._fs = FileSystemClient(self.project_root)
        self._registry = CustomPluginRegistry()
        self._plugins: dict[str, BasePlugin] = {}

    @property
    def registry(self) -> CustomPluginRegistry:
        """Get the custom plugin registry."""
        return self._registry

    # -------------------------------------------------------------------------
    # Loading
    # -------------------------------------------------------------------------

    def load_from_directory(self, directory: Path | None = None) -> list[CustomPluginConfig]:
        """Load custom plugins from a directory.

        Looks for YAML and JSON files containing plugin configurations.

        Args:
            directory: Directory to load from (defaults to specs/custom_plugins)

        Returns:
            List of loaded plugin configurations
        """
        if directory is None:
            directory = self.project_root / self._specs_dir / self.CUSTOM_PLUGINS_DIR

        if not self._fs.directory_exists(directory):
            logger.debug("Custom plugins directory not found", path=str(directory))
            return []

        loaded: list[CustomPluginConfig] = []

        for file_path in self._fs.list_directory(directory):
            if file_path.suffix in (".yaml", ".yml", ".json"):
                try:
                    configs = self._load_plugin_file(file_path)
                    for config in configs:
                        self._registry.add_plugin(config)
                        loaded.append(config)
                        logger.info(
                            "Loaded custom plugin",
                            name=config.name,
                            type=config.plugin_type.value,
                            file=str(file_path),
                        )
                except Exception as e:
                    logger.warning(
                        "Failed to load custom plugin file",
                        file=str(file_path),
                        error=str(e),
                    )

        return loaded

    def load_from_file(self, file_path: Path) -> list[CustomPluginConfig]:
        """Load custom plugins from a specific file.

        Args:
            file_path: Path to the plugin configuration file

        Returns:
            List of loaded plugin configurations
        """
        configs = self._load_plugin_file(file_path)
        for config in configs:
            self._registry.add_plugin(config)
        return configs

    def _load_plugin_file(self, file_path: Path) -> list[CustomPluginConfig]:
        """Load plugins from a file.

        Args:
            file_path: Path to the file

        Returns:
            List of plugin configurations
        """
        content = self._fs.read_file(file_path)
        file_ext: str = file_path.suffix.lower()

        if file_ext == ".json":
            import json

            data = json.loads(content)
        else:
            data = yaml.safe_load(content)

        if data is None:
            return []

        # Handle single plugin or list of plugins
        if isinstance(data, dict):
            if "plugins" in data:
                # File contains a list of plugins
                plugins_data = data["plugins"]
            elif "name" in data:
                # Single plugin definition
                plugins_data = [data]
            else:
                # Unknown format
                return []
        elif isinstance(data, list):
            plugins_data = data
        else:
            return []

        configs: list[CustomPluginConfig] = []
        for plugin_data in plugins_data:
            if isinstance(plugin_data, dict):
                try:
                    config = CustomPluginConfig.model_validate(plugin_data)
                    configs.append(config)
                except Exception as e:
                    logger.warning(
                        "Invalid plugin configuration",
                        data=str(plugin_data),
                        error=str(e),
                    )

        return configs

    # -------------------------------------------------------------------------
    # Plugin Creation
    # -------------------------------------------------------------------------

    def create_plugin(self, config: CustomPluginConfig) -> BasePlugin:
        """Create a plugin instance from configuration.

        Args:
            config: Plugin configuration

        Returns:
            Plugin instance

        Raises:
            PluginError: If plugin cannot be created
        """
        if config.plugin_type == CustomPluginType.ROLE:
            return self._create_role_plugin(config)
        else:
            raise PluginError(f"Unsupported plugin type: {config.plugin_type}")

    def _create_role_plugin(self, config: CustomPluginConfig) -> DynamicRolePlugin:
        """Create a role plugin from configuration.

        Args:
            config: Plugin configuration

        Returns:
            DynamicRolePlugin instance
        """
        plugin = DynamicRolePlugin(config)
        self._plugins[config.name] = plugin
        return plugin

    def get_plugin(self, name: str) -> BasePlugin | None:
        """Get a created plugin by name.

        Args:
            name: Plugin name

        Returns:
            Plugin instance or None
        """
        return self._plugins.get(name)

    def get_all_plugins(self) -> dict[str, BasePlugin]:
        """Get all created plugins.

        Returns:
            Dictionary of plugin name to instance
        """
        return self._plugins.copy()

    # -------------------------------------------------------------------------
    # Plugin Management
    # -------------------------------------------------------------------------

    def create_plugin_config(
        self,
        name: str,
        plugin_type: str = "role",
        description: str = "",
        stage: str | None = None,
        priority: int = 100,
        dependencies: list[str] | None = None,
        instructions: str | None = None,
        prompt: str | None = None,
        extensions: list[str] | None = None,
        enabled: bool = True,
    ) -> CustomPluginConfig:
        """Create a new plugin configuration.

        Args:
            name: Plugin name
            plugin_type: Type of plugin
            description: Plugin description
            stage: Workflow stage (for role plugins)
            priority: Execution priority
            dependencies: List of dependency plugin names
            instructions: Instructions for the AI
            prompt: Prompt for the AI
            extensions: Required extensions

        Returns:
            Created plugin configuration
        """
        stage_enum = RoleStage(stage) if stage else None
        plugin_type_enum = CustomPluginType(plugin_type)

        config = CustomPluginConfig(
            name=name,
            plugin_type=plugin_type_enum,
            description=description,
            stage=stage_enum,
            priority=priority,
            dependencies=dependencies or [],
            instructions=instructions,
            prompt=prompt,
            extensions=extensions or ["developer"],
            enabled=enabled,
        )

        self._registry.add_plugin(config)
        return config

    def save_plugin_config(
        self,
        config: CustomPluginConfig,
        file_path: Path | None = None,
    ) -> Path:
        """Save a plugin configuration to a file.

        Args:
            config: Plugin configuration to save
            file_path: Optional file path (defaults to custom_plugins/{name}.yaml)

        Returns:
            Path to the saved file
        """
        if file_path is None:
            plugins_dir = self.project_root / self._specs_dir / self.CUSTOM_PLUGINS_DIR
            self._fs.ensure_directory(plugins_dir)
            file_path = plugins_dir / f"{config.name}.yaml"

        # Ensure parent directory exists
        self._fs.ensure_directory(file_path.parent)

        # Serialize to YAML
        content = yaml.dump(
            config.model_dump(mode="json"),
            default_flow_style=False,
            sort_keys=False,
        )
        self._fs.write_file(file_path, content)

        logger.info("Saved custom plugin config", name=config.name, path=str(file_path))
        return file_path

    def delete_plugin(self, name: str, delete_file: bool = True) -> bool:
        """Delete a plugin from the registry.

        Args:
            name: Plugin name
            delete_file: Whether to delete the configuration file

        Returns:
            True if plugin was deleted
        """
        config = self._registry.get_plugin(name)
        if config is None:
            return False

        self._registry.remove_plugin(name)

        if name in self._plugins:
            del self._plugins[name]

        if delete_file:
            plugins_dir = self.project_root / self._specs_dir / self.CUSTOM_PLUGINS_DIR
            for ext in (".yaml", ".yml", ".json"):
                file_path = plugins_dir / f"{name}{ext}"
                if self._fs.file_exists(file_path):
                    self._fs.delete_file(file_path)
                    logger.info("Deleted custom plugin file", path=str(file_path))
                    break

        logger.info("Deleted custom plugin", name=name)
        return True

    # -------------------------------------------------------------------------
    # Listing
    # -------------------------------------------------------------------------

    def list_plugins(self) -> list[CustomPluginConfig]:
        """List all registered custom plugins.

        Returns:
            List of plugin configurations
        """
        return self._registry.list_plugins()

    def list_enabled_plugins(self) -> list[CustomPluginConfig]:
        """List all enabled custom plugins.

        Returns:
            List of enabled plugin configurations
        """
        return self._registry.list_enabled_plugins()

    def get_plugin_config(self, name: str) -> CustomPluginConfig | None:
        """Get a plugin configuration by name.

        Args:
            name: Plugin name

        Returns:
            Plugin configuration or None
        """
        return self._registry.get_plugin(name)
