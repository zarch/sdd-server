"""MCP resources for specs."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from sdd_server.core.spec_manager import SpecManager
from sdd_server.infrastructure.exceptions import SpecNotFoundError
from sdd_server.models.spec import SpecType


def _get_spec_manager() -> SpecManager:
    import os
    from pathlib import Path

    root = Path(os.getenv("SDD_PROJECT_ROOT", ".")).resolve()
    return SpecManager(root)


def register_resources(mcp: FastMCP) -> None:
    """Register spec resources on the given FastMCP instance."""

    @mcp.resource("sdd://specs/{spec_type}")
    async def read_spec(spec_type: str) -> str:
        """Read a root-level spec file by type."""
        try:
            stype = SpecType(spec_type)
        except ValueError:
            return f"Unknown spec type: {spec_type}"
        mgr = _get_spec_manager()
        try:
            content: str = mgr.read_spec(stype)
            return content
        except SpecNotFoundError:
            return f"Spec not found: {spec_type}"

    @mcp.resource("sdd://specs/features/{feature}/{spec_type}")
    async def read_feature_spec(feature: str, spec_type: str) -> str:
        """Read a feature-level spec file."""
        try:
            stype = SpecType(spec_type)
        except ValueError:
            return f"Unknown spec type: {spec_type}"
        mgr = _get_spec_manager()
        try:
            content: str = mgr.read_spec(stype, feature)
            return content
        except SpecNotFoundError:
            return f"Spec not found: {feature}/{spec_type}"
