"""Spec validation models."""

from __future__ import annotations

from enum import StrEnum

from sdd_server.models.base import SDDBaseModel
from sdd_server.models.spec import SpecType


class ValidationSeverity(StrEnum):
    """Severity level of validation issues."""

    ERROR = "error"  # Must be fixed
    WARNING = "warning"  # Should be fixed
    INFO = "info"  # Suggestion


class ValidationRuleType(StrEnum):
    """Types of validation rules."""

    REQUIRED_SECTION = "required_section"
    REQUIRED_FIELD = "required_field"
    FORMAT_CHECK = "format_check"
    CONTENT_PATTERN = "content_pattern"
    CUSTOM = "custom"


class ValidationRule(SDDBaseModel):
    """A single validation rule."""

    rule_id: str
    name: str
    description: str
    rule_type: ValidationRuleType
    spec_types: list[SpecType]  # Which spec types this applies to
    severity: ValidationSeverity = ValidationSeverity.ERROR
    pattern: str | None = None  # Regex pattern for pattern-based rules
    section: str | None = None  # Section name for section-based rules
    field: str | None = None  # Field name for field-based rules
    enabled: bool = True


class ValidationIssue(SDDBaseModel):
    """A single validation issue found in a spec."""

    rule_id: str
    rule_name: str
    severity: ValidationSeverity
    message: str
    spec_type: SpecType
    feature: str | None = None
    line_number: int | None = None
    section: str | None = None
    suggestion: str | None = None


class SpecValidationResult(SDDBaseModel):
    """Result of validating a single spec file."""

    spec_type: SpecType
    feature: str | None = None
    is_valid: bool
    issues: list[ValidationIssue] = []  # noqa: RUF012
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0


class ProjectValidationResult(SDDBaseModel):
    """Result of validating all specs in a project."""

    is_valid: bool
    spec_results: list[SpecValidationResult] = []  # noqa: RUF012
    total_errors: int = 0
    total_warnings: int = 0
    total_infos: int = 0
    features_checked: list[str] = []  # noqa: RUF012


# Default validation rules for each spec type
DEFAULT_PRD_RULES: list[dict[str, object]] = [
    {
        "rule_id": "prd_title",
        "name": "PRD Title",
        "description": "PRD must have a title starting with '# Product Requirements Document'",
        "rule_type": ValidationRuleType.CONTENT_PATTERN,
        "spec_types": [SpecType.PRD],
        "severity": ValidationSeverity.ERROR,
        "pattern": r"^#\s*Product Requirements Document",
    },
    {
        "rule_id": "prd_exec_summary",
        "name": "Executive Summary",
        "description": "PRD must have an Executive Summary section",
        "rule_type": ValidationRuleType.REQUIRED_SECTION,
        "spec_types": [SpecType.PRD],
        "severity": ValidationSeverity.ERROR,
        "section": "Executive Summary",
    },
    {
        "rule_id": "prd_features",
        "name": "Features Section",
        "description": "PRD must have a Features section",
        "rule_type": ValidationRuleType.REQUIRED_SECTION,
        "spec_types": [SpecType.PRD],
        "severity": ValidationSeverity.ERROR,
        "section": "Features",
    },
    {
        "rule_id": "prd_workflow",
        "name": "Development Workflow",
        "description": "PRD should document the SDD workflow",
        "rule_type": ValidationRuleType.REQUIRED_SECTION,
        "spec_types": [SpecType.PRD],
        "severity": ValidationSeverity.WARNING,
        "section": "Development Workflow",
    },
    {
        "rule_id": "prd_nfr",
        "name": "Non-Functional Requirements",
        "description": "PRD should include non-functional requirements",
        "rule_type": ValidationRuleType.REQUIRED_SECTION,
        "spec_types": [SpecType.PRD],
        "severity": ValidationSeverity.WARNING,
        "section": "Non-Functional Requirements",
    },
    {
        "rule_id": "prd_success",
        "name": "Success Metrics",
        "description": "PRD should define success metrics",
        "rule_type": ValidationRuleType.REQUIRED_SECTION,
        "spec_types": [SpecType.PRD],
        "severity": ValidationSeverity.INFO,
        "section": "Success Metrics",
    },
]

DEFAULT_ARCH_RULES: list[dict[str, object]] = [
    {
        "rule_id": "arch_title",
        "name": "Architecture Title",
        "description": "Architecture doc must have a title starting with '# Architecture Document'",
        "rule_type": ValidationRuleType.CONTENT_PATTERN,
        "spec_types": [SpecType.ARCH],
        "severity": ValidationSeverity.ERROR,
        "pattern": r"^#\s*Architecture Document",
    },
    {
        "rule_id": "arch_overview",
        "name": "Overview Section",
        "description": "Architecture must have an Overview section",
        "rule_type": ValidationRuleType.REQUIRED_SECTION,
        "spec_types": [SpecType.ARCH],
        "severity": ValidationSeverity.ERROR,
        "section": "Overview",
    },
    {
        "rule_id": "arch_tech_stack",
        "name": "Tech Stack",
        "description": "Architecture must define the tech stack",
        "rule_type": ValidationRuleType.REQUIRED_SECTION,
        "spec_types": [SpecType.ARCH],
        "severity": ValidationSeverity.ERROR,
        "section": "Tech Stack",
    },
    {
        "rule_id": "arch_components",
        "name": "Components Section",
        "description": "Architecture should document components",
        "rule_type": ValidationRuleType.REQUIRED_SECTION,
        "spec_types": [SpecType.ARCH],
        "severity": ValidationSeverity.WARNING,
        "section": "Components",
    },
    {
        "rule_id": "arch_data_flow",
        "name": "Data Flow",
        "description": "Architecture should document data flow",
        "rule_type": ValidationRuleType.REQUIRED_SECTION,
        "spec_types": [SpecType.ARCH],
        "severity": ValidationSeverity.WARNING,
        "section": "Data Flow",
    },
    {
        "rule_id": "arch_security",
        "name": "Security Section",
        "description": "Architecture should document security considerations",
        "rule_type": ValidationRuleType.REQUIRED_SECTION,
        "spec_types": [SpecType.ARCH],
        "severity": ValidationSeverity.INFO,
        "section": "Security",
    },
]

DEFAULT_TASKS_RULES: list[dict[str, object]] = [
    {
        "rule_id": "tasks_title",
        "name": "Tasks Title",
        "description": "Tasks file must have a title starting with '# Tasks'",
        "rule_type": ValidationRuleType.CONTENT_PATTERN,
        "spec_types": [SpecType.TASKS],
        "severity": ValidationSeverity.ERROR,
        "pattern": r"^#\s*Tasks",
    },
    {
        "rule_id": "tasks_pending",
        "name": "Pending Section",
        "description": "Tasks must have a Pending section for upcoming work",
        "rule_type": ValidationRuleType.REQUIRED_SECTION,
        "spec_types": [SpecType.TASKS],
        "severity": ValidationSeverity.ERROR,
        "section": "Pending",
    },
    {
        "rule_id": "tasks_progress",
        "name": "In Progress Section",
        "description": "Tasks should have an In Progress section",
        "rule_type": ValidationRuleType.REQUIRED_SECTION,
        "spec_types": [SpecType.TASKS],
        "severity": ValidationSeverity.WARNING,
        "section": "In Progress",
    },
    {
        "rule_id": "tasks_completed",
        "name": "Completed Section",
        "description": "Tasks should have a Completed section",
        "rule_type": ValidationRuleType.REQUIRED_SECTION,
        "spec_types": [SpecType.TASKS],
        "severity": ValidationSeverity.WARNING,
        "section": "Completed",
    },
    {
        "rule_id": "tasks_id_format",
        "name": "Task ID Format",
        "description": "Task IDs should follow format t<hex> (e.g., t0000001)",
        "rule_type": ValidationRuleType.CONTENT_PATTERN,
        "spec_types": [SpecType.TASKS],
        "severity": ValidationSeverity.INFO,
        "pattern": r"t[0-9a-f]{7}",
    },
]

DEFAULT_CONTEXT_HINTS_RULES: list[dict[str, object]] = [
    {
        "rule_id": "hints_valid_yaml",
        "name": "Valid YAML",
        "description": "Context hints file should be valid YAML",
        "rule_type": ValidationRuleType.FORMAT_CHECK,
        "spec_types": [SpecType.CONTEXT_HINTS],
        "severity": ValidationSeverity.WARNING,
    },
]


def get_default_rules() -> list[ValidationRule]:
    """Get all default validation rules."""
    rules: list[ValidationRule] = []
    for rule_data in (
        DEFAULT_PRD_RULES + DEFAULT_ARCH_RULES + DEFAULT_TASKS_RULES + DEFAULT_CONTEXT_HINTS_RULES
    ):
        rules.append(ValidationRule.model_validate(rule_data))
    return rules
