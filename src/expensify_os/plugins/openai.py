"""OpenAI expense plugin.

Fetches monthly billing data via the Organization Costs API
and downloads the invoice PDF from the OpenAI Platform via browser automation.
"""

from __future__ import annotations

import calendar
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

OPENAI_API_URL = "https://api.openai.com"
OPENAI_PLATFORM_URL = "https://platform.openai.com"


@register_plugin("openai")
class OpenAIPlugin(ExpensePlugin):
    """Fetch OpenAI billing data and download invoice PDF.

    Uses:
    - Organization Costs API (`/v1/organization/costs`) for cost data
    - Platform browser automation for invoice PDF download
    """

    name = "openai"

    def __init__(self, config: PluginConfig) -> None:
        super().__init__(config)
        self._http = httpx.AsyncClient(timeout=30.0)

    async def cleanup(self) -> None:
        await self._http.aclose()

    async def validate_credentials(self) -> bool:
        """Validate the admin API key by making a minimal costs request."""
        try:
            now = int(datetime.datetime.now(tz=datetime.timezone.utc).timestamp())
            response = await self._http.get(
                f"{OPENAI_API_URL}/v1/organization/costs",
                headers=self._api_headers(),
                params={"start_time": now - 86400, "limit": 1},
            )
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def fetch_expense(
        self, year: int, month: int, *, dry_run: bool = False
    ) -> ExpenseData | None:
        """Fetch OpenAI billing for the given month."""
        start_date = datetime.date(year, month, 1)
        if month == 12:
            end_date = datetime.date(year + 1, 1, 1)
        else:
            end_date = datetime.date(year, month + 1, 1)

        self.log.info("fetching_costs", year=year, month=month)

        total_cents = await self._fetch_total_cost(start_date, end_date)

        if total_cents == 0:
            self.log.info("no_charges", year=year, month=month)
            return None

        self.log.info("cost_found", amount_cents=total_cents, amount_usd=total_cents / 100)

        receipt_path = Path("downloads") / "openai" / f"openai_{year}-{month:02d}.pdf"
        if not dry_run:
            receipt_path = await self._download_invoice(year, month)
        else:
            receipt_path.parent.mkdir(parents=True, exist_ok=True)
            receipt_path.write_text(f"[DRY RUN] Invoice for {year}-{month:02d}")
            self.log.info("dry_run_skip_download")

        return ExpenseData(
            merchant="OpenAI",
            amount=total_cents,
            currency="USD",
            date=start_date,
            category=self.config.category,
            comment=f"OpenAI API usage for {year}-{month:02d}",
            receipt_path=receipt_path,
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def _fetch_total_cost(
        self, start_date: datetime.date, end_date: datetime.date
    ) -> int:
        """Fetch total cost from the Organization Costs API.

        Returns total in integer cents (e.g. 12345 = $123.45).
        The API returns amounts as floats in dollars.
        """
        start_ts = int(
            datetime.datetime.combine(start_date, datetime.time.min, tzinfo=datetime.timezone.utc).timestamp()
        )
        end_ts = int(
            datetime.datetime.combine(end_date, datetime.time.min, tzinfo=datetime.timezone.utc).timestamp()
        )

        total = Decimal("0")
        page: str | None = None
        days_in_range = (end_date - start_date).days

        while True:
            params: dict = {
                "start_time": start_ts,
                "end_time": end_ts,
                "bucket_width": "1d",
                "limit": min(days_in_range, 180),
            }
            if page:
                params["page"] = page

            response = await self._http.get(
                f"{OPENAI_API_URL}/v1/organization/costs",
                headers=self._api_headers(),
                params=params,
            )
            response.raise_for_status()
            data = response.json()

            for bucket in data.get("data", []):
                for result in bucket.get("results", []):
                    amount = result.get("amount", {})
                    value = amount.get("value", 0)
                    # API returns dollars as float, convert to cents
                    total += Decimal(str(value)) * 100

            if not data.get("has_more"):
                break
            page = data.get("next_page")

        return int(math.ceil(total))

    async def _download_invoice(self, year: int, month: int) -> Path:
        """Download the invoice PDF from OpenAI Platform via browser automation."""
        browser_config = BrowserConfig(
            headless=True,
            timeout=30000,
            screenshots_on_error=True,
        )

        async with BrowserSession(browser_config, "openai") as session:
            page = await session.new_page()

            # Navigate to OpenAI Platform login
            await page.goto(f"{OPENAI_PLATFORM_URL}/login")

            email = self.config.credentials.get("platform_email", "")
            password = self.config.credentials.get("platform_password", "")

            await page.fill('input[name="email"], input[type="email"]', email)
            await page.click('button:has-text("Continue")')
            await page.fill('input[type="password"]', password)
            await page.click('button:has-text("Continue"), button:has-text("Log in")')

            await page.wait_for_load_state("networkidle")

            # Navigate to billing page
            await page.goto(
                f"{OPENAI_PLATFORM_URL}/settings/organization/billing/overview"
            )
            await page.wait_for_load_state("networkidle")

            month_str = f"{year}-{month:02d}"
            self.log.info("looking_for_invoice", month=month_str)

            download_link = page.locator(
                f'a:has-text("Download"):near(:has-text("{month_str}")), '
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
            "Authorization": f"Bearer {self.config.credentials.get('api_key', '')}",
            "Content-Type": "application/json",
        }
