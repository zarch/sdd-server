"""Unit tests for ProjectInitializer."""

from pathlib import Path

from sdd_server.core.initializer import ProjectInitializer
from sdd_server.core.metadata import MetadataManager
from sdd_server.core.spec_manager import SpecManager
from sdd_server.infrastructure.git import GitClient
from sdd_server.models.state import WorkflowState


def test_init_new_project_creates_specs(tmp_project: Path) -> None:
    git = GitClient(tmp_project)
    sm = SpecManager(tmp_project)
    init = ProjectInitializer(tmp_project, sm, git)
    init.init_new_project("test-proj", "A test project")

    assert (tmp_project / "specs" / "prd.md").exists()
    assert (tmp_project / "specs" / "arch.md").exists()
    assert (tmp_project / "specs" / "tasks.md").exists()
    assert (tmp_project / "specs" / ".context-hints").exists()
    assert (tmp_project / "specs" / ".metadata.json").exists()


def test_init_new_project_installs_hook(tmp_project: Path) -> None:
    git = GitClient(tmp_project)
    sm = SpecManager(tmp_project)
    init = ProjectInitializer(tmp_project, sm, git)
    init.init_new_project("hook-test")
    assert git.is_hook_installed("pre-commit")


def test_init_new_project_metadata(tmp_project: Path) -> None:
    git = GitClient(tmp_project)
    sm = SpecManager(tmp_project)
    init = ProjectInitializer(tmp_project, sm, git)
    init.init_new_project("meta-proj", "desc")

    meta = MetadataManager(tmp_project)
    state = meta.load()
    assert "__root__" in state.features
    assert state.features["__root__"].state == WorkflowState.UNINITIALIZED
    assert state.metadata.get("project_name") == "meta-proj"


def test_init_existing_project_preserves_existing(tmp_project: Path) -> None:
    git = GitClient(tmp_project)
    sm = SpecManager(tmp_project)
    init = ProjectInitializer(tmp_project, sm, git)

    # Create existing PRD
    (tmp_project / "specs").mkdir(exist_ok=True)
    (tmp_project / "specs" / "prd.md").write_text("# Existing PRD")

    init.init_existing_project()

    # Existing PRD should be preserved
    assert (tmp_project / "specs" / "prd.md").read_text() == "# Existing PRD"
    # Missing files should be created
    assert (tmp_project / "specs" / "arch.md").exists()
    assert (tmp_project / "specs" / "tasks.md").exists()
