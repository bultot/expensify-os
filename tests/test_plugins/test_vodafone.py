"""Tests for the Vodafone expense plugin."""

from __future__ import annotations

import pytest

from expensify_os.models import PluginConfig
from expensify_os.plugins.vodafone import VodafonePlugin


@pytest.fixture
def vodafone_config() -> PluginConfig:
    return PluginConfig(
        enabled=True,
        credentials={
            "username": "test@example.com",
            "password": "password123",
        },
        category="Mobile & Telecom",
    )


@pytest.fixture
def plugin(vodafone_config: PluginConfig) -> VodafonePlugin:
    return VodafonePlugin(vodafone_config)


class TestVodafonePlugin:
    def test_plugin_creation(self, plugin: VodafonePlugin):
        assert plugin.name == "vodafone"
        assert plugin.config.category == "Mobile & Telecom"

    def test_credentials_available(self, plugin: VodafonePlugin):
        assert plugin.config.credentials["username"] == "test@example.com"
        assert plugin.config.credentials["password"] == "password123"

    def test_plugin_is_registered(self):
        from expensify_os.plugins.registry import _registry

        assert "vodafone" in _registry
