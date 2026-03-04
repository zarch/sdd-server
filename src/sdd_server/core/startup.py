"""Server startup validation."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from sdd_server.infrastructure.exceptions import SDDError
from sdd_server.infrastructure.git import GitClient
from sdd_server.utils.paths import SpecsPaths


@dataclass
class CheckResult:
    """Result of a single startup check."""

    name: str
    passed: bool
    fatal: bool
    message: str


@dataclass
class StartupReport:
    """Collection of startup check results."""

    checks: list[CheckResult] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(c.passed for c in self.checks)

    @property
    def fatal_failures(self) -> list[CheckResult]:
        return [c for c in self.checks if not c.passed and c.fatal]

    @property
    def warnings(self) -> list[CheckResult]:
        return [c for c in self.checks if not c.passed and not c.fatal]


class StartupValidator:
    """Runs pre-flight checks when the MCP server starts."""

    def __init__(self, project_root: Path, specs_dir: str = "specs") -> None:
        self.project_root = project_root.resolve()
        self._paths = SpecsPaths(self.project_root, specs_dir)
        self._git = GitClient(self.project_root)

    def run(self) -> StartupReport:
        """Run all startup checks and return a report."""
        report = StartupReport()
        report.checks.append(self._check_python_version())
        report.checks.append(self._check_specs_dir())
        report.checks.append(self._check_recipes_dir())
        report.checks.append(self._check_git_repo())
        report.checks.append(self._check_pre_commit_hook())
        return report

    def assert_ready(self, report: StartupReport | None = None) -> None:
        """Raise SDDError if any fatal check failed."""
        if report is None:
            report = self.run()
        if report.fatal_failures:
            msgs = "; ".join(c.message for c in report.fatal_failures)
            raise SDDError(f"Startup validation failed: {msgs}")

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def _check_python_version(self) -> CheckResult:
        ok = sys.version_info >= (3, 14)
        return CheckResult(
            name="python_version",
            passed=ok,
            fatal=True,
            message=(
                f"Python >= 3.14 required, got {sys.version_info.major}.{sys.version_info.minor}"
                if not ok
                else f"Python {sys.version_info.major}.{sys.version_info.minor} OK"
            ),
        )

    def _check_specs_dir(self) -> CheckResult:
        specs = self._paths.specs_dir
        exists = specs.is_dir()
        writable = exists and os.access(specs, os.W_OK)
        ok = exists and bool(writable)
        return CheckResult(
            name="specs_dir",
            passed=ok,
            fatal=True,
            message=(
                f"specs/ directory found and writable at '{specs}'"
                if ok
                else f"specs/ directory missing or not writable at '{specs}'"
            ),
        )

    def _check_recipes_dir(self) -> CheckResult:
        recipes = self._paths.recipes_dir
        exists = recipes.is_dir()
        return CheckResult(
            name="recipes_dir",
            passed=True,  # non-fatal: recipes/ is created on sdd init
            fatal=False,
            message=(
                f"recipes/ directory found at '{recipes}'"
                if exists
                else f"recipes/ directory absent at '{recipes}' — run 'sdd init' to create it"
            ),
        )

    def _check_git_repo(self) -> CheckResult:
        ok = self._git.is_repo()
        return CheckResult(
            name="git_repo",
            passed=ok,
            fatal=True,
            message=(
                "Git repository detected"
                if ok
                else f"'{self.project_root}' is not inside a git repository"
            ),
        )

    def _check_pre_commit_hook(self) -> CheckResult:
        ok = self._git.is_hook_installed("pre-commit")
        return CheckResult(
            name="pre_commit_hook",
            passed=ok,
            fatal=False,
            message=(
                "pre-commit hook installed"
                if ok
                else "pre-commit hook not installed — run 'sdd init' to install it"
            ),
        )
