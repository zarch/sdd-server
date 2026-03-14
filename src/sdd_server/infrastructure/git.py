"""Git client for repository operations."""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

from sdd_server.infrastructure.exceptions import GitError

PRE_COMMIT_HOOK_CONTENT = """\
#!/bin/sh
# SDD pre-commit enforcement hook — installed by 'sdd init'. Do not edit manually.
set -e

echo "SDD: Running preflight checks..."
sdd preflight --hook-mode
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "SDD: Commit blocked. Fix the violations above, then:"
    echo "  sdd bypass --reason \\"<your reason>\\"  # bypass for 24 h"
    echo "  sdd preflight                           # re-check status"
    exit 1
fi
"""


class GitClient:
    """Thin wrapper around git CLI for SDD needs."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()

    def _run(self, args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                ["git", *args],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=check,
            )
        except subprocess.CalledProcessError as exc:
            raise GitError(f"git {' '.join(args)} failed: {exc.stderr.strip()}") from exc
        except FileNotFoundError as exc:
            raise GitError("git executable not found") from exc

    def is_repo(self) -> bool:
        """Return True if project_root is inside a git repository."""
        result = self._run(["rev-parse", "--git-dir"], check=False)
        return result.returncode == 0

    def _hook_path(self, hook_name: str) -> Path:
        return self.project_root / ".git" / "hooks" / hook_name

    def is_hook_installed(self, hook_name: str = "pre-commit") -> bool:
        """Return True if the named hook file exists and is executable."""
        hook = self._hook_path(hook_name)
        return hook.exists() and os.access(hook, os.X_OK)

    def install_hook(
        self, hook_name: str = "pre-commit", content: str = PRE_COMMIT_HOOK_CONTENT
    ) -> None:
        """Write hook file and make it executable (chmod 755)."""
        hook = self._hook_path(hook_name)
        hook.parent.mkdir(parents=True, exist_ok=True)
        hook.write_text(content, encoding="utf-8")
        hook.chmod(stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)

    def get_user_name(self) -> str:
        """Return the git user.name config value."""
        result = self._run(["config", "user.name"], check=False)
        return result.stdout.strip() if result.returncode == 0 else "unknown"

    def get_diff(self, paths: list[str] | None = None) -> str:
        """Return the git diff (staged + unstaged) for the working tree.

        Args:
            paths: Optional list of file paths to restrict the diff to.

        Returns:
            Diff string, or empty string if repository is clean.
        """
        args = ["diff", "HEAD"]
        if paths:
            args += ["--", *paths]
        result = self._run(args, check=False)
        return result.stdout if result.returncode == 0 else ""
