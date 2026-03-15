"""Unit tests for RecipeGenerator."""

from datetime import datetime
from pathlib import Path

import pytest
import yaml

from sdd_server.core.recipe_generator import RecipeGenerationError, RecipeGenerator
from sdd_server.plugins.base import RoleResult, RoleStatus
from sdd_server.plugins.registry import PluginRegistry
from sdd_server.plugins.roles import BUILTIN_ROLES


@pytest.fixture
def registry_with_roles() -> PluginRegistry:
    """Create a registry with all builtin roles registered."""
    registry = PluginRegistry()
    for role_class in BUILTIN_ROLES:
        role = role_class()
        registry.register(role.metadata.name, role)
    return registry


@pytest.fixture
def generator(tmp_project: Path, registry_with_roles: PluginRegistry) -> RecipeGenerator:
    """Create a RecipeGenerator with a populated registry."""
    return RecipeGenerator(tmp_project, registry_with_roles)


class TestRecipeGeneratorBasic:
    """Basic RecipeGenerator tests."""

    def test_generate_recipe_creates_file(
        self,
        generator: RecipeGenerator,
        tmp_project: Path,
    ) -> None:
        """Test that generate_recipe creates a recipe file."""
        path = generator.generate_recipe(
            "architect",
            {"project_name": "TestProject", "description": "A test"},
        )

        assert path.exists()
        assert path.name == "architect.yaml"

    def test_generate_recipe_content_is_valid_yaml(
        self,
        generator: RecipeGenerator,
    ) -> None:
        """Test that generated recipe is valid YAML."""
        generator.generate_recipe(
            "architect",
            {"project_name": "TestProject"},
        )

        content = generator.render_recipe(
            "architect",
            {"project_name": "TestProject"},
        )

        # Should not raise
        data = yaml.safe_load(content)
        assert isinstance(data, dict)

    def test_generate_recipe_includes_project_name(
        self,
        generator: RecipeGenerator,
    ) -> None:
        """Test that project name is included in the recipe."""
        content = generator.render_recipe(
            "architect",
            {"project_name": "MyAwesomeProject"},
        )

        assert "MyAwesomeProject" in content

    def test_generate_recipe_skips_existing_by_default(
        self,
        generator: RecipeGenerator,
        tmp_project: Path,
    ) -> None:
        """Test that existing recipes are skipped by default."""
        # Create initial recipe
        path1 = generator.generate_recipe(
            "architect",
            {"project_name": "FirstProject"},
        )
        first_content = path1.read_text()

        # Try to generate again without overwrite
        path2 = generator.generate_recipe(
            "architect",
            {"project_name": "SecondProject"},
        )

        # Should be same file with same content
        assert path1 == path2
        assert path2.read_text() == first_content

    def test_generate_recipe_overwrites_when_flag_set(
        self,
        generator: RecipeGenerator,
        tmp_project: Path,
    ) -> None:
        """Test that overwrite flag replaces existing recipe."""
        generator.generate_recipe(
            "architect",
            {"project_name": "FirstProject"},
        )

        generator.generate_recipe(
            "architect",
            {"project_name": "SecondProject"},
            overwrite=True,
        )

        path = tmp_project / "specs" / "recipes" / "architect.yaml"
        assert "SecondProject" in path.read_text()

    def test_generate_recipe_unknown_role_raises(
        self,
        generator: RecipeGenerator,
    ) -> None:
        """Test that unknown role raises RecipeGenerationError."""
        with pytest.raises(RecipeGenerationError, match="Role not found"):
            generator.generate_recipe("unknown-role", {"project_name": "Test"})

    def test_render_recipe_returns_string(
        self,
        generator: RecipeGenerator,
    ) -> None:
        """Test that render_recipe returns rendered string."""
        content = generator.render_recipe(
            "architect",
            {"project_name": "TestProject"},
        )

        assert isinstance(content, str)
        assert len(content) > 0

    def test_render_recipe_does_not_write_file(
        self,
        generator: RecipeGenerator,
        tmp_project: Path,
    ) -> None:
        """Test that render_recipe doesn't create a file."""
        generator.render_recipe(
            "architect",
            {"project_name": "TestProject"},
        )

        path = tmp_project / "specs" / "recipes" / "architect.yaml"
        assert not path.exists()


class TestRecipeGeneratorAllRecipes:
    """Tests for generate_all_recipes."""

    def test_generate_all_recipes_creates_all(
        self,
        generator: RecipeGenerator,
    ) -> None:
        """Test that all role recipes are generated."""
        paths = generator.generate_all_recipes(
            {"project_name": "TestProject", "description": "A test"},
        )

        assert len(paths) == 11

        # All should exist
        for path in paths:
            assert path.exists()
            assert path.suffix == ".yaml"

    def test_generate_all_recipes_in_dependency_order(
        self,
        generator: RecipeGenerator,
    ) -> None:
        """Test that recipes are generated in dependency order."""
        paths = generator.generate_all_recipes(
            {"project_name": "TestProject"},
        )

        names = [p.stem for p in paths]

        # Spec linter should be first (no dependencies, priority 5)
        assert names[0] == "spec-linter"
        # Architect is second (depends on spec-linter)
        assert names[1] == "architect"

        # Product owner should be last (depends on qa, tech-writer, devops)
        assert names[-1] == "product-owner"

    def test_generate_all_recipes_valid_yaml(
        self,
        generator: RecipeGenerator,
    ) -> None:
        """Test that all generated recipes are valid YAML."""
        generator.generate_all_recipes({"project_name": "TestProject"})

        for role_name in [
            "architect",
            "ui-designer",
            "interface-designer",
            "security-analyst",
            "edge-case-analyst",
            "senior-developer",
        ]:
            content = generator.render_recipe(
                role_name,
                {"project_name": "TestProject"},
            )
            # Should not raise
            data = yaml.safe_load(content)
            assert data is not None


class TestRecipeGeneratorContext:
    """Tests for context building."""

    def test_get_recipe_context_includes_role_metadata(
        self,
        generator: RecipeGenerator,
    ) -> None:
        """Test that context includes role metadata."""
        context = generator.get_recipe_context(
            "architect",
            {"project_name": "TestProject"},
        )

        assert context["role_name"] == "architect"
        assert context["role_version"] == "1.0.0"
        assert context["role_dependencies"] == ["spec-linter"]

    def test_get_recipe_context_includes_date(
        self,
        generator: RecipeGenerator,
    ) -> None:
        """Test that context includes current date."""
        context = generator.get_recipe_context(
            "architect",
            {"project_name": "TestProject"},
        )

        assert "date" in context
        assert "timestamp" in context

    def test_get_recipe_context_with_previous_results(
        self,
        generator: RecipeGenerator,
    ) -> None:
        """Test that context includes previous results."""
        # Create a mock result from architect
        architect_result = RoleResult(
            role="architect",
            status=RoleStatus.COMPLETED,
            success=True,
            output="Architecture reviewed",
            issues=["Issue 1"],
            suggestions=["Suggestion 1"],
            started_at=datetime.now(),
        )

        previous = {"architect": architect_result}

        # Get context for security-analyst (which depends on architect)
        context = generator.get_recipe_context(
            "security-analyst",
            {"project_name": "TestProject"},
            previous_results=previous,
        )

        # Should have dependency results
        assert "dependency_results" in context
        assert "architect" in context["dependency_results"]
        assert context["dependency_results"]["architect"]["success"] is True

        # Should have aggregated issues and suggestions
        assert "Issue 1" in context["previous_issues"]
        assert "Suggestion 1" in context["previous_suggestions"]

    def test_get_recipe_context_no_dependencies(
        self,
        generator: RecipeGenerator,
    ) -> None:
        """Test context for role with no dependencies."""
        context = generator.get_recipe_context(
            "architect",
            {"project_name": "TestProject"},
            previous_results={},
        )

        assert context["dependency_results"] == {}
        assert context["previous_issues"] == []
        assert context["previous_suggestions"] == []


class TestRecipeGeneratorValidation:
    """Tests for recipe validation."""

    def test_validate_recipe_ok(
        self,
        generator: RecipeGenerator,
    ) -> None:
        """Test validation of a valid recipe."""
        generator.generate_recipe("architect", {"project_name": "TestProject"})

        issues = generator.validate_recipe("architect")

        assert issues == []

    def test_validate_recipe_missing_file(
        self,
        generator: RecipeGenerator,
    ) -> None:
        """Test validation of missing recipe file."""
        issues = generator.validate_recipe("architect")

        assert len(issues) == 1
        assert "missing" in issues[0].lower()

    def test_validate_all_recipes(
        self,
        generator: RecipeGenerator,
    ) -> None:
        """Test validation of all recipes."""
        generator.generate_all_recipes({"project_name": "TestProject"})

        results = generator.validate_all_recipes()

        # All should be valid
        for role_name, issues in results.items():
            assert issues == [], f"{role_name} has issues: {issues}"


class TestRecipeGeneratorErrorHandling:
    """Tests for error handling."""

    def test_render_recipe_unknown_role_raises(
        self,
        generator: RecipeGenerator,
    ) -> None:
        """Test that render_recipe raises for unknown role."""
        with pytest.raises(RecipeGenerationError, match="Role not found"):
            generator.render_recipe("unknown", {"project_name": "Test"})

    def test_get_recipe_context_unknown_role_raises(
        self,
        generator: RecipeGenerator,
    ) -> None:
        """Test that get_recipe_context raises for unknown role."""
        with pytest.raises(RecipeGenerationError, match="Role not found"):
            generator.get_recipe_context("unknown", {"project_name": "Test"})


class TestRecipeGeneratorIntegration:
    """Integration tests with registry."""

    def test_works_with_empty_registry(
        self,
        tmp_project: Path,
    ) -> None:
        """Test that generator works with empty registry (but can't generate)."""
        registry = PluginRegistry()
        generator = RecipeGenerator(tmp_project, registry)

        with pytest.raises(RecipeGenerationError, match="Role not found"):
            generator.generate_recipe("architect", {"project_name": "Test"})

    def test_works_with_single_role(
        self,
        tmp_project: Path,
    ) -> None:
        """Test generator with two registered roles (spec-linter + architect)."""
        from sdd_server.plugins.roles.architect import ArchitectRole
        from sdd_server.plugins.roles.spec_linter import SpecLinterRole

        registry = PluginRegistry()
        linter = SpecLinterRole()
        registry.register(linter.metadata.name, linter)
        role = ArchitectRole()
        registry.register(role.metadata.name, role)

        generator = RecipeGenerator(tmp_project, registry)

        path = generator.generate_recipe("architect", {"project_name": "Test"})
        assert path.exists()

        # Can't generate for unregistered roles
        with pytest.raises(RecipeGenerationError, match="Role not found"):
            generator.generate_recipe("security-analyst", {"project_name": "Test"})
