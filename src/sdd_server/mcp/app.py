"""Central FastMCP application instance."""

from mcp.server.fastmcp import FastMCP

mcp: FastMCP = FastMCP("sdd-server", version="0.1.0")
