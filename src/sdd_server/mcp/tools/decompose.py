"""MCP tool: sdd_decompose_specs — decompose monolithic PRD into feature specs.

Architecture reference: specs/features/spec-decomposer/arch.md
"""

from __future__ import annotations

import os
from pathlib import Path

from mcp.server.fastmcp import Context, FastMCP

from sdd_server.core.spec_decomposer import SpecDecomposer
from sdd_server.infrastructure.filesystem import FileSystemClient
from sdd_server.mcp.tools._utils import check_rate_limit, format_error


def _get_decomposer(ctx: Context | None, project_root: Path | None = None) -> SpecDecomposer:  # type: ignore[type-arg]
    if project_root is None:
        if ctx and hasattr(ctx, "request_context") and ctx.request_context:
            state = ctx.request_context.lifespan_context
            project_root = state["project_root"]
        else:
            project_root = Path(os.getenv("SDD_PROJECT_ROOT", ".")).resolve()
    fs = FileSystemClient(project_root)
    return SpecDecomposer(project_root, fs)


def register_tools(mcp: FastMCP) -> None:
    """Register decompose tools on the given FastMCP instance."""

    @mcp.tool()
    async def sdd_decompose_specs(
        dry_run: bool = False,
        force: bool = False,
        target_feature: str | None = None,
        ctx: Context | None = None,  # type: ignore[type-arg]
    ) -> dict[str, object]:
        """Decompose root specs/prd.md into feature-scoped specs/features/<slug>/ directories.

        Detects feature boundaries from H2/H3 headings and AC-XX groupings, then
        creates prd.md, arch.md, and tasks.md stubs for each detected feature.

        Args:
            dry_run:        If True, return a preview without writing any files.
            force:          If True, overwrite existing feature directories.
            target_feature: If set, only decompose this feature (slug or heading text).
        """
        if rate_err := check_rate_limit("sdd_decompose_specs"):
            return rate_err

        try:
            decomposer = _get_decomposer(ctx)
            result = decomposer.decompose(
                dry_run=dry_run,
                force=force,
                target=target_feature,
            )
            return {
                "status": "dry_run" if dry_run else "ok",
                "features": [
                    {
                        "slug": f.slug,
                        "title": f.title,
                        "acs": f.acs,
                        "files_created": (
                            [
                                f"specs/features/{f.slug}/prd.md",
                                f"specs/features/{f.slug}/arch.md",
                                f"specs/features/{f.slug}/tasks.md",
                            ]
                            if not dry_run
                            else []
                        ),
                    }
                    for f in result.features
                ],
                "skipped": result.skipped,
                "unassigned_acs": result.unassigned_acs,
                "coverage_pct": result.coverage_pct,
                "files_created": result.files_created,
            }
        except Exception as exc:
            return format_error(exc)
