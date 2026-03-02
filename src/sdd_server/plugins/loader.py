"""Plugin loader for discovering and loading SDD plugins.

This module implements the PluginLoader that discovers plugins from:
1. Built-in plugins (src/sdd_server/plugins/roles/)
2. User plugins (SDD_PLUGINS_PATH environment variable)
3. Entry point plugins (Python package entry points)

Architecture reference: arch.md Section 9.1
"""

import importlib
import importlib.util
import os
import sys
from pathlib import Path
from typing import Any

from sdd_server.plugins.base import (
    BasePlugin,
    PluginError,
    PluginLoadError,
    PluginMetadata,
    PluginValidationError,
    RolePlugin,
    validate_role_plugin,
)
from sdd_server.utils.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# Plugin Loader
# =============================================================================


class PluginLoader:
    """Discovers and loads plugins from multiple sources.

    Discovery order (later sources override earlier):
    1. Built-in plugins in src/sdd_server/plugins/roles/
    2. User plugins from SDD_PLUGINS_PATH environment variable
    3. Entry point plugins from installed packages

    The loader validates plugins and maintains a cache of discovered
    plugin classes.
    """

    ENTRY_POINT_GROUP = "sdd.plugins"

    def __init__(self, plugins_path: Path | None = None) -> None:
        """Initialize the plugin loader.

        Args:
            plugins_path: Optional path to user plugins directory.
                         Defaults to SDD_PLUGINS_PATH env var or None.
        """
        self._plugins_path = plugins_path or self._get_plugins_path()
        self._discovered_classes: dict[str, type[BasePlugin]] = {}
        self._loaded_plugins: dict[str, BasePlugin] = {}
        self._context: dict[str, Any] = {}

    def _get_plugins_path(self) -> Path | None:
        """Get user plugins path from environment."""
        path = os.environ.get("SDD_PLUGINS_PATH")
        return Path(path) if path else None

    # -------------------------------------------------------------------------
    # Discovery
    # -------------------------------------------------------------------------

    async def discover_plugins(self) -> dict[str, type[BasePlugin]]:
        """Discover all available plugins.

        Returns:
            Dictionary mapping plugin name to plugin class
        """
        self._discovered_classes.clear()

        # 1. Built-in plugins
        builtin_count = await self._discover_builtins()
        logger.info(
            "Discovered built-in plugins",
            plugin_count=builtin_count,
        )

        # 2. User plugins from path
        if self._plugins_path and self._plugins_path.exists():
            user_count = await self._discover_from_path(self._plugins_path)
            logger.info(
                "Discovered user plugins",
                path=str(self._plugins_path),
                plugin_count=user_count,
            )

        # 3. Entry point plugins
        entry_count = await self._discover_from_entry_points()
        logger.info(
            "Discovered entry point plugins",
            plugin_count=entry_count,
        )

        logger.info(
            "Plugin discovery complete",
            total_plugins=len(self._discovered_classes),
        )

        return self._discovered_classes.copy()

    async def _discover_builtins(self) -> int:
        """Discover built-in role plugins.

        Returns:
            Number of plugins discovered
        """
        builtin_dir = Path(__file__).parent / "roles"
        if not builtin_dir.exists():
            logger.debug("No built-in roles directory found")
            return 0

        count = 0
        for file_path in builtin_dir.iterdir():
            if file_path.suffix == ".py" and not file_path.name.startswith("_"):
                try:
                    plugin_classes = await self._load_module_plugins(file_path)
                    for plugin_class in plugin_classes:
                        if isinstance(plugin_class, type) and issubclass(plugin_class, BasePlugin):
                            name = self._get_plugin_name(plugin_class)
                            self._discovered_classes[name] = plugin_class
                            count += 1
                            logger.debug(
                                "Discovered built-in plugin",
                                name=name,
                                file=str(file_path),
                            )
                except Exception as e:
                    logger.warning(
                        "Failed to load built-in plugin",
                        file=str(file_path),
                        error=str(e),
                    )

        return count

    async def _discover_from_path(self, path: Path) -> int:
        """Discover plugins from a user plugins directory.

        Args:
            path: Directory containing user plugins

        Returns:
            Number of plugins discovered
        """
        count = 0
        for file_path in path.rglob("*.py"):
            if file_path.name.startswith("_"):
                continue
            try:
                plugin_classes = await self._load_module_plugins(file_path)
                for plugin_class in plugin_classes:
                    if isinstance(plugin_class, type) and issubclass(plugin_class, BasePlugin):
                        name = self._get_plugin_name(plugin_class)
                        self._discovered_classes[name] = plugin_class
                        count += 1
                        logger.debug(
                            "Discovered user plugin",
                            name=name,
                            file=str(file_path),
                        )
            except Exception as e:
                logger.warning(
                    "Failed to load user plugin",
                    file=str(file_path),
                    error=str(e),
                )

        return count

    async def _discover_from_entry_points(self) -> int:
        """Discover plugins from package entry points.

        Entry points should be defined in pyproject.toml:
        [project.entry-points."sdd.plugins"]
        my-plugin = "my_package.plugins:MyPlugin"

        Returns:
            Number of plugins discovered
        """
        count = 0
        try:
            # Python 3.10+ uses importlib.metadata
            import importlib.metadata as metadata

            entry_points = metadata.entry_points()
            # Python 3.14 only uses select()
            sdd_entries = entry_points.select(group=self.ENTRY_POINT_GROUP)

            for entry in sdd_entries:
                try:
                    plugin_class = entry.load()
                    if isinstance(plugin_class, type) and issubclass(plugin_class, BasePlugin):
                        name = self._get_plugin_name(plugin_class)
                        self._discovered_classes[name] = plugin_class
                        count += 1
                        logger.debug(
                            "Discovered entry point plugin",
                            name=name,
                            entry_point=entry.value,
                        )
                except Exception as e:
                    logger.warning(
                        "Failed to load entry point plugin",
                        entry_point=str(entry),
                        error=str(e),
                    )
        except Exception as e:
            logger.debug(
                "No entry points found or error loading",
                error=str(e),
            )

        return count

    async def _load_module_plugins(self, file_path: Path) -> list[type[BasePlugin]]:
        """Load plugin classes from a Python module.

        Args:
            file_path: Path to Python module

        Returns:
            List of plugin classes found in module
        """
        # Create module name from file path
        module_name = f"sdd_user_plugin_{file_path.stem}"

        # Load module from file
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            raise PluginLoadError(f"Cannot load module from {file_path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        # Find plugin classes in module
        plugin_classes: list[type[BasePlugin]] = []
        for attr_name in dir(module):
            if attr_name.startswith("_"):
                continue
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, BasePlugin)
                and attr is not BasePlugin
                and attr is not RolePlugin
            ):
                plugin_classes.append(attr)

        return plugin_classes

    def _get_plugin_name(self, plugin_class: type[BasePlugin]) -> str:
        """Get plugin name from class.

        Args:
            plugin_class: Plugin class

        Returns:
            Plugin name from metadata or class name
        """
        # Try to get name from metadata attribute
        if hasattr(plugin_class, "metadata"):
            metadata = plugin_class.metadata
            if isinstance(metadata, PluginMetadata):
                return str(metadata.name)

        # Fall back to class name converted to kebab-case
        class_name = plugin_class.__name__
        # Convert CamelCase to kebab-case
        name = ""
        for i, char in enumerate(class_name):
            if char.isupper() and i > 0:
                name += "-"
            name += char.lower()
        return name

    # -------------------------------------------------------------------------
    # Loading
    # -------------------------------------------------------------------------

    async def load_plugin(self, name: str) -> BasePlugin:
        """Load and initialize a plugin by name.

        Args:
            name: Plugin name

        Returns:
            Initialized plugin instance

        Raises:
            PluginLoadError: If plugin not found or initialization fails
        """
        # Check cache
        if name in self._loaded_plugins:
            return self._loaded_plugins[name]

        # Get plugin class
        plugin_class = self._discovered_classes.get(name)
        if plugin_class is None:
            # Try discovery if not found
            await self.discover_plugins()
            plugin_class = self._discovered_classes.get(name)

        if plugin_class is None:
            raise PluginLoadError(f"Plugin not found: {name}")

        # Instantiate and validate
        try:
            plugin = plugin_class()
        except Exception as e:
            raise PluginLoadError(f"Failed to instantiate plugin {name}: {e}") from e

        # Validate plugin
        errors = self.validate_plugin(plugin)
        if errors:
            raise PluginValidationError(f"Plugin validation failed for {name}: {'; '.join(errors)}")

        # Initialize with context
        try:
            await plugin.initialize(self._context)
        except Exception as e:
            raise PluginLoadError(f"Failed to initialize plugin {name}: {e}") from e

        # Cache and return
        self._loaded_plugins[name] = plugin
        logger.info("Loaded plugin", name=name)

        return plugin

    async def load_all_plugins(self) -> dict[str, BasePlugin]:
        """Load all discovered plugins.

        Returns:
            Dictionary of loaded plugins
        """
        if not self._discovered_classes:
            await self.discover_plugins()

        for name in self._discovered_classes:
            if name not in self._loaded_plugins:
                try:
                    await self.load_plugin(name)
                except PluginError as e:
                    logger.warning(
                        "Failed to load plugin",
                        name=name,
                        error=str(e),
                    )

        return self._loaded_plugins.copy()

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------

    def validate_plugin(self, plugin: BasePlugin) -> list[str]:
        """Validate a plugin instance.

        Args:
            plugin: Plugin instance to validate

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Check metadata exists
        if not hasattr(plugin, "metadata") or plugin.metadata is None:
            errors.append("Plugin must have metadata attribute")
            return errors

        # Role-specific validation
        if isinstance(plugin, RolePlugin):
            errors.extend(validate_role_plugin(plugin))

        return errors

    # -------------------------------------------------------------------------
    # Context Management
    # -------------------------------------------------------------------------

    def set_context(self, context: dict[str, Any]) -> None:
        """Set the context for plugin initialization.

        Args:
            context: Context dictionary with SDD services
        """
        self._context = context

    # -------------------------------------------------------------------------
    # Accessors
    # -------------------------------------------------------------------------

    def get_discovered_plugins(self) -> dict[str, type[BasePlugin]]:
        """Get all discovered plugin classes.

        Returns:
            Dictionary mapping plugin name to plugin class
        """
        return self._discovered_classes.copy()

    def get_loaded_plugins(self) -> dict[str, BasePlugin]:
        """Get all loaded plugin instances.

        Returns:
            Dictionary mapping plugin name to plugin instance
        """
        return self._loaded_plugins.copy()

    def get_plugin_class(self, name: str) -> type[BasePlugin] | None:
        """Get a discovered plugin class by name.

        Args:
            name: Plugin name

        Returns:
            Plugin class or None if not found
        """
        return self._discovered_classes.get(name)
