"""QA Engineer role plugin.

The QA Engineer role is responsible for:
- Writing and executing acceptance tests against the implementation
- Verifying every PRD acceptance criterion is met
- Reporting test failures and regression coverage gaps
- Producing a release-quality test report

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


class QAEngineerRole(RolePlugin):
    """QA Engineer role plugin.

    Runs after the Senior Developer review. Focuses exclusively on
    testing: acceptance tests against PRD criteria, regression coverage
    across catalogued edge cases, and a structured test report.

    Responsibilities:
    - Map PRD acceptance criteria to executable test scenarios
    - Run (or generate) acceptance tests
    - Cross-check edge case catalogue for missing test coverage
    - Produce a prioritised defect list
    - Emit a release-quality test report in specs/arch.md
    """

    metadata = PluginMetadata(
        name="qa-engineer",
        version="1.0.0",
        description="Acceptance testing and quality assurance report",
        author="SDD Team",
        priority=60,
        stage=RoleStage.QA,
        dependencies=["senior-developer"],
    )

    async def initialize(self, context: dict[str, Any]) -> None:
        """Initialize QA engineer role with context."""
        await super().initialize(context)
        self._specs_dir = context.get("specs_dir")
        self._logger = context.get("logger")

    async def review(
        self,
        scope: str = "all",
        target: str | None = None,
    ) -> RoleResult:
        """Perform QA review and acceptance test analysis.

        Args:
            scope: Review scope - "specs", "code", or "all"
            target: Optional feature name to focus on

        Returns:
            RoleResult with QA findings and test report
        """
        return await self._run_with_ai_client(scope, target, datetime.now())

    def get_recipe_template(self) -> str:
        """Return Jinja2 template for QA engineer recipe."""
        return """version: "1.0.0"
title: "QA Engineer — {{ project_name }}"
description: "Acceptance testing and quality assurance"

instructions: |
  You are the QA Engineer for the {{ project_name }} project.

  Your responsibilities:
  1. Map PRD acceptance criteria to test scenarios
  2. Run or generate acceptance tests
  3. Verify edge case coverage
  4. Produce a defect list and test report

prompt: |
  Review the implementation against PRD acceptance criteria.
  Generate missing tests. Report defects and coverage gaps.

extensions:
  - type: builtin
    name: developer

parameters:
  - key: feature
    input_type: string
    requirement: optional
    default: ""
    description: Feature to focus QA review on
"""


__all__ = ["QAEngineerRole"]
