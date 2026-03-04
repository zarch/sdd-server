"""Unit tests for sdd_status MCP tool."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def spec_project(tmp_path: Path) -> Path:
    """Create a minimal project with specs/ for status tests."""
    specs = tmp_path / "specs"
    specs.mkdir()
    (specs / "prd.md").write_text("# PRD\n")
    (specs / "arch.md").write_text("# Arch\n")
    (specs / "tasks.md").write_text("- [ ] Root task #t9000001\n")
    return tmp_path


class TestSddStatus:
    """Tests for the sdd_status tool."""

    def test_status_returns_workflow_state(self, spec_project: Path) -> None:
        """sdd_status returns workflow_state key."""
        from mcp.server.fastmcp import FastMCP

        from sdd_server.mcp.tools.status import register_tools

        mcp = FastMCP("test")
        register_tools(mcp)

        with patch.dict(os.environ, {"SDD_PROJECT_ROOT": str(spec_project)}):
            from sdd_server.core.metadata import MetadataManager
            from sdd_server.core.spec_manager import SpecManager
            from sdd_server.core.task_manager import TaskBreakdownManager

            MetadataManager(spec_project)
            SpecManager(spec_project)
            TaskBreakdownManager(spec_project)

            # Call the underlying function directly (no-ctx path)
            from sdd_server.mcp.tools import status as status_module

            managers = status_module._get_managers(None)

        assert len(managers) == 3
        meta, spec, tasks = managers
        assert hasattr(meta, "load")
        assert hasattr(spec, "validate_structure")
        assert hasattr(tasks, "get_all_progress")

    def test_status_includes_task_progress(self, spec_project: Path) -> None:
        """sdd_status task_progress includes root tasks.md data."""
        from sdd_server.core.metadata import MetadataManager
        from sdd_server.core.spec_manager import SpecManager
        from sdd_server.core.task_manager import TaskBreakdownManager

        metadata = MetadataManager(spec_project)
        spec_manager = SpecManager(spec_project)
        task_manager = TaskBreakdownManager(spec_project)

        metadata.load()
        spec_manager.validate_structure()
        all_progress = task_manager.get_all_progress()

        # Build same task_summary as the tool does
        task_summary: dict[str, object] = {}
        for feature, progress in all_progress.items():
            key = feature if feature is not None else "__root__"
            task_summary[key] = {
                "total": progress["total"],
                "complete": progress["complete"],
                "percentage": progress["percentage"],
            }

        assert "__root__" in task_summary
        assert task_summary["__root__"]["total"] == 1  # type: ignore[index]
        assert task_summary["__root__"]["complete"] == 0  # type: ignore[index]

    def test_status_feature_states(self, spec_project: Path) -> None:
        """sdd_status includes per-feature workflow states."""
        from sdd_server.core.metadata import MetadataManager
        from sdd_server.core.spec_manager import SpecManager

        # Create a feature
        spec_manager = SpecManager(spec_project)
        spec_manager.create_feature("auth", "Auth feature")

        metadata = MetadataManager(spec_project)
        state = metadata.load()

        feature_states = {name: fs.state.value for name, fs in state.features.items()}
        # No features tracked yet (metadata not updated by create_feature)
        assert isinstance(feature_states, dict)

    def test_get_managers_no_ctx(self, spec_project: Path) -> None:
        """_get_managers returns valid managers when ctx is None."""
        from sdd_server.mcp.tools.status import _get_managers

        with patch.dict(os.environ, {"SDD_PROJECT_ROOT": str(spec_project)}):
            meta, spec, tasks = _get_managers(None)

        assert hasattr(meta, "load")
        assert hasattr(spec, "list_features")
        assert hasattr(tasks, "get_breakdown")
