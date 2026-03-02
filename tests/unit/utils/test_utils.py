"""Unit tests for utility modules."""

from pathlib import Path

from sdd_server.utils.fs import atomic_write, ensure_directory
from sdd_server.utils.logging import configure_logging, get_logger
from sdd_server.utils.paths import SpecsPaths

# ── fs.py ──────────────────────────────────────────────────────────────────────


def test_atomic_write_creates_file(tmp_path: Path) -> None:
    target = tmp_path / "out.txt"
    atomic_write(target, "hello")
    assert target.read_text() == "hello"


def test_atomic_write_creates_parent_dirs(tmp_path: Path) -> None:
    target = tmp_path / "a" / "b" / "out.txt"
    atomic_write(target, "nested")
    assert target.read_text() == "nested"


def test_atomic_write_overwrites_existing(tmp_path: Path) -> None:
    target = tmp_path / "out.txt"
    atomic_write(target, "first")
    atomic_write(target, "second")
    assert target.read_text() == "second"


def test_ensure_directory_creates(tmp_path: Path) -> None:
    new_dir = tmp_path / "x" / "y"
    result = ensure_directory(new_dir)
    assert result.is_dir()
    assert result == new_dir


def test_ensure_directory_idempotent(tmp_path: Path) -> None:
    d = tmp_path / "dir"
    ensure_directory(d)
    ensure_directory(d)  # no error
    assert d.is_dir()


# ── paths.py ───────────────────────────────────────────────────────────────────


def test_specs_paths_properties(tmp_path: Path) -> None:
    paths = SpecsPaths(tmp_path)
    assert paths.specs_dir == tmp_path / "specs"
    assert paths.prd_path == tmp_path / "specs" / "prd.md"
    assert paths.arch_path == tmp_path / "specs" / "arch.md"
    assert paths.tasks_path == tmp_path / "specs" / "tasks.md"
    assert paths.metadata_path == tmp_path / "specs" / ".metadata.json"
    assert paths.context_hints_path == tmp_path / "specs" / ".context-hints"
    assert paths.recipes_dir == tmp_path / "recipes"


def test_specs_paths_custom_specs_dir(tmp_path: Path) -> None:
    paths = SpecsPaths(tmp_path, specs_dir="my-specs")
    assert paths.specs_dir == tmp_path / "my-specs"


def test_specs_paths_feature_paths(tmp_path: Path) -> None:
    paths = SpecsPaths(tmp_path)
    assert paths.feature_dir("auth") == tmp_path / "specs" / "auth"
    assert paths.feature_prd("auth") == tmp_path / "specs" / "auth" / "prd.md"
    assert paths.feature_arch("auth") == tmp_path / "specs" / "auth" / "arch.md"
    assert paths.feature_tasks("auth") == tmp_path / "specs" / "auth" / "tasks.md"
    assert paths.feature_context_hints("auth") == tmp_path / "specs" / "auth" / ".context-hints"


# ── logging.py ─────────────────────────────────────────────────────────────────


def test_configure_logging_does_not_raise() -> None:
    configure_logging(level="DEBUG", json_output=False)
    configure_logging(level="INFO", json_output=True)


def test_get_logger_returns_logger() -> None:
    logger = get_logger("test.module")
    assert logger is not None
