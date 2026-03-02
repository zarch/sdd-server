"""Unit tests for GitClient."""

import stat
from pathlib import Path

import pytest

from sdd_server.infrastructure.exceptions import GitError
from sdd_server.infrastructure.git import PRE_COMMIT_HOOK_CONTENT, GitClient


def test_is_repo_true(tmp_project: Path) -> None:
    git = GitClient(tmp_project)
    assert git.is_repo() is True


def test_is_repo_false(tmp_path: Path) -> None:
    git = GitClient(tmp_path)
    assert git.is_repo() is False


def test_install_hook(tmp_project: Path) -> None:
    git = GitClient(tmp_project)
    git.install_hook("pre-commit")
    hook = tmp_project / ".git" / "hooks" / "pre-commit"
    assert hook.exists()
    assert hook.read_text() == PRE_COMMIT_HOOK_CONTENT
    assert hook.stat().st_mode & stat.S_IXUSR


def test_is_hook_installed_false(tmp_project: Path) -> None:
    git = GitClient(tmp_project)
    assert git.is_hook_installed("pre-commit") is False


def test_is_hook_installed_true(tmp_project: Path) -> None:
    git = GitClient(tmp_project)
    git.install_hook("pre-commit")
    assert git.is_hook_installed("pre-commit") is True


def test_get_user_name(tmp_project: Path) -> None:
    git = GitClient(tmp_project)
    name = git.get_user_name()
    assert isinstance(name, str)
    assert len(name) > 0


def test_git_error_on_bad_command(tmp_project: Path) -> None:
    git = GitClient(tmp_project)
    with pytest.raises(GitError):
        git._run(["nonexistent-subcommand-xyz"])
