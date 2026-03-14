"""Unit tests for FileSystemClient."""

from pathlib import Path

import pytest

from sdd_server.infrastructure.exceptions import PathTraversalError
from sdd_server.infrastructure.filesystem import FileSystemClient


def test_write_and_read_file(tmp_path: Path) -> None:
    fs = FileSystemClient(tmp_path)
    target = tmp_path / "hello.txt"
    fs.write_file(target, "hello world")
    assert fs.read_file(target) == "hello world"


def test_atomic_write_creates_file(tmp_path: Path) -> None:
    fs = FileSystemClient(tmp_path)
    path = tmp_path / "subdir" / "file.txt"
    fs.write_file(path, "content")
    assert path.read_text() == "content"


def test_path_traversal_blocked(tmp_path: Path) -> None:
    fs = FileSystemClient(tmp_path)
    evil_path = tmp_path / ".." / "outside.txt"
    with pytest.raises(PathTraversalError):
        fs._validate_path(evil_path)


def test_file_exists(tmp_path: Path) -> None:
    fs = FileSystemClient(tmp_path)
    p = tmp_path / "exists.txt"
    assert not fs.file_exists(p)
    fs.write_file(p, "data")
    assert fs.file_exists(p)


def test_ensure_directory(tmp_path: Path) -> None:
    fs = FileSystemClient(tmp_path)
    new_dir = tmp_path / "a" / "b" / "c"
    result = fs.ensure_directory(new_dir)
    assert result.is_dir()


def test_list_directory(tmp_path: Path) -> None:
    fs = FileSystemClient(tmp_path)
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.txt").write_text("b")
    items = fs.list_directory(tmp_path)
    names = [p.name for p in items]
    assert "a.txt" in names
    assert "b.txt" in names


def test_write_file_has_retry_decorator(tmp_path: Path) -> None:
    """write_file should be wrapped with retry_on_file_lock."""
    from sdd_server.infrastructure.filesystem import FileSystemClient

    fs = FileSystemClient(tmp_path)
    # The decorator wraps the original; __wrapped__ is set by functools.wraps
    assert hasattr(fs.write_file, "__wrapped__"), "write_file should be decorated with retry"


def test_write_file_retries_on_oserror(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """write_file retries transient OSErrors before succeeding."""
    import os

    call_count = 0
    original_replace = os.replace

    def flaky_replace(src: str, dst: str) -> None:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise OSError("resource temporarily unavailable")
        original_replace(src, dst)

    monkeypatch.setattr(os, "replace", flaky_replace)

    fs = FileSystemClient(tmp_path)
    target = tmp_path / "retry_test.txt"
    fs.write_file(target, "data")
    assert target.read_text() == "data"
    assert call_count == 3
