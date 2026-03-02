"""Unit tests for RecipeManager."""

from pathlib import Path

import pytest
import yaml

from sdd_server.core.recipe_manager import ROLES, RecipeManager


def test_render_recipe_returns_valid_yaml(tmp_project: Path) -> None:
    mgr = RecipeManager(tmp_project)
    content = mgr.render_recipe("architect", {"project_name": "test-proj", "description": "desc"})
    data = yaml.safe_load(content)
    assert data["version"] == "1.0.0"
    assert "test-proj" in data["title"]
    assert data["instructions"]


def test_render_recipe_unknown_role(tmp_project: Path) -> None:
    mgr = RecipeManager(tmp_project)
    with pytest.raises(ValueError, match="Unknown role"):
        mgr.render_recipe("wizard", {"project_name": "x"})


def test_write_recipe_creates_yaml_file(tmp_project: Path) -> None:
    mgr = RecipeManager(tmp_project)
    (tmp_project / "specs" / "recipes").mkdir(parents=True, exist_ok=True)
    path = mgr.write_recipe("architect", {"project_name": "p", "description": "d"})
    assert path.exists()
    assert path.suffix == ".yaml"


def test_write_recipe_skips_existing_by_default(tmp_project: Path) -> None:
    mgr = RecipeManager(tmp_project)
    (tmp_project / "specs" / "recipes").mkdir(parents=True, exist_ok=True)
    mgr.write_recipe("architect", {"project_name": "p1", "description": ""})
    first_content = (tmp_project / "specs" / "recipes" / "architect.yaml").read_text()

    # Write again without overwrite — should be skipped
    mgr.write_recipe("architect", {"project_name": "p2", "description": ""})
    assert (tmp_project / "specs" / "recipes" / "architect.yaml").read_text() == first_content


def test_write_recipe_overwrites_when_flag_set(tmp_project: Path) -> None:
    mgr = RecipeManager(tmp_project)
    (tmp_project / "specs" / "recipes").mkdir(parents=True, exist_ok=True)
    mgr.write_recipe("architect", {"project_name": "p1", "description": ""})
    mgr.write_recipe("architect", {"project_name": "p2", "description": ""}, overwrite=True)
    content = (tmp_project / "specs" / "recipes" / "architect.yaml").read_text()
    assert "p2" in content


def test_init_recipes_creates_all_roles(tmp_project: Path) -> None:
    mgr = RecipeManager(tmp_project)
    written = mgr.init_recipes("my-project", "A project")
    assert len(written) == len(ROLES)
    for path in written:
        assert path.exists()
        data = yaml.safe_load(path.read_text())
        assert data["version"] == "1.0.0"
        assert data["instructions"]


def test_list_recipes(tmp_project: Path) -> None:
    mgr = RecipeManager(tmp_project)
    mgr.init_recipes("proj")
    names = mgr.list_recipes()
    for role in ROLES:
        assert role in names


def test_validate_recipe_ok(tmp_project: Path) -> None:
    mgr = RecipeManager(tmp_project)
    mgr.init_recipes("proj")
    issues = mgr.validate_recipe("architect")
    assert issues == []


def test_validate_recipe_missing(tmp_project: Path) -> None:
    mgr = RecipeManager(tmp_project)
    issues = mgr.validate_recipe("architect")
    assert any("missing" in i.lower() for i in issues)


def test_all_roles_have_required_fields(tmp_project: Path) -> None:
    mgr = RecipeManager(tmp_project)
    mgr.init_recipes("proj")
    for role in ROLES:
        issues = mgr.validate_recipe(role)
        assert issues == [], f"Role '{role}' has issues: {issues}"
