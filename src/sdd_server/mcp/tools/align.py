"""MCP tool: sdd_alignment_check — LLM-based spec-code alignment verification.

Architecture reference: arch.md Section 5.4
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import Context, FastMCP

from sdd_server.utils.logging import get_logger

logger = get_logger(__name__)


def _get_project_root() -> Path:
    return Path(os.getenv("SDD_PROJECT_ROOT", ".")).resolve()


def register_tools(mcp: FastMCP) -> None:
    """Register alignment tools on the given FastMCP instance."""

    @mcp.tool()
    async def sdd_alignment_check(
        scope: str = "all",
        ctx: Context | None = None,  # type: ignore[type-arg]
    ) -> dict[str, Any]:
        """Check spec-code alignment using LLM semantic analysis.

        Reads the relevant spec sections (prd.md / arch.md), collects the
        current git diff, and asks the configured AI client (Goose by default)
        to identify any misalignment between specs and code changes.

        The check is language-agnostic — it detects semantic misalignment
        (wrong behaviour, missing requirement coverage) rather than syntactic
        issues.

        Args:
            scope: What to check:
                - ``"all"``             — whole project (default)
                - ``"feature:<name>"``  — a specific feature
                - ``"file:<path>"``     — focused on a single source file

        Returns:
            overall_status: "aligned" | "diverged" | "missing_spec" | "missing_code"
            issues: List of alignment issues with file, spec_ref, severity, description
            summary: Count of issues by status
            ai_available: Whether the AI client (Goose) was reachable
        """
        project_root = _get_project_root()

        # --- Resolve dependencies from lifespan context or build fresh ---
        if ctx is not None:
            lc = ctx.request_context.lifespan_context
            spec_manager = lc["spec_manager"]
            git_client = lc["git_client"]
        else:
            from sdd_server.core.spec_manager import SpecManager
            from sdd_server.infrastructure.git import GitClient

            spec_manager = SpecManager(project_root)
            git_client = GitClient(project_root)

        # Build AI client
        from sdd_server.core.ai_client import GooseClientBridge
        from sdd_server.core.alignment import AlignmentChecker

        ai_client = GooseClientBridge(project_root=project_root)
        ai_available = ai_client.is_available

        checker = AlignmentChecker(
            spec_manager=spec_manager,
            ai_client=ai_client,
            project_root=project_root,
            git_client=git_client,
        )

        if not ai_available:
            logger.warning("Goose CLI not found; alignment check skipped")
            return {
                "overall_status": "unknown",
                "issues": [],
                "summary": {},
                "ai_available": False,
                "message": (
                    "Goose CLI is not installed or not on PATH. "
                    "Install Goose and ensure it is accessible to run alignment checks."
                ),
            }

        logger.info("Running alignment check", scope=scope)
        report = await checker.check_alignment(scope=scope)

        return {
            "overall_status": report.overall_status.value,
            "issues": [
                {
                    "file": issue.file,
                    "spec_ref": issue.spec_ref,
                    "status": issue.status.value,
                    "description": issue.description,
                    "suggested_action": issue.suggested_action,
                    "severity": issue.severity,
                }
                for issue in report.issues
            ],
            "summary": report.summary,
            "ai_available": True,
        }

    @mcp.tool()
    async def sdd_task_completion_check(
        task_id: str,
        ctx: Context | None = None,  # type: ignore[type-arg]
    ) -> dict[str, Any]:
        """Ask the AI client whether a specific task has been completed.

        Uses LLM semantic analysis to evaluate whether the code changes
        in the repository satisfy the requirements described in the task.

        Args:
            task_id: Task identifier (e.g. "t0000060")

        Returns:
            completed: Whether the task appears to be complete
            gaps: List of identified gaps or missing items
            ai_available: Whether the AI client was reachable
        """
        project_root = _get_project_root()

        if ctx is not None:
            lc = ctx.request_context.lifespan_context
            spec_manager = lc["spec_manager"]
            git_client = lc["git_client"]
        else:
            from sdd_server.core.spec_manager import SpecManager
            from sdd_server.infrastructure.git import GitClient

            spec_manager = SpecManager(project_root)
            git_client = GitClient(project_root)

        from sdd_server.core.ai_client import GooseClientBridge
        from sdd_server.core.alignment import AlignmentChecker

        ai_client = GooseClientBridge(project_root=project_root)
        if not ai_client.is_available:
            return {
                "completed": False,
                "gaps": ["Goose CLI not available"],
                "ai_available": False,
            }

        checker = AlignmentChecker(
            spec_manager=spec_manager,
            ai_client=ai_client,
            project_root=project_root,
            git_client=git_client,
        )

        completed, gaps = await checker.check_task_completion(task_id)

        return {
            "task_id": task_id,
            "completed": completed,
            "gaps": gaps,
            "ai_available": True,
        }
