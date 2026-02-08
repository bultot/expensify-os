"""Tests for the Expensify API client."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from expensify_os.expensify.client import EXPENSIFY_API_URL, ExpensifyClient
from expensify_os.models import ExpenseData, ExpensifyConfig


@pytest.fixture
def expensify_config() -> ExpensifyConfig:
    return ExpensifyConfig(
        partner_user_id="test_user",
        partner_user_secret="test_secret",
        employee_email="test@example.com",
    )


@pytest.fixture
def expense(tmp_path: Path) -> ExpenseData:
    receipt = tmp_path / "receipt.pdf"
    receipt.write_bytes(b"%PDF-1.4 test receipt")
    return ExpenseData(
        merchant="Anthropic",
        amount=12345,
        currency="USD",
        date=date(2026, 1, 1),
        category="AI & ML Services",
        comment="Claude API usage for 2026-01",
        receipt_path=receipt,
    )


@pytest.mark.asyncio
@respx.mock
async def test_create_expense(expensify_config: ExpensifyConfig, expense: ExpenseData):
    route = respx.post(EXPENSIFY_API_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "responseCode": 200,
                "transactionList": [{"transactionID": "txn_123"}],
            },
        )
    )

    async with ExpensifyClient(expensify_config) as client:
        result = await client.create_expense(expense)

    assert route.called
    assert result["transactionList"][0]["transactionID"] == "txn_123"


@pytest.mark.asyncio
@respx.mock
async def test_create_expense_api_error(expensify_config: ExpensifyConfig, expense: ExpenseData):
    respx.post(EXPENSIFY_API_URL).mock(
        return_value=httpx.Response(
            200,
            json={"responseCode": 410, "responseMessage": "Invalid credentials"},
        )
    )

    async with ExpensifyClient(expensify_config) as client:
        with pytest.raises(RuntimeError, match="Invalid credentials"):
            await client.create_expense(expense)


@pytest.mark.asyncio
@respx.mock
async def test_upload_receipt(expensify_config: ExpensifyConfig, expense: ExpenseData):
    respx.post(EXPENSIFY_API_URL).mock(
        return_value=httpx.Response(200, json={"responseCode": 200})
    )

    async with ExpensifyClient(expensify_config) as client:
        result = await client.upload_receipt(expense, "txn_123")

    assert result["responseCode"] == 200


@pytest.mark.asyncio
async def test_upload_receipt_missing_file(expensify_config: ExpensifyConfig, tmp_path: Path):
    expense = ExpenseData(
        merchant="Test",
        amount=100,
        date=date(2026, 1, 1),
        category="Test",
        receipt_path=tmp_path / "nonexistent.pdf",
    )

    async with ExpensifyClient(expensify_config) as client:
        with pytest.raises(FileNotFoundError):
            await client.upload_receipt(expense, "txn_123")


@pytest.mark.asyncio
@respx.mock
async def test_submit_expense_full_flow(expensify_config: ExpensifyConfig, expense: ExpenseData):
    call_count = 0

    def side_effect(request):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # create_expense response
            return httpx.Response(
                200,
                json={
                    "responseCode": 200,
                    "transactionList": [{"transactionID": "txn_456"}],
                },
            )
        else:
            # upload_receipt response
            return httpx.Response(200, json={"responseCode": 200})

    respx.post(EXPENSIFY_API_URL).mock(side_effect=side_effect)

    async with ExpensifyClient(expensify_config) as client:
        result = await client.submit_expense(expense)

    assert result["transaction_id"] == "txn_456"
    assert result["receipt"] is not None
