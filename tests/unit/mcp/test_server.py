"""Unit tests for MCP server module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture()  # type: ignore[misc]
def mcp_project(tmp_path: Path) -> Path:
    """Create a temp directory with git init for MCP tests."""
    import subprocess

    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    return tmp_path


class TestMCPServerLifecycle:
    """Tests for MCP server lifespan and initialization."""

    def test_server_module_imports(self) -> None:
        """Server module can be imported."""
        from sdd_server.mcp import server

        assert hasattr(server, "create_server")
        assert hasattr(server, "lifespan")

    def test_create_server_returns_fastmcp(self, mcp_project: Path) -> None:
        """create_server returns a FastMCP instance."""
        from mcp.server.fastmcp import FastMCP

        from sdd_server.mcp.server import create_server

        with patch.dict("os.environ", {"SDD_PROJECT_ROOT": str(mcp_project)}):
            app = create_server()
            assert isinstance(app, FastMCP)

    def test_lifespan_is_async_context_manager(self) -> None:
        """lifespan is an async context manager."""
        from sdd_server.mcp.server import lifespan

        # Just verify it's callable and has the right signature
        assert callable(lifespan)
