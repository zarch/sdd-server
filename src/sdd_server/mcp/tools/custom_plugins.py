"""MCP tools for custom plugin management."""

from __future__ import annotations

from mcp.server.fastmcp import Context, FastMCP

from sdd_server.core.custom_plugin_manager import CustomPluginManager
from sdd_server.models.custom_plugin import CustomPluginConfig, CustomPluginType


def _format_plugin_config(config: CustomPluginConfig) -> str:
    """Format a plugin configuration for display."""
    lines = [
        f"## {config.name}",
        "",
        f"**Type:** {config.plugin_type.value}",
        f"**Version:** {config.version}",
        f"**Author:** {config.author}",
        f"**Description:** {config.description or 'No description'}",
    ]

    if config.plugin_type == CustomPluginType.ROLE:
        lines.append(f"**Stage:** {config.stage.value if config.stage else 'None'}")
        lines.append(f"**Priority:** {config.priority}")
        if config.dependencies:
            lines.append(f"**Dependencies:** {', '.join(config.dependencies)}")

    if config.extensions:
        lines.append(f"**Extensions:** {', '.join(config.extensions)}")

    lines.append(f"**Enabled:** {'Yes' if config.enabled else 'No'}")

    if config.instructions:
        lines.append("")
        lines.append("### Instructions")
        lines.append("```")
        lines.append(config.instructions[:500] + ("..." if len(config.instructions) > 500 else ""))
        lines.append("```")

    return "\n".join(lines)


def register_tools(server: FastMCP) -> None:
    """Register custom plugin tools with the MCP server."""

    @server.tool(
        name="sdd_plugin_list",
        description="List all custom plugins",
    )
    async def list_plugins(
        ctx: Context,
        enabled_only: bool = False,
    ) -> str:
        """List all registered custom plugins.

        Args:
            enabled_only: Only show enabled plugins

        Returns:
            List of custom plugins
        """
        manager: CustomPluginManager = ctx.request_context.lifespan_context.custom_plugin_manager

        plugins = manager.list_enabled_plugins() if enabled_only else manager.list_plugins()

        if not plugins:
            return "No custom plugins found. Use `sdd_plugin_create` to add one."

        lines = [
            "# Custom Plugins",
            "",
            f"**Total:** {len(plugins)} plugin(s)",
            "",
        ]

        for config in plugins:
            lines.append(_format_plugin_config(config))
            lines.append("")

        return "\n".join(lines)

    @server.tool(
        name="sdd_plugin_create",
        description="Create a new custom plugin",
    )
    async def create_plugin(
        ctx: Context,
        name: str,
        plugin_type: str = "role",
        description: str = "",
        stage: str | None = None,
        priority: int = 100,
        dependencies: str | None = None,
        instructions: str | None = None,
        prompt: str | None = None,
        extensions: str | None = None,
        save: bool = True,
    ) -> str:
        """Create a new custom plugin.

        Args:
            name: Unique plugin name (lowercase, hyphens allowed)
            plugin_type: Plugin type (role, validator, generator, hook)
            description: Plugin description
            stage: Workflow stage for role plugins (architecture, ui-design,
                   interface-design, security, edge-case-analysis, implementation, review)
            priority: Execution priority (lower = runs first)
            dependencies: Comma-separated list of dependency plugin names
            instructions: Instructions for the AI role
            prompt: Prompt for the AI role
            extensions: Comma-separated list of required extensions
            save: Whether to save the configuration to a file

        Returns:
            Confirmation of plugin creation
        """
        manager: CustomPluginManager = ctx.request_context.lifespan_context.custom_plugin_manager

        # Check if plugin already exists
        if manager.get_plugin_config(name):
            return f"❌ Plugin '{name}' already exists. Use `sdd_plugin_update` to modify it."

        # Parse dependencies
        deps_list = None
        if dependencies:
            deps_list = [d.strip() for d in dependencies.split(",") if d.strip()]

        # Parse extensions
        ext_list = None
        if extensions:
            ext_list = [e.strip() for e in extensions.split(",") if e.strip()]

        try:
            config = manager.create_plugin_config(
                name=name,
                plugin_type=plugin_type,
                description=description,
                stage=stage,
                priority=priority,
                dependencies=deps_list,
                instructions=instructions,
                prompt=prompt,
                extensions=ext_list,
            )

            if save:
                file_path = manager.save_plugin_config(config)
                return (
                    f"✅ Created custom plugin '{name}'\n\n"
                    f"Configuration saved to: `{file_path.relative_to(manager.project_root)}`\n\n"
                    f"Use `sdd_plugin_show {name}` to view details."
                )
            else:
                return (
                    f"✅ Created custom plugin '{name}' (not saved to file)\n\n"
                    f"Use `sdd_plugin_save {name}` to save the configuration."
                )

        except Exception as e:
            return f"❌ Failed to create plugin: {e}"

    @server.tool(
        name="sdd_plugin_show",
        description="Show details of a custom plugin",
    )
    async def show_plugin(
        ctx: Context,
        name: str,
    ) -> str:
        """Show details of a custom plugin.

        Args:
            name: Plugin name

        Returns:
            Plugin details
        """
        manager: CustomPluginManager = ctx.request_context.lifespan_context.custom_plugin_manager

        config = manager.get_plugin_config(name)
        if not config:
            return f"❌ Plugin '{name}' not found. Use `sdd_plugin_list` to see available plugins."

        lines = [
            f"# Custom Plugin: {name}",
            "",
        ]
        lines.append(_format_plugin_config(config))

        # Show recipe template for role plugins
        if config.plugin_type == CustomPluginType.ROLE and config.recipe_template:
            lines.append("")
            lines.append("### Recipe Template")
            lines.append("```yaml")
            lines.append(config.recipe_template[:1000])
            if len(config.recipe_template) > 1000:
                lines.append("... (truncated)")
            lines.append("```")

        return "\n".join(lines)

    @server.tool(
        name="sdd_plugin_update",
        description="Update an existing custom plugin",
    )
    async def update_plugin(
        ctx: Context,
        name: str,
        description: str | None = None,
        stage: str | None = None,
        priority: int | None = None,
        dependencies: str | None = None,
        instructions: str | None = None,
        prompt: str | None = None,
        extensions: str | None = None,
        enabled: bool | None = None,
    ) -> str:
        """Update an existing custom plugin.

        Args:
            name: Plugin name
            description: New description
            stage: New workflow stage
            priority: New priority
            dependencies: New comma-separated dependencies (replaces existing)
            instructions: New instructions
            prompt: New prompt
            extensions: New comma-separated extensions (replaces existing)
            enabled: Enable/disable the plugin

        Returns:
            Confirmation of update
        """
        manager: CustomPluginManager = ctx.request_context.lifespan_context.custom_plugin_manager

        config = manager.get_plugin_config(name)
        if not config:
            return f"❌ Plugin '{name}' not found."

        # Update fields
        updates: list[str] = []

        if description is not None:
            config.description = description
            updates.append("description")

        if stage is not None:
            from sdd_server.plugins.base import RoleStage

            config.stage = RoleStage(stage)
            updates.append("stage")

        if priority is not None:
            config.priority = priority
            updates.append("priority")

        if dependencies is not None:
            config.dependencies = [d.strip() for d in dependencies.split(",") if d.strip()]
            updates.append("dependencies")

        if instructions is not None:
            config.instructions = instructions
            updates.append("instructions")

        if prompt is not None:
            config.prompt = prompt
            updates.append("prompt")

        if extensions is not None:
            config.extensions = [e.strip() for e in extensions.split(",") if e.strip()]
            updates.append("extensions")

        if enabled is not None:
            config.enabled = enabled
            updates.append("enabled")

        if not updates:
            return "No updates provided. Specify at least one field to update."

        # Save the updated config
        manager.save_plugin_config(config)

        return f"✅ Updated plugin '{name}'\n\nUpdated fields: {', '.join(updates)}"

    @server.tool(
        name="sdd_plugin_delete",
        description="Delete a custom plugin",
    )
    async def delete_plugin(
        ctx: Context,
        name: str,
    ) -> str:
        """Delete a custom plugin.

        Args:
            name: Plugin name

        Returns:
            Confirmation of deletion
        """
        manager: CustomPluginManager = ctx.request_context.lifespan_context.custom_plugin_manager

        if not manager.get_plugin_config(name):
            return f"❌ Plugin '{name}' not found."

        if manager.delete_plugin(name, delete_file=True):
            return f"✅ Deleted plugin '{name}' and its configuration file."
        else:
            return f"❌ Failed to delete plugin '{name}'."

    @server.tool(
        name="sdd_plugin_enable",
        description="Enable a custom plugin",
    )
    async def enable_plugin(
        ctx: Context,
        name: str,
    ) -> str:
        """Enable a custom plugin.

        Args:
            name: Plugin name

        Returns:
            Confirmation
        """
        manager: CustomPluginManager = ctx.request_context.lifespan_context.custom_plugin_manager

        config = manager.get_plugin_config(name)
        if not config:
            return f"❌ Plugin '{name}' not found."

        if config.enabled:
            return f"Plugin '{name}' is already enabled."

        config.enabled = True
        manager.save_plugin_config(config)
        return f"✅ Enabled plugin '{name}'."

    @server.tool(
        name="sdd_plugin_disable",
        description="Disable a custom plugin",
    )
    async def disable_plugin(
        ctx: Context,
        name: str,
    ) -> str:
        """Disable a custom plugin.

        Args:
            name: Plugin name

        Returns:
            Confirmation
        """
        manager: CustomPluginManager = ctx.request_context.lifespan_context.custom_plugin_manager

        config = manager.get_plugin_config(name)
        if not config:
            return f"❌ Plugin '{name}' not found."

        if not config.enabled:
            return f"Plugin '{name}' is already disabled."

        config.enabled = False
        manager.save_plugin_config(config)
        return f"✅ Disabled plugin '{name}'."

    @server.tool(
        name="sdd_plugin_load",
        description="Load custom plugins from the plugins directory",
    )
    async def load_plugins(
        ctx: Context,
    ) -> str:
        """Load all custom plugins from the plugins directory.

        Returns:
            Summary of loaded plugins
        """
        manager: CustomPluginManager = ctx.request_context.lifespan_context.custom_plugin_manager

        loaded = manager.load_from_directory()

        if not loaded:
            return "No custom plugins found to load."

        lines = [
            "# Loaded Custom Plugins",
            "",
            f"**Total:** {len(loaded)} plugin(s)",
            "",
        ]

        for config in loaded:
            status = "✅" if config.enabled else "⚪"
            lines.append(f"- {status} **{config.name}** ({config.plugin_type.value})")

        return "\n".join(lines)


def reg_custom_plugins(server: FastMCP) -> None:
    """Register custom plugin tools with the MCP server."""
    register_tools(server)
