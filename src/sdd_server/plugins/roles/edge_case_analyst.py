"""Edge Case Analyst role plugin.

The Edge Case Analyst role is responsible for:
- Identifying edge cases in user interactions
- Analyzing data flow edge cases
- Reviewing process flow edge cases
- Generating test scenarios for edge cases

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


class EdgeCaseAnalystRole(RolePlugin):  # type: ignore[misc]
    """Edge Case Analyst role plugin.

    The Edge Case Analyst focuses on identifying unusual scenarios and
    boundary conditions that might be missed. It depends on Architect,
    Interface Designer, and Security Analyst roles to understand the
    full system context.

    Responsibilities:
    - Identify edge cases in user interactions
    - Analyze data flow edge cases (empty, null, max values)
    - Review process flow edge cases (timeouts, failures)
    - Generate test scenarios for edge cases
    - Document error handling completeness
    """

    metadata = PluginMetadata(
        name="edge-case-analyst",
        version="1.0.0",
        description="Edge case analysis and boundary condition review",
        author="SDD Team",
        priority=40,
        stage=RoleStage.EDGE_CASE_ANALYSIS,
        dependencies=[
            "architect",
            "interface-designer",
            "security-analyst",
        ],  # Depends on architecture, interfaces, and security
    )

    async def initialize(self, context: dict[str, Any]) -> None:
        """Initialize edge case analyst role with context."""
        await super().initialize(context)
        self._specs_dir = context.get("specs_dir")
        self._logger = context.get("logger")

    async def review(
        self,
        scope: str = "all",
        target: str | None = None,
    ) -> RoleResult:
        """Perform edge case analysis review.

        Args:
            scope: Review scope - "specs", "code", or "all"
            target: Optional feature name to focus on

        Returns:
            RoleResult with edge case findings
        """
        started_at = datetime.now()

        return RoleResult(
            role=self.name,
            status=RoleStatus.PENDING,
            success=False,
            output="Edge case analysis review pending - run with AI client",
            issues=[],
            suggestions=[
                "Run the edge-case-analyst recipe to perform full edge case review",
                "Review boundary conditions in data handling",
                "Check error handling for all failure modes",
            ],
            started_at=started_at,
        )

    def get_recipe_template(self) -> str:
        """Return Jinja2 template for edge case analyst recipe."""
        return """version: "1.0.0"
title: "Edge Case Analyst — {{ project_name }}"
description: "Edge case analysis and boundary condition review"

instructions: |
  You are the Edge Case Analyst for the {{ project_name }} project.

  Your responsibilities:
  1. Identify edge cases in user interactions
  2. Analyze data flow edge cases
  3. Review process flow edge cases
  4. Generate test scenarios for edge cases
  5. Document error handling completeness
  6. Identify race conditions and timing issues

  Review Process:
  1. Read the PRD at specs/prd.md for requirements
  2. Review the architecture at specs/arch.md for system design
  3. Analyze interfaces for boundary conditions
  4. Check security considerations for edge cases
  5. Review existing tests for coverage gaps

  Edge Case Categories:

  User Interaction Edge Cases:
  - Empty/null inputs
  - Maximum length inputs
  - Invalid characters/formats
  - Concurrent operations
  - Rapid repeated actions

  Data Flow Edge Cases:
  - Empty datasets
  - Single item vs bulk operations
  - Circular references
  - Deep nesting
  - Missing optional fields

  Process Flow Edge Cases:
  - Timeouts and retries
  - Partial failures
  - Network interruptions
  - Resource exhaustion
  - Concurrent access

  Output Requirements:
  - Add Edge Case Analysis section to specs/arch.md
  - List all identified edge cases by category
  - Document mitigation strategies
  - Provide test scenario recommendations
  - Track edge case test coverage

prompt: |
  Analyze the project for edge cases and boundary conditions.
  Review user interactions, data flows, and process flows for
  unusual scenarios. Document edge cases and recommend tests.

extensions:
  - type: builtin
    name: developer

parameters:
  - key: feature
    input_type: string
    requirement: optional
    default: ""
    description: Feature to focus edge case analysis on

response:
  json_schema:
    type: object
    properties:
      spec_updated:
        type: boolean
      edge_cases_identified:
        type: integer
      user_interaction_cases:
        type: integer
      data_flow_cases:
        type: integer
      process_flow_cases:
        type: integer
      test_scenarios_recommended:
        type: integer
    required:
      - spec_updated

retry:
  max_retries: 2
  timeout_seconds: 300
  checks:
    - type: shell
      command: "test -f specs/arch.md"
  on_failure: "echo 'Edge case analysis failed.'"
"""


__all__ = ["EdgeCaseAnalystRole"]
