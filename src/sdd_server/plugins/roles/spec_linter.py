"""Spec Linter role plugin.

The Spec Linter is the first role to run in every pipeline cycle. It validates
the specs/ folder structure, required sections, AC ID cross-references, naming
conventions, and broken links before any other role consumes the specs.

It is also the recommended entry point for onboarding an existing project that
already has specs written following SDD conventions.

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


class SpecLinterRole(RolePlugin):
    """Spec Linter role plugin for pre-flight spec validation.

    The Spec Linter runs before all other roles (priority 5) and has no
    dependencies. It validates specs/ folder structure, file naming conventions,
    required sections, AC ID cross-references, and broken relative links.

    Responsibilities:
    - Verify required spec files exist (prd.md mandatory)
    - Check file and directory naming conventions (kebab-case)
    - Validate required sections in prd.md, arch.md, and tasks.md
    - Cross-reference Acceptance Criteria IDs across spec files
    - Check feature subdirectory consistency under specs/features/
    - Detect stale task references to removed ACs or features
    - Scan for broken relative markdown links
    - Write Spec Audit section to specs/arch.md
    """

    metadata = PluginMetadata(
        name="spec-linter",
        version="1.0.0",
        description="Pre-flight spec structure and consistency validator",
        author="SDD Team",
        priority=5,  # Runs before all other roles
        stage=RoleStage.SPEC_AUDIT,
        dependencies=[],  # No dependencies — first in the chain
    )

    async def initialize(self, context: dict[str, Any]) -> None:
        """Initialize spec linter role with context."""
        await super().initialize(context)
        self._specs_dir = context.get("specs_dir")
        self._logger = context.get("logger")

    async def review(
        self,
        scope: str = "all",
        target: str | None = None,
    ) -> RoleResult:
        """Run spec audit via AI client."""
        return await self._run_with_ai_client(scope, target, datetime.now())

    def get_recipe_template(self) -> str:
        """Return Jinja2 template for spec-linter recipe."""
        return """version: "1.0.0"
title: "Spec Linter — {{ project_name }}"
description: "Pre-flight spec structure and consistency validation"

instructions: |
  You are the Spec Linter for the {{ project_name }} project.

  Your responsibilities:
  1. Verify specs/prd.md exists (mandatory — block if missing)
  2. Check all spec files have required sections
  3. Cross-reference AC IDs across prd.md, arch.md, and tasks.md
  4. Validate naming conventions (kebab-case, lowercase)
  5. Detect broken relative markdown links
  6. Write a Spec Audit section to specs/arch.md

  Severity levels:
  - critical: Pipeline cannot proceed (e.g. prd.md missing)
  - high: Structural gaps that will mislead downstream agents
  - medium: Inconsistencies that reduce quality
  - low: Style and completeness suggestions

prompt: |
  Audit the specs/ folder at {{ project_root }}. Validate structure,
  required sections, AC cross-references, naming conventions, and links.
  Write findings to a "## Spec Audit" section in specs/arch.md.

extensions:
  - type: builtin
    name: developer

parameters:
  - key: feature
    input_type: string
    requirement: optional
    default: ""
    description: Feature slug to audit (empty = whole specs/ tree)

retry:
  max_retries: 1
  timeout_seconds: 120
  checks:
    - type: shell
      command: "test -f specs/prd.md"
  on_failure: "echo 'Spec linter blocked — specs/prd.md not found'"
"""


# Export for discovery
__all__ = ["SpecLinterRole"]
