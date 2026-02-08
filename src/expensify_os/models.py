"""Core data models for expensify-os."""

import datetime
from pathlib import Path

from pydantic import BaseModel, Field


class ExpenseData(BaseModel):
    """Represents a single expense to be submitted to Expensify."""

    merchant: str = Field(description="Merchant name, e.g. 'Anthropic'")
    amount: int = Field(description="Amount in minor units (cents). 12345 = $123.45")
    currency: str = Field(default="EUR", description="ISO 4217 currency code")
    date: datetime.date = Field(description="Expense date, typically first of the billing month")
    category: str = Field(description="Expense category, e.g. 'AI & ML Services'")
    comment: str | None = Field(default=None, description="Optional comment for the expense")
    receipt_path: Path = Field(description="Path to the downloaded PDF receipt")

    @property
    def amount_decimal(self) -> float:
        """Return amount as a decimal value (e.g. 12345 -> 123.45)."""
        return self.amount / 100


class PluginConfig(BaseModel):
    """Configuration for a single plugin."""

    enabled: bool = True
    credentials: dict[str, str] = Field(default_factory=dict)
    category: str = "Uncategorized"


class ExpensifyConfig(BaseModel):
    """Expensify API configuration."""

    partner_user_id: str
    partner_user_secret: str
    employee_email: str
    default_currency: str = "EUR"


class BrowserConfig(BaseModel):
    """Browser automation configuration."""

    headless: bool = True
    timeout: int = 30000
    screenshots_on_error: bool = True


class AppConfig(BaseModel):
    """Top-level application configuration."""

    expensify: ExpensifyConfig
    plugins: dict[str, PluginConfig] = Field(default_factory=dict)
    browser: BrowserConfig = Field(default_factory=BrowserConfig)
