"""Tests for result aggregation and reporting."""

from datetime import datetime

from sdd_server.core.aggregation import (
    AggregatedIssue,
    AggregatedReport,
    IssueCategory,
    IssueSeverity,
    ResultAggregator,
    RoleSummary,
    are_similar,
    classify_category,
    classify_severity,
    deduplicate_issues,
    extract_file_paths,
    format_report_json,
    format_report_markdown,
)
from sdd_server.plugins.base import RoleResult, RoleStatus


class TestIssueSeverity:
    """Tests for IssueSeverity enum."""

    def test_severity_values(self) -> None:
        """Test severity enum values."""
        assert IssueSeverity.CRITICAL.value == "critical"
        assert IssueSeverity.HIGH.value == "high"
        assert IssueSeverity.MEDIUM.value == "medium"
        assert IssueSeverity.LOW.value == "low"
        assert IssueSeverity.INFO.value == "info"


class TestIssueCategory:
    """Tests for IssueCategory enum."""

    def test_category_values(self) -> None:
        """Test category enum values."""
        assert IssueCategory.SECURITY.value == "security"
        assert IssueCategory.PERFORMANCE.value == "performance"
        assert IssueCategory.ARCHITECTURE.value == "architecture"


class TestAggregatedIssue:
    """Tests for AggregatedIssue."""

    def test_role_count(self) -> None:
        """Test role_count property."""
        issue = AggregatedIssue(
            title="Test issue",
            description="Description",
            severity=IssueSeverity.HIGH,
            category=IssueCategory.SECURITY,
            source_roles=["architect", "reviewer"],
        )
        assert issue.role_count == 2

    def test_role_count_single(self) -> None:
        """Test role_count with single role."""
        issue = AggregatedIssue(
            title="Test",
            description="Desc",
            severity=IssueSeverity.LOW,
            category=IssueCategory.GENERAL,
            source_roles=["architect"],
        )
        assert issue.role_count == 1


class TestRoleSummary:
    """Tests for RoleSummary."""

    def test_from_result_success(self) -> None:
        """Test creating summary from successful result."""
        result = RoleResult(
            role="architect",
            status=RoleStatus.COMPLETED,
            success=True,
            output="All checks passed",
            issues=[],
            started_at=datetime.now(),
            completed_at=datetime.now(),
            duration_seconds=1.5,
        )

        summary = RoleSummary.from_result(result)

        assert summary.role_name == "architect"
        assert summary.status == RoleStatus.COMPLETED
        assert summary.success is True
        assert summary.issue_count == 0
        assert summary.duration_seconds == 1.5
        assert summary.error is None

    def test_from_result_with_issues(self) -> None:
        """Test creating summary from result with issues."""
        result = RoleResult(
            role="reviewer",
            status=RoleStatus.FAILED,
            success=False,
            output="Found problems",
            issues=["Missing tests", "Poor naming"],
            started_at=datetime.now(),
        )

        summary = RoleSummary.from_result(result)

        assert summary.success is False
        assert summary.issue_count == 2
        assert summary.error == "Missing tests"

    def test_output_preview_truncation(self) -> None:
        """Test output preview is truncated."""
        long_output = "x" * 500
        result = RoleResult(
            role="test",
            status=RoleStatus.COMPLETED,
            success=True,
            output=long_output,
            issues=[],
            started_at=datetime.now(),
        )

        summary = RoleSummary.from_result(result, max_preview=100)

        assert len(summary.output_preview) == 100


class TestAggregatedReport:
    """Tests for AggregatedReport."""

    def test_success_rate_empty(self) -> None:
        """Test success rate with no roles."""
        report = AggregatedReport(started_at=datetime.now())
        assert report.success_rate == 100.0

    def test_success_rate_half(self) -> None:
        """Test success rate at 50%."""
        report = AggregatedReport(
            started_at=datetime.now(),
            total_roles=4,
            successful_roles=2,
            failed_roles=2,
        )
        assert report.success_rate == 50.0

    def test_success_rate_full(self) -> None:
        """Test success rate at 100%."""
        report = AggregatedReport(
            started_at=datetime.now(),
            total_roles=3,
            successful_roles=3,
        )
        assert report.success_rate == 100.0

    def test_has_critical_issues(self) -> None:
        """Test has_critical_issues property."""
        report = AggregatedReport(started_at=datetime.now(), critical_count=1)
        assert report.has_critical_issues is True

        report = AggregatedReport(started_at=datetime.now(), critical_count=0)
        assert report.has_critical_issues is False

    def test_has_blocking_issues(self) -> None:
        """Test has_blocking_issues property."""
        report = AggregatedReport(started_at=datetime.now(), high_count=1)
        assert report.has_blocking_issues is True

        report = AggregatedReport(started_at=datetime.now(), medium_count=5)
        assert report.has_blocking_issues is False

    def test_get_issues_by_severity(self) -> None:
        """Test filtering issues by severity."""
        issue1 = AggregatedIssue(
            title="Critical",
            description="",
            severity=IssueSeverity.CRITICAL,
            category=IssueCategory.GENERAL,
            source_roles=["a"],
        )
        issue2 = AggregatedIssue(
            title="High",
            description="",
            severity=IssueSeverity.HIGH,
            category=IssueCategory.GENERAL,
            source_roles=["b"],
        )

        report = AggregatedReport(started_at=datetime.now(), issues=[issue1, issue2])

        critical = report.get_issues_by_severity(IssueSeverity.CRITICAL)
        assert len(critical) == 1
        assert critical[0].title == "Critical"

    def test_to_dict(self) -> None:
        """Test to_dict serialization."""
        report = AggregatedReport(
            started_at=datetime(2026, 1, 1, 12, 0, 0),
            total_roles=2,
            successful_roles=1,
            failed_roles=1,
        )

        data = report.to_dict()

        assert data["total_roles"] == 2
        assert data["success_rate"] == 50.0
        assert "issues" in data
        assert "role_summaries" in data


class TestClassifySeverity:
    """Tests for classify_severity."""

    def test_critical_keywords(self) -> None:
        """Test critical severity classification."""
        assert classify_severity("security vulnerability found") == IssueSeverity.CRITICAL
        assert classify_severity("critical error") == IssueSeverity.CRITICAL

    def test_high_keywords(self) -> None:
        """Test high severity classification."""
        assert classify_severity("high priority issue") == IssueSeverity.HIGH
        assert classify_severity("important change needed") == IssueSeverity.HIGH

    def test_medium_keywords(self) -> None:
        """Test medium severity classification."""
        assert classify_severity("medium concern") == IssueSeverity.MEDIUM
        assert classify_severity("should be fixed") == IssueSeverity.MEDIUM

    def test_low_keywords(self) -> None:
        """Test low severity classification."""
        assert classify_severity("low priority") == IssueSeverity.LOW
        assert classify_severity("minor issue") == IssueSeverity.LOW

    def test_default_medium(self) -> None:
        """Test default is medium."""
        assert classify_severity("some random text") == IssueSeverity.MEDIUM


class TestClassifyCategory:
    """Tests for classify_category."""

    def test_security_from_role_name(self) -> None:
        """Test security category from role name."""
        assert classify_category("xss attack", "security-analyst") == IssueCategory.SECURITY

    def test_security_from_keywords(self) -> None:
        """Test security category from keywords."""
        assert classify_category("authentication bypass", "reviewer") == IssueCategory.SECURITY

    def test_performance_keywords(self) -> None:
        """Test performance category."""
        assert classify_category("slow query performance", "a") == IssueCategory.PERFORMANCE

    def test_architecture_keywords(self) -> None:
        """Test architecture category."""
        assert classify_category("bad architecture design", "a") == IssueCategory.ARCHITECTURE

    def test_default_general(self) -> None:
        """Test default is general."""
        assert classify_category("random text", "some-role") == IssueCategory.GENERAL


class TestExtractFilePaths:
    """Tests for extract_file_paths."""

    def test_backtick_paths(self) -> None:
        """Test extracting backtick quoted paths."""
        text = "See `src/main.py` for details"
        paths = extract_file_paths(text)
        assert "src/main.py" in paths

    def test_quoted_paths(self) -> None:
        """Test extracting quoted paths."""
        text = "Check \"lib/utils.ts\" and 'config.json'"
        paths = extract_file_paths(text)
        assert "lib/utils.ts" in paths
        assert "config.json" in paths

    def test_code_file_extensions(self) -> None:
        """Test extracting code files."""
        text = "Files: app.py, index.js, main.go"
        paths = extract_file_paths(text)
        assert "app.py" in paths
        assert "index.js" in paths
        assert "main.go" in paths

    def test_no_paths(self) -> None:
        """Test text with no paths."""
        text = "This is just regular text"
        paths = extract_file_paths(text)
        assert len(paths) == 0


class TestAreSimilar:
    """Tests for are_similar."""

    def test_identical(self) -> None:
        """Test identical texts."""
        assert are_similar("hello world", "hello world") is True

    def test_one_contains_other(self) -> None:
        """Test when one contains the other."""
        assert are_similar("error", "error: file not found") is True

    def test_high_overlap(self) -> None:
        """Test high word overlap."""
        assert are_similar("the quick brown fox", "the quick brown dog") is True

    def test_low_overlap(self) -> None:
        """Test low word overlap."""
        assert are_similar("completely different", "totally unrelated") is False

    def test_empty(self) -> None:
        """Test empty texts."""
        assert are_similar("", "") is True


class TestDeduplicateIssues:
    """Tests for deduplicate_issues."""

    def test_empty(self) -> None:
        """Test empty list."""
        assert deduplicate_issues([]) == []

    def test_unique_issues(self) -> None:
        """Test all unique issues."""
        issues = [
            AggregatedIssue("A", "", IssueSeverity.LOW, IssueCategory.GENERAL, ["r1"]),
            AggregatedIssue("B", "", IssueSeverity.LOW, IssueCategory.GENERAL, ["r2"]),
        ]
        result = deduplicate_issues(issues)
        assert len(result) == 2

    def test_duplicate_merges_roles(self) -> None:
        """Test duplicate issues merge source roles."""
        issues = [
            AggregatedIssue("Same issue", "", IssueSeverity.LOW, IssueCategory.GENERAL, ["r1"]),
            AggregatedIssue("Same issue", "", IssueSeverity.LOW, IssueCategory.GENERAL, ["r2"]),
        ]
        result = deduplicate_issues(issues)
        assert len(result) == 1
        assert "r1" in result[0].source_roles
        assert "r2" in result[0].source_roles

    def test_duplicate_merges_paths(self) -> None:
        """Test duplicate issues merge file paths."""
        issues = [
            AggregatedIssue("X", "", IssueSeverity.LOW, IssueCategory.GENERAL, ["r1"], ["a.py"]),
            AggregatedIssue("X", "", IssueSeverity.LOW, IssueCategory.GENERAL, ["r2"], ["b.py"]),
        ]
        result = deduplicate_issues(issues)
        assert len(result) == 1
        assert "a.py" in result[0].file_paths
        assert "b.py" in result[0].file_paths


class TestResultAggregator:
    """Tests for ResultAggregator."""

    def test_add_result(self) -> None:
        """Test adding a result."""
        aggregator = ResultAggregator()
        result = RoleResult(
            role="architect",
            status=RoleStatus.COMPLETED,
            success=True,
            output="OK",
            issues=[],
            started_at=datetime.now(),
        )

        aggregator.add_result(result)
        report = aggregator.aggregate()

        assert report.total_roles == 1
        assert report.successful_roles == 1

    def test_add_results(self) -> None:
        """Test adding multiple results."""
        aggregator = ResultAggregator()
        results = [
            RoleResult(
                role="a",
                status=RoleStatus.COMPLETED,
                success=True,
                output="OK",
                issues=[],
                started_at=datetime.now(),
            ),
            RoleResult(
                role="b",
                status=RoleStatus.COMPLETED,
                success=True,
                output="OK",
                issues=[],
                started_at=datetime.now(),
            ),
        ]

        aggregator.add_results(results)
        report = aggregator.aggregate()

        assert report.total_roles == 2

    def test_aggregate_counts(self) -> None:
        """Test aggregation counts."""
        aggregator = ResultAggregator()
        aggregator.add_results(
            [
                RoleResult(
                    role="a",
                    status=RoleStatus.COMPLETED,
                    success=True,
                    output="OK",
                    issues=[],
                    started_at=datetime.now(),
                ),
                RoleResult(
                    role="b",
                    status=RoleStatus.FAILED,
                    success=False,
                    output="Err",
                    issues=["issue"],
                    started_at=datetime.now(),
                ),
                RoleResult(
                    role="c",
                    status=RoleStatus.SKIPPED,
                    success=False,
                    output="",
                    issues=[],
                    started_at=datetime.now(),
                ),
            ]
        )

        report = aggregator.aggregate()

        assert report.total_roles == 3
        assert report.successful_roles == 1
        assert report.failed_roles == 1
        assert report.skipped_roles == 1

    def test_aggregate_issues(self) -> None:
        """Test issue aggregation."""
        aggregator = ResultAggregator()
        aggregator.add_result(
            RoleResult(
                role="a",
                status=RoleStatus.FAILED,
                success=False,
                output="",
                issues=["critical security issue"],
                started_at=datetime.now(),
            )
        )
        aggregator.add_result(
            RoleResult(
                role="b",
                status=RoleStatus.FAILED,
                success=False,
                output="",
                issues=["high priority bug"],
                started_at=datetime.now(),
            )
        )

        report = aggregator.aggregate()

        assert report.total_issues == 2
        assert report.critical_count == 1
        assert report.high_count == 1

    def test_clear(self) -> None:
        """Test clearing aggregator."""
        aggregator = ResultAggregator()
        aggregator.add_result(
            RoleResult(
                role="a",
                status=RoleStatus.COMPLETED,
                success=True,
                output="",
                issues=[],
                started_at=datetime.now(),
            )
        )

        aggregator.clear()
        report = aggregator.aggregate()

        assert report.total_roles == 0


class TestFormatReportMarkdown:
    """Tests for format_report_markdown."""

    def test_basic_format(self) -> None:
        """Test basic markdown formatting."""
        report = AggregatedReport(
            started_at=datetime(2026, 1, 1, 12, 0, 0),
            total_roles=2,
            successful_roles=1,
            failed_roles=1,
            skipped_roles=0,
        )

        md = format_report_markdown(report)

        assert "# SDD Review Report" in md
        assert "## Summary" in md
        assert "**Total Roles:** 2" in md

    def test_critical_issues_section(self) -> None:
        """Test critical issues section appears."""
        issue = AggregatedIssue(
            title="Critical Bug",
            description="desc",
            severity=IssueSeverity.CRITICAL,
            category=IssueCategory.GENERAL,
            source_roles=["reviewer"],
        )
        report = AggregatedReport(started_at=datetime.now(), issues=[issue], critical_count=1)

        md = format_report_markdown(report)

        assert "🚨 Critical Issues" in md
        assert "Critical Bug" in md

    def test_role_summaries(self) -> None:
        """Test role summaries appear."""
        summary = RoleSummary(
            role_name="architect",
            status=RoleStatus.COMPLETED,
            success=True,
            issue_count=0,
            duration_seconds=1.5,
            output_preview="OK",
        )
        report = AggregatedReport(started_at=datetime.now(), role_summaries=[summary])

        md = format_report_markdown(report)

        assert "architect" in md
        assert "✅" in md


class TestFormatReportJson:
    """Tests for format_report_json."""

    def test_json_format(self) -> None:
        """Test JSON formatting."""
        report = AggregatedReport(
            started_at=datetime(2026, 1, 1, 12, 0, 0),
            total_roles=1,
        )

        json_str = format_report_json(report)

        assert '"total_roles": 1' in json_str
        assert '"success_rate"' in json_str
