"""Unit tests for __main__ module."""

from __future__ import annotations


def test_main_module_imports() -> None:
    """__main__ module can be imported."""
    # Just verify the module structure exists
    from sdd_server import __main__

    assert hasattr(__main__, "main")


def test_main_module_has_main_function() -> None:
    """__main__ module has a main function."""
    from sdd_server.__main__ import main

    assert callable(main)
