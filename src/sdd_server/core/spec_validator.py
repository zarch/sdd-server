"""Spec file validator — validates spec files against rules."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from sdd_server.infrastructure.filesystem import FileSystemClient
from sdd_server.models.spec import SpecType
from sdd_server.models.validation import (
    ProjectValidationResult,
    SpecValidationResult,
    ValidationIssue,
    ValidationRule,
    ValidationRuleType,
    ValidationSeverity,
    get_default_rules,
)
from sdd_server.utils.paths import SpecsPaths


class SpecValidator:
    """Validates spec files against a set of rules."""

    def __init__(
        self,
        project_root: Path,
        specs_dir: str = "specs",
        rules: list[ValidationRule] | None = None,
    ) -> None:
        self.project_root = project_root.resolve()
        self.paths = SpecsPaths(self.project_root, specs_dir)
        self._fs = FileSystemClient(self.project_root)
        self._rules = rules if rules is not None else get_default_rules()

    @property
    def rules(self) -> list[ValidationRule]:
        """Get all validation rules."""
        return self._rules

    def add_rule(self, rule: ValidationRule) -> None:
        """Add a custom validation rule."""
        self._rules.append(rule)

    def remove_rule(self, rule_id: str) -> bool:
        """Remove a rule by ID. Returns True if found and removed."""
        for i, rule in enumerate(self._rules):
            if rule.rule_id == rule_id:
                self._rules.pop(i)
                return True
        return False

    def get_rules_for_spec_type(self, spec_type: SpecType) -> list[ValidationRule]:
        """Get rules that apply to a specific spec type."""
        return [r for r in self._rules if r.enabled and spec_type in r.spec_types]

    def _find_section_line(self, content: str, section: str) -> int | None:
        """Find the line number of a section header."""
        pattern = rf"^#+\s*{re.escape(section)}\s*$"
        for i, line in enumerate(content.split("\n"), start=1):
            if re.match(pattern, line, re.IGNORECASE):
                return i
        return None

    def _check_required_section(
        self,
        content: str,
        rule: ValidationRule,
        spec_type: SpecType,
        feature: str | None,
    ) -> ValidationIssue | None:
        """Check if a required section exists."""
        if not rule.section:
            return None

        line_num = self._find_section_line(content, rule.section)
        if line_num is None:
            return ValidationIssue(
                rule_id=rule.rule_id,
                rule_name=rule.name,
                severity=rule.severity,
                message=f"Missing required section: '{rule.section}'",
                spec_type=spec_type,
                feature=feature,
                section=rule.section,
                suggestion=f"Add a '## {rule.section}' section to the document",
            )
        return None

    def _check_content_pattern(
        self,
        content: str,
        rule: ValidationRule,
        spec_type: SpecType,
        feature: str | None,
    ) -> ValidationIssue | None:
        """Check if content matches a pattern."""
        if not rule.pattern:
            return None

        if not re.search(rule.pattern, content, re.MULTILINE):
            return ValidationIssue(
                rule_id=rule.rule_id,
                rule_name=rule.name,
                severity=rule.severity,
                message=f"Content does not match expected pattern: {rule.description}",
                spec_type=spec_type,
                feature=feature,
                suggestion="Check the document format matches the expected structure",
            )
        return None

    def _check_format(
        self,
        content: str,
        rule: ValidationRule,
        spec_type: SpecType,
        feature: str | None,
    ) -> ValidationIssue | None:
        """Check format validity (e.g., YAML)."""
        if spec_type == SpecType.CONTEXT_HINTS and content.strip():
            try:
                yaml.safe_load(content)
            except yaml.YAMLError as e:
                return ValidationIssue(
                    rule_id=rule.rule_id,
                    rule_name=rule.name,
                    severity=rule.severity,
                    message=f"Invalid YAML format: {e}",
                    spec_type=spec_type,
                    feature=feature,
                    suggestion="Fix the YAML syntax in the context-hints file",
                )
        return None

    def validate_spec_content(
        self,
        content: str,
        spec_type: SpecType,
        feature: str | None = None,
    ) -> SpecValidationResult:
        """Validate spec content against all applicable rules."""
        issues: list[ValidationIssue] = []
        rules = self.get_rules_for_spec_type(spec_type)

        for rule in rules:
            issue: ValidationIssue | None = None

            if rule.rule_type == ValidationRuleType.REQUIRED_SECTION:
                issue = self._check_required_section(content, rule, spec_type, feature)
            elif rule.rule_type == ValidationRuleType.CONTENT_PATTERN:
                issue = self._check_content_pattern(content, rule, spec_type, feature)
            elif rule.rule_type == ValidationRuleType.FORMAT_CHECK:
                issue = self._check_format(content, rule, spec_type, feature)

            if issue:
                issues.append(issue)

        error_count = sum(1 for i in issues if i.severity == ValidationSeverity.ERROR)
        warning_count = sum(1 for i in issues if i.severity == ValidationSeverity.WARNING)
        info_count = sum(1 for i in issues if i.severity == ValidationSeverity.INFO)

        return SpecValidationResult(
            spec_type=spec_type,
            feature=feature,
            is_valid=error_count == 0,
            issues=issues,
            error_count=error_count,
            warning_count=warning_count,
            info_count=info_count,
        )

    def validate_spec_file(
        self,
        spec_type: SpecType,
        feature: str | None = None,
    ) -> SpecValidationResult:
        """Validate a spec file on disk."""
        spec_path: Path
        if feature:
            spec_path = self.paths.feature_spec_path(feature, spec_type)
        else:
            spec_path = self.paths.root_spec_path(spec_type)

        if not self._fs.file_exists(spec_path):
            return SpecValidationResult(
                spec_type=spec_type,
                feature=feature,
                is_valid=False,
                issues=[
                    ValidationIssue(
                        rule_id="file_exists",
                        rule_name="File Exists",
                        severity=ValidationSeverity.ERROR,
                        message=f"Spec file not found: {spec_path}",
                        spec_type=spec_type,
                        feature=feature,
                    )
                ],
                error_count=1,
                warning_count=0,
                info_count=0,
            )

        content = self._fs.read_file(spec_path)
        return self.validate_spec_content(content, spec_type, feature)

    def validate_feature(self, feature: str) -> list[SpecValidationResult]:
        """Validate all spec files for a feature."""
        results: list[SpecValidationResult] = []
        for spec_type in SpecType:
            results.append(self.validate_spec_file(spec_type, feature))
        return results

    def validate_project(
        self,
        include_features: bool = True,
    ) -> ProjectValidationResult:
        """Validate all specs in the project."""
        spec_results: list[SpecValidationResult] = []
        features_checked: list[str] = []

        # Validate root specs
        for spec_type in [SpecType.PRD, SpecType.ARCH, SpecType.TASKS]:
            result = self.validate_spec_file(spec_type, feature=None)
            spec_results.append(result)

        # Validate feature specs if requested
        if include_features and self._fs.directory_exists(self.paths.specs_dir):
            for item in self._fs.list_directory(self.paths.specs_dir):
                if item.is_dir() and not item.name.startswith("."):
                    feature = item.name
                    features_checked.append(feature)
                    for result in self.validate_feature(feature):
                        spec_results.append(result)

        total_errors = sum(r.error_count for r in spec_results)
        total_warnings = sum(r.warning_count for r in spec_results)
        total_infos = sum(r.info_count for r in spec_results)

        return ProjectValidationResult(
            is_valid=total_errors == 0,
            spec_results=spec_results,
            total_errors=total_errors,
            total_warnings=total_warnings,
            total_infos=total_infos,
            features_checked=features_checked,
        )
