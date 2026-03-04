"""Result aggregation and reporting for role executions.

This module provides functionality to aggregate results from multiple
role executions, deduplicate issues, classify severity, and generate
comprehensive reports.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from sdd_server.plugins.base import RoleResult, RoleStatus
from sdd_server.utils.logging import get_logger

logger = get_logger(__name__)


class IssueSeverity(StrEnum):
    """Severity level for issues."""

    CRITICAL = "critical"  # Must fix before proceeding
    HIGH = "high"  # Important, should fix soon
    MEDIUM = "medium"  # Notable, should address
    LOW = "low"  # Minor improvement
    INFO = "info"  # Informational only


class IssueCategory(StrEnum):
    """Category for classifying issues."""

    SECURITY = "security"
    PERFORMANCE = "performance"
    ARCHITECTURE = "architecture"
    CODE_QUALITY = "code-quality"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    EDGE_CASE = "edge-case"
    UI_UX = "ui-ux"
    GENERAL = "general"


@dataclass
class AggregatedIssue:
    """An issue aggregated from one or more role results."""

    title: str
    description: str
    severity: IssueSeverity
    category: IssueCategory
    source_roles: list[str]
    file_paths: list[str] = field(default_factory=list)
    line_numbers: dict[str, list[int]] = field(default_factory=dict)
    suggestions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def role_count(self) -> int:
        """Number of roles that reported this issue."""
        return len(self.source_roles)


@dataclass
class RoleSummary:
    """Summary of a single role's execution."""

    role_name: str
    status: RoleStatus
    success: bool
    issue_count: int
    duration_seconds: float | None
    output_preview: str  # First 200 chars of output
    error: str | None = None

    @classmethod
    def from_result(cls, result: RoleResult, max_preview: int = 200) -> RoleSummary:
        """Create summary from a RoleResult."""
        return cls(
            role_name=result.role,
            status=result.status,
            success=result.success,
            issue_count=len(result.issues),
            duration_seconds=result.duration_seconds,
            output_preview=result.output[:max_preview] if result.output else "",
            error=result.issues[0] if result.issues and not result.success else None,
        )


@dataclass
class AggregatedReport:
    """Aggregated report from multiple role executions."""

    # Timing
    started_at: datetime
    completed_at: datetime | None = None
    total_duration_seconds: float | None = None

    # Execution summary
    total_roles: int = 0
    successful_roles: int = 0
    failed_roles: int = 0
    skipped_roles: int = 0

    # Issues
    issues: list[AggregatedIssue] = field(default_factory=list)
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    info_count: int = 0

    # Role details
    role_summaries: list[RoleSummary] = field(default_factory=list)

    # Raw results
    raw_results: dict[str, RoleResult] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_roles == 0:
            return 100.0
        return (self.successful_roles / self.total_roles) * 100

    @property
    def has_critical_issues(self) -> bool:
        """Check if there are any critical issues."""
        return self.critical_count > 0

    @property
    def has_blocking_issues(self) -> bool:
        """Check if there are issues that should block progress."""
        return self.critical_count > 0 or self.high_count > 0

    @property
    def total_issues(self) -> int:
        """Get total issue count."""
        return len(self.issues)

    def get_issues_by_severity(self, severity: IssueSeverity) -> list[AggregatedIssue]:
        """Get issues filtered by severity."""
        return [i for i in self.issues if i.severity == severity]

    def get_issues_by_category(self, category: IssueCategory) -> list[AggregatedIssue]:
        """Get issues filtered by category."""
        return [i for i in self.issues if i.category == category]

    def to_dict(self) -> dict[str, Any]:
        """Convert report to dictionary for serialization."""
        return {
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "total_duration_seconds": self.total_duration_seconds,
            "total_roles": self.total_roles,
            "successful_roles": self.successful_roles,
            "failed_roles": self.failed_roles,
            "skipped_roles": self.skipped_roles,
            "success_rate": self.success_rate,
            "issues": {
                "total": self.total_issues,
                "critical": self.critical_count,
                "high": self.high_count,
                "medium": self.medium_count,
                "low": self.low_count,
                "info": self.info_count,
            },
            "has_blocking_issues": self.has_blocking_issues,
            "role_summaries": [
                {
                    "role": s.role_name,
                    "status": s.status.value,
                    "success": s.success,
                    "issue_count": s.issue_count,
                    "duration_seconds": s.duration_seconds,
                }
                for s in self.role_summaries
            ],
        }


# Severity classification keywords
SEVERITY_KEYWORDS: dict[IssueSeverity, list[str]] = {
    IssueSeverity.CRITICAL: [
        "security vulnerability",
        "critical",
        "severe",
        "exploit",
        "injection",
        "authentication bypass",
        "data breach",
    ],
    IssueSeverity.HIGH: [
        "high",
        "important",
        "significant",
        "breaking",
        "major",
        "vulnerability",
    ],
    IssueSeverity.MEDIUM: [
        "medium",
        "moderate",
        "notable",
        "should",
        "recommended",
    ],
    IssueSeverity.LOW: [
        "low",
        "minor",
        "small",
        "cosmetic",
        "optional",
        "consider",
    ],
}

# Category classification keywords
CATEGORY_KEYWORDS: dict[IssueCategory, list[str]] = {
    IssueCategory.SECURITY: [
        "security",
        "auth",
        "permission",
        "access",
        "encrypt",
        "decrypt",
        "secret",
        "password",
        "token",
        "vulnerability",
        "xss",
        "csrf",
        "sql injection",
    ],
    IssueCategory.PERFORMANCE: [
        "performance",
        "slow",
        "latency",
        "throughput",
        "memory",
        "cpu",
        "optimization",
        "n+1",
        "caching",
    ],
    IssueCategory.ARCHITECTURE: [
        "architecture",
        "design",
        "pattern",
        "coupling",
        "cohesion",
        "module",
        "component",
        "service",
        "api",
        "interface",
    ],
    IssueCategory.TESTING: [
        "test",
        "coverage",
        "unit",
        "integration",
        "e2e",
        "mock",
        "assertion",
    ],
    IssueCategory.DOCUMENTATION: [
        "documentation",
        "comment",
        "readme",
        "docstring",
        "example",
    ],
    IssueCategory.EDGE_CASE: [
        "edge case",
        "boundary",
        "null",
        "empty",
        "undefined",
        "corner case",
    ],
    IssueCategory.UI_UX: [
        "ui",
        "ux",
        "user interface",
        "accessibility",
        "responsive",
        "design",
    ],
}


def classify_severity(text: str) -> IssueSeverity:
    """Classify issue severity from text."""
    text_lower = text.lower()
    for severity, keywords in SEVERITY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                return severity
    return IssueSeverity.MEDIUM


def classify_category(text: str, role_name: str | None = None) -> IssueCategory:
    """Classify issue category from text and role name."""
    text_lower = text.lower()

    # Check role name for hints
    if role_name:
        role_lower = role_name.lower()
        if "security" in role_lower:
            return IssueCategory.SECURITY
        if "ui" in role_lower or "ux" in role_lower:
            return IssueCategory.UI_UX
        if "edge" in role_lower:
            return IssueCategory.EDGE_CASE

    # Check keywords
    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                return category

    return IssueCategory.GENERAL


def extract_file_paths(text: str) -> list[str]:
    """Extract file paths from text."""
    patterns = [
        r"`([^`]+\.[a-z]{1,10})`",  # Backtick quoted paths
        r"['\"]([^'\"]+\.[a-z]{1,10})['\"]",  # Quoted paths
        r"(?:file|path|in)[:\s]+([^\s,]+\.[a-z]{1,10})",  # file: path.ext
        r"([a-zA-Z0-9_/.-]+\.(?:py|js|ts|jsx|tsx|go|rs|java|c|cpp|h))",  # Code files
    ]

    paths: set[str] = set()
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            if isinstance(match, str) and len(match) < 200:
                paths.add(match)

    return sorted(paths)


def are_similar(text1: str, text2: str) -> bool:
    """Check if two texts are similar."""
    if text1 == text2:
        return True
    if text1 in text2 or text2 in text1:
        return True

    words1 = set(text1.split())
    words2 = set(text2.split())
    if not words1 or not words2:
        return False

    overlap = len(words1 & words2)
    max_len = max(len(words1), len(words2))

    return overlap / max_len > 0.7


def deduplicate_issues(issues: list[AggregatedIssue]) -> list[AggregatedIssue]:
    """Deduplicate similar issues."""
    if not issues:
        return []

    unique_issues: dict[str, AggregatedIssue] = {}

    for issue in issues:
        key = issue.title.lower().strip()

        found_similar = False
        for existing_key, existing in list(unique_issues.items()):
            if are_similar(key, existing_key):
                # Merge source roles
                for role in issue.source_roles:
                    if role not in existing.source_roles:
                        existing.source_roles.append(role)
                # Merge file paths
                for path in issue.file_paths:
                    if path not in existing.file_paths:
                        existing.file_paths.append(path)
                # Merge suggestions
                for suggestion in issue.suggestions:
                    if suggestion not in existing.suggestions:
                        existing.suggestions.append(suggestion)
                found_similar = True
                break

        if not found_similar:
            unique_issues[key] = issue

    return list(unique_issues.values())


class ResultAggregator:
    """Aggregates results from multiple role executions."""

    def __init__(self) -> None:
        """Initialize the result aggregator."""
        self._results: dict[str, RoleResult] = {}
        self._started_at: datetime | None = None

    def add_result(self, result: RoleResult) -> None:
        """Add a role result for aggregation."""
        if self._started_at is None:
            self._started_at = result.started_at

        self._results[result.role] = result
        logger.debug("Added result for aggregation", role=result.role, success=result.success)

    def add_results(self, results: list[RoleResult]) -> None:
        """Add multiple role results for aggregation."""
        for result in results:
            self.add_result(result)

    def aggregate(self) -> AggregatedReport:
        """Aggregate all added results into a report."""
        report = AggregatedReport(
            started_at=self._started_at or datetime.now(),
        )

        all_issues: list[AggregatedIssue] = []

        for role_name, result in self._results.items():
            # Update counts
            report.total_roles += 1

            if result.status == RoleStatus.SKIPPED:
                report.skipped_roles += 1
            elif result.success:
                report.successful_roles += 1
            else:
                report.failed_roles += 1

            # Create role summary
            report.role_summaries.append(RoleSummary.from_result(result))

            # Process issues
            for issue_text in result.issues:
                issue = AggregatedIssue(
                    title=issue_text[:100],
                    description=issue_text,
                    severity=classify_severity(issue_text),
                    category=classify_category(issue_text, role_name),
                    source_roles=[role_name],
                    file_paths=extract_file_paths(issue_text),
                    suggestions=result.suggestions if not result.success else [],
                )
                all_issues.append(issue)

            # Store raw result
            report.raw_results[role_name] = result

        # Deduplicate issues
        report.issues = deduplicate_issues(all_issues)

        # Count by severity
        for issue in report.issues:
            if issue.severity == IssueSeverity.CRITICAL:
                report.critical_count += 1
            elif issue.severity == IssueSeverity.HIGH:
                report.high_count += 1
            elif issue.severity == IssueSeverity.MEDIUM:
                report.medium_count += 1
            elif issue.severity == IssueSeverity.LOW:
                report.low_count += 1
            else:
                report.info_count += 1

        # Calculate timing
        if report.raw_results:
            completed_times = [
                r.completed_at for r in report.raw_results.values() if r.completed_at
            ]
            if completed_times:
                max_completed = max(completed_times)
                report.completed_at = max_completed
                if report.started_at:
                    report.total_duration_seconds = (
                        max_completed - report.started_at
                    ).total_seconds()

        logger.info(
            "Aggregated report generated",
            total_roles=report.total_roles,
            total_issues=report.total_issues,
            critical=report.critical_count,
            high=report.high_count,
        )

        return report

    def clear(self) -> None:
        """Clear all stored results."""
        self._results.clear()
        self._started_at = None


def format_report_markdown(report: AggregatedReport) -> str:
    """Format an aggregated report as markdown."""
    lines: list[str] = []

    # Header
    lines.append("# SDD Review Report")
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Total Roles:** {report.total_roles}")
    lines.append(f"- **Successful:** {report.successful_roles}")
    lines.append(f"- **Failed:** {report.failed_roles}")
    lines.append(f"- **Skipped:** {report.skipped_roles}")
    lines.append(f"- **Success Rate:** {report.success_rate:.1f}%")
    duration_str = (
        f"{report.total_duration_seconds:.2f}s" if report.total_duration_seconds else "N/A"
    )
    lines.append(f"- **Duration:** {duration_str}")
    lines.append("")

    # Issues summary
    lines.append("## Issues")
    lines.append("")
    lines.append(f"- **Critical:** {report.critical_count}")
    lines.append(f"- **High:** {report.high_count}")
    lines.append(f"- **Medium:** {report.medium_count}")
    lines.append(f"- **Low:** {report.low_count}")
    lines.append(f"- **Info:** {report.info_count}")
    lines.append("")

    # Critical issues
    if report.critical_count > 0:
        lines.append("### 🚨 Critical Issues")
        lines.append("")
        for issue in report.get_issues_by_severity(IssueSeverity.CRITICAL):
            lines.append(f"- **{issue.title}**")
            lines.append(f"  - Roles: {', '.join(issue.source_roles)}")
            if issue.file_paths:
                lines.append(f"  - Files: {', '.join(issue.file_paths[:5])}")
        lines.append("")

    # High issues
    if report.high_count > 0:
        lines.append("### ⚠️ High Priority Issues")
        lines.append("")
        for issue in report.get_issues_by_severity(IssueSeverity.HIGH):
            lines.append(f"- **{issue.title}**")
            lines.append(f"  - Roles: {', '.join(issue.source_roles)}")
        lines.append("")

    # Role summaries
    lines.append("## Role Results")
    lines.append("")
    for summary in report.role_summaries:
        status_emoji = "✅" if summary.success else "❌"
        lines.append(f"### {status_emoji} {summary.role_name}")
        lines.append("")
        lines.append(f"- Status: {summary.status.value}")
        lines.append(f"- Issues: {summary.issue_count}")
        if summary.duration_seconds:
            lines.append(f"- Duration: {summary.duration_seconds:.2f}s")
        if summary.error:
            lines.append(f"- Error: {summary.error}")
        lines.append("")

    return "\n".join(lines)


def format_report_json(report: AggregatedReport) -> str:
    """Format an aggregated report as JSON string."""
    import json

    return json.dumps(report.to_dict(), indent=2, default=str)
