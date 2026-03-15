"""MCP tool: sdd_bootstrap_specs — generate SDD specs from an existing codebase.

Delegates all analysis to the Goose agent recipe (specs/recipes/spec-bootstrapper.yaml).
Python handles:
  - update_existing guard (pre-flight check before invoking Goose)
  - target_path resolution and path-traversal validation
  - max_features clamping
  - RoleCompletionEnvelope extraction from raw agent output

Architecture reference: specs/features/spec-bootstrapper/arch.md
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import Context, FastMCP

from sdd_server.core.ai_client import AIClientBridge, GooseClientBridge
from sdd_server.infrastructure.exceptions import PathTraversalError
from sdd_server.mcp.tools._utils import check_rate_limit, format_error

MAX_FEATURES = 20
_RECIPE_RELATIVE = "specs/recipes/spec-bootstrapper.yaml"

# Blocked response returned without calling Goose
_BLOCKED_RESPONSE: dict[str, Any] = {
    "status": "blocked",
    "summary": "specs already exist; pass update_existing=true to update",
    "mode": None,
    "generated": [],
    "skipped": [],
    "omitted_features": [],
    "stats": {
        "source_files_scanned": 0,
        "tests_analyzed": 0,
        "acs_generated": 0,
        "features_detected": 0,
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_context(ctx: Context | None) -> tuple[AIClientBridge, Path]:  # type: ignore[type-arg]
    """Return (ai_client, project_root) from MCP lifespan context or env fallback."""
    if ctx and hasattr(ctx, "request_context") and ctx.request_context:
        state = ctx.request_context.lifespan_context
        return state["ai_client"], state["project_root"]
    root = Path(os.getenv("SDD_PROJECT_ROOT", ".")).resolve()
    return GooseClientBridge(project_root=root), root


def _resolve_target(target_path: str, server_root: Path) -> Path:
    """Resolve target_path relative to server_root; raise PathTraversalError if unsafe."""
    raw = Path(target_path)
    candidate = (server_root / raw).resolve() if not raw.is_absolute() else raw.resolve()
    try:
        candidate.relative_to(server_root)
    except ValueError as exc:
        raise PathTraversalError(
            f"target_path '{target_path}' resolves outside the server root '{server_root}'"
        ) from exc
    return candidate


def _extract_envelope(raw_output: str) -> dict[str, Any]:
    """Scan output lines from the bottom up for the bootstrapper completion envelope."""
    for line in reversed(raw_output.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            if isinstance(data, dict) and data.get("sdd_role") == "spec-bootstrapper":
                return data
        except json.JSONDecodeError:
            continue
    return {}


def _prd_exists(project_root: Path) -> bool:
    return (project_root / "specs" / "prd.md").is_file()


def _build_response(
    client_result: Any,
    envelope: dict[str, Any],
) -> dict[str, Any]:
    """Build the final tool response from client result + parsed envelope."""
    if not client_result.success and not envelope:
        return {
            "status": "error",
            "summary": client_result.error or "Goose invocation failed",
            "mode": None,
            "generated": [],
            "skipped": [],
            "omitted_features": [],
            "stats": {
                "source_files_scanned": 0,
                "tests_analyzed": 0,
                "acs_generated": 0,
                "features_detected": 0,
            },
        }

    return {
        "status": envelope.get("status", "completed" if client_result.success else "error"),
        "summary": envelope.get("summary", ""),
        "mode": envelope.get("mode"),
        "generated": envelope.get("generated", []),
        "skipped": envelope.get("skipped", []),
        "omitted_features": envelope.get("omitted_features", []),
        "stats": envelope.get(
            "stats",
            {
                "source_files_scanned": 0,
                "tests_analyzed": 0,
                "acs_generated": 0,
                "features_detected": 0,
            },
        ),
    }


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------


def register_tools(mcp: FastMCP) -> None:
    """Register bootstrap tools on the given FastMCP instance."""

    @mcp.tool()
    async def sdd_bootstrap_specs(
        update_existing: bool = False,
        target_path: str = ".",
        max_features: int = MAX_FEATURES,
        ctx: Context | None = None,  # type: ignore[type-arg]
    ) -> dict[str, Any]:
        """Reverse-engineer an existing codebase into SDD-compliant specs.

        Invokes the spec-bootstrapper Goose recipe which surveys the source tree,
        reads package manifests, mines test names for acceptance criteria, and
        generates specs/prd.md, specs/arch.md, and specs/features/<slug>/ stubs.

        Args:
            update_existing: Extend existing specs instead of blocking. Feature
                             directories are always skipped if they already exist.
            target_path:     Path to the project to bootstrap (default: current directory).
            max_features:    Max number of feature stubs to generate (capped at 20).
        """
        if rate_err := check_rate_limit("sdd_bootstrap_specs"):
            return rate_err

        try:
            ai_client, server_root = _get_context(ctx)

            # Validate target_path
            project_root = _resolve_target(target_path, server_root)

            # Clamp max_features to 20
            max_features = min(max_features, MAX_FEATURES)

            # update_existing guard — short-circuit before touching Goose
            if not update_existing and _prd_exists(project_root):
                return dict(_BLOCKED_RESPONSE)

            recipe_path = project_root / _RECIPE_RELATIVE

            context: dict[str, Any] = {
                "update_existing": str(update_existing).lower(),
                "project_root": str(project_root),
                "max_features": max_features,
            }

            result = await ai_client.invoke_role(
                "spec-bootstrapper",
                context,
                recipe_path=recipe_path,
            )

            envelope = _extract_envelope(result.output)
            return _build_response(result, envelope)

        except PathTraversalError as exc:
            return {"status": "error", "summary": str(exc), "error": str(exc)}
        except Exception as exc:
            return format_error(exc)
