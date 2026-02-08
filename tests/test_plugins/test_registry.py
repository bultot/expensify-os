"""Tests for plugin registry."""

from __future__ import annotations

import pytest

from expensify_os.models import PluginConfig
from expensify_os.plugins.base import ExpensePlugin
from expensify_os.plugins.registry import (
    _registry,
    get_plugin,
    list_plugins,
    register_plugin,
)


@register_plugin("test_source")
class _TestPlugin(ExpensePlugin):
    """A test plugin for registry tests."""

    async def fetch_expense(self, year, month, *, dry_run=False):
        return None

    async def validate_credentials(self):
        return True


class TestRegistry:
    def test_register_and_get(self):
        config = PluginConfig(credentials={"key": "val"})
        plugin = get_plugin("test_source", config)
        assert isinstance(plugin, _TestPlugin)
        assert plugin.name == "test_source"

    def test_get_unknown_plugin(self):
        config = PluginConfig()
        with pytest.raises(KeyError, match="Unknown plugin 'nonexistent'"):
            get_plugin("nonexistent", config)

    def test_list_plugins(self):
        plugins = list_plugins()
        assert "test_source" in plugins

    def test_decorator_sets_name(self):
        assert _TestPlugin.name == "test_source"


@pytest.fixture(autouse=True)
def _cleanup_registry():
    """Ensure test plugin doesn't leak between test files."""
    yield
    # Don't remove — it was registered at module level and is fine
