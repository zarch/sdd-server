"""SDD Plugin System.

This module provides the plugin architecture for SDD extensibility:
- Role plugins: Architect, UI Designer, Security Analyst, etc.
- Analyzer plugins: Language-specific code analysis
- Linter plugins: Linter integrations

Usage:
    from sdd_server.plugins import RolePlugin, PluginMetadata
    from sdd_server.plugins import PluginLoader, PluginRegistry
    from sdd_server.plugins.base import RoleResult, RoleStage

Example:
    # Discover and load plugins
    loader = PluginLoader()
    await loader.discover_plugins()
    plugins = await loader.load_all_plugins()

    # Register in registry
    registry = PluginRegistry()
    for name, plugin in plugins.items():
        registry.register(name, plugin)

    # Get roles sorted by priority
    roles = registry.get_roles_sorted_by_priority()
"""

from sdd_server.plugins.base import (
    BasePlugin,
    PluginError,
    PluginLoadError,
    PluginMetadata,
    PluginValidationError,
    RolePlugin,
    RoleResult,
    RoleStage,
    RoleStatus,
    validate_plugin_metadata,
    validate_role_plugin,
)
from sdd_server.plugins.loader import PluginLoader
from sdd_server.plugins.registry import PluginRegistry
from sdd_server.plugins.roles import (
    BUILTIN_ROLES,
    ArchitectRole,
    EdgeCaseAnalystRole,
    InterfaceDesignerRole,
    SecurityAnalystRole,
    SeniorDeveloperRole,
    UIDesignerRole,
)

__all__ = [
    "BUILTIN_ROLES",
    # Built-in roles
    "ArchitectRole",
    # Base classes
    "BasePlugin",
    "EdgeCaseAnalystRole",
    "InterfaceDesignerRole",
    # Exceptions
    "PluginError",
    "PluginLoadError",
    # Loader and Registry
    "PluginLoader",
    "PluginMetadata",
    "PluginRegistry",
    "PluginValidationError",
    "RolePlugin",
    # Models
    "RoleResult",
    "RoleStage",
    "RoleStatus",
    "SecurityAnalystRole",
    "SeniorDeveloperRole",
    "UIDesignerRole",
    # Validation
    "validate_plugin_metadata",
    "validate_role_plugin",
]
