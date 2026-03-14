"""Architect role plugin.

The Architect role is responsible for:
- Defining system components and their interactions
- Documenting technical decisions and rationale
- Designing data flow and system architecture
- Identifying dependencies and integration points

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


class ArchitectRole(RolePlugin):
    """Architect role plugin for system architecture design.

    The Architect is the first role to run in the workflow and has no
    dependencies. It establishes the foundational architecture that
    other roles build upon.

    Responsibilities:
    - Define system components and boundaries
    - Document technology choices and rationale
    - Design data flow diagrams
    - Identify external dependencies
    - Create component interaction diagrams
    - Establish coding standards and patterns
    """

    metadata = PluginMetadata(
        name="architect",
        version="1.0.0",
        description="System architecture design and review",
        author="SDD Team",
        priority=10,  # Highest priority - runs first
        stage=RoleStage.ARCHITECTURE,
        dependencies=[],  # No dependencies
    )

    async def initialize(self, context: dict[str, Any]) -> None:
        """Initialize architect role with context."""
        await super().initialize(context)
        # Architect can access specs_dir for reading existing specs
        self._specs_dir = context.get("specs_dir")
        self._logger = context.get("logger")

    async def review(
        self,
        scope: str = "all",
        target: str | None = None,
    ) -> RoleResult:
        """Perform architecture review via AI client."""
        return await self._run_with_ai_client(scope, target, datetime.now())

    def get_recipe_template(self) -> str:
        """Return Jinja2 template for architect recipe.

        The template includes:
        - Role instructions for architecture review
        - Input specifications (PRD, existing specs)
        - Output specifications (arch.md updates)
        - Success criteria
        """
        return """version: "1.0.0"
title: "Architect — {{ project_name }}"
description: "Define and review system architecture"

instructions: |
  You are the System Architect for the {{ project_name }} project.

  Your responsibilities:
  1. Define system components and their boundaries
  2. Document technology choices with rationale
  3. Design data flow between components
  4. Identify external dependencies
  5. Create component interaction diagrams
  6. Establish coding standards and patterns

  Review Process:
  1. Read the PRD at specs/prd.md to understand requirements
  2. Review existing architecture in specs/arch.md (if exists)
  3. Analyze the codebase structure
  4. Update or create the architecture document

  Output Requirements:
  - Update specs/arch.md with your findings
  - Include component diagrams using ASCII or Mermaid
  - Document all significant technical decisions
  - List assumptions and constraints
  - Identify potential risks and mitigations

prompt: |
  Review the PRD at specs/prd.md and generate/update the architecture
  document at specs/arch.md. Focus on component design, data flow,
  and technology choices.

extensions:
  - type: builtin
    name: developer

parameters:
  - key: feature
    input_type: string
    requirement: optional
    default: ""
    description: Feature subdirectory to focus architecture review on

response:
  json_schema:
    type: object
    properties:
      spec_updated:
        type: boolean
      components_defined:
        type: array
        items:
          type: string
      decisions_documented:
        type: integer
      risks_identified:
        type: integer
    required:
      - spec_updated

retry:
  max_retries: 2
  timeout_seconds: 300
  checks:
    - type: shell
      command: "test -f specs/arch.md"
  on_failure: "echo 'Architecture generation failed.'"
"""


# Export for discovery
__all__ = ["ArchitectRole"]
