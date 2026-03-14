"""Goose CLI session integration.

This module provides integration with the Goose CLI for executing
role-based reviews via recipes.
"""

import asyncio
import contextlib
import json
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from sdd_server.plugins.base import RoleResult, RoleStatus
from sdd_server.utils.logging import get_logger

logger = get_logger(__name__)


class SessionStatus(StrEnum):
    """Status of a Goose session."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class OutputFormat(StrEnum):
    """Output format for Goose CLI."""

    TEXT = "text"
    JSON = "json"
    STREAM_JSON = "stream-json"


@dataclass
class RoleCompletionEnvelope:
    """Structured completion envelope emitted by SDD role agents.

    The agent writes this as the last NDJSON line so the orchestrator
    can reliably detect success vs. silent failure.
    """

    sdd_role: str
    status: str  # "completed" | "needs_retry" | "blocked"
    summary: str
    findings: list[dict[str, Any]] = field(default_factory=list)
    session_name: str | None = None
    retry_hint: str | None = None

    @property
    def is_completed(self) -> bool:
        return self.status == "completed"

    @property
    def needs_retry(self) -> bool:
        return self.status == "needs_retry"

    @property
    def is_blocked(self) -> bool:
        return self.status == "blocked"


@dataclass
class GooseConfig:
    """Configuration for Goose CLI execution."""

    goose_path: str = "goose"
    output_format: OutputFormat = OutputFormat.JSON
    timeout_seconds: float = 300.0  # 5 minutes default
    max_turns: int | None = None
    max_tool_repetitions: int | None = None
    provider: str | None = None
    model: str | None = None
    no_session: bool = True  # Run without creating session files
    quiet: bool = True
    working_dir: Path | None = None
    env: dict[str, str] = field(default_factory=dict)
    # Session management
    session_name: str | None = None  # --name for goose session
    resume: bool = False  # --resume flag
    fork: bool = False  # --fork flag (implies resume)
    # Context window management (Goose env vars)
    context_strategy: str = "summarize"  # GOOSE_CONTEXT_STRATEGY
    auto_compact_threshold: float = 0.35  # GOOSE_AUTO_COMPACT_THRESHOLD

    def __post_init__(self) -> None:
        """Convert working_dir to Path if string."""
        if isinstance(self.working_dir, str):
            self.working_dir = Path(self.working_dir)


@dataclass
class SessionResult:
    """Result from a Goose session execution."""

    session_id: str | None
    status: SessionStatus
    output: str
    raw_output: str
    started_at: datetime
    completed_at: datetime | None = None
    duration_seconds: float | None = None
    error: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    messages: list[dict[str, Any]] = field(default_factory=list)
    envelope: RoleCompletionEnvelope | None = None

    @property
    def success(self) -> bool:
        """Check if session completed successfully."""
        if self.envelope is not None:
            return self.envelope.is_completed
        return self.status == SessionStatus.COMPLETED

    @property
    def needs_retry(self) -> bool:
        """Check if the role agent requested a retry."""
        if self.envelope is not None:
            return self.envelope.needs_retry
        return False


class GooseSessionError(Exception):
    """Error during Goose session execution."""

    def __init__(self, message: str, result: SessionResult | None = None) -> None:
        super().__init__(message)
        self.result = result


class GooseNotFoundError(GooseSessionError):
    """Goose CLI not found on system."""


class RecipeNotFoundError(GooseSessionError):
    """Recipe file not found."""


class GooseSession:
    """Manages Goose CLI sessions for recipe execution."""

    def __init__(self, config: GooseConfig | None = None) -> None:
        """Initialize Goose session manager.

        Args:
            config: Configuration for Goose CLI execution
        """
        self._config = config or GooseConfig()
        self._process: asyncio.subprocess.Process | None = None
        self._cancelled = False

    @property
    def is_running(self) -> bool:
        """Check if a session is currently running."""
        return self._process is not None and self._process.returncode is None

    @property
    def config(self) -> GooseConfig:
        """Get current configuration."""
        return self._config

    def _build_run_command(
        self,
        recipe_path: Path | str,
        params: dict[str, str] | None = None,
        instructions: str | None = None,
    ) -> list[str]:
        """Build ``goose run`` command (existing behaviour).

        Args:
            recipe_path: Path to recipe file
            params: Parameters to pass to the recipe
            instructions: Additional instructions text

        Returns:
            Command arguments list
        """
        cmd = [self._config.goose_path, "run"]

        # Recipe file
        cmd.extend(["--recipe", str(recipe_path)])

        # Output format
        cmd.extend(["--output-format", self._config.output_format.value])

        # Run without session files by default for automation
        if self._config.no_session:
            cmd.append("--no-session")

        if self._config.quiet:
            cmd.append("--quiet")

        # Optional parameters
        if self._config.max_turns is not None:
            cmd.extend(["--max-turns", str(self._config.max_turns)])

        if self._config.max_tool_repetitions is not None:
            cmd.extend(["--max-tool-repetitions", str(self._config.max_tool_repetitions)])

        if self._config.provider:
            cmd.extend(["--provider", self._config.provider])

        if self._config.model:
            cmd.extend(["--model", self._config.model])

        # Recipe parameters
        if params:
            for key, value in params.items():
                cmd.extend(["--params", f"{key}={value}"])

        # Instructions text
        if instructions:
            cmd.extend(["--text", instructions])

        return cmd

    def _build_session_command(
        self,
        recipe_path: Path | str,
        params: dict[str, str] | None = None,
        instructions: str | None = None,
    ) -> list[str]:
        """Build ``goose session`` command for named/resumable sessions.

        Args:
            recipe_path: Path to recipe file (content passed via stdin)
            params: Parameters (passed via stdin)
            instructions: Additional instructions (passed via stdin)

        Returns:
            Command arguments list
        """
        session_name = self._config.session_name or ""
        cmd = [self._config.goose_path, "session"]
        if session_name:
            cmd.extend(["--name", session_name])

        if self._config.resume or self._config.fork:
            cmd.append("--resume")
        if self._config.fork:
            cmd.append("--fork")

        if self._config.max_turns is not None:
            cmd.extend(["--max-turns", str(self._config.max_turns)])

        if self._config.max_tool_repetitions is not None:
            cmd.extend(["--max-tool-repetitions", str(self._config.max_tool_repetitions)])

        return cmd

    def _build_command(
        self,
        recipe_path: Path | str,
        params: dict[str, str] | None = None,
        instructions: str | None = None,
    ) -> list[str]:
        """Build Goose CLI command.

        Dispatches to ``_build_run_command`` or ``_build_session_command``
        depending on whether a session name is configured.

        Args:
            recipe_path: Path to recipe file
            params: Parameters to pass to the recipe
            instructions: Additional instructions text

        Returns:
            Command arguments list
        """
        if self._config.session_name:
            return self._build_session_command(recipe_path, params, instructions)
        return self._build_run_command(recipe_path, params, instructions)

    def _build_env(self) -> dict[str, str]:
        """Build environment variables for subprocess.

        Always injects context-window management variables
        (``GOOSE_CONTEXT_STRATEGY``, ``GOOSE_AUTO_COMPACT_THRESHOLD``).
        User-supplied ``env`` overrides the defaults.

        Returns:
            Environment dict
        """
        env = os.environ.copy()
        # Context window management — always set defaults first
        env["GOOSE_CONTEXT_STRATEGY"] = self._config.context_strategy
        env["GOOSE_AUTO_COMPACT_THRESHOLD"] = str(self._config.auto_compact_threshold)
        # Caller overrides last
        env.update(self._config.env)
        return env

    async def _run_command(
        self,
        cmd: list[str],
        *,
        stdin_data: bytes | None = None,
    ) -> tuple[int, str, str]:
        """Run command and capture output.

        Args:
            cmd: Command and arguments
            stdin_data: Optional bytes to feed to the process stdin

        Returns:
            Tuple of (return_code, stdout, stderr)

        Raises:
            GooseNotFoundError: If Goose CLI not found
        """
        logger.info("Running Goose command", cmd=" ".join(cmd[:5]))

        try:
            self._process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE if stdin_data else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self._config.working_dir) if self._config.working_dir else None,
                env=self._build_env(),
            )
        except FileNotFoundError as e:
            raise GooseNotFoundError(f"Goose CLI not found at {self._config.goose_path}") from e

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                self._process.communicate(input=stdin_data),
                timeout=self._config.timeout_seconds,
            )
        except TimeoutError:
            self._process.kill()
            await self._process.wait()
            raise

        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")

        assert self._process.returncode is not None
        return self._process.returncode, stdout, stderr

    def _parse_json_output(self, output: str) -> tuple[str, list[dict[str, Any]]]:
        """Parse JSON output from Goose CLI.

        Args:
            output: Raw output string

        Returns:
            Tuple of (final_response, tool_calls)
        """
        final_response = ""
        tool_calls: list[dict[str, Any]] = []

        for line in output.strip().split("\n"):
            if not line.strip():
                continue

            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                # Non-JSON line, might be log output
                continue

            # Handle different message types
            if isinstance(data, dict):
                msg_type = data.get("type")

                if msg_type == "response":
                    # Final response text
                    final_response = data.get("content", "")
                elif msg_type == "tool_call":
                    tool_calls.append(data)
                elif msg_type == "message":
                    # Message content
                    content = data.get("content", "")
                    if isinstance(content, str):
                        final_response = content

        return final_response, tool_calls

    def _extract_envelope(self, output: str) -> RoleCompletionEnvelope | None:
        """Scan output lines in reverse for the first valid SDD envelope.

        The role agent is expected to emit a JSON object with at least
        ``sdd_role`` and ``status`` keys as the last meaningful line.

        Args:
            output: Raw stdout from the Goose subprocess

        Returns:
            Parsed envelope or ``None`` if not found
        """
        for line in reversed(output.strip().split("\n")):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                if isinstance(data, dict) and "sdd_role" in data and "status" in data:
                    return RoleCompletionEnvelope(
                        sdd_role=data["sdd_role"],
                        status=data.get("status", "completed"),
                        summary=data.get("summary", ""),
                        findings=data.get("findings", []),
                        session_name=data.get("session_name"),
                        retry_hint=data.get("retry_hint"),
                    )
            except json.JSONDecodeError:
                continue
        return None

    async def execute_recipe(
        self,
        recipe_path: Path | str,
        params: dict[str, str] | None = None,
        instructions: str | None = None,
    ) -> SessionResult:
        """Execute a recipe via Goose CLI.

        Args:
            recipe_path: Path to recipe file
            params: Parameters to pass to the recipe
            instructions: Additional instructions text

        Returns:
            SessionResult with execution details

        Raises:
            GooseNotFoundError: If Goose CLI not found
            RecipeNotFoundError: If recipe file not found
            GooseSessionError: If execution fails
        """
        started_at = datetime.now()
        recipe_path = Path(recipe_path)

        # Validate recipe exists
        if not recipe_path.exists():
            raise RecipeNotFoundError(f"Recipe not found: {recipe_path}")

        # Build command
        cmd = self._build_command(recipe_path, params, instructions)

        # Build stdin data for session mode
        stdin_data: bytes | None = None
        if self._config.session_name:
            parts: list[str] = []
            with contextlib.suppress(Exception):
                parts.append(recipe_path.read_text(encoding="utf-8"))
            if params:
                parts.append("Parameters:\n" + "\n".join(f"  {k}: {v}" for k, v in params.items()))
            if instructions:
                parts.append(instructions)
            stdin_data = "\n\n".join(parts).encode("utf-8") if parts else None

        try:
            returncode, stdout, stderr = await self._run_command(cmd, stdin_data=stdin_data)

            # Parse output
            if self._config.output_format == OutputFormat.JSON:
                output, tool_calls = self._parse_json_output(stdout)
            else:
                output = stdout
                tool_calls = []

            completed_at = datetime.now()
            duration = (completed_at - started_at).total_seconds()

            # Extract role completion envelope
            envelope = self._extract_envelope(stdout)

            # Determine status
            if self._cancelled:
                status = SessionStatus.CANCELLED
            elif returncode != 0:
                status = SessionStatus.FAILED
            elif self._config.session_name:
                # Session mode: envelope presence + status determine success
                if envelope is not None and envelope.is_completed:
                    status = SessionStatus.COMPLETED
                else:
                    status = SessionStatus.FAILED  # no envelope or needs_retry/blocked
            else:
                # Run mode (no session): exit code is authoritative
                status = SessionStatus.COMPLETED

            result = SessionResult(
                session_id=None,
                status=status,
                output=output,
                raw_output=stdout + stderr,
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=duration,
                error=stderr if returncode != 0 else None,
                tool_calls=tool_calls,
                envelope=envelope,
            )

            if returncode != 0:
                logger.error(
                    "Goose execution failed",
                    returncode=returncode,
                    stderr=stderr[:500],
                )

            return result

        except TimeoutError:
            completed_at = datetime.now()
            duration = (completed_at - started_at).total_seconds()

            return SessionResult(
                session_id=None,
                status=SessionStatus.TIMEOUT,
                output="",
                raw_output="",
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=duration,
                error=f"Execution timed out after {self._config.timeout_seconds}s",
            )

        except GooseNotFoundError:
            raise

        except Exception as e:
            completed_at = datetime.now()
            duration = (completed_at - started_at).total_seconds()

            logger.exception("Goose execution error")

            return SessionResult(
                session_id=None,
                status=SessionStatus.FAILED,
                output="",
                raw_output="",
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=duration,
                error=str(e),
            )

        finally:
            self._process = None

    def cancel(self) -> None:
        """Cancel the current running session."""
        self._cancelled = True
        if self._process and self._process.returncode is None:
            self._process.kill()
            logger.info("Goose session cancelled")

    @staticmethod
    def is_available(goose_path: str = "goose") -> bool:
        """Check if Goose CLI is available on the system.

        Args:
            goose_path: Path to Goose executable

        Returns:
            True if Goose is available
        """
        return shutil.which(goose_path) is not None


def session_result_to_role_result(
    session_result: SessionResult,
    role_name: str,
) -> RoleResult:
    """Convert SessionResult to RoleResult.

    Args:
        session_result: Result from Goose session
        role_name: Name of the role

    Returns:
        RoleResult for the role
    """
    # Map session status to role status
    status_map = {
        SessionStatus.COMPLETED: RoleStatus.COMPLETED,
        SessionStatus.FAILED: RoleStatus.FAILED,
        SessionStatus.CANCELLED: RoleStatus.SKIPPED,
        SessionStatus.TIMEOUT: RoleStatus.FAILED,
        SessionStatus.PENDING: RoleStatus.PENDING,
        SessionStatus.RUNNING: RoleStatus.RUNNING,
    }

    role_status = status_map.get(session_result.status, RoleStatus.FAILED)

    # Build issues list from errors
    issues: list[str] = []
    if session_result.error:
        issues.append(session_result.error)

    return RoleResult(
        role=role_name,
        status=role_status,
        success=session_result.success,
        output=session_result.output,
        issues=issues,
        started_at=session_result.started_at,
        completed_at=session_result.completed_at,
        duration_seconds=session_result.duration_seconds,
    )
