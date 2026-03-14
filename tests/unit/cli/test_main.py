"""Unit tests for CLI commands."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from sdd_server.cli.main import app

runner = CliRunner()


@pytest.fixture()  # type: ignore[misc]
def cli_project(tmp_path: Path) -> Path:
    """Create a temp directory with git init for CLI tests."""
    import subprocess

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
    return tmp_path


class TestInitCommand:
    """Tests for the `sdd init` command."""

    def test_init_new_project(self, cli_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Init creates specs directory and files."""
        monkeypatch.chdir(cli_project)
        result = runner.invoke(app, ["init", "test-project"])
        assert result.exit_code == 0, f"Output: {result.stdout}"
        assert (cli_project / "specs").is_dir()
        assert (cli_project / "specs" / "prd.md").exists()
        assert (cli_project / "specs" / "arch.md").exists()
        assert (cli_project / "specs" / "tasks.md").exists()

    def test_init_creates_recipes(self, cli_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Init creates recipe files."""
        monkeypatch.chdir(cli_project)
        result = runner.invoke(app, ["init", "test-project"])
        assert result.exit_code == 0, f"Output: {result.stdout}"
        recipes_dir = cli_project / "specs" / "recipes"
        assert recipes_dir.is_dir()
        # Check for at least one recipe file
        recipe_files = list(recipes_dir.glob("*.yaml"))
        assert len(recipe_files) > 0

    def test_init_with_description(
        self, cli_project: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Init with description option."""
        monkeypatch.chdir(cli_project)
        result = runner.invoke(app, ["init", "test-project", "--description", "A test project"])
        assert result.exit_code == 0, f"Output: {result.stdout}"
        assert (cli_project / "specs").is_dir()

    def test_init_with_root_option(self, cli_project: Path) -> None:
        """Init with explicit root option."""
        result = runner.invoke(app, ["init", "test-project", "--root", str(cli_project)])
        assert result.exit_code == 0, f"Output: {result.stdout}"
        assert (cli_project / "specs").is_dir()


class TestPreflightCommand:
    """Tests for the `sdd preflight` command."""

    def test_preflight_fails_without_init(
        self, cli_project: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Preflight fails when project not initialized."""
        monkeypatch.chdir(cli_project)
        result = runner.invoke(app, ["preflight"])
        assert result.exit_code != 0

    def test_preflight_passes_after_init(
        self, cli_project: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Preflight passes after init creates required files."""
        monkeypatch.chdir(cli_project)
        init_result = runner.invoke(app, ["init", "test-project"])
        assert init_result.exit_code == 0, f"Init failed: {init_result.stdout}"
        result = runner.invoke(app, ["preflight"])
        assert result.exit_code == 0, f"Output: {result.stdout}"


class TestStatusCommand:
    """Tests for the `sdd status` command."""

    def test_status_shows_project_name(
        self, cli_project: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Status shows project name."""
        monkeypatch.chdir(cli_project)
        runner.invoke(app, ["init", "test-project"])
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        # Project name should appear in output
        assert cli_project.name in result.stdout or "uninitialized" in result.stdout.lower()

    def test_status_after_init(self, cli_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Status shows info after init."""
        monkeypatch.chdir(cli_project)
        runner.invoke(app, ["init", "test-project"])
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0


class TestBypassCommand:
    """Tests for the `sdd bypass` command."""

    def test_bypass_requires_reason(
        self, cli_project: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """bypass fails without --reason."""
        monkeypatch.chdir(cli_project)
        runner.invoke(app, ["init", "test-project"])
        result = runner.invoke(app, ["bypass"])
        assert result.exit_code != 0

    def test_bypass_records_reason(
        self, cli_project: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """bypass with --reason succeeds and shows the reason."""
        monkeypatch.chdir(cli_project)
        runner.invoke(app, ["init", "test-project"])
        result = runner.invoke(app, ["bypass", "--reason", "emergency fix"])
        assert result.exit_code == 0
        assert "emergency fix" in result.stdout

    def test_bypass_shows_expiry(self, cli_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """bypass output mentions expiry timeframe."""
        monkeypatch.chdir(cli_project)
        runner.invoke(app, ["init", "test-project"])
        result = runner.invoke(app, ["bypass", "--reason", "test"])
        assert result.exit_code == 0
        assert "24" in result.stdout  # grace period hours

    def test_bypass_with_action_option(
        self, cli_project: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """bypass --action records the specified action."""
        monkeypatch.chdir(cli_project)
        runner.invoke(app, ["init", "test-project"])
        result = runner.invoke(app, ["bypass", "--reason", "test", "--action", "push"])
        assert result.exit_code == 0
        assert "push" in result.stdout

    def test_bypass_allows_subsequent_preflight(
        self, cli_project: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """After bypass, preflight exits 0 even with blocking violations."""
        monkeypatch.chdir(cli_project)
        # Init project then remove prd.md to create a violation
        runner.invoke(app, ["init", "test-project"])
        (cli_project / "specs" / "prd.md").unlink()
        # Confirm preflight is blocked
        pre = runner.invoke(app, ["preflight"])
        assert pre.exit_code != 0
        # Record bypass
        bp = runner.invoke(app, ["bypass", "--reason", "hotfix"])
        assert bp.exit_code == 0
        # Preflight should now pass
        post = runner.invoke(app, ["preflight"])
        assert post.exit_code == 0


class TestPreflightCIMode:
    """Tests for preflight --ci JSON output."""

    @staticmethod
    def _parse_json(stdout: str) -> dict:
        """Extract JSON from output that may contain leading log lines."""
        import json

        # Find the first '{' — everything from there is the JSON payload
        idx = stdout.find("{")
        return json.loads(stdout[idx:])

    def test_ci_mode_outputs_json(self, cli_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """--ci flag produces JSON output."""
        monkeypatch.chdir(cli_project)
        runner.invoke(app, ["init", "test-project"])
        result = runner.invoke(app, ["preflight", "--ci"])
        data = self._parse_json(result.stdout)
        assert "blocked" in data
        assert "violations" in data
        assert "warnings" in data

    def test_ci_mode_allowed_true_on_success(
        self, cli_project: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--ci flag returns allowed=True when no blocking violations."""
        monkeypatch.chdir(cli_project)
        runner.invoke(app, ["init", "test-project"])
        result = runner.invoke(app, ["preflight", "--ci"])
        data = self._parse_json(result.stdout)
        assert data["allowed"] is True

    def test_ci_mode_blocked_without_init(
        self, cli_project: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--ci flag returns blocked=True when spec files missing."""
        monkeypatch.chdir(cli_project)
        result = runner.invoke(app, ["preflight", "--ci"])
        data = self._parse_json(result.stdout)
        assert data["blocked"] is True
        assert result.exit_code != 0


class TestVersionCommand:
    """Tests for version flag."""

    def test_version_flag(self) -> None:
        """--version shows version."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.stdout
