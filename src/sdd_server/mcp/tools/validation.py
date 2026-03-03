"""MCP tools for spec validation."""

from __future__ import annotations

from collections import defaultdict

from mcp.server.fastmcp import Context, FastMCP

from sdd_server.core.spec_validator import SpecValidator
from sdd_server.models.spec import SpecType
from sdd_server.models.validation import (
    ProjectValidationResult,
    SpecValidationResult,
    ValidationIssue,
    ValidationRule,
    ValidationSeverity,
)


def _format_severity_icon(severity: ValidationSeverity) -> str:
    """Get an icon for a severity level."""
    icons = {
        ValidationSeverity.ERROR: "❌",
        ValidationSeverity.WARNING: "⚠️",
        ValidationSeverity.INFO: "💡",
    }
    return icons.get(severity, "•")


def _format_issue(issue: ValidationIssue) -> str:
    """Format a single validation issue for display."""
    icon = _format_severity_icon(issue.severity)
    location = f"{issue.spec_type.value}"
    if issue.feature:
        location += f"/{issue.feature}"
    if issue.section:
        location += f" (section: {issue.section})"

    lines = [f"{icon} **{issue.rule_name}** [{issue.severity.value.upper()}]"]
    lines.append(f"   Location: {location}")
    lines.append(f"   {issue.message}")
    if issue.suggestion:
        lines.append(f"   💡 Suggestion: {issue.suggestion}")
    return "\n".join(lines)


def _format_spec_result(result: SpecValidationResult) -> str:
    """Format a spec validation result for display."""
    location = result.spec_type.value
    if result.feature:
        location = f"{result.feature}/{location}"

    status = "✅ Valid" if result.is_valid else "❌ Invalid"
    lines = [f"### {location} — {status}"]

    if result.issues:
        counts = []
        if result.error_count:
            counts.append(f"{result.error_count} error(s)")
        if result.warning_count:
            counts.append(f"{result.warning_count} warning(s)")
        if result.info_count:
            counts.append(f"{result.info_count} info")
        lines.append(f"**Issues:** {', '.join(counts)}")
        lines.append("")
        for issue in result.issues:
            lines.append(_format_issue(issue))

    return "\n".join(lines)


def _format_project_result(result: ProjectValidationResult) -> str:
    """Format a project validation result for display."""
    status = "✅ All specs valid" if result.is_valid else "❌ Validation failed"
    lines = [
        "# Spec Validation Results",
        "",
        f"**Status:** {status}",
        f"**Total Errors:** {result.total_errors}",
        f"**Total Warnings:** {result.total_warnings}",
        f"**Total Info:** {result.total_infos}",
    ]

    if result.features_checked:
        lines.append(f"**Features Checked:** {', '.join(result.features_checked)}")

    lines.append("")
    lines.append("---")
    lines.append("")

    # Group results by feature
    root_results = [r for r in result.spec_results if not r.feature]
    feature_results = [r for r in result.spec_results if r.feature]

    if root_results:
        lines.append("## Root Specs")
        lines.append("")
        for res in root_results:
            if res.error_count or res.warning_count or not res.is_valid:
                lines.append(_format_spec_result(res))
                lines.append("")

    if feature_results:
        lines.append("## Feature Specs")
        lines.append("")
        features = sorted(set(r.feature for r in feature_results if r.feature))
        for feature in features:
            lines.append(f"### Feature: {feature}")
            for res in feature_results:
                if res.feature == feature and (
                    res.error_count or res.warning_count or not res.is_valid
                ):
                    lines.append(_format_spec_result(res))
                    lines.append("")

    return "\n".join(lines)


def register_tools(server: FastMCP) -> None:
    """Register validation tools with the MCP server."""

    @server.tool(
        name="sdd_validate_spec",
        description="Validate a single spec file against validation rules",
    )
    async def validate_spec(
        ctx: Context,
        spec_type: str,
        feature: str | None = None,
    ) -> str:
        """Validate a single spec file.

        Args:
            spec_type: Type of spec to validate (prd, arch, tasks, context-hints)
            feature: Feature name for feature-specific specs (None for root specs)

        Returns:
            Validation result with any issues found
        """
        try:
            spec_type_enum = SpecType(spec_type.lower())
        except ValueError:
            valid = ", ".join(t.value for t in SpecType)
            return f"❌ Invalid spec_type '{spec_type}'. Valid types: {valid}"

        validator: SpecValidator = ctx.request_context.lifespan_context.spec_validator
        result = validator.validate_spec_file(spec_type_enum, feature)
        return _format_spec_result(result)

    @server.tool(
        name="sdd_validate_feature",
        description="Validate all spec files for a feature",
    )
    async def validate_feature(
        ctx: Context,
        feature: str,
    ) -> str:
        """Validate all spec files for a feature.

        Args:
            feature: Feature name to validate

        Returns:
            Validation results for all feature specs
        """
        validator: SpecValidator = ctx.request_context.lifespan_context.spec_validator
        results = validator.validate_feature(feature)

        lines = [f"# Validation Results: {feature}", ""]
        for result in results:
            lines.append(_format_spec_result(result))
            lines.append("")

        error_count = sum(r.error_count for r in results)
        status = "✅ All valid" if error_count == 0 else f"❌ {error_count} error(s)"
        lines.insert(1, f"**Status:** {status}")

        return "\n".join(lines)

    @server.tool(
        name="sdd_validate_project",
        description="Validate all specs in the project (root and features)",
    )
    async def validate_project(
        ctx: Context,
        include_features: bool = True,
    ) -> str:
        """Validate all specs in the project.

        Args:
            include_features: Whether to include feature specs in validation

        Returns:
            Complete validation report for the project
        """
        validator: SpecValidator = ctx.request_context.lifespan_context.spec_validator
        result = validator.validate_project(include_features=include_features)
        return _format_project_result(result)

    @server.tool(
        name="sdd_list_validation_rules",
        description="List all available validation rules",
    )
    async def list_validation_rules(
        ctx: Context,
        spec_type: str | None = None,
    ) -> str:
        """List validation rules, optionally filtered by spec type.

        Args:
            spec_type: Filter to rules for this spec type (optional)

        Returns:
            List of validation rules
        """
        validator: SpecValidator = ctx.request_context.lifespan_context.spec_validator
        rules = validator.rules

        if spec_type:
            try:
                spec_type_enum = SpecType(spec_type.lower())
                rules = [r for r in rules if spec_type_enum in r.spec_types]
            except ValueError:
                valid = ", ".join(t.value for t in SpecType)
                return f"❌ Invalid spec_type '{spec_type}'. Valid types: {valid}"

        lines = ["# Validation Rules", ""]
        lines.append(f"**Total Rules:** {len(rules)}")
        lines.append("")

        # Group by spec type
        by_spec: dict[str, list[ValidationRule]] = defaultdict(list)
        for rule in rules:
            for st in rule.spec_types:
                by_spec[st.value].append(rule)

        for st, st_rules in sorted(by_spec.items()):
            lines.append(f"## {st.upper()}")
            lines.append("")
            for rule in st_rules:
                icon = _format_severity_icon(rule.severity)
                lines.append(f"### {icon} {rule.name} (`{rule.rule_id}`)")
                lines.append(f"- **Type:** {rule.rule_type.value}")
                lines.append(f"- **Severity:** {rule.severity.value}")
                lines.append(f"- **Description:** {rule.description}")
                if rule.section:
                    lines.append(f"- **Section:** {rule.section}")
                if rule.pattern:
                    lines.append(f"- **Pattern:** `{rule.pattern}`")
                lines.append("")

        return "\n".join(lines)

    @server.tool(
        name="sdd_add_validation_rule",
        description="Add a custom validation rule",
    )
    async def add_validation_rule(
        ctx: Context,
        rule_id: str,
        name: str,
        description: str,
        rule_type: str,
        spec_types: str,
        severity: str = "error",
        section: str | None = None,
        pattern: str | None = None,
    ) -> str:
        """Add a custom validation rule.

        Args:
            rule_id: Unique identifier for the rule (e.g., 'custom_prd_section')
            name: Human-readable rule name
            description: Description of what the rule checks
            rule_type: Type of rule (required_section, content_pattern, format_check)
            spec_types: Comma-separated list of spec types this applies to
            severity: Severity level (error, warning, info)
            section: Section name for required_section rules
            pattern: Regex pattern for content_pattern rules

        Returns:
            Confirmation of rule addition
        """
        from sdd_server.models.validation import ValidationRuleType

        try:
            rule_type_enum = ValidationRuleType(rule_type.lower())
        except ValueError:
            valid = ", ".join(t.value for t in ValidationRuleType)
            return f"❌ Invalid rule_type '{rule_type}'. Valid types: {valid}"

        try:
            severity_enum = ValidationSeverity(severity.lower())
        except ValueError:
            valid = ", ".join(s.value for s in ValidationSeverity)
            return f"❌ Invalid severity '{severity}'. Valid values: {valid}"

        # Parse spec types
        spec_type_list = []
        for st in spec_types.split(","):
            st = st.strip()
            try:
                spec_type_list.append(SpecType(st.lower()))
            except ValueError:
                valid = ", ".join(t.value for t in SpecType)
                return f"❌ Invalid spec_type '{st}'. Valid types: {valid}"

        if not spec_type_list:
            return "❌ At least one spec_type is required"

        rule = ValidationRule(
            rule_id=rule_id,
            name=name,
            description=description,
            rule_type=rule_type_enum,
            spec_types=spec_type_list,
            severity=severity_enum,
            section=section,
            pattern=pattern,
        )

        validator: SpecValidator = ctx.request_context.lifespan_context.spec_validator
        validator.add_rule(rule)

        return f"✅ Added validation rule '{rule_id}' ({rule_type}) for {spec_types}"


def reg_validation(server: FastMCP) -> None:
    """Register validation tools with the MCP server."""
    register_tools(server)
