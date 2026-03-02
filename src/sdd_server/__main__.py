"""Entry point for `uv run sdd-server`."""

from sdd_server.mcp.server import mcp


def main() -> None:
    """Start the SDD MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
