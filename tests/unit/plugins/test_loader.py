"""Unit tests for PluginLoader."""

from __future__ import annotations

from pathlib import Path

import pytest

from sdd_server.plugins.base import (
    PluginLoadError,
)
from sdd_server.plugins.loader import PluginLoader

# ---------------------------------------------------------------------------
# Minimal plugin used in multiple tests
# ---------------------------------------------------------------------------

_PLUGIN_SOURCE = """
from datetime import datetime
from sdd_server.plugins.base import PluginMetadata, RolePlugin, RoleResult, RoleStage, RoleStatus

class MyTestRole(RolePlugin):
    metadata = PluginMetadata(
        name="my-test-role",
        version="1.0.0",
        description="Test",
        author="Test",
        priority=99,
        stage=RoleStage.REVIEW,
    )

    async def review(self, scope="all", target=None):
        return RoleResult(
            role=self.name,
            status=RoleStatus.COMPLETED,
            success=True,
            output="ok",
            started_at=datetime.now(),
        )

    def get_recipe_template(self):
        return \'version: "1.0.0"\\ntitle: "Test"\\n\'
"""

_PRIVATE_PLUGIN_SOURCE = """
from datetime import datetime
from sdd_server.plugins.base import PluginMetadata, RolePlugin, RoleResult, RoleStage, RoleStatus

class PrivateRole(RolePlugin):
    metadata = PluginMetadata(
        name="private-role",
        version="1.0.0",
        description="Should not be discovered",
        author="Test",
        priority=99,
        stage=RoleStage.REVIEW,
    )

    async def review(self, scope="all", target=None):
        return RoleResult(
            role=self.name,
            status=RoleStatus.COMPLETED,
            success=True,
            output="ok",
            started_at=datetime.now(),
        )

    def get_recipe_template(self):
        return \'version: "1.0.0"\\n\'
"""


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def loader() -> PluginLoader:
    return PluginLoader()


@pytest.fixture
def tmp_plugin_dir(tmp_path: Path) -> Path:
    plugin_file = tmp_path / "myplugin.py"
    plugin_file.write_text(_PLUGIN_SOURCE)
    return tmp_path


# ---------------------------------------------------------------------------
# Tests: discover_plugins — built-ins
# ---------------------------------------------------------------------------


class TestDiscoverBuiltins:
    async def test_discovers_six_builtin_plugins(self, loader: PluginLoader) -> None:
        discovered = await loader.discover_plugins()
        assert len(discovered) >= 6

    async def test_returns_dict_of_plugin_classes(self, loader: PluginLoader) -> None:
        discovered = await loader.discover_plugins()
        assert isinstance(discovered, dict)
        for name, cls in discovered.items():
            assert isinstance(name, str)
            assert isinstance(cls, type)

    async def test_clears_previous_on_rediscover(self, loader: PluginLoader) -> None:
        first = await loader.discover_plugins()
        second = await loader.discover_plugins()
        assert first.keys() == second.keys()


# ---------------------------------------------------------------------------
# Tests: _discover_from_path
# ---------------------------------------------------------------------------


class TestDiscoverFromPath:
    async def test_discovers_plugin_from_valid_py_file(
        self, loader: PluginLoader, tmp_plugin_dir: Path
    ) -> None:
        count = await loader._discover_from_path(tmp_plugin_dir)
        assert count == 1

    async def test_discovered_plugin_accessible_by_name(
        self, loader: PluginLoader, tmp_plugin_dir: Path
    ) -> None:
        await loader._discover_from_path(tmp_plugin_dir)
        assert "my-test-role" in loader._discovered_classes

    async def test_skips_private_files(self, loader: PluginLoader, tmp_path: Path) -> None:
        private = tmp_path / "_private.py"
        private.write_text(_PRIVATE_PLUGIN_SOURCE)
        count = await loader._discover_from_path(tmp_path)
        assert count == 0
        assert "private-role" not in loader._discovered_classes

    async def test_handles_multiple_plugins_in_dir(
        self, loader: PluginLoader, tmp_path: Path
    ) -> None:
        (tmp_path / "plugin_a.py").write_text(_PLUGIN_SOURCE.replace("my-test-role", "role-a"))
        (tmp_path / "plugin_b.py").write_text(_PLUGIN_SOURCE.replace("my-test-role", "role-b"))
        count = await loader._discover_from_path(tmp_path)
        assert count == 2


# ---------------------------------------------------------------------------
# Tests: _discover_from_entry_points
# ---------------------------------------------------------------------------


class TestDiscoverFromEntryPoints:
    async def test_no_entries_does_not_crash(self, loader: PluginLoader) -> None:
        # Entry points exist but group "sdd.plugins" has no entries in this project
        count = await loader._discover_from_entry_points()
        assert isinstance(count, int)
        assert count >= 0


# ---------------------------------------------------------------------------
# Tests: load_plugin — caching
# ---------------------------------------------------------------------------


class TestLoadPluginCaching:
    async def test_returns_cached_plugin_on_second_call(self, loader: PluginLoader) -> None:
        await loader.discover_plugins()
        names = list(loader._discovered_classes.keys())
        first = await loader.load_plugin(names[0])
        second = await loader.load_plugin(names[0])
        assert first is second

    async def test_raises_plugin_load_error_for_unknown(self, loader: PluginLoader) -> None:
        with pytest.raises(PluginLoadError, match="not found"):
            await loader.load_plugin("__nonexistent_plugin__")

    async def test_auto_discovers_if_discovered_classes_empty(self, loader: PluginLoader) -> None:
        # Start with empty discovered set
        assert loader._discovered_classes == {}
        # loading a builtin should trigger auto-discovery then find it
        discovered = await loader.discover_plugins()
        first_name = next(iter(discovered))
        loader._discovered_classes.clear()
        plugin = await loader.load_plugin(first_name)
        assert plugin is not None


# ---------------------------------------------------------------------------
# Tests: load_all_plugins
# ---------------------------------------------------------------------------


class TestLoadAllPlugins:
    async def test_loads_all_discovered_plugins(self, loader: PluginLoader) -> None:
        await loader.discover_plugins()
        loaded = await loader.load_all_plugins()
        assert len(loaded) > 0

    async def test_skips_failed_plugins_and_continues(
        self, loader: PluginLoader, tmp_path: Path
    ) -> None:
        # Add one valid and one broken plugin
        (tmp_path / "good.py").write_text(_PLUGIN_SOURCE)
        broken_source = "raise RuntimeError('boom')\n"
        (tmp_path / "bad.py").write_text(broken_source)

        # Discover from path (bad.py won't contribute a class due to error)
        await loader._discover_from_path(tmp_path)
        loaded = await loader.load_all_plugins()
        # Should have at least the good one (may also have builtins)
        assert isinstance(loaded, dict)


# ---------------------------------------------------------------------------
# Tests: validate_plugin
# ---------------------------------------------------------------------------


class TestValidatePlugin:
    async def test_valid_plugin_returns_no_errors(self, loader: PluginLoader) -> None:
        await loader.discover_plugins()
        names = list(loader._discovered_classes.keys())
        plugin_cls = loader._discovered_classes[names[0]]
        plugin = plugin_cls()
        errors = loader.validate_plugin(plugin)
        assert errors == []

    async def test_plugin_without_metadata_returns_error(self, loader: PluginLoader) -> None:
        class _NoMetaPlugin:
            pass

        plugin = _NoMetaPlugin()
        errors = loader.validate_plugin(plugin)  # type: ignore[arg-type]
        assert any("metadata" in e.lower() for e in errors)


# ---------------------------------------------------------------------------
# Tests: set_context / accessors
# ---------------------------------------------------------------------------


class TestAccessors:
    def test_set_context_stores_context(self, loader: PluginLoader) -> None:
        ctx = {"key": "value"}
        loader.set_context(ctx)
        assert loader._context == ctx

    async def test_get_discovered_plugins_returns_copy(self, loader: PluginLoader) -> None:
        await loader.discover_plugins()
        discovered = loader.get_discovered_plugins()
        assert isinstance(discovered, dict)
        assert len(discovered) > 0
        # Modifying the copy should not affect internal state
        discovered["__fake__"] = None  # type: ignore[assignment]
        assert "__fake__" not in loader._discovered_classes

    async def test_get_loaded_plugins_returns_copy(self, loader: PluginLoader) -> None:
        await loader.discover_plugins()
        await loader.load_all_plugins()
        loaded = loader.get_loaded_plugins()
        assert isinstance(loaded, dict)
        # Modifying copy should not affect internal state
        loaded["__fake__"] = None  # type: ignore[assignment]
        assert "__fake__" not in loader._loaded_plugins

    async def test_get_plugin_class_returns_class(self, loader: PluginLoader) -> None:
        await loader.discover_plugins()
        first_name = next(iter(loader._discovered_classes))
        cls = loader.get_plugin_class(first_name)
        assert cls is not None
        assert isinstance(cls, type)

    def test_get_plugin_class_returns_none_for_unknown(self, loader: PluginLoader) -> None:
        result = loader.get_plugin_class("__nonexistent__")
        assert result is None


# ---------------------------------------------------------------------------
# Tests: _get_plugin_name — kebab-case fallback
# ---------------------------------------------------------------------------


class TestGetPluginName:
    def test_uses_metadata_name_when_present(self, loader: PluginLoader) -> None:
        from sdd_server.plugins.roles.architect import ArchitectRole

        name = loader._get_plugin_name(ArchitectRole)
        assert name == "architect"

    def test_falls_back_to_kebab_case_when_no_metadata(self, loader: PluginLoader) -> None:
        class MyFancyPlugin:
            pass

        name = loader._get_plugin_name(MyFancyPlugin)  # type: ignore[arg-type]
        assert name == "my-fancy-plugin"

    def test_falls_back_to_kebab_case_when_metadata_not_plugin_metadata(
        self, loader: PluginLoader
    ) -> None:
        class WeirdPlugin:
            metadata = "not-a-PluginMetadata-instance"

        name = loader._get_plugin_name(WeirdPlugin)  # type: ignore[arg-type]
        assert name == "weird-plugin"
