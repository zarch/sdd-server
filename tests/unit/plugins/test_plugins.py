"""Tests for PluginMetadata validation."""

from datetime import datetime

import pytest

from sdd_server.plugins import (
    BUILTIN_ROLES,
    ArchitectRole,
    EdgeCaseAnalystRole,
    InterfaceDesignerRole,
    PluginError,
    PluginLoader,
    PluginMetadata,
    PluginRegistry,
    RoleResult,
    RoleStage,
    RoleStatus,
    SecurityAnalystRole,
    SeniorDeveloperRole,
    UIDesignerRole,
    validate_plugin_metadata,
)


class TestValidatePluginMetadata:
    """Tests for validate_plugin_metadata function."""

    def test_valid_metadata(self) -> None:
        """Test valid metadata."""
        metadata = PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="Test plugin",
            author="Test",
        )
        errors = validate_plugin_metadata(metadata)
        assert errors == []

    def test_empty_name(self) -> None:
        """Test empty name is invalid."""
        metadata = PluginMetadata(
            name="",
            version="1.0.0",
            description="Test",
            author="Test",
        )
        errors = validate_plugin_metadata(metadata)
        assert "Plugin name is required" in errors

    def test_empty_version(self) -> None:
        """Test empty version is invalid."""
        metadata = PluginMetadata(
            name="test",
            version="",
            description="Test",
            author="Test",
        )
        errors = validate_plugin_metadata(metadata)
        assert "Plugin version is required" in errors

    def test_empty_description(self) -> None:
        """Test empty description is invalid."""
        metadata = PluginMetadata(
            name="test",
            version="1.0.0",
            description="",
            author="Test",
        )
        errors = validate_plugin_metadata(metadata)
        assert "Plugin description is required" in errors

    def test_negative_priority(self) -> None:
        """Test negative priority."""
        metadata = PluginMetadata(
            name="test",
            version="1.0.0",
            description="Test",
            author="Test",
            priority=-1,
        )
        errors = validate_plugin_metadata(metadata)
        assert len(errors) == 1
        assert "Plugin priority must be non-negative" in errors[0]

    def test_invalid_name_characters(self) -> None:
        """Test invalid characters in name."""
        metadata = PluginMetadata(
            name="test@plugin!",
            version="1.0.0",
            description="Test",
            author="Test",
        )
        errors = validate_plugin_metadata(metadata)
        assert len(errors) == 1
        assert "must be alphanumeric" in errors[0]


class TestRoleResult:
    """Tests for RoleResult model."""

    def test_role_result_defaults(self) -> None:
        """Test RoleResult with default values."""
        result = RoleResult(
            role="test-role",
            status=RoleStatus.PENDING,
            success=False,
            output="Test output",
            started_at=datetime.now(),
        )
        assert result.role == "test-role"
        assert result.status == RoleStatus.PENDING
        assert result.success is False
        assert result.output == "Test output"
        assert result.issues == []
        assert result.suggestions == []
        assert result.started_at is not None
        assert result.duration_seconds is None

    def test_role_result_with_values(self) -> None:
        """Test RoleResult with explicit values."""
        started_at = datetime(2026, 1, 1, 12, 0, 0)
        result = RoleResult(
            role="test-role",
            status=RoleStatus.COMPLETED,
            success=True,
            output="All done",
            issues=["issue1", "issue2"],
            suggestions=["suggestion1", "suggestion2"],
            started_at=started_at,
            session_id="session-123",
        )
        assert result.status == RoleStatus.COMPLETED
        assert result.success is True
        assert result.issues == ["issue1", "issue2"]
        assert result.suggestions == ["suggestion1", "suggestion2"]
        assert result.session_id == "session-123"

    def test_mark_completed(self) -> None:
        """Test mark_completed updates status."""
        result = RoleResult(
            role="test-role",
            status=RoleStatus.RUNNING,
            success=False,
            output="Test",
            started_at=datetime.now(),
        )
        result.mark_completed(success=True)
        assert result.success is True
        assert result.status == RoleStatus.COMPLETED
        assert result.duration_seconds is not None

    def test_mark_completed_with_failure(self) -> None:
        """Test mark_completed with failure."""
        result = RoleResult(
            role="test-role",
            status=RoleStatus.RUNNING,
            success=False,
            output="Test",
            started_at=datetime.now(),
        )
        result.mark_completed(success=False)
        assert result.success is False
        assert result.status == RoleStatus.FAILED


class TestBuiltInRoles:
    """Tests for built-in role plugins."""

    def test_builtin_roles_count(self) -> None:
        """Test we have 6 built-in roles."""
        assert len(BUILTIN_ROLES) == 11

    def test_architect_role_metadata(self) -> None:
        """Test ArchitectRole metadata."""
        role = ArchitectRole()
        assert role.metadata.name == "architect"
        assert role.metadata.priority == 10
        assert role.metadata.stage == RoleStage.ARCHITECTURE
        assert role.get_dependencies() == ["spec-linter"]

    def test_ui_designer_role_metadata(self) -> None:
        """Test UIDesignerRole metadata."""
        role = UIDesignerRole()
        assert role.metadata.name == "ui-designer"
        assert role.metadata.priority == 20
        assert role.metadata.stage == RoleStage.UI_DESIGN
        assert role.get_dependencies() == ["architect"]

    def test_interface_designer_role_metadata(self) -> None:
        """Test InterfaceDesignerRole metadata."""
        role = InterfaceDesignerRole()
        assert role.metadata.name == "interface-designer"
        assert role.metadata.priority == 20
        assert role.metadata.stage == RoleStage.INTERFACE_DESIGN
        assert role.get_dependencies() == ["architect"]

    def test_security_analyst_role_metadata(self) -> None:
        """Test SecurityAnalystRole metadata."""
        role = SecurityAnalystRole()
        assert role.metadata.name == "security-analyst"
        assert role.metadata.priority == 30
        assert role.metadata.stage == RoleStage.SECURITY
        assert set(role.get_dependencies()) == {"architect", "interface-designer"}

    def test_edge_case_analyst_role_metadata(self) -> None:
        """Test EdgeCaseAnalystRole metadata."""
        role = EdgeCaseAnalystRole()
        assert role.metadata.name == "edge-case-analyst"
        assert role.metadata.priority == 40
        assert role.metadata.stage == RoleStage.EDGE_CASE_ANALYSIS
        deps = set(role.get_dependencies())
        assert deps == {"architect", "interface-designer", "security-analyst"}

    def test_senior_developer_role_metadata(self) -> None:
        """Test SeniorDeveloperRole metadata."""
        role = SeniorDeveloperRole()
        assert role.metadata.name == "senior-developer"
        assert role.metadata.priority == 50
        assert role.metadata.stage == RoleStage.IMPLEMENTATION
        deps = set(role.get_dependencies())
        assert "architect" in deps
        assert "security-analyst" in deps

    def test_all_roles_have_recipe_template(self) -> None:
        """Test all roles return a recipe template."""
        for role_class in BUILTIN_ROLES:
            role = role_class()
            template = role.get_recipe_template()
            assert isinstance(template, str)
            assert len(template) > 0
            assert "version:" in template


class TestPluginLoader:
    """Tests for PluginLoader class."""

    @pytest.mark.asyncio
    async def test_discover_builtins(self) -> None:
        """Test discovering built-in plugins."""
        loader = PluginLoader()
        discovered = await loader.discover_plugins()
        assert len(discovered) >= 6
        assert "architect" in discovered
        assert "security-analyst" in discovered

    @pytest.mark.asyncio
    async def test_load_plugin(self) -> None:
        """Test loading a plugin."""
        loader = PluginLoader()
        await loader.discover_plugins()
        plugin = await loader.load_plugin("architect")
        assert plugin.metadata.name == "architect"

    @pytest.mark.asyncio
    async def test_load_all_plugins(self) -> None:
        """Test loading all plugins."""
        loader = PluginLoader()
        await loader.discover_plugins()
        loaded = await loader.load_all_plugins()
        assert len(loaded) >= 6


class TestPluginRegistry:
    """Tests for PluginRegistry class."""

    def test_empty_registry(self) -> None:
        """Test empty registry."""
        registry = PluginRegistry()
        assert registry.count_plugins() == 0
        assert registry.count_roles() == 0

    @pytest.mark.asyncio
    async def test_register_role(self) -> None:
        """Test registering a role plugin."""
        loader = PluginLoader()
        await loader.discover_plugins()
        spec_linter = await loader.load_plugin("spec-linter")
        architect = await loader.load_plugin("architect")

        registry = PluginRegistry()
        registry.register("spec-linter", spec_linter)
        registry.register("architect", architect)

        assert registry.has_role("architect")
        assert registry.get_role("architect") == architect

    @pytest.mark.asyncio
    async def test_register_duplicate_fails(self) -> None:
        """Test registering duplicate raises error."""
        loader = PluginLoader()
        await loader.discover_plugins()
        spec_linter = await loader.load_plugin("spec-linter")
        architect = await loader.load_plugin("architect")

        registry = PluginRegistry()
        registry.register("spec-linter", spec_linter)
        registry.register("architect", architect)

        with pytest.raises(PluginError, match="already registered"):
            registry.register("architect", architect)

    @pytest.mark.asyncio
    async def test_missing_dependency_fails(self) -> None:
        """Test registering with missing dependency fails."""
        loader = PluginLoader()
        await loader.discover_plugins()

        # Try to register security without architect first
        security = await loader.load_plugin("security-analyst")

        registry = PluginRegistry()
        with pytest.raises(PluginError, match="missing dependencies"):
            registry.register("security-analyst", security)

    @pytest.mark.asyncio
    async def test_get_roles_sorted_by_priority(self) -> None:
        """Test getting roles sorted by priority."""
        loader = PluginLoader()
        await loader.discover_plugins()
        registry = PluginRegistry()

        # Register in dependency order
        for name in [
            "spec-linter",
            "architect",
            "ui-designer",
            "interface-designer",
            "security-analyst",
        ]:
            plugin = await loader.load_plugin(name)
            registry.register(name, plugin)

        roles = registry.get_roles_sorted_by_priority()
        assert len(roles) == 5
        # Spec linter has lowest priority number (runs first)
        assert roles[0].metadata.name == "spec-linter"
        assert roles[1].metadata.name == "architect"

    @pytest.mark.asyncio
    async def test_get_execution_order(self) -> None:
        """Test getting execution order."""
        loader = PluginLoader()
        await loader.discover_plugins()
        registry = PluginRegistry()

        # Register all in dependency order
        for name in [
            "spec-linter",
            "architect",
            "ui-designer",
            "interface-designer",
            "security-analyst",
            "edge-case-analyst",
            "senior-developer",
        ]:
            plugin = await loader.load_plugin(name)
            registry.register(name, plugin)

        order = registry.get_execution_order()
        # Spec linter must come first
        assert order[0] == "spec-linter"
        # Architect must come after spec-linter
        assert order.index("architect") > order.index("spec-linter")
        # Security must come after interface-designer
        assert order.index("security-analyst") > order.index("interface-designer")
        # Senior-developer must come last
        assert order[-1] == "senior-developer"
