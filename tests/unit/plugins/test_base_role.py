"""Tests for RolePlugin._run_with_ai_client base helper."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

from sdd_server.core.ai_client import AIClientBridge, ClientResult
from sdd_server.plugins.base import (
    PluginMetadata,
    RolePlugin,
    RoleResult,
    RoleStage,
    RoleStatus,
)

# ---------------------------------------------------------------------------
# Minimal concrete role for testing
# ---------------------------------------------------------------------------


class _SimpleRole(RolePlugin):
    metadata = PluginMetadata(
        name="simple-role",
        version="1.0.0",
        description="Test role",
        author="Test",
        priority=99,
        stage=RoleStage.REVIEW,
    )

    async def review(self, scope: str = "all", target: str | None = None) -> RoleResult:
        return await self._run_with_ai_client(scope, target, datetime.now())

    def get_recipe_template(self) -> str:
        return 'version: "1.0.0"\ntitle: "Simple"\n'


# ---------------------------------------------------------------------------
# Mock AI client
# ---------------------------------------------------------------------------


def _make_ai_client(
    *, success: bool, output: str = "ok", error: str | None = None
) -> AIClientBridge:
    """Return an AsyncMock AIClientBridge."""
    client = AsyncMock(spec=AIClientBridge)
    client.invoke_role.return_value = ClientResult(
        success=success,
        output=output,
        error=error,
    )
    return client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRunWithAiClientNoBridge:
    """When no ai_client is in context the result is PENDING."""

    @pytest.mark.asyncio
    async def test_returns_pending_without_ai_client(self) -> None:
        role = _SimpleRole()
        await role.initialize({})

        result = await role.review()

        assert result.role == "simple-role"
        assert result.status == RoleStatus.PENDING
        assert result.success is False
        assert "pending" in result.output.lower() or "no AI client" in result.output

    @pytest.mark.asyncio
    async def test_pending_result_has_suggestion(self) -> None:
        role = _SimpleRole()
        await role.initialize({})

        result = await role.review()

        assert len(result.suggestions) >= 1

    @pytest.mark.asyncio
    async def test_pending_preserves_role_name(self) -> None:
        role = _SimpleRole()
        await role.initialize({})

        result = await role.review(scope="specs", target="auth")

        assert result.role == "simple-role"


class TestRunWithAiClientSuccess:
    """When the AI client succeeds the result is COMPLETED."""

    @pytest.mark.asyncio
    async def test_success_returns_completed(self) -> None:
        role = _SimpleRole()
        ai_client = _make_ai_client(success=True, output="All good")
        await role.initialize({"ai_client": ai_client, "project_root": "."})

        result = await role.review()

        assert result.status == RoleStatus.COMPLETED
        assert result.success is True
        assert result.output == "All good"

    @pytest.mark.asyncio
    async def test_invoke_role_called_with_correct_args(self, tmp_path: Path) -> None:
        role = _SimpleRole()
        ai_client = _make_ai_client(success=True, output="done")
        await role.initialize({"ai_client": ai_client, "project_root": str(tmp_path)})

        await role.review(scope="code", target="payments")

        ai_client.invoke_role.assert_awaited_once()
        call_args = ai_client.invoke_role.call_args
        assert call_args[0][0] == "simple-role"  # role_name
        ctx: dict[str, Any] = call_args[0][1]
        assert ctx["scope"] == "code"
        assert ctx["target"] == "payments"

    @pytest.mark.asyncio
    async def test_recipe_path_passed_when_file_exists(self, tmp_path: Path) -> None:
        recipes_dir = tmp_path / "recipes"
        recipes_dir.mkdir()
        recipe_file = recipes_dir / "simple-role.yml"
        recipe_file.write_text("version: '1.0.0'\n")

        role = _SimpleRole()
        ai_client = _make_ai_client(success=True, output="done")
        await role.initialize({"ai_client": ai_client, "project_root": str(tmp_path)})

        await role.review()

        call_args = ai_client.invoke_role.call_args
        assert call_args[0][2] == recipe_file  # recipe_path arg

    @pytest.mark.asyncio
    async def test_recipe_path_none_when_file_missing(self, tmp_path: Path) -> None:
        role = _SimpleRole()
        ai_client = _make_ai_client(success=True, output="done")
        await role.initialize({"ai_client": ai_client, "project_root": str(tmp_path)})

        await role.review()

        call_args = ai_client.invoke_role.call_args
        assert call_args[0][2] is None  # recipe_path is None


class TestRunWithAiClientFailure:
    """When the AI client reports failure the result is FAILED."""

    @pytest.mark.asyncio
    async def test_failure_returns_failed_status(self) -> None:
        role = _SimpleRole()
        ai_client = _make_ai_client(success=False, output="", error="timeout")
        await role.initialize({"ai_client": ai_client, "project_root": "."})

        result = await role.review()

        assert result.status == RoleStatus.FAILED
        assert result.success is False

    @pytest.mark.asyncio
    async def test_failure_captures_error_in_issues(self) -> None:
        role = _SimpleRole()
        ai_client = _make_ai_client(success=False, output="", error="timeout")
        await role.initialize({"ai_client": ai_client, "project_root": "."})

        result = await role.review()

        assert len(result.issues) >= 1
        assert "timeout" in result.issues[0]

    @pytest.mark.asyncio
    async def test_failure_with_no_error_string_uses_fallback(self) -> None:
        role = _SimpleRole()
        ai_client = _make_ai_client(success=False, output="bad output", error=None)
        await role.initialize({"ai_client": ai_client, "project_root": "."})

        result = await role.review()

        assert result.status == RoleStatus.FAILED
        assert len(result.issues) >= 1
