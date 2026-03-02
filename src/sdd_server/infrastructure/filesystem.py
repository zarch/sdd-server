"""Filesystem client with path-traversal protection and atomic writes."""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path

from sdd_server.infrastructure.exceptions import FileSystemError, PathTraversalError


class FileSystemClient:
    """Safe filesystem operations constrained to an allowed root directory."""

    def __init__(self, allowed_root: Path) -> None:
        self.allowed_root = allowed_root.resolve()

    def _validate_path(self, path: Path) -> Path:
        """Resolve path and raise PathTraversalError if outside allowed_root."""
        resolved = (
            (self.allowed_root / path).resolve() if not path.is_absolute() else path.resolve()
        )
        try:
            resolved.relative_to(self.allowed_root)
        except ValueError as exc:
            raise PathTraversalError(
                f"Path '{path}' resolves to '{resolved}' which is outside "
                f"the allowed root '{self.allowed_root}'"
            ) from exc
        return resolved

    def read_file(self, path: Path) -> str:
        """Read a text file and return its contents."""
        safe_path = self._validate_path(path)
        try:
            return safe_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise FileSystemError(f"Cannot read '{safe_path}': {exc}") from exc

    def write_file(self, path: Path, content: str) -> None:
        """Atomically write content to a file (tempfile + replace)."""
        safe_path = self._validate_path(path)
        safe_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_fd, tmp_path = tempfile.mkstemp(dir=safe_path.parent, prefix=".sdd_tmp_")
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp_path, safe_path)
        except OSError as exc:
            with contextlib.suppress(OSError):
                os.unlink(tmp_path)
            raise FileSystemError(f"Cannot write '{safe_path}': {exc}") from exc

    def ensure_directory(self, path: Path) -> Path:
        """Create directory and all parents; return the resolved path."""
        safe_path = self._validate_path(path)
        safe_path.mkdir(parents=True, exist_ok=True)
        return safe_path

    def file_exists(self, path: Path) -> bool:
        """Return True if the path exists and is a file."""
        try:
            safe_path = self._validate_path(path)
        except PathTraversalError:
            return False
        return safe_path.is_file()

    def directory_exists(self, path: Path) -> bool:
        """Return True if the path exists and is a directory."""
        try:
            safe_path = self._validate_path(path)
        except PathTraversalError:
            return False
        return safe_path.is_dir()

    def list_directory(self, path: Path) -> list[Path]:
        """Return a sorted list of items inside a directory."""
        safe_path = self._validate_path(path)
        if not safe_path.is_dir():
            raise FileSystemError(f"'{safe_path}' is not a directory")
        return sorted(safe_path.iterdir())
