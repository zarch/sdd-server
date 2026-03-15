"""Base classes for SDD plugins.

This module defines the abstract base classes for all plugin types:
- PluginMetadata: Plugin identification and configuration
- BasePlugin: Abstract base for all plugins
- RolePlugin: Base for role-specific plugins
- RoleResult: Result model for role execution
- RoleStage: Enum for workflow stages

Architecture reference: arch.md Section 9.1-9.2
"""

from abc import ABC, abstractmethod
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import Field

from sdd_server.infrastructure.exceptions import (
    PluginError,
    PluginLoadError,
    PluginNotFoundError,
    PluginValidationError,
)
from sdd_server.models.base import SDDBaseModel

# Re-export for type checkers
__all__ = [
    "BasePlugin",
    "PluginError",
    "PluginLoadError",
    "PluginMetadata",
    "PluginNotFoundError",
    "PluginValidationError",
    "RolePlugin",
    "RoleResult",
    "RoleStage",
    "RoleStatus",
    "validate_plugin_metadata",
    "validate_role_plugin",
]


# =============================================================================
# Enums
# =============================================================================


class RoleStage(StrEnum):
    """Workflow stages for role execution.

    Order defines the default execution sequence.
    Dependencies between stages are handled by RoleEngine.
    """

    SPEC_AUDIT = "spec-audit"
    ARCHITECTURE = "architecture"
    UI_DESIGN = "ui-design"
    INTERFACE_DESIGN = "interface-design"
    SECURITY = "security"
    EDGE_CASE_ANALYSIS = "edge-case-analysis"
    IMPLEMENTATION = "implementation"
    REVIEW = "review"
    QA = "qa"
    DOCUMENTATION = "documentation"
    DEVOPS = "devops"
    RELEASE = "release"


class RoleStatus(StrEnum):
    """Status of a role execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


# =============================================================================
# Models
# =============================================================================


class PluginMetadata(SDDBaseModel):
    """Metadata for a plugin.

    Attributes:
        name: Unique plugin identifier (e.g., "architect", "security-analyst")
        version: Plugin version (semver recommended)
        description: Human-readable description
        author: Plugin author
        priority: Execution priority (lower = higher priority, runs first)
        stage: Workflow stage this role belongs to (for role plugins)
        dependencies: List of role names this role depends on
    """

    name: str
    version: str
    description: str
    author: str
    priority: int = 100
    stage: RoleStage | None = None
    dependencies: list[str] = Field(default_factory=list)


class RoleResult(SDDBaseModel):
    """Result from a role execution.

    Captures the outcome of running a role plugin, including
    success/failure status, output, issues found, and suggestions.
    """

    role: str
    status: RoleStatus
    success: bool

    # Feedback
    output: str
    issues: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)

    # Metadata
    started_at: datetime
    completed_at: datetime | None = None
    duration_seconds: float | None = None

    # AI client integration (for Goose sessions)
    session_id: str | None = None

    def mark_completed(self, success: bool = True) -> None:
        """Mark the result as completed with timing."""
        self.completed_at = datetime.now()
        self.duration_seconds = (self.completed_at - self.started_at).total_seconds()
        self.success = success
        self.status = RoleStatus.COMPLETED if success else RoleStatus.FAILED


# =============================================================================
# Base Plugin Classes
# =============================================================================


class BasePlugin(ABC):
    """Abstract base class for all SDD plugins.

    All plugins must implement:
    - metadata: Plugin identification
    - initialize(): Setup with context
    - shutdown(): Cleanup resources

    The context dict provides access to SDD services:
    - specs_dir: Path to specs directory
    - recipes_dir: Path to recipes directory
    - logger: Structured logger instance
    """

    metadata: PluginMetadata

    def __init__(self) -> None:
        """Initialize plugin with empty context."""
        self._context: dict[str, Any] = {}

    @abstractmethod
    async def initialize(self, context: dict[str, Any]) -> None:
        """Initialize plugin with context.

        Args:
            context: Dictionary containing SDD services and configuration
        """
        ...

    @abstractmethod
    async def shutdown(self) -> None:
        """Cleanup plugin resources."""
        ...

    @property
    def name(self) -> str:
        """Get plugin name from metadata."""
        return self.metadata.name

    @property
    def context(self) -> dict[str, Any]:
        """Get the plugin context."""
        return self._context


class RolePlugin(BasePlugin):
    """Abstract base class for role plugins.

    Role plugins implement specific review/analysis roles in the SDD workflow.
    Each role:
    - Has a specific stage in the workflow
    - May depend on other roles (via dependencies in metadata)
    - Generates a recipe template for AI client execution
    - Returns structured RoleResult after execution

    Built-in roles:
    - spec-linter: Pre-flight spec structure and consistency validator (stage: SPEC_AUDIT)
    - architect: System architecture design (stage: ARCHITECTURE)
    - ui-designer: UI/UX design review (stage: UI_DESIGN)
    - interface-designer: API/interface design (stage: INTERFACE_DESIGN)
    - security-analyst: Security analysis (stage: SECURITY)
    - edge-case-analyst: Edge case analysis (stage: EDGE_CASE_ANALYSIS)
    - senior-developer: Implementation review (stage: IMPLEMENTATION)
    - qa-engineer: Acceptance testing and quality assurance (stage: QA)
    - tech-writer: Documentation generation (stage: DOCUMENTATION)
    - devops-engineer: CI/CD and deployment review (stage: DEVOPS)
    - product-owner: Release sign-off and PRD acceptance (stage: RELEASE)
    """

    @abstractmethod
    async def review(
        self,
        scope: str = "all",  # "specs" | "code" | "all"
        target: str | None = None,  # Optional feature name
    ) -> RoleResult:
        """Perform role-specific review.

        Args:
            scope: What to review - "specs", "code", or "all"
            target: Optional feature name to focus review on

        Returns:
            RoleResult with findings, issues, and suggestions
        """
        ...

    @abstractmethod
    def get_recipe_template(self) -> str:
        """Return Jinja2 template for AI client recipe.

        The template is used to generate a recipe file that can be
        executed by the AI client (Goose). It should include:
        - Role instructions
        - Input/output specifications
        - Success criteria

        Returns:
            Jinja2 template string
        """
        ...

    async def _run_with_ai_client(
        self,
        scope: str,
        target: str | None,
        started_at: datetime,
    ) -> RoleResult:
        """Invoke this role via the AI client stored in context.

        Falls back to a PENDING stub when no AI client is available so that
        the rest of the pipeline can continue without crashing.
        """
        ai_client = self._context.get("ai_client")
        project_root = str(self._context.get("project_root", "."))

        if ai_client is None:
            return RoleResult(
                role=self.name,
                status=RoleStatus.PENDING,
                success=False,
                output=f"{self.name} review pending — no AI client configured",
                suggestions=[
                    "Pass ai_client in context or set SDD_AI_CLIENT=goose and ensure Goose is on PATH"
                ],
                started_at=started_at,
            )

        recipe_path = Path(project_root) / "recipes" / f"{self.name}.yml"
        invoke_context: dict[str, Any] = {
            "scope": scope,
            "target": target or "",
            "project_root": project_root,
        }
        result = await ai_client.invoke_role(
            self.name,
            invoke_context,
            recipe_path if recipe_path.exists() else None,
        )

        if result.success:
            return RoleResult(
                role=self.name,
                status=RoleStatus.COMPLETED,
                success=True,
                output=result.output,
                started_at=started_at,
            )
        return RoleResult(
            role=self.name,
            status=RoleStatus.FAILED,
            success=False,
            output=result.output or "",
            issues=[result.error or "AI client invocation failed"],
            started_at=started_at,
        )

    def get_dependencies(self) -> list[str]:
        """Return list of role names this role depends on.

        Dependencies determine execution order in RoleEngine.
        A role will not run until all its dependencies have completed.

        Returns:
            List of role names (e.g., ["architect", "interface-designer"])
        """
        return self.metadata.dependencies

    def get_stage(self) -> RoleStage:
        """Get the workflow stage for this role."""
        if self.metadata.stage is None:
            raise PluginError(f"Role {self.name} has no stage defined")
        return self.metadata.stage

    async def initialize(self, context: dict[str, Any]) -> None:
        """Initialize role plugin with context.

        Default implementation stores context. Override to add
        role-specific initialization.
        """
        self._context = context

    async def shutdown(self) -> None:
        """Cleanup role plugin resources.

        Default implementation is a no-op. Override if cleanup needed.
        """
        pass


# =============================================================================
# Plugin Validation Helpers
# =============================================================================


def validate_plugin_metadata(metadata: PluginMetadata) -> list[str]:
    """Validate plugin metadata.

    Args:
        metadata: Plugin metadata to validate

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    if not metadata.name:
        errors.append("Plugin name is required")
    elif not metadata.name.replace("-", "").replace("_", "").isalnum():
        errors.append(f"Plugin name '{metadata.name}' must be alphanumeric with - or _")

    if not metadata.version:
        errors.append("Plugin version is required")

    if not metadata.description:
        errors.append("Plugin description is required")

    if metadata.priority < 0:
        errors.append("Plugin priority must be non-negative")

    return errors


def validate_role_plugin(plugin: RolePlugin) -> list[str]:
    """Validate a role plugin implementation.

    Args:
        plugin: Role plugin to validate

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    # Validate metadata
    errors.extend(validate_plugin_metadata(plugin.metadata))

    # Validate stage is set for role plugins
    if plugin.metadata.stage is None:
        errors.append(f"Role plugin {plugin.metadata.name} must have a stage defined")

    # Validate dependencies exist as strings
    for dep in plugin.metadata.dependencies:
        if not isinstance(dep, str):
            errors.append(f"Dependency must be string, got {type(dep)}")

    return errors
