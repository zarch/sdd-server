"""Tests for SpecValidator."""

from __future__ import annotations

from pathlib import Path

from sdd_server.core.spec_validator import SpecValidator
from sdd_server.models.spec import SpecType
from sdd_server.models.validation import (
    ValidationRule,
    ValidationRuleType,
    ValidationSeverity,
)


class TestSpecValidatorInit:
    """Tests for SpecValidator initialization."""

    def test_init_with_defaults(self, tmp_path: Path):
        """Test initialization with default rules."""
        validator = SpecValidator(tmp_path)
        assert validator.project_root == tmp_path.resolve()
        assert len(validator.rules) > 0

    def test_init_with_custom_rules(self, tmp_path: Path):
        """Test initialization with custom rules."""
        custom_rules = [
            ValidationRule(
                rule_id="custom",
                name="Custom Rule",
                description="A custom rule",
                rule_type=ValidationRuleType.CUSTOM,
                spec_types=[SpecType.PRD],
            )
        ]
        validator = SpecValidator(tmp_path, rules=custom_rules)
        assert len(validator.rules) == 1
        assert validator.rules[0].rule_id == "custom"


class TestSpecValidatorRules:
    """Tests for rule management."""

    def test_add_rule(self, tmp_path: Path):
        """Test adding a rule."""
        validator = SpecValidator(tmp_path)
        initial_count = len(validator.rules)
        new_rule = ValidationRule(
            rule_id="new_rule",
            name="New Rule",
            description="A new rule",
            rule_type=ValidationRuleType.CUSTOM,
            spec_types=[SpecType.PRD],
        )
        validator.add_rule(new_rule)
        assert len(validator.rules) == initial_count + 1

    def test_remove_rule_existing(self, tmp_path: Path):
        """Test removing an existing rule."""
        validator = SpecValidator(tmp_path)
        # Get the ID of the first rule
        rule_id = validator.rules[0].rule_id
        result = validator.remove_rule(rule_id)
        assert result is True
        # Verify it's gone
        remaining_ids = [r.rule_id for r in validator.rules]
        assert rule_id not in remaining_ids

    def test_remove_rule_nonexistent(self, tmp_path: Path):
        """Test removing a non-existent rule."""
        validator = SpecValidator(tmp_path)
        result = validator.remove_rule("nonexistent_rule")
        assert result is False

    def test_get_rules_for_spec_type(self, tmp_path: Path):
        """Test filtering rules by spec type."""
        validator = SpecValidator(tmp_path)
        prd_rules = validator.get_rules_for_spec_type(SpecType.PRD)
        for rule in prd_rules:
            assert SpecType.PRD in rule.spec_types
            assert rule.enabled


class TestSpecValidatorSections:
    """Tests for section validation."""

    def test_find_section_line_exists(self, tmp_path: Path):
        """Test finding an existing section."""
        content = """# Title

## Overview

Some content here.

## Features

More content.
"""
        validator = SpecValidator(tmp_path)
        line_num = validator._find_section_line(content, "Overview")
        assert line_num == 3

    def test_find_section_line_case_insensitive(self, tmp_path: Path):
        """Test section finding is case insensitive."""
        content = """# Title

## overview

Content.
"""
        validator = SpecValidator(tmp_path)
        line_num = validator._find_section_line(content, "OVERVIEW")
        assert line_num == 3

    def test_find_section_line_not_found(self, tmp_path: Path):
        """Test when section is not found."""
        content = """# Title

## Other Section
"""
        validator = SpecValidator(tmp_path)
        line_num = validator._find_section_line(content, "Missing Section")
        assert line_num is None

    def test_find_section_with_different_levels(self, tmp_path: Path):
        """Test finding sections with different heading levels."""
        content = """# Main

### Subsection

#### Deep Section
"""
        validator = SpecValidator(tmp_path)
        assert validator._find_section_line(content, "Subsection") == 3
        assert validator._find_section_line(content, "Deep Section") == 5


class TestSpecValidatorRequiredSection:
    """Tests for required section validation."""

    def test_required_section_present(self, tmp_path: Path):
        """Test when required section is present."""
        rule = ValidationRule(
            rule_id="test",
            name="Test",
            description="Test",
            rule_type=ValidationRuleType.REQUIRED_SECTION,
            spec_types=[SpecType.PRD],
            section="Overview",
        )
        content = "# Title\n\n## Overview\n\nContent."
        validator = SpecValidator(tmp_path)
        issue = validator._check_required_section(content, rule, SpecType.PRD, None)
        assert issue is None

    def test_required_section_missing(self, tmp_path: Path):
        """Test when required section is missing."""
        rule = ValidationRule(
            rule_id="test",
            name="Test",
            description="Test",
            rule_type=ValidationRuleType.REQUIRED_SECTION,
            spec_types=[SpecType.PRD],
            section="Overview",
            severity=ValidationSeverity.ERROR,
        )
        content = "# Title\n\n## Other\n\nContent."
        validator = SpecValidator(tmp_path)
        issue = validator._check_required_section(content, rule, SpecType.PRD, None)
        assert issue is not None
        assert issue.severity == ValidationSeverity.ERROR
        assert "Missing" in issue.message


class TestSpecValidatorContentPattern:
    """Tests for content pattern validation."""

    def test_pattern_matches(self, tmp_path: Path):
        """Test when pattern matches."""
        rule = ValidationRule(
            rule_id="test",
            name="Test",
            description="Test",
            rule_type=ValidationRuleType.CONTENT_PATTERN,
            spec_types=[SpecType.PRD],
            pattern=r"^#\s*Product Requirements",
        )
        content = "# Product Requirements Document\n\nContent."
        validator = SpecValidator(tmp_path)
        issue = validator._check_content_pattern(content, rule, SpecType.PRD, None)
        assert issue is None

    def test_pattern_does_not_match(self, tmp_path: Path):
        """Test when pattern does not match."""
        rule = ValidationRule(
            rule_id="test",
            name="Test",
            description="Test",
            rule_type=ValidationRuleType.CONTENT_PATTERN,
            spec_types=[SpecType.PRD],
            pattern=r"^#\s*Product Requirements",
        )
        content = "# Some Other Title\n\nContent."
        validator = SpecValidator(tmp_path)
        issue = validator._check_content_pattern(content, rule, SpecType.PRD, None)
        assert issue is not None
        assert "does not match" in issue.message


class TestSpecValidatorFormat:
    """Tests for format validation."""

    def test_valid_yaml_format(self, tmp_path: Path):
        """Test valid YAML format."""
        rule = ValidationRule(
            rule_id="yaml",
            name="YAML Check",
            description="Check YAML format",
            rule_type=ValidationRuleType.FORMAT_CHECK,
            spec_types=[SpecType.CONTEXT_HINTS],
        )
        content = "key: value\nlist:\n  - item1\n  - item2"
        validator = SpecValidator(tmp_path)
        issue = validator._check_format(content, rule, SpecType.CONTEXT_HINTS, None)
        assert issue is None

    def test_invalid_yaml_format(self, tmp_path: Path):
        """Test invalid YAML format."""
        rule = ValidationRule(
            rule_id="yaml",
            name="YAML Check",
            description="Check YAML format",
            rule_type=ValidationRuleType.FORMAT_CHECK,
            spec_types=[SpecType.CONTEXT_HINTS],
        )
        # This is actually invalid YAML - unbalanced brackets
        content = "key: [unclosed\nanother: value"
        validator = SpecValidator(tmp_path)
        issue = validator._check_format(content, rule, SpecType.CONTEXT_HINTS, None)
        assert issue is not None
        assert "Invalid YAML" in issue.message

    def test_empty_yaml_is_valid(self, tmp_path: Path):
        """Test that empty content is valid."""
        rule = ValidationRule(
            rule_id="yaml",
            name="YAML Check",
            description="Check YAML format",
            rule_type=ValidationRuleType.FORMAT_CHECK,
            spec_types=[SpecType.CONTEXT_HINTS],
        )
        validator = SpecValidator(tmp_path)
        issue = validator._check_format("", rule, SpecType.CONTEXT_HINTS, None)
        assert issue is None

        issue = validator._check_format("   \n  ", rule, SpecType.CONTEXT_HINTS, None)
        assert issue is None


class TestSpecValidatorValidateSpecContent:
    """Tests for validate_spec_content."""

    def test_valid_prd_content(self, tmp_path: Path):
        """Test validating valid PRD content."""
        content = """# Product Requirements Document

**Project:** Test

## Executive Summary

This is a summary.

## Features

Some features.

## Development Workflow

Workflow here.
"""
        validator = SpecValidator(tmp_path)
        result = validator.validate_spec_content(content, SpecType.PRD)
        # Should have warnings but no errors (some sections are warnings)
        assert result.is_valid is True or result.error_count == 0

    def test_invalid_prd_missing_title(self, tmp_path: Path):
        """Test validating PRD without proper title."""
        content = """# Some Other Title

## Executive Summary

Summary here.
"""
        validator = SpecValidator(tmp_path)
        result = validator.validate_spec_content(content, SpecType.PRD)
        assert result.is_valid is False
        assert result.error_count > 0
        # Check that title error is present
        rule_ids = [i.rule_id for i in result.issues]
        assert "prd_title" in rule_ids

    def test_invalid_prd_missing_sections(self, tmp_path: Path):
        """Test validating PRD missing required sections."""
        content = """# Product Requirements Document

Some content but no sections.
"""
        validator = SpecValidator(tmp_path)
        result = validator.validate_spec_content(content, SpecType.PRD)
        assert result.is_valid is False
        assert result.error_count >= 2  # Missing exec summary and features

    def test_valid_arch_content(self, tmp_path: Path):
        """Test validating valid architecture content."""
        content = """# Architecture Document

**Project:** Test

## Overview

Overview here.

## Tech Stack

| Layer | Tech |
|-------|------|
| Lang | Python |

## Components

Components here.
"""
        validator = SpecValidator(tmp_path)
        result = validator.validate_spec_content(content, SpecType.ARCH)
        assert result.error_count == 0

    def test_valid_tasks_content(self, tmp_path: Path):
        """Test validating valid tasks content."""
        content = """# Tasks

**Project:** Test

## Pending

| ID | Title | Priority |
|----|-------|----------|
| t0000001 | Do thing | high |

## In Progress

| ID | Title |
|----|-------|

## Completed

| ID | Title |
|----|-------|
"""
        validator = SpecValidator(tmp_path)
        result = validator.validate_spec_content(content, SpecType.TASKS)
        assert result.error_count == 0


class TestSpecValidatorValidateSpecFile:
    """Tests for validate_spec_file."""

    def test_validate_existing_file(self, tmp_path: Path):
        """Test validating an existing spec file."""
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()
        prd_file = specs_dir / "prd.md"
        prd_file.write_text(
            """# Product Requirements Document

## Executive Summary

Summary.

## Features

Features.
"""
        )

        validator = SpecValidator(tmp_path)
        result = validator.validate_spec_file(SpecType.PRD)
        assert result.spec_type == SpecType.PRD
        assert result.feature is None

    def test_validate_missing_file(self, tmp_path: Path):
        """Test validating a missing spec file."""
        validator = SpecValidator(tmp_path)
        result = validator.validate_spec_file(SpecType.PRD)
        assert result.is_valid is False
        assert result.error_count == 1
        assert "not found" in result.issues[0].message.lower()

    def test_validate_feature_spec(self, tmp_path: Path):
        """Test validating a feature spec file."""
        specs_dir = tmp_path / "specs"
        feature_dir = specs_dir / "my-feature"
        feature_dir.mkdir(parents=True)
        arch_file = feature_dir / "arch.md"
        arch_file.write_text(
            """# Architecture Document: my-feature

## Overview

Overview.

## Tech Stack

Python.
"""
        )

        validator = SpecValidator(tmp_path)
        result = validator.validate_spec_file(SpecType.ARCH, feature="my-feature")
        assert result.feature == "my-feature"
        assert result.spec_type == SpecType.ARCH


class TestSpecValidatorValidateFeature:
    """Tests for validate_feature."""

    def test_validate_feature_all_specs(self, tmp_path: Path):
        """Test validating all specs for a feature."""
        specs_dir = tmp_path / "specs"
        feature_dir = specs_dir / "test-feature"
        feature_dir.mkdir(parents=True)

        # Create all spec files
        (feature_dir / "prd.md").write_text(
            "# Product Requirements Document\n\n## Executive Summary\n\nSum.\n\n## Features\n\nFeat."
        )
        (feature_dir / "arch.md").write_text(
            "# Architecture Document\n\n## Overview\n\nOv.\n\n## Tech Stack\n\nTS."
        )
        (feature_dir / "tasks.md").write_text(
            "# Tasks\n\n## Pending\n\n| ID | Title |\n|----|-------|"
        )
        (feature_dir / ".context-hints").write_text("key: value")

        validator = SpecValidator(tmp_path)
        results = validator.validate_feature("test-feature")
        assert len(results) == 4  # One for each spec type
        spec_types = {r.spec_type for r in results}
        assert SpecType.PRD in spec_types
        assert SpecType.ARCH in spec_types
        assert SpecType.TASKS in spec_types
        assert SpecType.CONTEXT_HINTS in spec_types


class TestSpecValidatorValidateProject:
    """Tests for validate_project."""

    def test_validate_project_root_only(self, tmp_path: Path):
        """Test validating only root specs."""
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()

        (specs_dir / "prd.md").write_text(
            "# Product Requirements Document\n\n## Executive Summary\n\nSum.\n\n## Features\n\nFeat."
        )
        (specs_dir / "arch.md").write_text(
            "# Architecture Document\n\n## Overview\n\nOv.\n\n## Tech Stack\n\nTS."
        )
        (specs_dir / "tasks.md").write_text(
            "# Tasks\n\n## Pending\n\n| ID | Title |\n|----|-------|"
        )

        validator = SpecValidator(tmp_path)
        result = validator.validate_project(include_features=False)
        assert result.is_valid is True
        assert len(result.features_checked) == 0
        # Should have at least 3 results (PRD, ARCH, TASKS)
        assert len(result.spec_results) >= 3

    def test_validate_project_with_features(self, tmp_path: Path):
        """Test validating project with features."""
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()

        # Root specs
        (specs_dir / "prd.md").write_text(
            "# Product Requirements Document\n\n## Executive Summary\n\nSum.\n\n## Features\n\nFeat."
        )
        (specs_dir / "arch.md").write_text(
            "# Architecture Document\n\n## Overview\n\nOv.\n\n## Tech Stack\n\nTS."
        )
        (specs_dir / "tasks.md").write_text(
            "# Tasks\n\n## Pending\n\n| ID | Title |\n|----|-------|"
        )

        # Feature specs
        feature_dir = specs_dir / "auth"
        feature_dir.mkdir()
        (feature_dir / "prd.md").write_text(
            "# Product Requirements Document: auth\n\n## Executive Summary\n\nSum.\n\n## Features\n\nFeat."
        )

        validator = SpecValidator(tmp_path)
        result = validator.validate_project(include_features=True)
        assert "auth" in result.features_checked
        # Should have root specs + feature specs
        assert len(result.spec_results) >= 4

    def test_validate_project_empty(self, tmp_path: Path):
        """Test validating empty project."""
        validator = SpecValidator(tmp_path)
        result = validator.validate_project()
        # Should fail because root specs don't exist
        assert result.is_valid is False
        assert result.total_errors >= 3  # Missing PRD, ARCH, TASKS

    def test_validate_project_counts_totals(self, tmp_path: Path):
        """Test that project validation counts totals correctly."""
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()

        (specs_dir / "prd.md").write_text(
            "# Product Requirements Document\n\n## Executive Summary\n\nSum.\n\n## Features\n\nFeat."
        )
        (specs_dir / "arch.md").write_text(
            "# Architecture Document\n\n## Overview\n\nOv.\n\n## Tech Stack\n\nTS."
        )
        (specs_dir / "tasks.md").write_text(
            "# Tasks\n\n## Pending\n\n| ID | Title |\n|----|-------|"
        )

        validator = SpecValidator(tmp_path)
        result = validator.validate_project()

        # Calculate totals from spec_results
        calc_errors = sum(r.error_count for r in result.spec_results)
        calc_warnings = sum(r.warning_count for r in result.spec_results)
        calc_infos = sum(r.info_count for r in result.spec_results)

        assert result.total_errors == calc_errors
        assert result.total_warnings == calc_warnings
        assert result.total_infos == calc_infos
