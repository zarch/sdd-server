"""Tests for validation models."""

from __future__ import annotations

from sdd_server.models.spec import SpecType
from sdd_server.models.validation import (
    DEFAULT_ARCH_RULES,
    DEFAULT_CONTEXT_HINTS_RULES,
    DEFAULT_PRD_RULES,
    DEFAULT_TASKS_RULES,
    ProjectValidationResult,
    SpecValidationResult,
    ValidationIssue,
    ValidationRule,
    ValidationRuleType,
    ValidationSeverity,
    get_default_rules,
)


class TestValidationSeverity:
    """Tests for ValidationSeverity enum."""

    def test_severity_values(self):
        """Test severity enum values."""
        assert ValidationSeverity.ERROR == "error"
        assert ValidationSeverity.WARNING == "warning"
        assert ValidationSeverity.INFO == "info"

    def test_severity_is_string_enum(self):
        """Test that severity values are strings."""
        assert ValidationSeverity.ERROR.value == "error"


class TestValidationRuleType:
    """Tests for ValidationRuleType enum."""

    def test_rule_type_values(self):
        """Test rule type enum values."""
        assert ValidationRuleType.REQUIRED_SECTION == "required_section"
        assert ValidationRuleType.REQUIRED_FIELD == "required_field"
        assert ValidationRuleType.FORMAT_CHECK == "format_check"
        assert ValidationRuleType.CONTENT_PATTERN == "content_pattern"
        assert ValidationRuleType.CUSTOM == "custom"


class TestValidationRule:
    """Tests for ValidationRule model."""

    def test_create_required_section_rule(self):
        """Test creating a required section rule."""
        rule = ValidationRule(
            rule_id="test_section",
            name="Test Section",
            description="A test section must exist",
            rule_type=ValidationRuleType.REQUIRED_SECTION,
            spec_types=[SpecType.PRD],
            severity=ValidationSeverity.ERROR,
            section="Test Section",
        )
        assert rule.rule_id == "test_section"
        assert rule.rule_type == ValidationRuleType.REQUIRED_SECTION
        assert SpecType.PRD in rule.spec_types
        assert rule.section == "Test Section"
        assert rule.enabled is True

    def test_create_pattern_rule(self):
        """Test creating a content pattern rule."""
        rule = ValidationRule(
            rule_id="test_pattern",
            name="Test Pattern",
            description="Content must match pattern",
            rule_type=ValidationRuleType.CONTENT_PATTERN,
            spec_types=[SpecType.PRD, SpecType.ARCH],
            severity=ValidationSeverity.WARNING,
            pattern=r"^#\s*Title",
        )
        assert rule.pattern == r"^#\s*Title"
        assert len(rule.spec_types) == 2

    def test_rule_defaults(self):
        """Test rule default values."""
        rule = ValidationRule(
            rule_id="test",
            name="Test",
            description="Test rule",
            rule_type=ValidationRuleType.CUSTOM,
            spec_types=[SpecType.PRD],
        )
        assert rule.severity == ValidationSeverity.ERROR
        assert rule.enabled is True
        assert rule.pattern is None
        assert rule.section is None
        assert rule.field is None


class TestValidationIssue:
    """Tests for ValidationIssue model."""

    def test_create_issue(self):
        """Test creating a validation issue."""
        issue = ValidationIssue(
            rule_id="test_rule",
            rule_name="Test Rule",
            severity=ValidationSeverity.ERROR,
            message="Something is wrong",
            spec_type=SpecType.PRD,
        )
        assert issue.rule_id == "test_rule"
        assert issue.severity == ValidationSeverity.ERROR
        assert issue.line_number is None
        assert issue.suggestion is None

    def test_create_issue_with_all_fields(self):
        """Test creating an issue with all optional fields."""
        issue = ValidationIssue(
            rule_id="test_rule",
            rule_name="Test Rule",
            severity=ValidationSeverity.WARNING,
            message="Missing section",
            spec_type=SpecType.ARCH,
            feature="auth",
            line_number=42,
            section="Security",
            suggestion="Add a Security section",
        )
        assert issue.feature == "auth"
        assert issue.line_number == 42
        assert issue.section == "Security"
        assert issue.suggestion == "Add a Security section"


class TestSpecValidationResult:
    """Tests for SpecValidationResult model."""

    def test_valid_result(self):
        """Test a valid result with no issues."""
        result = SpecValidationResult(
            spec_type=SpecType.PRD,
            is_valid=True,
        )
        assert result.is_valid is True
        assert len(result.issues) == 0
        assert result.error_count == 0

    def test_result_with_issues(self):
        """Test result with multiple issues."""
        issues = [
            ValidationIssue(
                rule_id="r1",
                rule_name="Rule 1",
                severity=ValidationSeverity.ERROR,
                message="Error",
                spec_type=SpecType.PRD,
            ),
            ValidationIssue(
                rule_id="r2",
                rule_name="Rule 2",
                severity=ValidationSeverity.WARNING,
                message="Warning",
                spec_type=SpecType.PRD,
            ),
            ValidationIssue(
                rule_id="r3",
                rule_name="Rule 3",
                severity=ValidationSeverity.INFO,
                message="Info",
                spec_type=SpecType.PRD,
            ),
        ]
        result = SpecValidationResult(
            spec_type=SpecType.PRD,
            is_valid=False,
            issues=issues,
            error_count=1,
            warning_count=1,
            info_count=1,
        )
        assert result.is_valid is False
        assert result.error_count == 1
        assert result.warning_count == 1
        assert result.info_count == 1

    def test_result_with_feature(self):
        """Test result for a feature spec."""
        result = SpecValidationResult(
            spec_type=SpecType.ARCH,
            feature="authentication",
            is_valid=True,
        )
        assert result.feature == "authentication"


class TestProjectValidationResult:
    """Tests for ProjectValidationResult model."""

    def test_empty_project_result(self):
        """Test an empty project result."""
        result = ProjectValidationResult(is_valid=True)
        assert result.is_valid is True
        assert len(result.spec_results) == 0
        assert result.total_errors == 0

    def test_project_result_with_spec_results(self):
        """Test project result with multiple spec results."""
        spec_result = SpecValidationResult(
            spec_type=SpecType.PRD,
            is_valid=False,
            error_count=1,
        )
        result = ProjectValidationResult(
            is_valid=False,
            spec_results=[spec_result],
            total_errors=1,
        )
        assert result.is_valid is False
        assert len(result.spec_results) == 1
        assert result.total_errors == 1

    def test_project_result_with_features(self):
        """Test project result with features checked."""
        result = ProjectValidationResult(
            is_valid=True,
            features_checked=["auth", "payment"],
        )
        assert "auth" in result.features_checked
        assert "payment" in result.features_checked


class TestDefaultRules:
    """Tests for default validation rules."""

    def test_get_default_rules_returns_list(self):
        """Test that get_default_rules returns a list."""
        rules = get_default_rules()
        assert isinstance(rules, list)
        assert len(rules) > 0

    def test_default_rules_are_valid(self):
        """Test that all default rules are valid ValidationRule instances."""
        rules = get_default_rules()
        for rule in rules:
            assert isinstance(rule, ValidationRule)
            assert rule.rule_id
            assert rule.name
            assert rule.description

    def test_prd_rules_exist(self):
        """Test that PRD rules are defined."""
        assert len(DEFAULT_PRD_RULES) >= 3
        rule_ids = [r["rule_id"] for r in DEFAULT_PRD_RULES]
        assert "prd_title" in rule_ids
        assert "prd_exec_summary" in rule_ids
        assert "prd_features" in rule_ids

    def test_arch_rules_exist(self):
        """Test that Architecture rules are defined."""
        assert len(DEFAULT_ARCH_RULES) >= 3
        rule_ids = [r["rule_id"] for r in DEFAULT_ARCH_RULES]
        assert "arch_title" in rule_ids
        assert "arch_overview" in rule_ids
        assert "arch_tech_stack" in rule_ids

    def test_tasks_rules_exist(self):
        """Test that Tasks rules are defined."""
        assert len(DEFAULT_TASKS_RULES) >= 2
        rule_ids = [r["rule_id"] for r in DEFAULT_TASKS_RULES]
        assert "tasks_title" in rule_ids
        assert "tasks_pending" in rule_ids

    def test_context_hints_rules_exist(self):
        """Test that context hints rules are defined."""
        assert len(DEFAULT_CONTEXT_HINTS_RULES) >= 1
        rule_ids = [r["rule_id"] for r in DEFAULT_CONTEXT_HINTS_RULES]
        assert "hints_valid_yaml" in rule_ids

    def test_default_rules_cover_all_spec_types(self):
        """Test that default rules cover all spec types."""
        rules = get_default_rules()
        covered_types = set()
        for rule in rules:
            covered_types.update(rule.spec_types)
        assert SpecType.PRD in covered_types
        assert SpecType.ARCH in covered_types
        assert SpecType.TASKS in covered_types
        assert SpecType.CONTEXT_HINTS in covered_types

    def test_default_rules_have_mixed_severities(self):
        """Test that default rules have mixed severity levels."""
        rules = get_default_rules()
        severities = {rule.severity for rule in rules}
        assert ValidationSeverity.ERROR in severities
        assert ValidationSeverity.WARNING in severities
        assert ValidationSeverity.INFO in severities
