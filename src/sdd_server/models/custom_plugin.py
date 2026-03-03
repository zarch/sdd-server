"""Custom plugin models for user-defined plugins."""

from __future__ import annotations

from enum import StrEnum

from sdd_server.models.base import SDDBaseModel
from sdd_server.plugins.base import RoleStage


class CustomPluginType(StrEnum):
    """Types of custom plugins."""

    ROLE = "role"
    VALIDATOR = "validator"
    GENERATOR = "generator"
    HOOK = "hook"


class CustomPluginConfig(SDDBaseModel):
    """Configuration for a custom plugin.

    This model allows users to define plugins via YAML/JSON configuration
    without writing Python code. The plugin system will create appropriate
    plugin instances from these configurations.
    """

    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = "User"
    plugin_type: CustomPluginType = CustomPluginType.ROLE

    # Role-specific configuration
    stage: RoleStage | None = None
    priority: int = 100
    dependencies: list[str] = []  # noqa: RUF012

    # Recipe template (for role plugins)
    recipe_template: str | None = None

    # Instructions/prompt for the plugin
    instructions: str | None = None
    prompt: str | None = None

    # Extensions required
    extensions: list[str] = []  # noqa: RUF012

    # Custom script path (for advanced customization)
    script_path: str | None = None

    # Hook configuration
    hook_events: list[str] = []  # noqa: RUF012  # e.g., ["pre_review", "post_review"]

    # Enabled flag
    enabled: bool = True


class CustomPluginFile(SDDBaseModel):
    """A file containing custom plugin configurations."""

    path: str
    plugins: list[CustomPluginConfig] = []  # noqa: RUF012
    errors: list[str] = []  # noqa: RUF012


class CustomPluginRegistry(SDDBaseModel):
    """Registry of all custom plugins."""

    plugins: dict[str, CustomPluginConfig] = {}  # noqa: RUF012
    plugin_files: list[str] = []  # noqa: RUF012

    def add_plugin(self, config: CustomPluginConfig) -> None:
        """Add a plugin configuration to the registry."""
        self.plugins[config.name] = config

    def remove_plugin(self, name: str) -> bool:
        """Remove a plugin by name. Returns True if found."""
        if name in self.plugins:
            del self.plugins[name]
            return True
        return False

    def get_plugin(self, name: str) -> CustomPluginConfig | None:
        """Get a plugin configuration by name."""
        return self.plugins.get(name)

    def list_plugins(self) -> list[CustomPluginConfig]:
        """List all plugin configurations."""
        return list(self.plugins.values())

    def list_enabled_plugins(self) -> list[CustomPluginConfig]:
        """List all enabled plugin configurations."""
        return [p for p in self.plugins.values() if p.enabled]
