"""Tests for core data models."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from expensify_os.models import AppConfig, ExpenseData, ExpensifyConfig, PluginConfig


class TestExpenseData:
    def test_create_valid(self, sample_expense: ExpenseData):
        assert sample_expense.merchant == "Anthropic"
        assert sample_expense.amount == 12345
        assert sample_expense.currency == "USD"

    def test_amount_decimal(self, sample_expense: ExpenseData):
        assert sample_expense.amount_decimal == 123.45

    def test_amount_decimal_zero(self, tmp_path: Path):
        receipt = tmp_path / "receipt.pdf"
        receipt.touch()
        expense = ExpenseData(
            merchant="Test",
            amount=0,
            date=date(2026, 1, 1),
            category="Test",
            receipt_path=receipt,
        )
        assert expense.amount_decimal == 0.0

    def test_default_currency(self, tmp_path: Path):
        receipt = tmp_path / "receipt.pdf"
        receipt.touch()
        expense = ExpenseData(
            merchant="Test",
            amount=100,
            date=date(2026, 1, 1),
            category="Test",
            receipt_path=receipt,
        )
        assert expense.currency == "EUR"

    def test_missing_required_field(self):
        with pytest.raises(ValidationError):
            ExpenseData(merchant="Test")  # type: ignore[call-arg]


class TestPluginConfig:
    def test_defaults(self):
        config = PluginConfig()
        assert config.enabled is True
        assert config.credentials == {}
        assert config.category == "Uncategorized"

    def test_custom_values(self, sample_plugin_config: PluginConfig):
        assert sample_plugin_config.enabled is True
        assert sample_plugin_config.credentials["api_key"] == "test-key-123"


class TestAppConfig:
    def test_create_valid(self, sample_app_config: AppConfig):
        assert sample_app_config.expensify.employee_email == "test@example.com"
        assert "anthropic" in sample_app_config.plugins
        assert sample_app_config.browser.headless is True

    def test_missing_expensify(self):
        with pytest.raises(ValidationError):
            AppConfig()  # type: ignore[call-arg]

    def test_default_browser_config(self):
        config = AppConfig(
            expensify=ExpensifyConfig(
                partner_user_id="u",
                partner_user_secret="s",
                employee_email="e@e.com",
            ),
        )
        assert config.browser.headless is True
        assert config.browser.timeout == 30000
