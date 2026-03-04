"""UI/UX Designer role plugin.

The UI/UX Designer role is responsible for:
- User experience design and flows
- Interface mockups and wireframes
- Accessibility considerations
- User interaction patterns

Architecture reference: arch.md Section 9.3
"""

from datetime import datetime
from typing import Any

from sdd_server.plugins.base import (
    PluginMetadata,
    RolePlugin,
    RoleResult,
    RoleStage,
    RoleStatus,
)


class UIDesignerRole(RolePlugin):
    """UI/UX Designer role plugin.

    The UI/UX Designer focuses on user-facing aspects of the system.
    It depends on the Architect role to understand the system structure
    before designing user interfaces.

    Responsibilities:
    - Design user experience flows
    - Create wireframes and mockups
    - Define accessibility requirements
    - Document user interaction patterns
    - Specify responsive design requirements
    """

    metadata = PluginMetadata(
        name="ui-designer",
        version="1.0.0",
        description="UI/UX design and user experience review",
        author="SDD Team",
        priority=20,
        stage=RoleStage.UI_DESIGN,
        dependencies=["architect"],  # Depends on architecture
    )

    async def initialize(self, context: dict[str, Any]) -> None:
        """Initialize UI designer role with context."""
        await super().initialize(context)
        self._specs_dir = context.get("specs_dir")
        self._logger = context.get("logger")

    async def review(
        self,
        scope: str = "all",
        target: str | None = None,
    ) -> RoleResult:
        """Perform UI/UX design review.

        Args:
            scope: Review scope - "specs", "code", or "all"
            target: Optional feature name to focus on

        Returns:
            RoleResult with UI/UX findings
        """
        started_at = datetime.now()

        return RoleResult(
            role=self.name,
            status=RoleStatus.PENDING,
            success=False,
            output="UI/UX design review pending - run with AI client",
            issues=[],
            suggestions=[
                "Run the ui-designer recipe to perform full UX review",
                "Review user flows documented in specs",
                "Ensure accessibility requirements are specified",
            ],
            started_at=started_at,
        )

    def get_recipe_template(self) -> str:
        """Return Jinja2 template for UI designer recipe."""
        return """version: "1.0.0"
title: "UI/UX Designer — {{ project_name }}"
description: "Design and review user experience"

instructions: |
  You are the UI/UX Designer for the {{ project_name }} project.

  Your responsibilities:
  1. Design user experience flows and journeys
  2. Create wireframes and mockup descriptions
  3. Define accessibility requirements (WCAG compliance)
  4. Document user interaction patterns
  5. Specify responsive design breakpoints
  6. Review existing UI for usability issues

  Review Process:
  1. Read the PRD at specs/prd.md for user requirements
  2. Review the architecture at specs/arch.md for system structure
  3. Analyze existing UI components and flows
  4. Document UX decisions and improvements

  Output Requirements:
  - Add UI/UX section to specs/arch.md or create specs/ui-design.md
  - Include user flow diagrams
  - Document accessibility requirements
  - List UI components and their states
  - Specify responsive design requirements

prompt: |
  Review the user-facing aspects of the project. Design user flows,
  document accessibility requirements, and specify UI components.
  Focus on creating a great user experience.

extensions:
  - type: builtin
    name: developer

parameters:
  - key: feature
    input_type: string
    requirement: optional
    default: ""
    description: Feature to focus UI design on

response:
  json_schema:
    type: object
    properties:
      spec_updated:
        type: boolean
      user_flows_documented:
        type: integer
      accessibility_issues:
        type: integer
      components_defined:
        type: integer
    required:
      - spec_updated

retry:
  max_retries: 2
  timeout_seconds: 300
  checks:
    - type: shell
      command: "test -f specs/arch.md"
  on_failure: "echo 'UI/UX design review failed.'"
"""


__all__ = ["UIDesignerRole"]
