"""Unit tests for AIClientBridge and GooseClientBridge."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sdd_server.core.ai_client import (
    ClientResult,
    GooseClientBridge,
    create_ai_client,
)


class TestClientResult:
    def test_defaults(self) -> None:
        r = ClientResult(success=True, output="hello")
        assert r.exit_code == 0
        assert r.error is None
        assert r.tokens_used is None

    def test_failure(self) -> None:
        r = ClientResult(success=False, output="", error="oops", exit_code=1)
        assert not r.success
        assert r.error == "oops"


class TestGooseClientBridgeIsAvailable:
    def test_available_when_goose_on_path(self, tmp_path: Path) -> None:
        bridge = GooseClientBridge(project_root=tmp_path)
        with patch("shutil.which", return_value="/usr/bin/goose"):
            assert bridge.is_available is True

    def test_not_available_when_missing(self, tmp_path: Path) -> None:
        bridge = GooseClientBridge(project_root=tmp_path)
        with patch("shutil.which", return_value=None):
            assert bridge.is_available is False


class TestGooseClientBridgeGetVersion:
    async def test_returns_version_string(self, tmp_path: Path) -> None:
        bridge = GooseClientBridge(project_root=tmp_path)

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"goose 1.2.3\n", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            version = await bridge.get_version()

        assert "goose" in version.lower() or "1.2.3" in version

    async def test_returns_unavailable_when_not_found(self, tmp_path: Path) -> None:
        bridge = GooseClientBridge(project_root=tmp_path, goose_path="nonexistent-goose")

        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            version = await bridge.get_version()

        assert version == "unavailable"


class TestGooseClientBridgeCheckCompatibility:
    async def test_compatible_when_available(self, tmp_path: Path) -> None:
        bridge = GooseClientBridge(project_root=tmp_path)

        with patch.object(bridge, "get_version", new_callable=AsyncMock, return_value="goose 2.0"):
            ok, msg = await bridge.check_compatibility()

        assert ok is True
        assert "goose" in msg.lower() or "2.0" in msg

    async def test_incompatible_when_unavailable(self, tmp_path: Path) -> None:
        bridge = GooseClientBridge(project_root=tmp_path)

        with patch.object(
            bridge, "get_version", new_callable=AsyncMock, return_value="unavailable"
        ):
            ok, msg = await bridge.check_compatibility()

        assert ok is False
        assert "not found" in msg.lower()


class TestGooseClientBridgeInvokeRole:
    async def test_missing_recipe_returns_failure(self, tmp_path: Path) -> None:
        """If recipe file does not exist, execute_recipe raises RecipeNotFoundError."""
        bridge = GooseClientBridge(project_root=tmp_path)

        result = await bridge.invoke_role(
            role_name="architect",
            context={"feature": "auth"},
            recipe_path=tmp_path / "nonexistent.yml",
        )

        # Should return a ClientResult with success=False (RecipeNotFoundError handled)
        assert not result.success


class TestGooseClientBridgeRunAlignmentCheck:
    async def test_no_recipe_returns_error(self, tmp_path: Path) -> None:
        """With no recipe files present, returns an error result."""
        bridge = GooseClientBridge(project_root=tmp_path)

        result = await bridge.run_alignment_check(
            spec_context="# PRD\nSome spec",
            code_diff="- removed\n+ added",
        )

        assert not result.success
        assert result.error is not None


class TestCreateAiClient:
    def test_creates_goose_bridge(self, tmp_path: Path) -> None:
        client = create_ai_client("goose", tmp_path)
        assert isinstance(client, GooseClientBridge)

    def test_unknown_type_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="Unknown AI client"):
            create_ai_client("claude", tmp_path)


class TestGooseClientBridgeInvokeRoleSession:
    """Tests for named-session behaviour in invoke_role."""

    async def test_invoke_role_uses_named_session(self, tmp_path: Path) -> None:
        bridge = GooseClientBridge(project_root=tmp_path)
        recipe = tmp_path / "recipes" / "architect.yml"
        recipe.parent.mkdir(parents=True)
        recipe.write_text("version: '1.0'\n")

        envelope = '{"sdd_role": "architect", "status": "completed", "summary": "done"}'
        with patch("sdd_server.core.goose_session.asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = MagicMock()
            mock_proc.returncode = 0
            mock_proc.communicate = AsyncMock(return_value=(envelope.encode(), b""))
            mock_exec.return_value = mock_proc

            result = await bridge.invoke_role(
                "architect", {"scope": "all", "feature": "auth"}, recipe_path=recipe
            )

        # Check that session subcommand was used with --name
        call_args = mock_exec.call_args[0]
        cmd = list(call_args)
        assert "session" in cmd
        assert "--name" in cmd
        name_idx = cmd.index("--name")
        assert "sdd-architect" in cmd[name_idx + 1]
        assert result.success is True

    async def test_invoke_role_session_name_includes_feature(self, tmp_path: Path) -> None:
        bridge = GooseClientBridge(project_root=tmp_path)
        recipe = tmp_path / "recipes" / "security-analyst.yml"
        recipe.parent.mkdir(parents=True)
        recipe.write_text("version: '1.0'\n")

        envelope = '{"sdd_role": "security-analyst", "status": "completed", "summary": "done"}'
        with patch("sdd_server.core.goose_session.asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = MagicMock()
            mock_proc.returncode = 0
            mock_proc.communicate = AsyncMock(return_value=(envelope.encode(), b""))
            mock_exec.return_value = mock_proc

            await bridge.invoke_role(
                "security-analyst", {"feature": "auth-flow"}, recipe_path=recipe
            )

        call_args = mock_exec.call_args[0]
        cmd = list(call_args)
        name_idx = cmd.index("--name")
        assert "auth-flow" in cmd[name_idx + 1] or "auth" in cmd[name_idx + 1]

    async def test_needs_retry_propagated_in_error(self, tmp_path: Path) -> None:
        bridge = GooseClientBridge(project_root=tmp_path)
        recipe = tmp_path / "recipes" / "architect.yml"
        recipe.parent.mkdir(parents=True)
        recipe.write_text("v: 1\n")

        envelope = (
            '{"sdd_role": "architect", "status": "needs_retry", '
            '"summary": "lost context", "retry_hint": "please restart"}'
        )
        with patch("sdd_server.core.goose_session.asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = MagicMock()
            mock_proc.returncode = 0
            mock_proc.communicate = AsyncMock(return_value=(envelope.encode(), b""))
            mock_exec.return_value = mock_proc

            result = await bridge.invoke_role("architect", {"scope": "all"}, recipe_path=recipe)

        assert not result.success
        assert "needs_retry" in (result.error or "")


class TestGetVersionSyntaxFix:
    """Verify the Python 2 except syntax has been fixed."""

    async def test_file_not_found_handled(self, tmp_path: Path) -> None:
        bridge = GooseClientBridge(project_root=tmp_path)
        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            version = await bridge.get_version()
        assert version == "unavailable"

    async def test_timeout_handled(self, tmp_path: Path) -> None:
        bridge = GooseClientBridge(project_root=tmp_path)
        mock_proc = MagicMock()
        mock_proc.communicate = AsyncMock(side_effect=TimeoutError())
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            version = await bridge.get_version()
        assert version == "unavailable"
