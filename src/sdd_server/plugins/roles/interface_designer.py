"""Interface Designer role plugin.

The Interface Designer role is responsible for:
- API and interface design
- Contract definitions
- Data models and schemas
- Integration specifications

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


class InterfaceDesignerRole(RolePlugin):
    """Interface Designer role plugin.

    The Interface Designer focuses on defining interfaces between components,
    APIs, and integration points. It depends on the Architect role to
    understand the system structure.

    Responsibilities:
    - Design API contracts and interfaces
    - Define data models and schemas
    - Specify integration protocols
    - Document error handling and status codes
    - Create interface versioning strategy
    """

    metadata = PluginMetadata(
        name="interface-designer",
        version="1.0.0",
        description="API and interface design review",
        author="SDD Team",
        priority=20,
        stage=RoleStage.INTERFACE_DESIGN,
        dependencies=["architect"],  # Depends on architecture
    )

    async def initialize(self, context: dict[str, Any]) -> None:
        """Initialize interface designer role with context."""
        await super().initialize(context)
        self._specs_dir = context.get("specs_dir")
        self._logger = context.get("logger")

    async def review(
        self,
        scope: str = "all",
        target: str | None = None,
    ) -> RoleResult:
        """Perform interface design review.

        Args:
            scope: Review scope - "specs", "code", or "all"
            target: Optional feature name to focus on

        Returns:
            RoleResult with interface design findings
        """
        return await self._run_with_ai_client(scope, target, datetime.now())

    def get_recipe_template(self) -> str:
        """Return Jinja2 template for interface designer recipe."""
        return """version: "1.0.0"
title: "Interface Designer — {{ project_name }}"
description: "Design and review APIs and interfaces"

instructions: |
  You are the Interface Designer for the {{ project_name }} project.

  Your responsibilities:
  1. Design API contracts and interfaces
  2. Define data models and schemas
  3. Specify integration protocols (REST, MCP, etc.)
  4. Document error handling and status codes
  5. Create interface versioning strategy
  6. Review existing interfaces for consistency

  Review Process:
  1. Read the PRD at specs/prd.md for interface requirements
  2. Review the architecture at specs/arch.md for component structure
  3. Analyze existing API definitions and data models
  4. Document interface decisions and improvements

  Output Requirements:
  - Add Interface Design section to specs/arch.md
  - Include API endpoint definitions
  - Document request/response schemas
  - List error codes and handling
  - Specify authentication/authorization requirements

prompt: |
  Review the interfaces and APIs of the project. Design contracts,
  define schemas, and document integration points. Focus on
  consistency and clarity.

extensions:
  - type: builtin
    name: developer

parameters:
  - key: feature
    input_type: string
    requirement: optional
    default: ""
    description: Feature to focus interface design on

response:
  json_schema:
    type: object
    properties:
      spec_updated:
        type: boolean
      apis_documented:
        type: integer
      schemas_defined:
        type: integer
      errors_specified:
        type: integer
    required:
      - spec_updated

retry:
  max_retries: 2
  timeout_seconds: 300
  checks:
    - type: shell
      command: "test -f specs/arch.md"
  on_failure: "echo 'Interface design review failed.'"
"""


__all__ = ["InterfaceDesignerRole"]
