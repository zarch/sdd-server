"""Unit tests for StartupValidator."""

from pathlib import Path

import pytest

from sdd_server.core.startup import StartupValidator
from sdd_server.infrastructure.exceptions import SDDError


def test_python_version_check(tmp_project: Path) -> None:
    validator = StartupValidator(tmp_project)
    result = validator._check_python_version()
    # We're running on 3.14+ per the project requirement
    assert result.fatal is True
    assert result.passed is True


def test_specs_dir_check_missing(tmp_project: Path) -> None:
    validator = StartupValidator(tmp_project)
    result = validator._check_specs_dir()
    assert result.fatal is True
    assert result.passed is False


def test_specs_dir_check_present(tmp_project: Path) -> None:
    (tmp_project / "specs").mkdir()
    validator = StartupValidator(tmp_project)
    result = validator._check_specs_dir()
    assert result.passed is True


def test_recipes_dir_auto_created(tmp_project: Path) -> None:
    validator = StartupValidator(tmp_project)
    result = validator._check_recipes_dir()
    assert result.passed is True
    assert result.fatal is False
    assert (tmp_project / "specs" / "recipes").is_dir()


def test_git_repo_check(tmp_project: Path) -> None:
    validator = StartupValidator(tmp_project)
    result = validator._check_git_repo()
    assert result.passed is True
    assert result.fatal is True


def test_git_repo_check_not_repo(tmp_path: Path) -> None:
    validator = StartupValidator(tmp_path)
    result = validator._check_git_repo()
    assert result.passed is False


def test_pre_commit_hook_missing(tmp_project: Path) -> None:
    validator = StartupValidator(tmp_project)
    result = validator._check_pre_commit_hook()
    assert result.fatal is False
    assert result.passed is False


def test_assert_ready_raises_on_missing_specs(tmp_project: Path) -> None:
    validator = StartupValidator(tmp_project)
    with pytest.raises(SDDError, match="Startup validation failed"):
        validator.assert_ready()
