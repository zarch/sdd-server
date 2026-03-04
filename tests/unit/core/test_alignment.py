"""Unit tests for AlignmentChecker."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from sdd_server.core.ai_client import ClientResult
from sdd_server.core.alignment import (
    AlignmentChecker,
    AlignmentIssue,
    AlignmentReport,
    AlignmentStatus,
)

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_checker(tmp_path: Path, ai_result: ClientResult) -> AlignmentChecker:
    """Build an AlignmentChecker with mocked spec_manager, ai_client, git_client."""
    spec_manager = MagicMock()
    spec_manager.read_spec.return_value = "# PRD\nSome requirement"

    ai_client = MagicMock()
    ai_client.run_alignment_check = AsyncMock(return_value=ai_result)

    git_client = MagicMock()
    git_client.get_diff.return_value = "+ added line\n- removed line"

    return AlignmentChecker(
        spec_manager=spec_manager,
        ai_client=ai_client,
        project_root=tmp_path,
        git_client=git_client,
    )


def _aligned_json() -> str:
    return json.dumps(
        {
            "overall_status": "aligned",
            "issues": [],
            "summary": {"aligned": 1},
        }
    )


def _diverged_json() -> str:
    return json.dumps(
        {
            "overall_status": "diverged",
            "issues": [
                {
                    "file": "src/auth.py",
                    "spec_ref": "arch.md §5.1",
                    "status": "diverged",
                    "description": "Auth module missing JWT validation",
                    "suggested_action": "update_code",
                    "severity": "critical",
                }
            ],
            "summary": {"diverged": 1},
        }
    )


# ---------------------------------------------------------------------------
# AlignmentStatus enum
# ---------------------------------------------------------------------------


class TestAlignmentStatus:
    def test_values(self) -> None:
        assert AlignmentStatus.ALIGNED.value == "aligned"
        assert AlignmentStatus.DIVERGED.value == "diverged"
        assert AlignmentStatus.MISSING_SPEC.value == "missing_spec"
        assert AlignmentStatus.MISSING_CODE.value == "missing_code"


# ---------------------------------------------------------------------------
# AlignmentReport model
# ---------------------------------------------------------------------------


class TestAlignmentReport:
    def test_defaults(self) -> None:
        report = AlignmentReport(overall_status=AlignmentStatus.ALIGNED)
        assert report.issues == []
        assert report.summary == {}
        assert report.tokens_used is None

    def test_with_issues(self) -> None:
        issue = AlignmentIssue(
            spec_ref="prd.md §3",
            status=AlignmentStatus.DIVERGED,
            description="Missing feature",
            suggested_action="update_code",
            severity="critical",
        )
        report = AlignmentReport(
            overall_status=AlignmentStatus.DIVERGED,
            issues=[issue],
            summary={"diverged": 1},
        )
        assert len(report.issues) == 1
        assert report.issues[0].severity == "critical"


# ---------------------------------------------------------------------------
# AlignmentChecker.check_alignment
# ---------------------------------------------------------------------------


class TestCheckAlignment:
    async def test_aligned_project(self, tmp_path: Path) -> None:
        checker = _make_checker(
            tmp_path,
            ClientResult(success=True, output=_aligned_json()),
        )

        report = await checker.check_alignment()

        assert report.overall_status == AlignmentStatus.ALIGNED
        assert report.issues == []
        assert report.summary.get("aligned") == 1

    async def test_diverged_project(self, tmp_path: Path) -> None:
        checker = _make_checker(
            tmp_path,
            ClientResult(success=True, output=_diverged_json()),
        )

        report = await checker.check_alignment()

        assert report.overall_status == AlignmentStatus.DIVERGED
        assert len(report.issues) == 1
        assert report.issues[0].severity == "critical"
        assert report.issues[0].spec_ref == "arch.md §5.1"

    async def test_ai_failure_returns_diverged(self, tmp_path: Path) -> None:
        checker = _make_checker(
            tmp_path,
            ClientResult(success=False, output="", error="Goose failed", exit_code=1),
        )

        report = await checker.check_alignment()

        assert report.overall_status == AlignmentStatus.DIVERGED

    async def test_feature_scope(self, tmp_path: Path) -> None:
        checker = _make_checker(
            tmp_path,
            ClientResult(success=True, output=_aligned_json()),
        )

        report = await checker.check_alignment(scope="feature:auth")

        assert report.overall_status == AlignmentStatus.ALIGNED
        # spec_manager.read_spec should have been called with a feature arg
        checker._spec_manager.read_spec.assert_called()

    async def test_invalid_json_falls_back(self, tmp_path: Path) -> None:
        checker = _make_checker(
            tmp_path,
            ClientResult(success=True, output="this is not json"),
        )

        report = await checker.check_alignment()

        # Graceful fallback
        assert report.overall_status == AlignmentStatus.DIVERGED
        assert "parse_error" in report.summary


# ---------------------------------------------------------------------------
# AlignmentChecker.check_task_completion
# ---------------------------------------------------------------------------


class TestCheckTaskCompletion:
    async def test_completed(self, tmp_path: Path) -> None:
        payload = json.dumps({"completed": True, "gaps": []})
        checker = _make_checker(tmp_path, ClientResult(success=True, output=payload))

        done, gaps = await checker.check_task_completion("t0000060")

        assert done is True
        assert gaps == []

    async def test_not_completed_with_gaps(self, tmp_path: Path) -> None:
        payload = json.dumps({"completed": False, "gaps": ["Missing unit tests"]})
        checker = _make_checker(tmp_path, ClientResult(success=True, output=payload))

        done, gaps = await checker.check_task_completion("t0000060")

        assert done is False
        assert "Missing unit tests" in gaps

    async def test_failure_returns_false(self, tmp_path: Path) -> None:
        checker = _make_checker(
            tmp_path,
            ClientResult(success=False, output="", error="timeout", exit_code=1),
        )

        done, gaps = await checker.check_task_completion("t0000060")

        assert done is False
        assert len(gaps) > 0


# ---------------------------------------------------------------------------
# AlignmentChecker.summarize_codebase_structure
# ---------------------------------------------------------------------------


class TestSummarizeCodebaseStructure:
    async def test_returns_string(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "main.py").write_text("# hello")

        checker = _make_checker(
            tmp_path,
            ClientResult(success=True, output=""),
        )
        checker._source_dirs = ["src"]

        summary = await checker.summarize_codebase_structure()

        assert "src/main.py" in summary or "main.py" in summary

    async def test_missing_source_dirs_graceful(self, tmp_path: Path) -> None:
        checker = _make_checker(tmp_path, ClientResult(success=True, output=""))
        checker._source_dirs = ["nonexistent"]

        summary = await checker.summarize_codebase_structure()

        # Should not raise; returns header only
        assert isinstance(summary, str)
