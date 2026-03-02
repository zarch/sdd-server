"""Shared test fixtures."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from sdd_server.core.metadata import MetadataManager
from sdd_server.core.spec_manager import SpecManager


@pytest.fixture()
def tmp_project(tmp_path: Path) -> Path:
    """Create a temp directory with git init."""
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


@pytest.fixture()
def spec_manager(tmp_project: Path) -> SpecManager:
    """Return a SpecManager pointing at tmp_project."""
    return SpecManager(tmp_project)


@pytest.fixture()
def metadata_manager(tmp_project: Path) -> MetadataManager:
    """Return a MetadataManager pointing at tmp_project."""
    return MetadataManager(tmp_project)
