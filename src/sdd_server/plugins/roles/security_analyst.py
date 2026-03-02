"""Security Analyst role plugin.

The Security Analyst role is responsible for:
- Identifying security vulnerabilities
- Reviewing authentication and authorization
- Checking for common attack vectors
- Validating security configurations

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


class SecurityAnalystRole(RolePlugin):  # type: ignore[misc]
    """Security Analyst role plugin.

    The Security Analyst focuses on identifying and mitigating security
    risks. It depends on the Architect and Interface Designer roles to
    understand the system structure and interfaces.

    Responsibilities:
    - Identify security vulnerabilities
    - Review authentication and authorization mechanisms
    - Check for common attack vectors (OWASP Top 10)
    - Validate security configurations
    - Review data protection and encryption
    - Assess third-party dependency risks
    """

    metadata = PluginMetadata(
        name="security-analyst",
        version="1.0.0",
        description="Security analysis and vulnerability review",
        author="SDD Team",
        priority=30,
        stage=RoleStage.SECURITY,
        dependencies=["architect", "interface-designer"],  # Depends on architecture and interfaces
    )

    async def initialize(self, context: dict[str, Any]) -> None:
        """Initialize security analyst role with context."""
        await super().initialize(context)
        self._specs_dir = context.get("specs_dir")
        self._logger = context.get("logger")

    async def review(
        self,
        scope: str = "all",
        target: str | None = None,
    ) -> RoleResult:
        """Perform security analysis review.

        Args:
            scope: Review scope - "specs", "code", or "all"
            target: Optional feature name to focus on

        Returns:
            RoleResult with security findings
        """
        started_at = datetime.now()

        return RoleResult(
            role=self.name,
            status=RoleStatus.PENDING,
            success=False,
            output="Security analysis review pending - run with AI client",
            issues=[],
            suggestions=[
                "Run the security-analyst recipe to perform full security review",
                "Review authentication mechanisms",
                "Check for OWASP Top 10 vulnerabilities",
            ],
            started_at=started_at,
        )

    def get_recipe_template(self) -> str:
        """Return Jinja2 template for security analyst recipe."""
        return """version: "1.0.0"
title: "Security Analyst — {{ project_name }}"
description: "Security analysis and vulnerability review"

instructions: |
  You are the Security Analyst for the {{ project_name }} project.

  Your responsibilities:
  1. Identify security vulnerabilities and risks
  2. Review authentication and authorization mechanisms
  3. Check for OWASP Top 10 vulnerabilities
  4. Validate security configurations
  5. Review data protection and encryption
  6. Assess third-party dependency risks
  7. Document threat model and mitigations

  Review Process:
  1. Read the PRD at specs/prd.md for security requirements
  2. Review the architecture at specs/arch.md for system design
  3. Analyze interfaces for security concerns
  4. Check code for common vulnerabilities
  5. Review dependencies for known CVEs

  Output Requirements:
  - Add Security Analysis section to specs/arch.md
  - Include threat model with trust boundaries
  - Document input validation requirements
  - List security findings with severity levels
  - Specify remediation recommendations

  OWASP Top 10 Checklist:
  - A01: Broken Access Control
  - A02: Cryptographic Failures
  - A03: Injection
  - A04: Insecure Design
  - A05: Security Misconfiguration
  - A06: Vulnerable Components
  - A07: Authentication Failures
  - A08: Software/Data Integrity
  - A09: Logging/Monitoring Failures
  - A10: Server-Side Request Forgery

prompt: |
  Perform a comprehensive security analysis of the project.
  Review authentication, authorization, input validation, and
  data protection. Identify vulnerabilities and document
  remediation recommendations.

extensions:
  - type: builtin
    name: developer

parameters:
  - key: feature
    input_type: string
    requirement: optional
    default: ""
    description: Feature to focus security analysis on

response:
  json_schema:
    type: object
    properties:
      spec_updated:
        type: boolean
      vulnerabilities_found:
        type: integer
      critical_issues:
        type: integer
      recommendations:
        type: integer
    required:
      - spec_updated

retry:
  max_retries: 2
  timeout_seconds: 300
  checks:
    - type: shell
      command: "test -f specs/arch.md"
  on_failure: "echo 'Security analysis failed.'"
"""


__all__ = ["SecurityAnalystRole"]
