"""Unit tests for MCP validation tools."""

from __future__ import annotations

from unittest.mock import MagicMock

from mcp.server.fastmcp import FastMCP

from sdd_server.mcp.tools import validation as validation_module
from sdd_server.models.spec import SpecType
from sdd_server.models.validation import (
    ProjectValidationResult,
    SpecValidationResult,
    ValidationIssue,
    ValidationRule,
    ValidationRuleType,
    ValidationSeverity,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_tool_fn(name: str):
    app = FastMCP("test")
    validation_module.register_tools(app)
    return app._tool_manager._tools[name].fn


def _make_ctx(spec_validator):
    ctx = MagicMock()
    ctx.request_context.lifespan_context.spec_validator = spec_validator
    return ctx


def _make_validator(**kwargs) -> MagicMock:
    validator = MagicMock()
    for k, v in kwargs.items():
        setattr(validator, k, v)
    return validator


def _make_spec_result(
    spec_type: SpecType = SpecType.PRD,
    feature: str | None = None,
    is_valid: bool = True,
    error_count: int = 0,
    warning_count: int = 0,
    info_count: int = 0,
    issues: list | None = None,
) -> SpecValidationResult:
    return SpecValidationResult(
        spec_type=spec_type,
        feature=feature,
        is_valid=is_valid,
        issues=issues or [],
        error_count=error_count,
        warning_count=warning_count,
        info_count=info_count,
    )


# ---------------------------------------------------------------------------
# sdd_validate_spec
# ---------------------------------------------------------------------------


class TestSddValidateSpec:
    async def test_valid_spec_type_returns_formatted_string(self) -> None:
        fn = _get_tool_fn("sdd_validate_spec")
        result = _make_spec_result(spec_type=SpecType.PRD, is_valid=True)
        validator = _make_validator()
        validator.validate_spec_file.return_value = result
        ctx = _make_ctx(validator)

        output = await fn(ctx=ctx, spec_type="prd")

        assert isinstance(output, str)
        assert "prd" in output.lower() or "Valid" in output

    async def test_invalid_spec_type_returns_error_string(self) -> None:
        fn = _get_tool_fn("sdd_validate_spec")
        validator = _make_validator()
        ctx = _make_ctx(validator)

        output = await fn(ctx=ctx, spec_type="__invalid__")

        assert "Invalid" in output or "invalid" in output.lower()

    async def test_with_feature_passes_feature_to_validator(self) -> None:
        fn = _get_tool_fn("sdd_validate_spec")
        result = _make_spec_result(spec_type=SpecType.PRD, feature="auth", is_valid=False)
        validator = _make_validator()
        validator.validate_spec_file.return_value = result
        ctx = _make_ctx(validator)

        output = await fn(ctx=ctx, spec_type="prd", feature="auth")

        validator.validate_spec_file.assert_called_once_with(SpecType.PRD, "auth")
        assert isinstance(output, str)

    async def test_result_with_issues_includes_issue_info(self) -> None:
        fn = _get_tool_fn("sdd_validate_spec")
        issue = ValidationIssue(
            rule_id="test-rule",
            rule_name="Test Rule",
            severity=ValidationSeverity.ERROR,
            message="Section missing",
            spec_type=SpecType.PRD,
            suggestion="Add the section",
        )
        result = _make_spec_result(
            spec_type=SpecType.PRD,
            is_valid=False,
            error_count=1,
            issues=[issue],
        )
        validator = _make_validator()
        validator.validate_spec_file.return_value = result
        ctx = _make_ctx(validator)

        output = await fn(ctx=ctx, spec_type="prd")

        assert "Section missing" in output or "Test Rule" in output


# ---------------------------------------------------------------------------
# sdd_validate_feature
# ---------------------------------------------------------------------------


class TestSddValidateFeature:
    async def test_returns_formatted_string(self) -> None:
        fn = _get_tool_fn("sdd_validate_feature")
        results = [
            _make_spec_result(spec_type=SpecType.PRD, feature="auth", is_valid=True),
            _make_spec_result(spec_type=SpecType.ARCH, feature="auth", is_valid=True),
        ]
        validator = _make_validator()
        validator.validate_feature.return_value = results
        ctx = _make_ctx(validator)

        output = await fn(ctx=ctx, feature="auth")

        assert "auth" in output
        assert isinstance(output, str)

    async def test_status_shows_valid_when_no_errors(self) -> None:
        fn = _get_tool_fn("sdd_validate_feature")
        validator = _make_validator()
        validator.validate_feature.return_value = [
            _make_spec_result(spec_type=SpecType.PRD, feature="billing", error_count=0)
        ]
        ctx = _make_ctx(validator)

        output = await fn(ctx=ctx, feature="billing")

        assert "All valid" in output or "valid" in output.lower()

    async def test_status_shows_error_count_when_errors(self) -> None:
        fn = _get_tool_fn("sdd_validate_feature")
        validator = _make_validator()
        validator.validate_feature.return_value = [
            _make_spec_result(
                spec_type=SpecType.PRD, feature="payments", is_valid=False, error_count=2
            )
        ]
        ctx = _make_ctx(validator)

        output = await fn(ctx=ctx, feature="payments")

        assert "2" in output


# ---------------------------------------------------------------------------
# sdd_validate_project
# ---------------------------------------------------------------------------


class TestSddValidateProject:
    async def test_returns_formatted_string(self) -> None:
        fn = _get_tool_fn("sdd_validate_project")
        project_result = ProjectValidationResult(
            is_valid=True,
            spec_results=[_make_spec_result(spec_type=SpecType.PRD)],
            total_errors=0,
            total_warnings=0,
            total_infos=0,
        )
        validator = _make_validator()
        validator.validate_project.return_value = project_result
        ctx = _make_ctx(validator)

        output = await fn(ctx=ctx)

        assert isinstance(output, str)
        assert "Spec Validation" in output or "validation" in output.lower()

    async def test_include_features_false_passes_flag(self) -> None:
        fn = _get_tool_fn("sdd_validate_project")
        project_result = ProjectValidationResult(
            is_valid=True,
            total_errors=0,
            total_warnings=0,
            total_infos=0,
        )
        validator = _make_validator()
        validator.validate_project.return_value = project_result
        ctx = _make_ctx(validator)

        await fn(ctx=ctx, include_features=False)

        validator.validate_project.assert_called_once_with(include_features=False)

    async def test_project_with_errors_shows_failed_status(self) -> None:
        fn = _get_tool_fn("sdd_validate_project")
        project_result = ProjectValidationResult(
            is_valid=False,
            total_errors=3,
            total_warnings=1,
            total_infos=0,
        )
        validator = _make_validator()
        validator.validate_project.return_value = project_result
        ctx = _make_ctx(validator)

        output = await fn(ctx=ctx)

        assert "failed" in output.lower() or "Invalid" in output


# ---------------------------------------------------------------------------
# sdd_list_validation_rules
# ---------------------------------------------------------------------------


class TestSddListValidationRules:
    async def test_returns_rules_list_string(self) -> None:
        fn = _get_tool_fn("sdd_list_validation_rules")
        rules = [
            ValidationRule(
                rule_id="prd-001",
                name="PRD Title Required",
                description="PRD must have a title",
                rule_type=ValidationRuleType.REQUIRED_SECTION,
                spec_types=[SpecType.PRD],
                severity=ValidationSeverity.ERROR,
                section="title",
            )
        ]
        validator = _make_validator(rules=rules)
        ctx = _make_ctx(validator)

        output = await fn(ctx=ctx)

        assert "prd-001" in output or "PRD Title Required" in output

    async def test_filtered_by_spec_type(self) -> None:
        fn = _get_tool_fn("sdd_list_validation_rules")
        rules = [
            ValidationRule(
                rule_id="prd-001",
                name="PRD Rule",
                description="PRD rule",
                rule_type=ValidationRuleType.REQUIRED_SECTION,
                spec_types=[SpecType.PRD],
                severity=ValidationSeverity.ERROR,
            ),
            ValidationRule(
                rule_id="arch-001",
                name="Arch Rule",
                description="Arch rule",
                rule_type=ValidationRuleType.REQUIRED_SECTION,
                spec_types=[SpecType.ARCH],
                severity=ValidationSeverity.ERROR,
            ),
        ]
        validator = _make_validator(rules=rules)
        ctx = _make_ctx(validator)

        output = await fn(ctx=ctx, spec_type="prd")

        assert "prd-001" in output or "PRD Rule" in output

    async def test_invalid_spec_type_filter_returns_error(self) -> None:
        fn = _get_tool_fn("sdd_list_validation_rules")
        validator = _make_validator(rules=[])
        ctx = _make_ctx(validator)

        output = await fn(ctx=ctx, spec_type="__invalid__")

        assert "Invalid" in output or "invalid" in output.lower()


# ---------------------------------------------------------------------------
# sdd_add_validation_rule
# ---------------------------------------------------------------------------


class TestSddAddValidationRule:
    async def test_adds_rule_successfully(self) -> None:
        fn = _get_tool_fn("sdd_add_validation_rule")
        validator = _make_validator()
        ctx = _make_ctx(validator)

        output = await fn(
            ctx=ctx,
            rule_id="custom-001",
            name="My Custom Rule",
            description="Checks something",
            rule_type="required_section",
            spec_types="prd",
            severity="warning",
            section="my-section",
        )

        assert "custom-001" in output or "Added" in output or "added" in output.lower()
        validator.add_rule.assert_called_once()

    async def test_invalid_rule_type_returns_error(self) -> None:
        fn = _get_tool_fn("sdd_add_validation_rule")
        validator = _make_validator()
        ctx = _make_ctx(validator)

        output = await fn(
            ctx=ctx,
            rule_id="custom-002",
            name="My Rule",
            description="desc",
            rule_type="__bad_type__",
            spec_types="prd",
        )

        assert "Invalid" in output or "invalid" in output.lower()

    async def test_invalid_severity_returns_error(self) -> None:
        fn = _get_tool_fn("sdd_add_validation_rule")
        validator = _make_validator()
        ctx = _make_ctx(validator)

        output = await fn(
            ctx=ctx,
            rule_id="custom-003",
            name="My Rule",
            description="desc",
            rule_type="required_section",
            spec_types="prd",
            severity="__extreme__",
        )

        assert "Invalid" in output or "invalid" in output.lower()

    async def test_invalid_spec_type_in_list_returns_error(self) -> None:
        fn = _get_tool_fn("sdd_add_validation_rule")
        validator = _make_validator()
        ctx = _make_ctx(validator)

        output = await fn(
            ctx=ctx,
            rule_id="custom-004",
            name="My Rule",
            description="desc",
            rule_type="required_section",
            spec_types="__bad_spec__",
        )

        assert "Invalid" in output or "invalid" in output.lower()
