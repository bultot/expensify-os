"""Tests for the Anthropic expense plugin."""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import respx

from expensify_os.models import PluginConfig
from expensify_os.plugins.anthropic import ANTHROPIC_API_URL, AnthropicPlugin


@pytest.fixture
def anthropic_config() -> PluginConfig:
    return PluginConfig(
        enabled=True,
        credentials={
            "admin_api_key": "sk-ant-admin-test",
            "console_email": "test@example.com",
            "console_password": "password123",
        },
        category="AI & ML Services",
    )


@pytest.fixture
def plugin(anthropic_config: PluginConfig) -> AnthropicPlugin:
    return AnthropicPlugin(anthropic_config)


class TestValidateCredentials:
    @pytest.mark.asyncio
    @respx.mock
    async def test_valid_credentials(self, plugin: AnthropicPlugin):
        respx.get(f"{ANTHROPIC_API_URL}/v1/organizations/me").mock(
            return_value=httpx.Response(200, json={"id": "org_123", "name": "Test Org"})
        )
        assert await plugin.validate_credentials() is True
        await plugin.cleanup()

    @pytest.mark.asyncio
    @respx.mock
    async def test_invalid_credentials(self, plugin: AnthropicPlugin):
        respx.get(f"{ANTHROPIC_API_URL}/v1/organizations/me").mock(
            return_value=httpx.Response(401, json={"error": "unauthorized"})
        )
        assert await plugin.validate_credentials() is False
        await plugin.cleanup()


class TestFetchTotalCost:
    @pytest.mark.asyncio
    @respx.mock
    async def test_single_page_cost(self, plugin: AnthropicPlugin):
        respx.get(f"{ANTHROPIC_API_URL}/v1/organizations/cost_report").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "starting_at": "2026-01-01T00:00:00Z",
                            "ending_at": "2026-01-02T00:00:00Z",
                            "results": [
                                {"amount": "5000.50", "currency": "USD"},
                                {"amount": "2500.25", "currency": "USD"},
                            ],
                        }
                    ],
                    "has_more": False,
                },
            )
        )

        total = await plugin._fetch_total_cost(
            datetime.date(2026, 1, 1), datetime.date(2026, 2, 1)
        )
        # 5000.50 + 2500.25 = 7500.75, ceil = 7501 cents = $75.01
        assert total == 7501
        await plugin.cleanup()

    @pytest.mark.asyncio
    @respx.mock
    async def test_paginated_cost(self, plugin: AnthropicPlugin):
        call_count = 0

        def side_effect(request):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(
                    200,
                    json={
                        "data": [
                            {
                                "starting_at": "2026-01-01T00:00:00Z",
                                "ending_at": "2026-01-02T00:00:00Z",
                                "results": [{"amount": "1000.00"}],
                            }
                        ],
                        "has_more": True,
                        "next_page": "2026-01-02T00:00:00Z",
                    },
                )
            else:
                return httpx.Response(
                    200,
                    json={
                        "data": [
                            {
                                "starting_at": "2026-01-02T00:00:00Z",
                                "ending_at": "2026-01-03T00:00:00Z",
                                "results": [{"amount": "500.00"}],
                            }
                        ],
                        "has_more": False,
                    },
                )

        respx.get(f"{ANTHROPIC_API_URL}/v1/organizations/cost_report").mock(
            side_effect=side_effect
        )

        total = await plugin._fetch_total_cost(
            datetime.date(2026, 1, 1), datetime.date(2026, 2, 1)
        )
        assert total == 1500  # 1000 + 500 cents
        assert call_count == 2
        await plugin.cleanup()

    @pytest.mark.asyncio
    @respx.mock
    async def test_zero_cost(self, plugin: AnthropicPlugin):
        respx.get(f"{ANTHROPIC_API_URL}/v1/organizations/cost_report").mock(
            return_value=httpx.Response(
                200,
                json={"data": [], "has_more": False},
            )
        )

        total = await plugin._fetch_total_cost(
            datetime.date(2026, 1, 1), datetime.date(2026, 2, 1)
        )
        assert total == 0
        await plugin.cleanup()


class TestFetchExpense:
    @pytest.mark.asyncio
    @respx.mock
    async def test_dry_run_skips_browser(self, plugin: AnthropicPlugin, tmp_path):
        respx.get(f"{ANTHROPIC_API_URL}/v1/organizations/cost_report").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "starting_at": "2026-01-01T00:00:00Z",
                            "ending_at": "2026-01-02T00:00:00Z",
                            "results": [{"amount": "5000.00"}],
                        }
                    ],
                    "has_more": False,
                },
            )
        )

        expense = await plugin.fetch_expense(2026, 1, dry_run=True)

        assert expense is not None
        assert expense.merchant == "Anthropic"
        assert expense.amount == 5000
        assert expense.currency == "USD"
        assert expense.category == "AI & ML Services"
        assert "2026-01" in expense.comment
        await plugin.cleanup()

    @pytest.mark.asyncio
    @respx.mock
    async def test_no_charges_returns_none(self, plugin: AnthropicPlugin):
        respx.get(f"{ANTHROPIC_API_URL}/v1/organizations/cost_report").mock(
            return_value=httpx.Response(
                200,
                json={"data": [], "has_more": False},
            )
        )

        expense = await plugin.fetch_expense(2026, 1, dry_run=True)
        assert expense is None
        await plugin.cleanup()
