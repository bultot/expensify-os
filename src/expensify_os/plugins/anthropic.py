"""Anthropic expense plugin.

Fetches monthly billing data via the Admin API cost report endpoint
and downloads the invoice PDF from the Anthropic Console via browser automation.
"""

from __future__ import annotations

import datetime
import math
from decimal import Decimal
from pathlib import Path

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from expensify_os.browser.automation import BrowserSession
from expensify_os.models import BrowserConfig, ExpenseData, PluginConfig
from expensify_os.plugins.base import ExpensePlugin
from expensify_os.plugins.registry import register_plugin

ANTHROPIC_API_URL = "https://api.anthropic.com"
ANTHROPIC_CONSOLE_URL = "https://console.anthropic.com"


@register_plugin("anthropic")
class AnthropicPlugin(ExpensePlugin):
    """Fetch Anthropic billing data and download invoice PDF.

    Uses:
    - Admin API (`/v1/organizations/cost_report`) for cost data
    - Console browser automation for invoice PDF download
    """

    name = "anthropic"

    def __init__(self, config: PluginConfig) -> None:
        super().__init__(config)
        self._http = httpx.AsyncClient(timeout=30.0)

    async def cleanup(self) -> None:
        await self._http.aclose()

    async def validate_credentials(self) -> bool:
        """Validate the admin API key by fetching organization info."""
        try:
            response = await self._http.get(
                f"{ANTHROPIC_API_URL}/v1/organizations/me",
                headers=self._api_headers(),
            )
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def fetch_expense(
        self, year: int, month: int, *, dry_run: bool = False
    ) -> ExpenseData | None:
        """Fetch Anthropic billing for the given month.

        1. Query cost report API for total spend
        2. Download invoice PDF from Console (unless dry_run)
        """
        start_date = datetime.date(year, month, 1)
        # Calculate end of month
        if month == 12:
            end_date = datetime.date(year + 1, 1, 1)
        else:
            end_date = datetime.date(year, month + 1, 1)

        self.log.info("fetching_cost_report", year=year, month=month)

        total_cents = await self._fetch_total_cost(start_date, end_date)

        if total_cents == 0:
            self.log.info("no_charges", year=year, month=month)
            return None

        self.log.info("cost_found", amount_cents=total_cents, amount_usd=total_cents / 100)

        # Download invoice PDF (skip in dry-run mode)
        receipt_path = Path("downloads") / "anthropic" / f"anthropic_{year}-{month:02d}.pdf"
        if not dry_run:
            receipt_path = await self._download_invoice(year, month)
        else:
            receipt_path.parent.mkdir(parents=True, exist_ok=True)
            receipt_path.write_text(f"[DRY RUN] Invoice for {year}-{month:02d}")
            self.log.info("dry_run_skip_download")

        return ExpenseData(
            merchant="Anthropic",
            amount=total_cents,
            currency="USD",
            date=start_date,
            category=self.config.category,
            comment=f"Anthropic API usage for {year}-{month:02d}",
            receipt_path=receipt_path,
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def _fetch_total_cost(
        self, start_date: datetime.date, end_date: datetime.date
    ) -> int:
        """Fetch total cost from the Admin API cost report.

        Returns total in integer cents (e.g. 12345 = $123.45).
        """
        total = Decimal("0")
        page: str | None = None

        while True:
            params: dict = {
                "starting_at": f"{start_date.isoformat()}T00:00:00Z",
                "ending_at": f"{end_date.isoformat()}T00:00:00Z",
                "bucket_width": "1d",
            }
            if page:
                params["page"] = page

            response = await self._http.get(
                f"{ANTHROPIC_API_URL}/v1/organizations/cost_report",
                headers=self._api_headers(),
                params=params,
            )
            response.raise_for_status()
            data = response.json()

            for bucket in data.get("data", []):
                for result in bucket.get("results", []):
                    amount_str = result.get("amount", "0")
                    total += Decimal(amount_str)

            if not data.get("has_more"):
                break
            page = data.get("next_page")

        # Convert from cent-fractions to whole cents (round up to not under-report)
        return int(math.ceil(total))

    async def _download_invoice(self, year: int, month: int) -> Path:
        """Download the invoice PDF from Anthropic Console via browser automation.

        Navigates to Console → Settings → Billing → Invoices and downloads
        the PDF for the specified month.
        """
        browser_config = BrowserConfig(
            headless=True,
            timeout=30000,
            screenshots_on_error=True,
        )

        async with BrowserSession(browser_config, "anthropic") as session:
            page = await session.new_page()

            # Navigate to Console login
            await page.goto(f"{ANTHROPIC_CONSOLE_URL}/login")

            # Fill login form
            email = self.config.credentials.get("console_email", "")
            password = self.config.credentials.get("console_password", "")

            await page.fill('input[type="email"]', email)
            await page.click('button:has-text("Continue")')
            await page.fill('input[type="password"]', password)
            await page.click('button:has-text("Sign in")')

            # Wait for dashboard to load
            await page.wait_for_load_state("networkidle")

            # Navigate to billing/invoices
            await page.goto(f"{ANTHROPIC_CONSOLE_URL}/settings/billing")
            await page.wait_for_load_state("networkidle")

            # Find and click the invoice for the target month
            month_str = f"{year}-{month:02d}"
            self.log.info("looking_for_invoice", month=month_str)

            # Look for download link/button matching the month
            # The Console UI may vary — this targets common patterns
            download_link = page.locator(
                f'a:has-text("{month_str}"), '
                f'button:has-text("Download"):near(:has-text("{month_str}"))'
            ).first

            async with page.expect_download() as download_info:
                await download_link.click()

            download = await download_info.value
            save_path = await session.save_download(download)

            self.log.info("invoice_downloaded", path=str(save_path))
            return save_path

    def _api_headers(self) -> dict[str, str]:
        return {
            "x-api-key": self.config.credentials.get("admin_api_key", ""),
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
