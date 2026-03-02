"""Plugin registry for managing loaded plugins.

This module provides the PluginRegistry that:
- Registers plugins by name and type
- Provides access to role plugins
- Lists available plugins with metadata
- Validates plugin dependencies

Architecture reference: arch.md Section 9.1
"""

from typing import Any

from sdd_server.plugins.base import (
    BasePlugin,
    PluginError,
    PluginMetadata,
    RolePlugin,
    RoleStage,
)
from sdd_server.utils.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# Plugin Registry
# =============================================================================


class PluginRegistry:
    """Registry for managing loaded SDD plugins.

    The registry maintains separate collections for different plugin types
    and provides convenient access methods. It also validates dependencies
    when registering plugins.

    Usage:
        registry = PluginRegistry()
        registry.register("architect", architect_plugin)
        registry.register("security-analyst", security_plugin)

        # Get a specific role
        architect = registry.get_role("architect")

        # List all roles for a stage
        stage_roles = registry.get_roles_by_stage(RoleStage.ARCHITECTURE)

        # Get roles sorted by priority
        sorted_roles = registry.get_roles_sorted_by_priority()
    """

    def __init__(self) -> None:
        """Initialize the plugin registry."""
        self._plugins: dict[str, BasePlugin] = {}
        self._roles: dict[str, RolePlugin] = {}
        self._metadata: dict[str, PluginMetadata] = {}

    # -------------------------------------------------------------------------
    # Registration
    # -------------------------------------------------------------------------

    def register(self, name: str, plugin: BasePlugin) -> None:
        """Register a plugin.

        Args:
            name: Plugin name
            plugin: Plugin instance

        Raises:
            PluginError: If plugin already registered or validation fails
        """
        if name in self._plugins:
            raise PluginError(f"Plugin already registered: {name}")

        # Validate plugin has metadata
        if not hasattr(plugin, "metadata"):
            raise PluginError(f"Plugin {name} has no metadata attribute")

        # Validate dependencies
        missing_deps = self._validate_dependencies(plugin)
        if missing_deps:
            raise PluginError(f"Plugin {name} has missing dependencies: {', '.join(missing_deps)}")

        # Register in appropriate collections
        self._plugins[name] = plugin
        self._metadata[name] = plugin.metadata

        if isinstance(plugin, RolePlugin):
            self._roles[name] = plugin
            logger.info(
                "Registered role plugin",
                name=name,
                stage=plugin.metadata.stage,
                priority=plugin.metadata.priority,
            )
        else:
            logger.info(
                "Registered plugin",
                name=name,
                type=type(plugin).__name__,
            )

    def unregister(self, name: str) -> BasePlugin | None:
        """Unregister a plugin.

        Args:
            name: Plugin name

        Returns:
            Unregistered plugin or None if not found
        """
        plugin = self._plugins.pop(name, None)
        if plugin:
            self._metadata.pop(name, None)
            self._roles.pop(name, None)
            logger.info("Unregistered plugin", name=name)
        return plugin

    def _validate_dependencies(self, plugin: BasePlugin) -> list[str]:
        """Validate plugin dependencies are registered.

        Args:
            plugin: Plugin to validate

        Returns:
            List of missing dependency names
        """
        missing = []
        if hasattr(plugin, "metadata") and plugin.metadata.dependencies:
            for dep in plugin.metadata.dependencies:
                if dep not in self._plugins:
                    missing.append(dep)
        return missing

    # -------------------------------------------------------------------------
    # Role Access
    # -------------------------------------------------------------------------

    def get_role(self, name: str) -> RolePlugin | None:
        """Get a role plugin by name.

        Args:
            name: Role name

        Returns:
            Role plugin or None if not found
        """
        return self._roles.get(name)

    def get_roles_by_stage(self, stage: RoleStage) -> list[RolePlugin]:
        """Get all role plugins for a specific stage.

        Args:
            stage: Workflow stage

        Returns:
            List of role plugins for the stage, sorted by priority
        """
        roles = [role for role in self._roles.values() if role.metadata.stage == stage]
        return sorted(roles, key=lambda r: r.metadata.priority)

    def get_roles_sorted_by_priority(self) -> list[RolePlugin]:
        """Get all role plugins sorted by priority.

        Returns:
            List of role plugins sorted by priority (lowest first)
        """
        return sorted(self._roles.values(), key=lambda r: r.metadata.priority)

    def get_role_dependencies(self, name: str) -> list[str]:
        """Get dependencies for a role.

        Args:
            name: Role name

        Returns:
            List of dependency role names
        """
        role = self._roles.get(name)
        if role:
            deps: list[str] = role.get_dependencies()
            return deps
        return []

    # -------------------------------------------------------------------------
    # General Access
    # -------------------------------------------------------------------------

    def get_plugin(self, name: str) -> BasePlugin | None:
        """Get any plugin by name.

        Args:
            name: Plugin name

        Returns:
            Plugin instance or None if not found
        """
        return self._plugins.get(name)

    def get_metadata(self, name: str) -> PluginMetadata | None:
        """Get plugin metadata by name.

        Args:
            name: Plugin name

        Returns:
            Plugin metadata or None if not found
        """
        return self._metadata.get(name)

    # -------------------------------------------------------------------------
    # Listing
    # -------------------------------------------------------------------------

    def list_plugins(self) -> list[str]:
        """List all registered plugin names.

        Returns:
            List of plugin names
        """
        return list(self._plugins.keys())

    def list_roles(self) -> list[str]:
        """List all registered role plugin names.

        Returns:
            List of role plugin names
        """
        return list(self._roles.keys())

    def list_metadata(self) -> list[PluginMetadata]:
        """List all plugin metadata.

        Returns:
            List of plugin metadata
        """
        return list(self._metadata.values())

    def get_roles_info(self) -> list[dict[str, Any]]:
        """Get detailed information about all roles.

        Returns:
            List of role info dictionaries
        """
        info = []
        for name, role in self._roles.items():
            info.append(
                {
                    "name": name,
                    "description": role.metadata.description,
                    "stage": role.metadata.stage.value if role.metadata.stage else None,
                    "priority": role.metadata.priority,
                    "dependencies": role.get_dependencies(),
                    "version": role.metadata.version,
                }
            )
        return info

    # -------------------------------------------------------------------------
    # Queries
    # -------------------------------------------------------------------------

    def has_plugin(self, name: str) -> bool:
        """Check if a plugin is registered.

        Args:
            name: Plugin name

        Returns:
            True if plugin is registered
        """
        return name in self._plugins

    def has_role(self, name: str) -> bool:
        """Check if a role plugin is registered.

        Args:
            name: Role name

        Returns:
            True if role is registered
        """
        return name in self._roles

    def count_plugins(self) -> int:
        """Get total number of registered plugins.

        Returns:
            Number of plugins
        """
        return len(self._plugins)

    def count_roles(self) -> int:
        """Get number of registered role plugins.

        Returns:
            Number of role plugins
        """
        return len(self._roles)

    # -------------------------------------------------------------------------
    # Dependency Graph
    # -------------------------------------------------------------------------

    def get_execution_order(self, role_names: list[str] | None = None) -> list[str]:
        """Get role execution order based on dependencies.

        Uses topological sort to determine the order in which roles
        should be executed to satisfy all dependencies.

        Args:
            role_names: Optional list of specific roles to order.
                       If None, orders all registered roles.

        Returns:
            List of role names in execution order

        Raises:
            PluginError: If circular dependency detected
        """
        if role_names is None:
            role_names = list(self._roles.keys())

        # Build dependency graph for requested roles
        graph: dict[str, list[str]] = {}
        for name in role_names:
            deps = self.get_role_dependencies(name)
            # Only include dependencies that are in the requested set
            graph[name] = [d for d in deps if d in role_names]

        # Topological sort using Kahn's algorithm
        result: list[str] = []
        in_degree = {name: 0 for name in role_names}

        # Calculate in-degrees
        for name, deps in graph.items():
            for dep in deps:
                if dep in in_degree:
                    in_degree[name] += 1

        # Start with nodes that have no dependencies
        queue = [name for name, degree in in_degree.items() if degree == 0]
        # Sort queue by priority for deterministic ordering
        queue.sort(key=lambda n: self._roles[n].metadata.priority if n in self._roles else 100)

        while queue:
            # Pop the first node (sorted by priority)
            current = queue.pop(0)
            result.append(current)

            # Reduce in-degree of dependents
            for name in role_names:
                if current in graph.get(name, []):
                    in_degree[name] -= 1
                    if in_degree[name] == 0:
                        # Insert in priority order
                        self._insert_by_priority(queue, name)

        # Check for circular dependencies
        if len(result) != len(role_names):
            missing = set(role_names) - set(result)
            raise PluginError(f"Circular dependency detected involving: {', '.join(missing)}")

        return result

    def _insert_by_priority(self, queue: list[str], name: str) -> None:
        """Insert a role name into queue maintaining priority order.

        Args:
            queue: Queue to insert into
            name: Role name to insert
        """
        priority = self._roles[name].metadata.priority if name in self._roles else 100
        inserted = False
        for i, existing in enumerate(queue):
            existing_priority = (
                self._roles[existing].metadata.priority if existing in self._roles else 100
            )
            if priority < existing_priority:
                queue.insert(i, name)
                inserted = True
                break
        if not inserted:
            queue.append(name)

    # -------------------------------------------------------------------------
    # Clear
    # -------------------------------------------------------------------------

    def clear(self) -> None:
        """Clear all registered plugins."""
        self._plugins.clear()
        self._roles.clear()
        self._metadata.clear()
        logger.info("Cleared plugin registry")
