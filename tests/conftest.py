"""Shared test fixtures for expensify-os."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import structlog

from expensify_os.models import (
    AppConfig,
    BrowserConfig,
    ExpenseData,
    ExpensifyConfig,
    PluginConfig,
)


@pytest.fixture(autouse=True)
def _reset_structlog():
    """Reset structlog configuration after each test.

    Prevents the CLI's setup_logging() from poisoning other tests
    with a logger bound to a closed stderr file descriptor.
    """
    yield
    structlog.reset_defaults()


@pytest.fixture
def sample_expense(tmp_path: Path) -> ExpenseData:
    receipt = tmp_path / "receipt.pdf"
    receipt.write_bytes(b"%PDF-1.4 fake receipt")
    return ExpenseData(
        merchant="Anthropic",
        amount=12345,
        currency="USD",
        date=date(2026, 1, 1),
        category="AI & ML Services",
        comment="Claude API usage for 2026-01",
        receipt_path=receipt,
    )


@pytest.fixture
def sample_plugin_config() -> PluginConfig:
    return PluginConfig(
        enabled=True,
        credentials={"api_key": "test-key-123"},
        category="AI & ML Services",
    )


@pytest.fixture
def sample_app_config() -> AppConfig:
    return AppConfig(
        expensify=ExpensifyConfig(
            partner_user_id="test_user",
            partner_user_secret="test_secret",
            employee_email="test@example.com",
        ),
        plugins={
            "anthropic": PluginConfig(
                enabled=True,
                credentials={"admin_api_key": "test-key"},
                category="AI & ML Services",
            ),
        },
        browser=BrowserConfig(),
    )


@pytest.fixture
def config_yaml_content() -> str:
    return """\
expensify:
  partner_user_id: "test_user"
  partner_user_secret: "test_secret"
  employee_email: "test@example.com"
  default_currency: "EUR"

plugins:
  anthropic:
    enabled: true
    credentials:
      admin_api_key: "test-key"
    category: "AI & ML Services"

browser:
  headless: true
  timeout: 30000
  screenshots_on_error: true
"""
