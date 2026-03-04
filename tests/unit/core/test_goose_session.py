"""Tests for Goose session integration."""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sdd_server.core.goose_session import (
    GooseConfig,
    GooseNotFoundError,
    GooseSession,
    GooseSessionError,
    OutputFormat,
    RecipeNotFoundError,
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

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = GooseConfig(
            goose_path="/custom/goose",
            timeout_seconds=60.0,
            max_turns=10,
            provider="anthropic",
            model="claude-3",
        )
        assert config.goose_path == "/custom/goose"
        assert config.timeout_seconds == 60.0
        assert config.max_turns == 10
        assert config.provider == "anthropic"
        assert config.model == "claude-3"

    def test_working_dir_conversion(self, tmp_path: Path) -> None:
        """Test working_dir string to Path conversion."""
        config = GooseConfig(working_dir=str(tmp_path))
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
        """Test basic command building."""
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
        text, _tool_calls = session._parse_json_output(output)

        assert text == "Done"

    @pytest.mark.asyncio
    async def test_execute_recipe_file_not_found(self, tmp_path: Path) -> None:
        """Test executing non-existent recipe."""
        session = GooseSession()

        with pytest.raises(RecipeNotFoundError):
            await session.execute_recipe(tmp_path / "nonexistent.yaml")

    @pytest.mark.asyncio
    async def test_execute_recipe_goose_not_found(self, tmp_path: Path) -> None:
        """Test executing when Goose not found."""
        recipe = tmp_path / "recipe.yaml"
        recipe.write_text("# Recipe")

        config = GooseConfig(goose_path="/nonexistent/goose")
        session = GooseSession(config)

        with pytest.raises(GooseNotFoundError):
            await session.execute_recipe(recipe)

    @pytest.mark.asyncio
    async def test_execute_recipe_timeout(self, tmp_path: Path) -> None:
        """Test execution timeout."""
        recipe = tmp_path / "recipe.yaml"
        recipe.write_text("# Recipe")

        # Use a command that will actually work but take too long
        # Use bash sleep since goose may not be available
        config = GooseConfig(timeout_seconds=0.01, goose_path="bash")
        session = GooseSession(config)

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
