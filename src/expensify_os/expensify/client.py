"""Expensify API client for creating expenses and uploading receipts."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import structlog

from expensify_os.expensify.rate_limiter import RateLimiter
from expensify_os.models import ExpenseData, ExpensifyConfig

logger = structlog.get_logger()

EXPENSIFY_API_URL = "https://integrations.expensify.com/Integration-Server/ExpensifyIntegrations"


class ExpensifyClient:
    """Client for the Expensify Integration API.

    Creates expenses and uploads receipt attachments via the single
    POST endpoint that Expensify provides.
    """

    def __init__(self, config: ExpensifyConfig) -> None:
        self.config = config
        self._http = httpx.AsyncClient(timeout=30.0)
        self._rate_limiter = RateLimiter()

    async def close(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> ExpensifyClient:
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()

    async def _request(self, request_type: str, input_settings: dict) -> dict:
        """Execute a rate-limited request to the Expensify API.

        Args:
            request_type: The Expensify API job type (e.g. "create").
            input_settings: The inputSettings portion of the request.

        Returns:
            Parsed JSON response from Expensify.

        Raises:
            httpx.HTTPStatusError: On non-2xx responses.
            RuntimeError: On API-level errors.
        """
        await self._rate_limiter.acquire()

        job_description = {
            "type": request_type,
            "credentials": {
                "partnerUserID": self.config.partner_user_id,
                "partnerUserSecret": self.config.partner_user_secret,
            },
            "inputSettings": input_settings,
        }

        logger.debug("expensify_request", type=request_type)

        response = await self._http.post(
            EXPENSIFY_API_URL,
            data={"requestJobDescription": json.dumps(job_description)},
        )
        response.raise_for_status()

        # Expensify returns JSON (sometimes wrapped in a string)
        try:
            result = response.json()
        except json.JSONDecodeError:
            # Some endpoints return plain text on success
            return {"responseCode": 200, "responseMessage": response.text}

        if isinstance(result, dict) and result.get("responseCode", 0) >= 400:
            raise RuntimeError(
                f"Expensify API error: {result.get('responseMessage', result)}"
            )

        return result

    async def create_expense(self, expense: ExpenseData) -> dict:
        """Create a single expense in Expensify.

        Args:
            expense: The expense data to submit.

        Returns:
            API response dict.
        """
        logger.info(
            "creating_expense",
            merchant=expense.merchant,
            amount=expense.amount_decimal,
            currency=expense.currency,
        )

        input_settings = {
            "type": "create",
            "employeeEmail": self.config.employee_email,
            "transactionList": [
                {
                    "merchant": expense.merchant,
                    "amount": expense.amount,
                    "currency": expense.currency,
                    "created": expense.date.isoformat(),
                    "category": expense.category,
                    "comment": expense.comment or "",
                }
            ],
        }

        return await self._request("create", input_settings)

    async def upload_receipt(self, expense: ExpenseData, transaction_id: str) -> dict:
        """Upload a receipt PDF to an existing expense.

        Args:
            expense: The expense with receipt_path set.
            transaction_id: The Expensify transaction ID from create_expense.

        Returns:
            API response dict.
        """
        receipt_path = Path(expense.receipt_path)
        if not receipt_path.exists():
            raise FileNotFoundError(f"Receipt not found: {receipt_path}")

        logger.info(
            "uploading_receipt",
            merchant=expense.merchant,
            receipt=str(receipt_path),
        )

        await self._rate_limiter.acquire()

        response = await self._http.post(
            EXPENSIFY_API_URL,
            data={
                "requestJobDescription": json.dumps(
                    {
                        "type": "create",
                        "credentials": {
                            "partnerUserID": self.config.partner_user_id,
                            "partnerUserSecret": self.config.partner_user_secret,
                        },
                        "inputSettings": {
                            "type": "receiptUpload",
                            "employeeEmail": self.config.employee_email,
                            "transactionID": transaction_id,
                        },
                    }
                ),
            },
            files={"file": (receipt_path.name, receipt_path.read_bytes(), "application/pdf")},
        )
        response.raise_for_status()

        try:
            return response.json()
        except json.JSONDecodeError:
            return {"responseCode": 200, "responseMessage": response.text}

    async def submit_expense(self, expense: ExpenseData) -> dict:
        """Create an expense and upload its receipt in one flow.

        Args:
            expense: Complete expense data with receipt.

        Returns:
            Combined result with transaction details.
        """
        create_result = await self.create_expense(expense)

        # Extract transaction ID from response to attach receipt
        transaction_id = None
        if isinstance(create_result, dict):
            transaction_list = create_result.get("transactionList", [])
            if transaction_list:
                transaction_id = transaction_list[0].get("transactionID")

        receipt_result = None
        if transaction_id and expense.receipt_path.exists():
            receipt_result = await self.upload_receipt(expense, transaction_id)

        return {
            "create": create_result,
            "receipt": receipt_result,
            "transaction_id": transaction_id,
        }
