"""Tests for Goose session integration."""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sdd_server.core.goose_session import (
    GooseConfig,
    GooseNotFoundError,
    GooseSession,
    GooseSessionError,
    OutputFormat,
    RecipeNotFoundError,
    RoleCompletionEnvelope,
    SessionResult,
    SessionStatus,
    session_result_to_role_result,
)
from sdd_server.plugins.base import RoleStatus


class TestGooseConfig:
    """Tests for GooseConfig."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = GooseConfig()
        assert config.goose_path == "goose"
        assert config.output_format == OutputFormat.JSON
        assert config.timeout_seconds == 300.0
        assert config.no_session is True
        assert config.quiet is True
        assert config.session_name is None
        assert config.resume is False
        assert config.fork is False
        assert config.context_strategy == "summarize"
        assert config.auto_compact_threshold == 0.35

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = GooseConfig(
            goose_path="/custom/goose",
            timeout_seconds=60.0,
            max_turns=10,
            provider="anthropic",
            model="claude-3",
            session_name="sdd-arch-test",
            resume=True,
            fork=True,
            context_strategy="truncate",
            auto_compact_threshold=0.5,
        )
        assert config.goose_path == "/custom/goose"
        assert config.timeout_seconds == 60.0
        assert config.max_turns == 10
        assert config.provider == "anthropic"
        assert config.model == "claude-3"
        assert config.session_name == "sdd-arch-test"
        assert config.resume is True
        assert config.fork is True
        assert config.context_strategy == "truncate"
        assert config.auto_compact_threshold == 0.5

    def test_working_dir_conversion(self, tmp_path: Path) -> None:
        """Test working_dir string to Path conversion."""
        config = GooseConfig(working_dir=str(tmp_path))  # type: ignore[arg-type]
        assert config.working_dir == tmp_path


class TestSessionResult:
    """Tests for SessionResult."""

    def test_success_completed(self) -> None:
        """Test success is True for completed status."""
        result = SessionResult(
            session_id="test",
            status=SessionStatus.COMPLETED,
            output="done",
            raw_output="done",
            started_at=datetime.now(),
        )
        assert result.success is True

    def test_success_failed(self) -> None:
        """Test success is False for failed status."""
        result = SessionResult(
            session_id="test",
            status=SessionStatus.FAILED,
            output="",
            raw_output="",
            started_at=datetime.now(),
            error="Failed",
        )
        assert result.success is False

    def test_success_timeout(self) -> None:
        """Test success is False for timeout status."""
        result = SessionResult(
            session_id="test",
            status=SessionStatus.TIMEOUT,
            output="",
            raw_output="",
            started_at=datetime.now(),
        )
        assert result.success is False


class TestGooseSession:
    """Tests for GooseSession."""

    def test_init_default_config(self) -> None:
        """Test initialization with default config."""
        session = GooseSession()
        assert session.config.goose_path == "goose"

    def test_init_custom_config(self) -> None:
        """Test initialization with custom config."""
        config = GooseConfig(timeout_seconds=60.0)
        session = GooseSession(config)
        assert session.config.timeout_seconds == 60.0

    def test_is_running_false_initially(self) -> None:
        """Test is_running is False initially."""
        session = GooseSession()
        assert session.is_running is False

    def test_build_command_basic(self) -> None:
        """Test basic command building (run mode, no session_name)."""
        config = GooseConfig(goose_path="goose")
        session = GooseSession(config)

        cmd = session._build_command("/path/to/recipe.yaml")

        assert "goose" in cmd
        assert "run" in cmd
        assert "--recipe" in cmd
        assert "/path/to/recipe.yaml" in cmd
        assert "--output-format" in cmd
        assert "json" in cmd
        assert "--no-session" in cmd
        assert "--quiet" in cmd

    def test_build_command_with_params(self) -> None:
        """Test command building with parameters."""
        session = GooseSession()

        cmd = session._build_command(
            "/path/to/recipe.yaml",
            params={"scope": "all", "target": "src/main.py"},
        )

        assert "--params" in cmd
        assert "scope=all" in cmd
        assert "target=src/main.py" in cmd

    def test_build_command_with_instructions(self) -> None:
        """Test command building with instructions."""
        session = GooseSession()

        cmd = session._build_command(
            "/path/to/recipe.yaml",
            instructions="Review the code for security issues",
        )

        assert "--text" in cmd
        assert "Review the code for security issues" in cmd

    def test_build_command_with_limits(self) -> None:
        """Test command building with limits."""
        config = GooseConfig(max_turns=5, max_tool_repetitions=10)
        session = GooseSession(config)

        cmd = session._build_command("/path/to/recipe.yaml")

        assert "--max-turns" in cmd
        assert "5" in cmd
        assert "--max-tool-repetitions" in cmd
        assert "10" in cmd

    def test_parse_json_output_simple(self) -> None:
        """Test parsing simple JSON output."""
        session = GooseSession()

        output = json.dumps({"type": "response", "content": "Done!"})
        text, tool_calls = session._parse_json_output(output)

        assert text == "Done!"
        assert len(tool_calls) == 0

    def test_parse_json_output_with_tool_calls(self) -> None:
        """Test parsing JSON output with tool calls."""
        session = GooseSession()

        output = "\n".join(
            [
                json.dumps({"type": "tool_call", "name": "read_file"}),
                json.dumps({"type": "tool_call", "name": "write_file"}),
                json.dumps({"type": "response", "content": "Complete"}),
            ]
        )
        text, tool_calls = session._parse_json_output(output)

        assert text == "Complete"
        assert len(tool_calls) == 2

    def test_parse_json_output_mixed(self) -> None:
        """Test parsing mixed JSON and non-JSON output."""
        session = GooseSession()

        output = "Some log output\n" + json.dumps({"type": "response", "content": "Done"})
        text, _ = session._parse_json_output(output)

        assert text == "Done"

    async def test_execute_recipe_file_not_found(self, tmp_path: Path) -> None:
        """Test executing non-existent recipe."""
        session = GooseSession()

        with pytest.raises(RecipeNotFoundError):
            await session.execute_recipe(tmp_path / "nonexistent.yaml")

    async def test_execute_recipe_goose_not_found(self, tmp_path: Path) -> None:
        """Test executing when Goose not found."""
        recipe = tmp_path / "recipe.yaml"
        recipe.write_text("# Recipe")

        config = GooseConfig(goose_path="/nonexistent/goose")
        session = GooseSession(config)

        with pytest.raises(GooseNotFoundError):
            await session.execute_recipe(recipe)

    async def test_execute_recipe_timeout(self, tmp_path: Path) -> None:
        """Test execution timeout."""
        recipe = tmp_path / "recipe.yaml"
        recipe.write_text("# Recipe")

        # Create a wrapper script that sleeps
        wrapper = tmp_path / "goose_mock"
        wrapper.write_text("#!/bin/bash\nsleep 10\n")
        wrapper.chmod(0o755)

        config = GooseConfig(timeout_seconds=0.01, goose_path=str(wrapper))
        session = GooseSession(config)

        result = await session.execute_recipe(recipe)

        assert result.status == SessionStatus.TIMEOUT
        assert result.success is False
        assert "timed out" in (result.error or "").lower()

    async def test_execute_recipe_session_mode_passes_recipe_via_stdin(
        self, tmp_path: Path
    ) -> None:
        """Test that session mode pipes recipe content via stdin."""
        recipe = tmp_path / "recipe.yaml"
        recipe.write_text("version: '1.0'\nrole: architect\n")

        config = GooseConfig(
            goose_path="/fake/goose",
            session_name="sdd-arch-test",
            resume=True,
            timeout_seconds=5,
        )
        session = GooseSession(config)

        envelope_line = '{"sdd_role": "architect", "status": "completed", "summary": "done"}'
        with patch.object(
            session,
            "_run_command",
            new_callable=AsyncMock,
            return_value=(0, envelope_line, ""),
        ) as mock_run:
            result = await session.execute_recipe(recipe)
            call_kwargs = mock_run.call_args
            stdin_data = call_kwargs.kwargs.get("stdin_data") or (
                call_kwargs.args[1] if len(call_kwargs.args) > 1 else None
            )
            assert stdin_data is not None
            assert b"architect" in stdin_data or b"version" in stdin_data

        assert result.success is True
        assert result.envelope is not None
        assert result.envelope.sdd_role == "architect"

    async def test_execute_recipe_session_mode_no_envelope_is_failure(self, tmp_path: Path) -> None:
        """Exit 0 but no SDD envelope should be treated as failure in session mode."""
        recipe = tmp_path / "recipe.yaml"
        recipe.write_text("version: '1.0'\n")

        config = GooseConfig(
            goose_path="/fake/goose", session_name="sdd-arch-test", timeout_seconds=5
        )
        session = GooseSession(config)

        with patch.object(
            session,
            "_run_command",
            new_callable=AsyncMock,
            return_value=(0, '{"type": "response", "content": "done but no envelope"}', ""),
        ):
            result = await session.execute_recipe(recipe)

        assert result.success is False
        assert result.status == SessionStatus.FAILED

    def test_cancel(self) -> None:
        """Test cancel method."""
        session = GooseSession()
        session.cancel()
        # No exception = success

    @patch("shutil.which")
    def test_is_available_true(self, mock_which: MagicMock) -> None:
        """Test is_available returns True."""
        mock_which.return_value = "/usr/bin/goose"
        assert GooseSession.is_available() is True

    @patch("shutil.which")
    def test_is_available_false(self, mock_which: MagicMock) -> None:
        """Test is_available returns False."""
        mock_which.return_value = None
        assert GooseSession.is_available() is False


class TestGooseBuildSessionCommand:
    """Tests for session-mode command building."""

    def test_session_command_uses_session_subcommand(self) -> None:
        config = GooseConfig(session_name="sdd-architect-auth")
        session = GooseSession(config)
        cmd = session._build_command("/path/recipe.yaml")
        assert "session" in cmd
        assert "--name" in cmd
        assert "sdd-architect-auth" in cmd
        assert "run" not in cmd

    def test_session_command_adds_resume_flag(self) -> None:
        config = GooseConfig(session_name="sdd-arch", resume=True)
        session = GooseSession(config)
        cmd = session._build_command("/path/recipe.yaml")
        assert "--resume" in cmd

    def test_session_command_fork_implies_resume(self) -> None:
        config = GooseConfig(session_name="sdd-arch", fork=True)
        session = GooseSession(config)
        cmd = session._build_command("/path/recipe.yaml")
        assert "--fork" in cmd
        assert "--resume" in cmd

    def test_session_command_no_output_format(self) -> None:
        config = GooseConfig(session_name="sdd-arch")
        session = GooseSession(config)
        cmd = session._build_command("/path/recipe.yaml")
        assert "--output-format" not in cmd
        assert "--no-session" not in cmd

    def test_run_command_no_session_flag(self) -> None:
        config = GooseConfig(no_session=True)  # no session_name → run mode
        session = GooseSession(config)
        cmd = session._build_command("/path/recipe.yaml")
        assert "--no-session" in cmd
        assert "run" in cmd


class TestExtractEnvelope:
    """Tests for _extract_envelope."""

    def test_finds_envelope_in_last_line(self) -> None:
        session = GooseSession()
        output = (
            '{"type": "message", "content": "thinking..."}\n'
            '{"sdd_role": "architect", "status": "completed", "summary": "done"}'
        )
        env = session._extract_envelope(output)
        assert env is not None
        assert env.sdd_role == "architect"
        assert env.is_completed

    def test_returns_none_when_no_envelope(self) -> None:
        session = GooseSession()
        output = '{"type": "response", "content": "some text"}'
        assert session._extract_envelope(output) is None

    def test_finds_envelope_among_non_json_lines(self) -> None:
        session = GooseSession()
        output = (
            "Log line\nMore output\n"
            '{"sdd_role": "security-analyst", "status": "needs_retry", '
            '"summary": "lost context", "retry_hint": "please restart"}'
        )
        env = session._extract_envelope(output)
        assert env is not None
        assert env.needs_retry
        assert env.retry_hint == "please restart"

    def test_needs_retry_envelope(self) -> None:
        session = GooseSession()
        output = '{"sdd_role": "arch", "status": "needs_retry", "summary": "lost"}'
        env = session._extract_envelope(output)
        assert env is not None
        assert env.needs_retry
        assert not env.is_completed
        assert not env.is_blocked

    def test_blocked_envelope(self) -> None:
        session = GooseSession()
        output = '{"sdd_role": "arch", "status": "blocked", "summary": "missing spec"}'
        env = session._extract_envelope(output)
        assert env is not None
        assert env.is_blocked

    def test_envelope_takes_last_match(self) -> None:
        """If multiple envelopes appear, last one wins (reversed scan = first found)."""
        session = GooseSession()
        first = '{"sdd_role": "arch", "status": "needs_retry", "summary": "first"}'
        last = '{"sdd_role": "arch", "status": "completed", "summary": "last"}'
        output = first + "\n" + last
        env = session._extract_envelope(output)
        assert env is not None
        assert env.is_completed


class TestBuildEnv:
    """Tests for _build_env context management injection."""

    def test_injects_context_strategy(self) -> None:
        session = GooseSession(GooseConfig(context_strategy="truncate"))
        env = session._build_env()
        assert env["GOOSE_CONTEXT_STRATEGY"] == "truncate"

    def test_injects_auto_compact_threshold(self) -> None:
        session = GooseSession(GooseConfig(auto_compact_threshold=0.5))
        env = session._build_env()
        assert env["GOOSE_AUTO_COMPACT_THRESHOLD"] == "0.5"

    def test_default_context_strategy_is_summarize(self) -> None:
        session = GooseSession()
        env = session._build_env()
        assert env["GOOSE_CONTEXT_STRATEGY"] == "summarize"

    def test_default_auto_compact_threshold(self) -> None:
        session = GooseSession()
        env = session._build_env()
        assert env["GOOSE_AUTO_COMPACT_THRESHOLD"] == "0.35"

    def test_custom_env_overrides_defaults(self) -> None:
        config = GooseConfig(env={"GOOSE_CONTEXT_STRATEGY": "custom"})
        session = GooseSession(config)
        env = session._build_env()
        assert env["GOOSE_CONTEXT_STRATEGY"] == "custom"


class TestSessionResultEnvelope:
    """Tests for SessionResult with envelope-based success detection."""

    def _make_envelope(self, status: str = "completed") -> RoleCompletionEnvelope:
        return RoleCompletionEnvelope(sdd_role="arch", status=status, summary="done")

    def test_success_defers_to_envelope_completed(self) -> None:
        result = SessionResult(
            session_id=None,
            status=SessionStatus.COMPLETED,
            output="",
            raw_output="",
            started_at=datetime.now(),
            envelope=self._make_envelope("completed"),
        )
        assert result.success is True

    def test_success_false_when_envelope_needs_retry(self) -> None:
        result = SessionResult(
            session_id=None,
            status=SessionStatus.COMPLETED,  # exit 0 but...
            output="",
            raw_output="",
            started_at=datetime.now(),
            envelope=self._make_envelope("needs_retry"),
        )
        assert result.success is False
        assert result.needs_retry is True

    def test_success_false_when_envelope_blocked(self) -> None:
        result = SessionResult(
            session_id=None,
            status=SessionStatus.COMPLETED,
            output="",
            raw_output="",
            started_at=datetime.now(),
            envelope=self._make_envelope("blocked"),
        )
        assert result.success is False
        assert result.needs_retry is False

    def test_success_without_envelope_uses_status(self) -> None:
        result = SessionResult(
            session_id=None,
            status=SessionStatus.COMPLETED,
            output="",
            raw_output="",
            started_at=datetime.now(),
        )
        assert result.success is True
        assert result.needs_retry is False


class TestSessionResultToRoleResult:
    """Tests for session_result_to_role_result."""

    def test_completed_session(self) -> None:
        """Test converting completed session."""
        session_result = SessionResult(
            session_id="test",
            status=SessionStatus.COMPLETED,
            output="Review complete",
            raw_output="Review complete",
            started_at=datetime.now(),
            completed_at=datetime.now(),
            duration_seconds=1.5,
        )

        role_result = session_result_to_role_result(session_result, "architect")

        assert role_result.role == "architect"
        assert role_result.status == RoleStatus.COMPLETED
        assert role_result.success is True
        assert role_result.output == "Review complete"
        assert len(role_result.issues) == 0

    def test_failed_session(self) -> None:
        """Test converting failed session."""
        session_result = SessionResult(
            session_id="test",
            status=SessionStatus.FAILED,
            output="",
            raw_output="",
            started_at=datetime.now(),
            error="Execution failed",
        )

        role_result = session_result_to_role_result(session_result, "reviewer")

        assert role_result.role == "reviewer"
        assert role_result.status == RoleStatus.FAILED
        assert role_result.success is False
        assert "Execution failed" in role_result.issues

    def test_timeout_session(self) -> None:
        """Test converting timed out session."""
        session_result = SessionResult(
            session_id="test",
            status=SessionStatus.TIMEOUT,
            output="",
            raw_output="",
            started_at=datetime.now(),
            error="Timed out after 300s",
        )

        role_result = session_result_to_role_result(session_result, "analyst")

        assert role_result.role == "analyst"
        assert role_result.status == RoleStatus.FAILED
        assert role_result.success is False

    def test_cancelled_session(self) -> None:
        """Test converting cancelled session."""
        session_result = SessionResult(
            session_id="test",
            status=SessionStatus.CANCELLED,
            output="",
            raw_output="",
            started_at=datetime.now(),
        )

        role_result = session_result_to_role_result(session_result, "dev")

        assert role_result.role == "dev"
        assert role_result.status == RoleStatus.SKIPPED
        assert role_result.success is False

    def test_metadata_preserved(self) -> None:
        """Test that metadata is preserved."""
        session_result = SessionResult(
            session_id="session-123",
            status=SessionStatus.COMPLETED,
            output="Done",
            raw_output="Done",
            started_at=datetime.now(),
            completed_at=datetime.now(),
            duration_seconds=5.0,
            tool_calls=[{"name": "read"}, {"name": "write"}],
        )

        role_result = session_result_to_role_result(session_result, "architect")

        # Verify the result was created successfully
        assert role_result.role == "architect"
        assert role_result.duration_seconds == 5.0
        assert role_result.success is True


class TestGooseSessionError:
    """Tests for GooseSessionError."""

    def test_error_message(self) -> None:
        """Test error message."""
        error = GooseSessionError("Something went wrong")
        assert str(error) == "Something went wrong"

    def test_error_with_result(self) -> None:
        """Test error with session result."""
        result = SessionResult(
            session_id="test",
            status=SessionStatus.FAILED,
            output="",
            raw_output="",
            started_at=datetime.now(),
            error="Failed",
        )
        error = GooseSessionError("Error", result=result)
        assert error.result is not None
        assert error.result.session_id == "test"
