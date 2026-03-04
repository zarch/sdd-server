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
        """If recipe file does not exist, execute_recipe raises RecipeNotFoundError → FAILED result."""
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
