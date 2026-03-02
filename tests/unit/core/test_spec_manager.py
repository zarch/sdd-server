"""Unit tests for SpecManager."""

from pathlib import Path

import pytest

from sdd_server.core.spec_manager import SpecManager
from sdd_server.infrastructure.exceptions import SpecNotFoundError, ValidationError
from sdd_server.models.spec import SpecType


def test_read_missing_spec_raises(spec_manager: SpecManager) -> None:
    with pytest.raises(SpecNotFoundError):
        spec_manager.read_spec(SpecType.PRD)


def test_write_and_read_spec(spec_manager: SpecManager, tmp_project: Path) -> None:
    (tmp_project / "specs").mkdir(exist_ok=True)
    spec_manager.write_spec(SpecType.PRD, "# My PRD")
    content = spec_manager.read_spec(SpecType.PRD)
    assert "# My PRD" in content


def test_write_append_mode(spec_manager: SpecManager, tmp_project: Path) -> None:
    (tmp_project / "specs").mkdir(exist_ok=True)
    spec_manager.write_spec(SpecType.PRD, "# Part 1\n")
    spec_manager.write_spec(SpecType.PRD, "## Part 2\n", mode="append")
    content = spec_manager.read_spec(SpecType.PRD)
    assert "# Part 1" in content
    assert "## Part 2" in content


def test_write_invalid_mode(spec_manager: SpecManager, tmp_project: Path) -> None:
    (tmp_project / "specs").mkdir(exist_ok=True)
    with pytest.raises(ValidationError, match="Invalid write mode"):
        spec_manager.write_spec(SpecType.PRD, "content", mode="invalid")


def test_create_feature(spec_manager: SpecManager, tmp_project: Path) -> None:
    (tmp_project / "specs").mkdir(exist_ok=True)
    feature_dir = spec_manager.create_feature("my-feature", "Test feature")
    assert feature_dir.is_dir()
    assert (feature_dir / "prd.md").exists()
    assert (feature_dir / "arch.md").exists()
    assert (feature_dir / "tasks.md").exists()


def test_create_feature_invalid_name(spec_manager: SpecManager, tmp_project: Path) -> None:
    (tmp_project / "specs").mkdir(exist_ok=True)
    with pytest.raises(ValidationError, match="Invalid feature name"):
        spec_manager.create_feature("My Feature!")


def test_create_feature_duplicate(spec_manager: SpecManager, tmp_project: Path) -> None:
    (tmp_project / "specs").mkdir(exist_ok=True)
    spec_manager.create_feature("feat-a")
    with pytest.raises(ValidationError, match="already exists"):
        spec_manager.create_feature("feat-a")


def test_list_features(spec_manager: SpecManager, tmp_project: Path) -> None:
    (tmp_project / "specs").mkdir(exist_ok=True)
    spec_manager.create_feature("alpha")
    spec_manager.create_feature("beta")
    features = spec_manager.list_features()
    assert "alpha" in features
    assert "beta" in features


def test_validate_structure_missing(spec_manager: SpecManager, tmp_project: Path) -> None:
    (tmp_project / "specs").mkdir(exist_ok=True)
    issues = spec_manager.validate_structure()
    assert len(issues) == 3  # prd, arch, tasks all missing


def test_validate_structure_ok(spec_manager: SpecManager, tmp_project: Path) -> None:
    (tmp_project / "specs").mkdir(exist_ok=True)
    spec_manager.write_spec(SpecType.PRD, "# PRD")
    spec_manager.write_spec(SpecType.ARCH, "# Arch")
    spec_manager.write_spec(SpecType.TASKS, "# Tasks")
    issues = spec_manager.validate_structure()
    assert issues == []
