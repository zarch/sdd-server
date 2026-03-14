"""MCP tool: sdd_health_check — reports health status of all registered subsystems."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from sdd_server.infrastructure.observability.health import health_check_registry


def register_tools(mcp: FastMCP) -> None:
    """Register health tools on the given FastMCP instance."""

    @mcp.tool()
    async def sdd_health_check() -> dict[str, object]:
        """Return health status of the SDD server and its subsystems."""
        report = health_check_registry.create_report()
        return {
            "status": report["status"],
            "checks": [
                {"name": c["name"], "status": c["status"], "message": c["message"]}
                for c in report["checks"]
            ],
        }
