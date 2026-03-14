"""Product Owner role plugin.

The Product Owner role is responsible for:
- Verifying the implementation satisfies every PRD acceptance criterion
- Reviewing QA test report and defect list for release readiness
- Confirming documentation is complete and accurate
- Confirming deployment configuration is production-ready
- Issuing a final SHIP / HOLD decision with rationale

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


class ProductOwnerRole(RolePlugin):
    """Product Owner role plugin.

    The final gate in the SDD pipeline. Runs after QA Engineer,
    Tech Writer, and DevOps Engineer are all complete. Issues a
    SHIP or HOLD verdict for the feature/release.

    Responsibilities:
    - Verify all PRD acceptance criteria are met
    - Review QA report: no open critical/high defects
    - Confirm documentation is complete
    - Confirm CI/CD and deployment are production-ready
    - Issue SHIP / HOLD decision in specs/arch.md
    - Emit RoleCompletionEnvelope with verdict
    """

    metadata = PluginMetadata(
        name="product-owner",
        version="1.0.0",
        description="Release sign-off: PRD acceptance verification and SHIP/HOLD verdict",
        author="SDD Team",
        priority=80,
        stage=RoleStage.RELEASE,
        dependencies=["qa-engineer", "tech-writer", "devops-engineer"],
    )

    async def initialize(self, context: dict[str, Any]) -> None:
        """Initialize product owner role with context."""
        await super().initialize(context)
        self._specs_dir = context.get("specs_dir")
        self._logger = context.get("logger")

    async def review(
        self,
        scope: str = "all",
        target: str | None = None,
    ) -> RoleResult:
        """Perform final release sign-off review.

        Args:
            scope: Review scope - "specs", "code", or "all"
            target: Optional feature name to focus on

        Returns:
            RoleResult with SHIP/HOLD verdict and rationale
        """
        return await self._run_with_ai_client(scope, target, datetime.now())

    def get_recipe_template(self) -> str:
        """Return Jinja2 template for product owner recipe."""
        return """version: "1.0.0"
title: "Product Owner — {{ project_name }}"
description: "Release sign-off and PRD acceptance verification"

instructions: |
  You are the Product Owner for the {{ project_name }} project.

  Your responsibilities:
  1. Verify all PRD acceptance criteria are met
  2. Review QA report for blocking defects
  3. Confirm documentation completeness
  4. Confirm deployment readiness
  5. Issue a SHIP or HOLD verdict with rationale

prompt: |
  Review the complete pipeline output (arch.md Implementation Review,
  QA Report, Documentation, DevOps sections). Verify all PRD criteria
  are satisfied. Issue SHIP or HOLD with a clear rationale.

extensions:
  - type: builtin
    name: developer

parameters:
  - key: feature
    input_type: string
    requirement: optional
    default: ""
    description: Feature to issue sign-off for
"""


__all__ = ["ProductOwnerRole"]
