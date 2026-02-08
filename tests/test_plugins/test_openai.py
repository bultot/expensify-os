"""Tests for the OpenAI expense plugin."""

from __future__ import annotations

import datetime

import httpx
import pytest
import respx

from expensify_os.models import PluginConfig
from expensify_os.plugins.openai import OPENAI_API_URL, OpenAIPlugin


@pytest.fixture
def openai_config() -> PluginConfig:
    return PluginConfig(
        enabled=True,
        credentials={
            "api_key": "sk-admin-test-key",
            "platform_email": "test@example.com",
            "platform_password": "password123",
        },
        category="AI & ML Services",
    )


@pytest.fixture
def plugin(openai_config: PluginConfig) -> OpenAIPlugin:
    return OpenAIPlugin(openai_config)


class TestValidateCredentials:
    @pytest.mark.asyncio
    @respx.mock
    async def test_valid(self, plugin: OpenAIPlugin):
        respx.get(f"{OPENAI_API_URL}/v1/organization/costs").mock(
            return_value=httpx.Response(200, json={"data": [], "has_more": False})
        )
        assert await plugin.validate_credentials() is True
        await plugin.cleanup()

    @pytest.mark.asyncio
    @respx.mock
    async def test_invalid(self, plugin: OpenAIPlugin):
        respx.get(f"{OPENAI_API_URL}/v1/organization/costs").mock(
            return_value=httpx.Response(401, json={"error": "unauthorized"})
        )
        assert await plugin.validate_credentials() is False
        await plugin.cleanup()


class TestFetchTotalCost:
    @pytest.mark.asyncio
    @respx.mock
    async def test_single_page(self, plugin: OpenAIPlugin):
        respx.get(f"{OPENAI_API_URL}/v1/organization/costs").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "start_time": 1735689600,
                            "end_time": 1735776000,
                            "results": [
                                {"amount": {"value": 50.25, "currency": "usd"}},
                                {"amount": {"value": 10.75, "currency": "usd"}},
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
        # 50.25 + 10.75 = 61.00 dollars = 6100 cents
        assert total == 6100
        await plugin.cleanup()

    @pytest.mark.asyncio
    @respx.mock
    async def test_zero_cost(self, plugin: OpenAIPlugin):
        respx.get(f"{OPENAI_API_URL}/v1/organization/costs").mock(
            return_value=httpx.Response(200, json={"data": [], "has_more": False})
        )
        total = await plugin._fetch_total_cost(
            datetime.date(2026, 1, 1), datetime.date(2026, 2, 1)
        )
        assert total == 0
        await plugin.cleanup()


class TestFetchExpense:
    @pytest.mark.asyncio
    @respx.mock
    async def test_dry_run(self, plugin: OpenAIPlugin):
        respx.get(f"{OPENAI_API_URL}/v1/organization/costs").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "start_time": 1735689600,
                            "end_time": 1735776000,
                            "results": [
                                {"amount": {"value": 42.50, "currency": "usd"}},
                            ],
                        }
                    ],
                    "has_more": False,
                },
            )
        )

        expense = await plugin.fetch_expense(2026, 1, dry_run=True)

        assert expense is not None
        assert expense.merchant == "OpenAI"
        assert expense.amount == 4250
        assert expense.currency == "USD"
        assert "2026-01" in expense.comment
        await plugin.cleanup()

    @pytest.mark.asyncio
    @respx.mock
    async def test_no_charges(self, plugin: OpenAIPlugin):
        respx.get(f"{OPENAI_API_URL}/v1/organization/costs").mock(
            return_value=httpx.Response(200, json={"data": [], "has_more": False})
        )
        expense = await plugin.fetch_expense(2026, 1, dry_run=True)
        assert expense is None
        await plugin.cleanup()
