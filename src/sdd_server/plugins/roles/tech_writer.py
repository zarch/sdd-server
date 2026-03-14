"""Tech Writer role plugin.

The Tech Writer role is responsible for:
- Generating user-facing documentation from specs and code
- Writing changelogs and release notes
- Producing API reference documentation
- Ensuring docs are consistent with the implementation

Architecture reference: arch.md Section 9.3
"""

from datetime import datetime
from typing import Any

from sdd_server.plugins.base import (
    PluginMetadata,
    RolePlugin,
    RoleResult,
    RoleStage,
)


class TechWriterRole(RolePlugin):
    """Tech Writer role plugin.

    Runs after the Senior Developer review. Translates specs and
    implementation details into user-facing documentation: README,
    API reference, changelog, and migration guides.

    Responsibilities:
    - Write or update README and getting-started guides
    - Generate API reference from interface contracts
    - Produce a changelog entry for this feature/release
    - Flag any undocumented public APIs or breaking changes
    - Add Documentation section to specs/arch.md
    """

    metadata = PluginMetadata(
        name="tech-writer",
        version="1.0.0",
        description="Documentation generation and review",
        author="SDD Team",
        priority=60,
        stage=RoleStage.DOCUMENTATION,
        dependencies=["senior-developer"],
    )

    async def initialize(self, context: dict[str, Any]) -> None:
        """Initialize tech writer role with context."""
        await super().initialize(context)
        self._specs_dir = context.get("specs_dir")
        self._logger = context.get("logger")

    async def review(
        self,
        scope: str = "all",
        target: str | None = None,
    ) -> RoleResult:
        """Perform documentation review and generation.

        Args:
            scope: Review scope - "specs", "code", or "all"
            target: Optional feature name to focus on

        Returns:
            RoleResult with documentation findings
        """
        return await self._run_with_ai_client(scope, target, datetime.now())

    def get_recipe_template(self) -> str:
        """Return Jinja2 template for tech writer recipe."""
        return """version: "1.0.0"
title: "Tech Writer — {{ project_name }}"
description: "Documentation generation and review"

instructions: |
  You are the Tech Writer for the {{ project_name }} project.

  Your responsibilities:
  1. Write or update README and getting-started guides
  2. Generate API reference from interface contracts
  3. Produce a changelog entry
  4. Flag undocumented public APIs or breaking changes

prompt: |
  Review specs and implementation. Generate user-facing documentation,
  API reference, and a changelog entry. Flag any documentation gaps.

extensions:
  - type: builtin
    name: developer

parameters:
  - key: feature
    input_type: string
    requirement: optional
    default: ""
    description: Feature to focus documentation on
"""


__all__ = ["TechWriterRole"]
