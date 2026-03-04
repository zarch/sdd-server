"""Senior Developer role plugin.

The Senior Developer role is responsible for:
- Code quality and maintainability review
- Best practices and patterns enforcement
- Performance considerations
- Implementation guidance

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


class SeniorDeveloperRole(RolePlugin):
    """Senior Developer role plugin.

    The Senior Developer focuses on implementation quality and best
    practices. It runs after all design/analysis roles to review
    the implementation approach.

    Responsibilities:
    - Review code quality and maintainability
    - Enforce coding standards and best practices
    - Identify performance considerations
    - Provide implementation guidance
    - Review test coverage and quality
    - Document technical debt
    """

    metadata = PluginMetadata(
        name="senior-developer",
        version="1.0.0",
        description="Implementation review and best practices guidance",
        author="SDD Team",
        priority=50,
        stage=RoleStage.IMPLEMENTATION,
        dependencies=[
            "architect",
            "interface-designer",
            "security-analyst",
            "edge-case-analyst",
        ],  # Depends on all design roles
    )

    async def initialize(self, context: dict[str, Any]) -> None:
        """Initialize senior developer role with context."""
        await super().initialize(context)
        self._specs_dir = context.get("specs_dir")
        self._logger = context.get("logger")

    async def review(
        self,
        scope: str = "all",
        target: str | None = None,
    ) -> RoleResult:
        """Perform implementation review.

        Args:
            scope: Review scope - "specs", "code", or "all"
            target: Optional feature name to focus on

        Returns:
            RoleResult with implementation findings
        """
        started_at = datetime.now()

        return RoleResult(
            role=self.name,
            status=RoleStatus.PENDING,
            success=False,
            output="Implementation review pending - run with AI client",
            issues=[],
            suggestions=[
                "Run the senior-developer recipe to perform full implementation review",
                "Review code for best practices compliance",
                "Check test coverage for critical paths",
            ],
            started_at=started_at,
        )

    def get_recipe_template(self) -> str:
        """Return Jinja2 template for senior developer recipe."""
        return """version: "1.0.0"
title: "Senior Developer — {{ project_name }}"
description: "Implementation review and best practices guidance"

instructions: |
  You are the Senior Developer for the {{ project_name }} project.

  Your responsibilities:
  1. Review code quality and maintainability
  2. Enforce coding standards and best practices
  3. Identify performance considerations
  4. Provide implementation guidance
  5. Review test coverage and quality
  6. Document technical debt and improvement opportunities

  Review Process:
  1. Read the PRD at specs/prd.md for requirements
  2. Review the architecture at specs/arch.md for design decisions
  3. Analyze the codebase structure and patterns
  4. Check test coverage and quality
  5. Review for security and edge case handling

  Code Quality Checklist:
  - [ ] Code is readable and well-documented
  - [ ] Functions/methods are appropriately sized
  - [ ] Error handling is comprehensive
  - [ ] Logging is sufficient for debugging
  - [ ] Type hints are used consistently
  - [ ] No code duplication (DRY principle)
  - [ ] Single responsibility principle followed
  - [ ] Dependencies are properly managed

  Performance Considerations:
  - [ ] Database queries are optimized
  - [ ] Caching is used where appropriate
  - [ ] Async operations used for I/O
  - [ ] Resource cleanup is handled properly
  - [ ] Memory usage is reasonable

  Test Quality Checklist:
  - [ ] Unit tests cover critical paths
  - [ ] Edge cases have test coverage
  - [ ] Integration tests verify workflows
  - [ ] Tests are maintainable and clear
  - [ ] Mocking is used appropriately

  Output Requirements:
  - Add Implementation Review section to specs/arch.md or tasks.md
  - Document code quality findings
  - List performance recommendations
  - Track technical debt items
  - Provide test coverage recommendations

prompt: |
  Review the implementation for code quality, best practices, and
  performance. Provide guidance on maintainability and document
  any technical debt. Focus on production-readiness.

extensions:
  - type: builtin
    name: developer

parameters:
  - key: feature
    input_type: string
    requirement: optional
    default: ""
    description: Feature to focus implementation review on

response:
  json_schema:
    type: object
    properties:
      spec_updated:
        type: boolean
      code_quality_issues:
        type: integer
      performance_recommendations:
        type: integer
      technical_debt_items:
        type: integer
      test_coverage_gaps:
        type: integer
    required:
      - spec_updated

retry:
  max_retries: 2
  timeout_seconds: 300
  checks:
    - type: shell
      command: "test -f specs/arch.md"
  on_failure: "echo 'Implementation review failed.'"
"""


__all__ = ["SeniorDeveloperRole"]
