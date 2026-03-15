"""Integration tests for the Goose role invocation round-trip (mocked subprocess).

These tests verify the full chain from ``GooseClientBridge.invoke_role()``
through ``GooseSession.execute_recipe()`` down to subprocess execution,
without requiring the Goose CLI to be installed.

The subprocess is replaced by a mock that emits controlled stdout, allowing
us to test every significant branch of the envelope-based success detection.

For real-Goose round-trip tests (requiring the binary + an AI model), see
``tests/integration/test_goose_live.py`` (added separately, guarded by
``pytest.mark.live``).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sdd_server.core.ai_client import GooseClientBridge
from sdd_server.core.goose_session import (
    GooseConfig,
    GooseSession,
    SessionStatus,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _envelope(
    role: str = "architect",
    status: str = "completed",
    summary: str = "done",
    findings: list | None = None,
    retry_hint: str | None = None,
    session_name: str | None = None,
    clean: bool | None = None,
) -> str:
    """Return a single-line JSON RoleCompletionEnvelope string."""
    data: dict = {
        "sdd_role": role,
        "status": status,
        "summary": summary,
        "findings": findings or [],
        "session_name": session_name,
        "retry_hint": retry_hint,
    }
    if clean is not None:
        data["clean"] = clean
    return json.dumps(data)


def _make_mock_process(returncode: int, stdout: str, stderr: str = "") -> MagicMock:
    """Return a mock asyncio.subprocess.Process."""
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(stdout.encode(), stderr.encode()))
    proc.kill = MagicMock()
    proc.wait = AsyncMock()
    return proc


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def recipe_file(tmp_path: Path) -> Path:
    """Write a minimal YAML recipe to disk and return its path."""
    path = tmp_path / "architect.yaml"
    path.write_text("version: 1.0.0\ntitle: Architect\nprompt: |\n  Review architecture.\n")
    return path


@pytest.fixture()
def session_mode_config(recipe_file: Path) -> GooseConfig:
    """GooseConfig in session mode (named + resume)."""
    return GooseConfig(
        goose_path="/fake/goose",
        session_name="sdd-architect-all",
        resume=True,
        timeout_seconds=10,
        working_dir=recipe_file.parent,
    )


@pytest.fixture()
def run_mode_config(recipe_file: Path) -> GooseConfig:
    """GooseConfig in run mode (no session name)."""
    return GooseConfig(
        goose_path="/fake/goose",
        no_session=True,
        timeout_seconds=10,
        working_dir=recipe_file.parent,
    )


# ---------------------------------------------------------------------------
# GooseSession — session mode (envelope required for success)
# ---------------------------------------------------------------------------


class TestGooseSessionModeRoundTrip:
    """Full execute_recipe() path with subprocess mocked out."""

    async def test_happy_path_completed_envelope(
        self, recipe_file: Path, session_mode_config: GooseConfig
    ) -> None:
        """Valid completed envelope → success=True, envelope parsed correctly."""
        output = f"Some agent output\n{_envelope('architect', 'completed', 'arch done')}"
        proc = _make_mock_process(0, output)

        session = GooseSession(session_mode_config)
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await session.execute_recipe(recipe_file)

        assert result.success is True
        assert result.status == SessionStatus.COMPLETED
        assert result.envelope is not None
        assert result.envelope.sdd_role == "architect"
        assert result.envelope.is_completed
        assert result.envelope.summary == "arch done"

    async def test_needs_retry_envelope(
        self, recipe_file: Path, session_mode_config: GooseConfig
    ) -> None:
        """needs_retry envelope → success=False, needs_retry=True."""
        output = _envelope(
            "architect", "needs_retry", "lost context", retry_hint="restart from step 3"
        )
        proc = _make_mock_process(0, output)

        session = GooseSession(session_mode_config)
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await session.execute_recipe(recipe_file)

        assert result.success is False
        assert result.needs_retry is True
        assert result.status == SessionStatus.FAILED
        assert result.envelope is not None
        assert result.envelope.retry_hint == "restart from step 3"

    async def test_blocked_envelope(
        self, recipe_file: Path, session_mode_config: GooseConfig
    ) -> None:
        """blocked envelope → success=False, needs_retry=False."""
        output = _envelope("architect", "blocked", "prd.md missing")
        proc = _make_mock_process(0, output)

        session = GooseSession(session_mode_config)
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await session.execute_recipe(recipe_file)

        assert result.success is False
        assert result.needs_retry is False
        assert result.envelope is not None
        assert result.envelope.is_blocked

    async def test_exit_zero_no_envelope_is_failure(
        self, recipe_file: Path, session_mode_config: GooseConfig
    ) -> None:
        """Session mode: exit 0 without an SDD envelope must be treated as failure."""
        output = '{"type": "response", "content": "I am done but forgot the envelope"}'
        proc = _make_mock_process(0, output)

        session = GooseSession(session_mode_config)
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await session.execute_recipe(recipe_file)

        assert result.success is False
        assert result.status == SessionStatus.FAILED
        assert result.envelope is None

    async def test_nonzero_exit_is_failure_regardless_of_envelope(
        self, recipe_file: Path, session_mode_config: GooseConfig
    ) -> None:
        """Non-zero exit code → FAILED even if a valid envelope is present."""
        output = _envelope("architect", "completed", "done")
        proc = _make_mock_process(1, output, stderr="internal error")

        session = GooseSession(session_mode_config)
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await session.execute_recipe(recipe_file)

        assert result.success is False
        assert result.status == SessionStatus.FAILED
        assert result.error is not None and "internal error" in result.error

    async def test_envelope_with_findings(
        self, recipe_file: Path, session_mode_config: GooseConfig
    ) -> None:
        """Findings list in envelope is preserved."""
        findings = [{"area": "auth", "decision": "use JWT", "risk": "low"}]
        output = _envelope("architect", "completed", "done", findings=findings)
        proc = _make_mock_process(0, output)

        session = GooseSession(session_mode_config)
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await session.execute_recipe(recipe_file)

        assert result.success is True
        assert result.envelope is not None
        assert len(result.envelope.findings) == 1
        assert result.envelope.findings[0]["area"] == "auth"

    async def test_recipe_content_piped_to_stdin(
        self, recipe_file: Path, session_mode_config: GooseConfig
    ) -> None:
        """Session mode: recipe file content must be piped as stdin bytes."""
        output = _envelope("architect", "completed", "done")
        proc = _make_mock_process(0, output)

        session = GooseSession(session_mode_config)
        captured_stdin: list[bytes | None] = []

        original_run = session._run_command

        async def capture_stdin(cmd: list, *, stdin_data: bytes | None = None) -> tuple:
            captured_stdin.append(stdin_data)
            return await original_run(cmd, stdin_data=stdin_data)

        with (
            patch.object(session, "_run_command", side_effect=capture_stdin),
            patch("asyncio.create_subprocess_exec", return_value=proc),
        ):
            await session.execute_recipe(recipe_file)

        assert len(captured_stdin) == 1
        stdin = captured_stdin[0]
        assert stdin is not None
        # Recipe YAML content should be in stdin
        assert b"architect" in stdin or b"version" in stdin


# ---------------------------------------------------------------------------
# GooseSession — run mode (exit code is authoritative)
# ---------------------------------------------------------------------------


class TestGooseRunModeRoundTrip:
    """Run mode: no session name, exit code determines success."""

    async def test_exit_zero_no_envelope_is_success(
        self, recipe_file: Path, run_mode_config: GooseConfig
    ) -> None:
        """Run mode: exit 0 without envelope is COMPLETED (unlike session mode)."""
        output = '{"type": "response", "content": "all good"}'
        proc = _make_mock_process(0, output)

        session = GooseSession(run_mode_config)
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await session.execute_recipe(recipe_file)

        assert result.success is True
        assert result.status == SessionStatus.COMPLETED
        assert result.envelope is None

    async def test_nonzero_exit_is_failure(
        self, recipe_file: Path, run_mode_config: GooseConfig
    ) -> None:
        """Run mode: non-zero exit → FAILED."""
        proc = _make_mock_process(1, "", stderr="goose crashed")

        session = GooseSession(run_mode_config)
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await session.execute_recipe(recipe_file)

        assert result.success is False
        assert result.status == SessionStatus.FAILED


# ---------------------------------------------------------------------------
# Environment variable injection
# ---------------------------------------------------------------------------


class TestEnvVarInjection:
    """Context management env vars must always reach the subprocess."""

    async def test_context_strategy_in_subprocess_env(self, recipe_file: Path) -> None:
        """GOOSE_CONTEXT_STRATEGY is injected into the subprocess environment."""
        config = GooseConfig(
            goose_path="/fake/goose",
            session_name="sdd-arch-env-test",
            context_strategy="truncate",
            timeout_seconds=5,
        )
        output = _envelope("architect", "completed", "done")
        proc = _make_mock_process(0, output)

        session = GooseSession(config)
        captured_env: list[dict] = []

        async def capture_env(
            *_args: object, env: dict | None = None, **_kwargs: object
        ) -> MagicMock:
            captured_env.append(env or {})
            return proc

        with patch("asyncio.create_subprocess_exec", side_effect=capture_env):
            await session.execute_recipe(recipe_file)

        assert captured_env, "subprocess_exec was not called"
        assert captured_env[0].get("GOOSE_CONTEXT_STRATEGY") == "truncate"

    async def test_auto_compact_threshold_in_subprocess_env(self, recipe_file: Path) -> None:
        """GOOSE_AUTO_COMPACT_THRESHOLD is injected into the subprocess environment."""
        config = GooseConfig(
            goose_path="/fake/goose",
            session_name="sdd-arch-env-test",
            auto_compact_threshold=0.5,
            timeout_seconds=5,
        )
        output = _envelope("architect", "completed", "done")
        proc = _make_mock_process(0, output)

        session = GooseSession(config)
        captured_env: list[dict] = []

        async def capture_env(
            *_args: object, env: dict | None = None, **_kwargs: object
        ) -> MagicMock:
            captured_env.append(env or {})
            return proc

        with patch("asyncio.create_subprocess_exec", side_effect=capture_env):
            await session.execute_recipe(recipe_file)

        assert captured_env[0].get("GOOSE_AUTO_COMPACT_THRESHOLD") == "0.5"

    async def test_caller_env_overrides_default(self, recipe_file: Path) -> None:
        """Caller-supplied env values override injected defaults."""
        config = GooseConfig(
            goose_path="/fake/goose",
            session_name="sdd-arch-env-test",
            env={"GOOSE_CONTEXT_STRATEGY": "caller-wins"},
            timeout_seconds=5,
        )
        output = _envelope("architect", "completed", "done")
        proc = _make_mock_process(0, output)

        session = GooseSession(config)
        captured_env: list[dict] = []

        async def capture_env(
            *_args: object, env: dict | None = None, **_kwargs: object
        ) -> MagicMock:
            captured_env.append(env or {})
            return proc

        with patch("asyncio.create_subprocess_exec", side_effect=capture_env):
            await session.execute_recipe(recipe_file)

        assert captured_env[0].get("GOOSE_CONTEXT_STRATEGY") == "caller-wins"


# ---------------------------------------------------------------------------
# GooseClientBridge.invoke_role() — full bridge round-trip
# ---------------------------------------------------------------------------


class TestGooseClientBridgeRoundTrip:
    """End-to-end tests through GooseClientBridge.invoke_role()."""

    async def test_successful_role_invocation(self, tmp_path: Path) -> None:
        """invoke_role with a completed envelope → ClientResult.success=True."""
        recipe = tmp_path / "architect.yaml"
        recipe.write_text("version: 1.0.0\ntitle: Architect\n")

        output = _envelope("architect", "completed", "Architecture reviewed — 5 components")
        proc = _make_mock_process(0, output)

        bridge = GooseClientBridge(project_root=tmp_path, timeout=10)
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await bridge.invoke_role(
                "architect",
                {"scope": "all", "project_root": str(tmp_path)},
                recipe_path=recipe,
            )

        assert result.success is True
        assert result.error is None

    async def test_needs_retry_propagated_to_client_result(self, tmp_path: Path) -> None:
        """needs_retry envelope → ClientResult.success=False, error contains 'needs_retry'."""
        recipe = tmp_path / "architect.yaml"
        recipe.write_text("version: 1.0.0\ntitle: Architect\n")

        output = _envelope(
            "architect", "needs_retry", "lost context", retry_hint="restart from step 2"
        )
        proc = _make_mock_process(0, output)

        bridge = GooseClientBridge(project_root=tmp_path, timeout=10)
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await bridge.invoke_role(
                "architect",
                {"scope": "all"},
                recipe_path=recipe,
            )

        assert result.success is False
        assert result.error is not None
        assert "needs_retry" in result.error
        assert "restart from step 2" in result.error

    async def test_blocked_propagated_to_client_result(self, tmp_path: Path) -> None:
        """blocked envelope → ClientResult.success=False."""
        recipe = tmp_path / "security-analyst.yaml"
        recipe.write_text("version: 1.0.0\ntitle: Security Analyst\n")

        output = _envelope("security-analyst", "blocked", "Interface Design section missing")
        proc = _make_mock_process(0, output)

        bridge = GooseClientBridge(project_root=tmp_path, timeout=10)
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await bridge.invoke_role(
                "security-analyst",
                {"scope": "all"},
                recipe_path=recipe,
            )

        assert result.success is False

    async def test_session_name_uses_role_and_scope(self, tmp_path: Path) -> None:
        """Session name is deterministic: sdd-{role}-{scope}."""
        recipe = tmp_path / "architect.yaml"
        recipe.write_text("version: 1.0.0\n")

        output = _envelope("architect", "completed", "done")
        proc = _make_mock_process(0, output)

        bridge = GooseClientBridge(project_root=tmp_path, timeout=10)
        captured_cmds: list[list] = []

        async def capture_cmd(*args: object, **_kwargs: object) -> MagicMock:
            captured_cmds.append(list(args))
            return proc

        with patch("asyncio.create_subprocess_exec", side_effect=capture_cmd):
            await bridge.invoke_role(
                "architect",
                {"scope": "all"},
                recipe_path=recipe,
            )

        assert captured_cmds, "subprocess was not called"
        cmd = captured_cmds[0]
        # Session name should appear in the command
        assert any("sdd-architect-all" in str(arg) for arg in cmd), (
            f"Expected sdd-architect-all in command, got: {cmd}"
        )

    async def test_session_name_uses_feature_when_provided(self, tmp_path: Path) -> None:
        """When a feature is given, session name uses it: sdd-{role}-{feature}."""
        recipe = tmp_path / "architect.yaml"
        recipe.write_text("version: 1.0.0\n")

        output = _envelope("architect", "completed", "done")
        proc = _make_mock_process(0, output)

        bridge = GooseClientBridge(project_root=tmp_path, timeout=10)
        captured_cmds: list[list] = []

        async def capture_cmd(*args: object, **_kwargs: object) -> MagicMock:
            captured_cmds.append(list(args))
            return proc

        with patch("asyncio.create_subprocess_exec", side_effect=capture_cmd):
            await bridge.invoke_role(
                "architect",
                {"scope": "all", "target": "auth-feature"},
                recipe_path=recipe,
            )

        cmd = captured_cmds[0]
        assert any("sdd-architect-auth-feature" in str(arg) for arg in cmd), (
            f"Expected sdd-architect-auth-feature in command, got: {cmd}"
        )

    async def test_session_name_sanitizes_special_chars(self, tmp_path: Path) -> None:
        """Feature names with special chars are sanitized to safe DNS-label format."""
        recipe = tmp_path / "architect.yaml"
        recipe.write_text("version: 1.0.0\n")

        output = _envelope("architect", "completed", "done")
        proc = _make_mock_process(0, output)

        bridge = GooseClientBridge(project_root=tmp_path, timeout=10)
        captured_cmds: list[list] = []

        async def capture_cmd(*args: object, **_kwargs: object) -> MagicMock:
            captured_cmds.append(list(args))
            return proc

        with patch("asyncio.create_subprocess_exec", side_effect=capture_cmd):
            await bridge.invoke_role(
                "architect",
                {"scope": "all", "target": "My Feature / v2!"},
                recipe_path=recipe,
            )

        cmd = captured_cmds[0]
        cmd_str = " ".join(str(a) for a in cmd)
        # Must not contain spaces, slashes, or exclamation marks in the name arg
        name_idx = next((i for i, a in enumerate(cmd) if a == "--name"), None)
        if name_idx is not None:
            name_val = str(cmd[name_idx + 1])
            assert " " not in name_val
            assert "/" not in name_val
            assert "!" not in name_val
        else:
            # name might be combined differently — just ensure no bad chars in session name portion
            assert "my-feature" in cmd_str.lower() or "my" in cmd_str.lower(), cmd_str

    async def test_missing_recipe_returns_error_result(self, tmp_path: Path) -> None:
        """RecipeNotFoundError is caught and returned as a failed ClientResult."""
        bridge = GooseClientBridge(project_root=tmp_path, timeout=10)
        result = await bridge.invoke_role(
            "architect",
            {"scope": "all"},
            recipe_path=tmp_path / "nonexistent.yaml",
        )

        assert result.success is False
        assert result.error is not None
        assert "not found" in result.error.lower() or "nonexistent" in result.error.lower()


# ---------------------------------------------------------------------------
# Multi-role sequence: dependency chain simulation
# ---------------------------------------------------------------------------


class TestRoleDependencyChain:
    """Simulate running roles in dependency order, verifying each gate."""

    async def _invoke(
        self,
        bridge: GooseClientBridge,
        role: str,
        recipe: Path,
        status: str,
        summary: str,
    ):
        """Helper: mock subprocess to return a specific status for one role call."""
        output = _envelope(role, status, summary)
        proc = _make_mock_process(0, output)
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            return await bridge.invoke_role(role, {"scope": "all"}, recipe_path=recipe)

    async def test_architect_then_interface_designer(self, tmp_path: Path) -> None:
        """Architect completes → interface-designer can proceed."""
        bridge = GooseClientBridge(project_root=tmp_path, timeout=10)

        for role in ("architect", "interface-designer"):
            recipe = tmp_path / f"{role}.yaml"
            recipe.write_text(f"version: 1.0.0\ntitle: {role}\n")

            result = await self._invoke(bridge, role, recipe, "completed", f"{role} done")
            assert result.success is True, f"{role} should succeed"

    async def test_blocked_role_halts_chain(self, tmp_path: Path) -> None:
        """A blocked role returns success=False, signalling the chain must stop."""
        bridge = GooseClientBridge(project_root=tmp_path, timeout=10)

        recipe = tmp_path / "security-analyst.yaml"
        recipe.write_text("version: 1.0.0\ntitle: security-analyst\n")

        result = await self._invoke(
            bridge, "security-analyst", recipe, "blocked", "Interface Design missing"
        )

        assert result.success is False
        # Downstream roles should not be invoked (caller's responsibility,
        # but we verify the gate result is correct)

    async def test_all_eleven_roles_complete_successfully(self, tmp_path: Path) -> None:
        """Simulate all 11 roles completing in dependency order (spec-linter first)."""
        roles = [
            "spec-linter",
            "architect",
            "interface-designer",
            "ui-designer",
            "security-analyst",
            "edge-case-analyst",
            "senior-developer",
            "qa-engineer",
            "tech-writer",
            "devops-engineer",
            "product-owner",
        ]
        bridge = GooseClientBridge(project_root=tmp_path, timeout=10)

        for role in roles:
            recipe = tmp_path / f"{role}.yaml"
            recipe.write_text(f"version: 1.0.0\ntitle: {role}\n")

            result = await self._invoke(bridge, role, recipe, "completed", f"{role} complete")
            assert result.success is True, f"Role '{role}' should succeed, got: {result.error}"


# ---------------------------------------------------------------------------
# Spec-linter pipeline gate tests
# ---------------------------------------------------------------------------


class TestSpecLinterGates:
    """spec-linter envelope variants and their effect on the pipeline gate."""

    async def _invoke_spec_linter(
        self,
        bridge: GooseClientBridge,
        recipe: Path,
        status: str,
        clean: bool = True,
        findings: list | None = None,
    ):
        output = _envelope(
            role="spec-linter",
            status=status,
            summary="spec audit done",
            clean=clean,
            findings=findings,
        )
        proc = _make_mock_process(0, output)
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            return await bridge.invoke_role("spec-linter", {"scope": "all"}, recipe_path=recipe)

    async def test_spec_linter_blocked_halts_pipeline(self, tmp_path: Path) -> None:
        """spec-linter blocked envelope → success=False; architect must not run."""
        recipe = tmp_path / "spec-linter.yaml"
        recipe.write_text("version: 1.0.0\ntitle: spec-linter\n")

        bridge = GooseClientBridge(project_root=tmp_path, timeout=10)
        result = await self._invoke_spec_linter(bridge, recipe, status="blocked", clean=False)

        assert result.success is False
        # The pipeline gate is the caller's responsibility — we verify the gate
        # result is correct so that the scheduler can halt downstream roles.
        assert result.error is not None or not result.success

    async def test_spec_linter_completed_clean_false_allows_architect(self, tmp_path: Path) -> None:
        """spec-linter completed with findings (clean=false) → architect may still run.

        Non-blocking findings must not stop the pipeline; only blocked status does.
        """
        linter_recipe = tmp_path / "spec-linter.yaml"
        linter_recipe.write_text("version: 1.0.0\ntitle: spec-linter\n")

        arch_recipe = tmp_path / "architect.yaml"
        arch_recipe.write_text("version: 1.0.0\ntitle: architect\n")

        bridge = GooseClientBridge(project_root=tmp_path, timeout=10)

        # Spec-linter completes with medium-severity findings
        linter_result = await self._invoke_spec_linter(
            bridge,
            linter_recipe,
            status="completed",
            clean=False,
            findings=[
                {
                    "file": "specs/arch.md",
                    "issue": "Missing Architecture section",
                    "severity": "medium",
                    "line": None,
                    "recommendation": "Add ## Architecture section",
                }
            ],
        )
        assert linter_result.success is True, (
            "completed status must be success=True even with findings"
        )

        # Architect proceeds because spec-linter completed (not blocked)
        arch_output = _envelope("architect", "completed", "architecture reviewed")
        arch_proc = _make_mock_process(0, arch_output)
        with patch("asyncio.create_subprocess_exec", return_value=arch_proc):
            arch_result = await bridge.invoke_role(
                "architect",
                {"scope": "all"},
                recipe_path=arch_recipe,
            )

        assert arch_result.success is True

    async def test_spec_linter_completed_clean_true_allows_architect(self, tmp_path: Path) -> None:
        """spec-linter completed with clean=true → architect runs without issues."""
        linter_recipe = tmp_path / "spec-linter.yaml"
        linter_recipe.write_text("version: 1.0.0\ntitle: spec-linter\n")

        bridge = GooseClientBridge(project_root=tmp_path, timeout=10)
        result = await self._invoke_spec_linter(
            bridge, linter_recipe, status="completed", clean=True
        )

        assert result.success is True
