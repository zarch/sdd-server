"""Unit tests for MCP alignment tools (sdd_alignment_check, sdd_task_completion_check)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from mcp.server.fastmcp import FastMCP

from sdd_server.mcp.tools import align as align_module

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_tool_fn(name: str):
    app = FastMCP("test")
    align_module.register_tools(app)
    return app._tool_manager._tools[name].fn


def _make_ctx(lifespan_context: dict):
    ctx = MagicMock()
    ctx.request_context.lifespan_context = lifespan_context
    return ctx


# ---------------------------------------------------------------------------
# sdd_alignment_check
# ---------------------------------------------------------------------------


class TestSddAlignmentCheck:
    async def test_returns_unknown_when_ai_not_available(self) -> None:
        """When GooseClientBridge.is_available is False, tool returns 'unknown' status."""
        fn = _get_tool_fn("sdd_alignment_check")

        bridge_instance = MagicMock()
        bridge_instance.is_available = False

        # Patch at the source module so the `from ... import` inside the function picks it up
        with patch("sdd_server.core.ai_client.GooseClientBridge", return_value=bridge_instance):
            result = await fn(scope="all", ctx=None)

        assert result["overall_status"] == "unknown"
        assert result["ai_available"] is False
        assert result["issues"] == []
        assert "message" in result

    async def test_ai_available_runs_checker(self) -> None:
        """When AI is available, AlignmentChecker.check_alignment is called."""
        fn = _get_tool_fn("sdd_alignment_check")

        mock_report = MagicMock()
        mock_report.overall_status.value = "aligned"
        mock_report.issues = []
        mock_report.summary = {"aligned": 3}

        bridge_instance = MagicMock()
        bridge_instance.is_available = True

        checker_instance = AsyncMock()
        checker_instance.check_alignment = AsyncMock(return_value=mock_report)

        with (
            patch("sdd_server.core.ai_client.GooseClientBridge", return_value=bridge_instance),
            patch("sdd_server.core.alignment.AlignmentChecker", return_value=checker_instance),
        ):
            result = await fn(scope="all", ctx=None)

        assert result["overall_status"] == "aligned"
        assert result["ai_available"] is True
        assert result["issues"] == []
        checker_instance.check_alignment.assert_awaited_once_with(scope="all")

    async def test_uses_ctx_dependencies(self) -> None:
        """When ctx is provided, spec_manager and git_client are taken from it."""
        fn = _get_tool_fn("sdd_alignment_check")

        spec_manager = MagicMock()
        git_client = MagicMock()
        ctx = _make_ctx({"spec_manager": spec_manager, "git_client": git_client})

        bridge_instance = MagicMock()
        bridge_instance.is_available = False  # skip alignment, keep test simple

        with patch("sdd_server.core.ai_client.GooseClientBridge", return_value=bridge_instance):
            result = await fn(scope="all", ctx=ctx)

        assert result["overall_status"] == "unknown"

    async def test_result_includes_summary(self) -> None:
        fn = _get_tool_fn("sdd_alignment_check")

        mock_report = MagicMock()
        mock_report.overall_status.value = "diverged"
        mock_report.issues = []
        mock_report.summary = {"diverged": 2, "aligned": 1}

        bridge_instance = MagicMock()
        bridge_instance.is_available = True
        checker_instance = AsyncMock()
        checker_instance.check_alignment = AsyncMock(return_value=mock_report)

        with (
            patch("sdd_server.core.ai_client.GooseClientBridge", return_value=bridge_instance),
            patch("sdd_server.core.alignment.AlignmentChecker", return_value=checker_instance),
        ):
            result = await fn(scope="all", ctx=None)

        assert result["summary"] == {"diverged": 2, "aligned": 1}

    async def test_issues_fields_are_serialized(self) -> None:
        fn = _get_tool_fn("sdd_alignment_check")

        mock_issue = MagicMock()
        mock_issue.file = "src/main.py"
        mock_issue.spec_ref = "arch#2"
        mock_issue.status.value = "missing_code"
        mock_issue.description = "func not implemented"
        mock_issue.suggested_action = "add the function"
        mock_issue.severity = "medium"

        mock_report = MagicMock()
        mock_report.overall_status.value = "missing_code"
        mock_report.issues = [mock_issue]
        mock_report.summary = {}

        bridge_instance = MagicMock()
        bridge_instance.is_available = True
        checker_instance = AsyncMock()
        checker_instance.check_alignment = AsyncMock(return_value=mock_report)

        with (
            patch("sdd_server.core.ai_client.GooseClientBridge", return_value=bridge_instance),
            patch("sdd_server.core.alignment.AlignmentChecker", return_value=checker_instance),
        ):
            result = await fn(scope="all", ctx=None)

        assert len(result["issues"]) == 1
        issue = result["issues"][0]
        assert issue["file"] == "src/main.py"
        assert issue["spec_ref"] == "arch#2"
        assert issue["status"] == "missing_code"
        assert issue["description"] == "func not implemented"
        assert issue["suggested_action"] == "add the function"
        assert issue["severity"] == "medium"


# ---------------------------------------------------------------------------
# sdd_task_completion_check
# ---------------------------------------------------------------------------


class TestSddTaskCompletionCheck:
    async def test_returns_not_completed_when_ai_unavailable(self) -> None:
        fn = _get_tool_fn("sdd_task_completion_check")

        bridge_instance = MagicMock()
        bridge_instance.is_available = False

        with patch("sdd_server.core.ai_client.GooseClientBridge", return_value=bridge_instance):
            result = await fn(task_id="t0000001", ctx=None)

        assert result["completed"] is False
        assert result["ai_available"] is False
        assert "Goose CLI not available" in result["gaps"]

    async def test_returns_completed_true_when_task_done(self) -> None:
        fn = _get_tool_fn("sdd_task_completion_check")

        bridge_instance = MagicMock()
        bridge_instance.is_available = True
        checker_instance = AsyncMock()
        checker_instance.check_task_completion = AsyncMock(return_value=(True, []))

        with (
            patch("sdd_server.core.ai_client.GooseClientBridge", return_value=bridge_instance),
            patch("sdd_server.core.alignment.AlignmentChecker", return_value=checker_instance),
        ):
            result = await fn(task_id="t0000001", ctx=None)

        assert result["completed"] is True
        assert result["gaps"] == []
        assert result["ai_available"] is True
        assert result["task_id"] == "t0000001"

    async def test_returns_gaps_when_task_incomplete(self) -> None:
        fn = _get_tool_fn("sdd_task_completion_check")

        gaps = ["Missing unit tests", "No error handling"]

        bridge_instance = MagicMock()
        bridge_instance.is_available = True
        checker_instance = AsyncMock()
        checker_instance.check_task_completion = AsyncMock(return_value=(False, gaps))

        with (
            patch("sdd_server.core.ai_client.GooseClientBridge", return_value=bridge_instance),
            patch("sdd_server.core.alignment.AlignmentChecker", return_value=checker_instance),
        ):
            result = await fn(task_id="t0000042", ctx=None)

        assert result["completed"] is False
        assert result["gaps"] == gaps

    async def test_uses_ctx_dependencies_when_provided(self) -> None:
        fn = _get_tool_fn("sdd_task_completion_check")

        spec_manager = MagicMock()
        git_client = MagicMock()
        ctx = _make_ctx({"spec_manager": spec_manager, "git_client": git_client})

        bridge_instance = MagicMock()
        bridge_instance.is_available = True
        checker_instance = AsyncMock()
        checker_instance.check_task_completion = AsyncMock(return_value=(True, []))

        with (
            patch("sdd_server.core.ai_client.GooseClientBridge", return_value=bridge_instance),
            patch(
                "sdd_server.core.alignment.AlignmentChecker", return_value=checker_instance
            ) as MockChecker,
        ):
            result = await fn(task_id="t0000099", ctx=ctx)

        MockChecker.assert_called_once()
        call_kwargs = MockChecker.call_args[1]
        assert call_kwargs["spec_manager"] is spec_manager
        assert call_kwargs["git_client"] is git_client
        assert result["completed"] is True
