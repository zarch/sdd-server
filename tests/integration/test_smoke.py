"""Integration smoke test for the full SDD init → read → status flow."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from sdd_server.core.initializer import ProjectInitializer
from sdd_server.core.metadata import MetadataManager
from sdd_server.core.spec_manager import SpecManager
from sdd_server.infrastructure.git import GitClient
from sdd_server.models.spec import SpecType
from sdd_server.models.state import WorkflowState


@pytest.fixture()
def initialized_project(tmp_path: Path) -> Path:
    """Create a temp git repo and run sdd_init on it."""
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

    git_client = GitClient(tmp_path)
    spec_manager = SpecManager(tmp_path)
    initializer = ProjectInitializer(tmp_path, spec_manager, git_client)
    initializer.init_new_project("smoke-test", "Integration test project")
    return tmp_path


def test_prd_exists(initialized_project: Path) -> None:
    """specs/prd.md should exist after sdd_init."""
    assert (initialized_project / "specs" / "prd.md").exists()


def test_arch_exists(initialized_project: Path) -> None:
    """specs/arch.md should exist after sdd_init."""
    assert (initialized_project / "specs" / "arch.md").exists()


def test_tasks_exists(initialized_project: Path) -> None:
    """specs/tasks.md should exist after sdd_init."""
    assert (initialized_project / "specs" / "tasks.md").exists()


def test_spec_read_returns_content(initialized_project: Path) -> None:
    """sdd_spec_read should return non-empty content for prd."""
    mgr = SpecManager(initialized_project)
    content = mgr.read_spec(SpecType.PRD)
    assert len(content) > 0
    assert "smoke-test" in content


def test_status_returns_uninitialized(initialized_project: Path) -> None:
    """Project root feature state should be uninitialized after plain init."""
    metadata = MetadataManager(initialized_project)
    state = metadata.load()
    assert state.workflow_state == WorkflowState.UNINITIALIZED


def test_spec_list_shows_files(initialized_project: Path) -> None:
    """validate_structure should pass after init."""
    mgr = SpecManager(initialized_project)
    issues = mgr.validate_structure()
    assert issues == [], f"Unexpected issues: {issues}"


def test_feature_create_and_list(initialized_project: Path) -> None:
    """Creating a feature should make it appear in list_features."""
    mgr = SpecManager(initialized_project)
    mgr.create_feature("auth", "Authentication feature")
    features = mgr.list_features()
    assert "auth" in features


def test_pre_commit_hook_installed(initialized_project: Path) -> None:
    """sdd_init should install the pre-commit hook."""
    git = GitClient(initialized_project)
    assert git.is_hook_installed("pre-commit")
