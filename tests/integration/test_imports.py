"""Tests that the full package import chain is free of circular imports.

These tests simulate what happens when the sdd-server process starts:
the __main__ module imports mcp.server, which pulls in the full import
graph.  Any circular import will raise ImportError here, catching the
class of bug that was previously invisible to unit tests.
"""

from __future__ import annotations

import importlib
import sys
from collections.abc import Generator

import pytest


@pytest.fixture()
def clean_sdd_modules() -> Generator[None]:
    """Remove sdd_server from sys.modules before the test, restore after."""
    prefix = "sdd_server"
    saved = {k: v for k, v in sys.modules.items() if k == prefix or k.startswith(prefix + ".")}
    for key in saved:
        del sys.modules[key]
    try:
        yield
    finally:
        # Remove any modules loaded during the test, then restore originals.
        to_remove = [k for k in sys.modules if k == prefix or k.startswith(prefix + ".")]
        for key in to_remove:
            del sys.modules[key]
        sys.modules.update(saved)


def test_full_package_import_no_circular(clean_sdd_modules: None) -> None:
    """Importing sdd_server top-level must not raise ImportError."""
    importlib.import_module("sdd_server")


def test_mcp_server_import_no_circular(clean_sdd_modules: None) -> None:
    """Importing sdd_server.mcp.server (the MCP entry point) must not raise."""
    importlib.import_module("sdd_server.mcp.server")


def test_plugins_before_models(clean_sdd_modules: None) -> None:
    """plugins.base imported before models must not raise (the original bug).

    Reproduces the exact sequence from the server startup traceback:
    goose_session → plugins.base → models.base → models.__init__ → custom_plugin
    """
    importlib.import_module("sdd_server.plugins.base")
    importlib.import_module("sdd_server.models.custom_plugin")
