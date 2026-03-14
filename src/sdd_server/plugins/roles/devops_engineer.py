"""DevOps Engineer role plugin.

The DevOps Engineer role is responsible for:
- Reviewing and generating CI/CD pipeline configuration
- Writing or auditing Dockerfile and container configuration
- Reviewing deployment manifests (k8s, docker-compose, etc.)
- Validating infrastructure-as-code against the architecture
- Ensuring observability hooks (metrics, logs, traces) are wired up

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


class DevOpsEngineerRole(RolePlugin):
    """DevOps Engineer role plugin.

    Runs after the Senior Developer review. Reviews or generates the
    CI/CD pipeline, Dockerfile, and deployment configuration, ensuring
    the implementation can be built, tested, and deployed reliably.

    Responsibilities:
    - Review or create CI/CD workflow files (.github/workflows, etc.)
    - Review or create Dockerfile / docker-compose
    - Validate deployment manifests against arch.md
    - Check environment variable and secrets management
    - Verify observability hooks (structured logs, health endpoints)
    - Add DevOps section to specs/arch.md
    """

    metadata = PluginMetadata(
        name="devops-engineer",
        version="1.0.0",
        description="CI/CD pipeline, containerisation, and deployment review",
        author="SDD Team",
        priority=60,
        stage=RoleStage.DEVOPS,
        dependencies=["senior-developer"],
    )

    async def initialize(self, context: dict[str, Any]) -> None:
        """Initialize DevOps engineer role with context."""
        await super().initialize(context)
        self._specs_dir = context.get("specs_dir")
        self._logger = context.get("logger")

    async def review(
        self,
        scope: str = "all",
        target: str | None = None,
    ) -> RoleResult:
        """Perform DevOps review.

        Args:
            scope: Review scope - "specs", "code", or "all"
            target: Optional feature name to focus on

        Returns:
            RoleResult with DevOps findings
        """
        return await self._run_with_ai_client(scope, target, datetime.now())

    def get_recipe_template(self) -> str:
        """Return Jinja2 template for DevOps engineer recipe."""
        return """version: "1.0.0"
title: "DevOps Engineer — {{ project_name }}"
description: "CI/CD, containerisation, and deployment review"

instructions: |
  You are the DevOps Engineer for the {{ project_name }} project.

  Your responsibilities:
  1. Review or generate CI/CD workflow files
  2. Review or create Dockerfile and docker-compose
  3. Validate deployment manifests against the architecture
  4. Check secrets and environment variable management
  5. Verify observability hooks are in place

prompt: |
  Review the architecture and implementation for deployability.
  Audit or generate CI/CD, Dockerfile, and deployment config.
  Flag any infrastructure gaps or security misconfigurations.

extensions:
  - type: builtin
    name: developer

parameters:
  - key: feature
    input_type: string
    requirement: optional
    default: ""
    description: Feature to focus DevOps review on
"""


__all__ = ["DevOpsEngineerRole"]
