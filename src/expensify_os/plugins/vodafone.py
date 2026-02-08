"""Vodafone expense plugin.

Downloads monthly invoice from My Vodafone portal via full browser automation.
Vodafone has no public billing API, so everything is done through the web UI.

Status: PARTIALLY WORKING — login and 2FA flow verified, but invoice page
selectors need calibration against the real DOM. See TODOs below.
"""

from __future__ import annotations

import datetime
import os
import re
import sys
from decimal import Decimal
from pathlib import Path

from tenacity import retry, stop_after_attempt, wait_exponential

from expensify_os.browser.automation import BrowserSession
from expensify_os.models import BrowserConfig, ExpenseData, PluginConfig
from expensify_os.plugins.base import ExpensePlugin
from expensify_os.plugins.registry import register_plugin

VODAFONE_URL = "https://www.vodafone.nl/my"


@register_plugin("vodafone")
class VodafonePlugin(ExpensePlugin):
    """Fetch Vodafone billing data and download invoice PDF.

    Uses full browser automation of the My Vodafone portal since
    Vodafone has no public API for billing data.
    """

    name = "vodafone"

    async def validate_credentials(self) -> bool:
        """Validate credentials by attempting to log in to My Vodafone."""
        browser_config = BrowserConfig(headless=True, timeout=30000)
        try:
            async with BrowserSession(browser_config, "vodafone") as session:
                page = await session.new_page()
                await page.goto(f"{VODAFONE_URL}/inloggen")
                await self._login(page)
                # If we get past login without error, credentials are valid
                return True
        except Exception:
            self.log.warning("credential_validation_failed", exc_info=True)
            return False

    async def fetch_expense(
        self, year: int, month: int, *, dry_run: bool = False
    ) -> ExpenseData | None:
        """Fetch Vodafone invoice for the given month via browser automation."""
        self.log.info("fetching_invoice", year=year, month=month)

        browser_config = BrowserConfig(
            headless=True,
            timeout=30000,
            screenshots_on_error=True,
        )

        async with BrowserSession(browser_config, "vodafone") as session:
            page = await session.new_page()

            # Log in to My Vodafone
            await page.goto(f"{VODAFONE_URL}/inloggen")
            await self._login(page)

            # Navigate to invoices page
            await page.goto(f"{VODAFONE_URL}/facturen")
            await page.wait_for_load_state("networkidle")

            # Find the invoice for the target month
            month_str = f"{year}-{month:02d}"
            self.log.info("looking_for_invoice", month=month_str)

            # Extract amount from the invoice row
            amount_cents = await self._extract_amount(page, year, month)

            if amount_cents is None or amount_cents == 0:
                self.log.info("no_invoice_found", year=year, month=month)
                return None

            # Download the PDF
            if dry_run:
                receipt_path = Path("downloads") / "vodafone" / f"vodafone_{month_str}.pdf"
                receipt_path.parent.mkdir(parents=True, exist_ok=True)
                receipt_path.write_text(f"[DRY RUN] Vodafone invoice for {month_str}")
                self.log.info("dry_run_skip_download")
            else:
                receipt_path = await self._download_invoice(page, session, year, month)

        return ExpenseData(
            merchant="Vodafone",
            amount=amount_cents,
            currency="EUR",
            date=datetime.date(year, month, 1),
            category=self.config.category,
            comment=f"Vodafone mobile subscription for {month_str}",
            receipt_path=receipt_path,
        )

    async def _login(self, page) -> None:
        """Log in to My Vodafone (Ziggo unified login).

        Handles SMS 2FA if required. On first run, prompts for the SMS code
        interactively (or reads from VODAFONE_SMS_CODE env var) and checks
        "remember this device" so subsequent runs skip 2FA via saved cookies.
        """
        username = self.config.credentials.get("username", "")
        password = self.config.credentials.get("password", "")

        # Check if we're already logged in (cookies restored the session)
        current_url = page.url
        if "/my/facturen" in current_url or "/my/dashboard" in current_url:
            self.log.info("already_logged_in")
            return

        # Fill the single-page login form (Vodafone/Ziggo unified login)
        await page.fill("#j_username", username)
        await page.fill("#j_password", password)
        await page.click("#loginFormSubmitButton")
        await page.wait_for_load_state("networkidle")

        # Check if 2FA SMS code is required
        sms_field = page.locator('input[name="sms-code"], input[id*="sms"], input[placeholder*="Sms"]')
        if await sms_field.count() > 0:
            self.log.info("2fa_sms_required")

            # Get SMS code from environment variable or interactive prompt
            sms_code = os.environ.get("VODAFONE_SMS_CODE", "")
            if not sms_code:
                print("\n=== Vodafone 2FA ===", file=sys.stderr)
                print("An SMS code was sent to your phone.", file=sys.stderr)
                sms_code = input("Enter the 6-digit SMS code: ").strip()
            else:
                self.log.info("2fa_code_from_env")

            await sms_field.fill(sms_code)

            # Check "remember this device" to skip 2FA next time
            remember_checkbox = page.locator('input[type="checkbox"]')
            if await remember_checkbox.count() > 0:
                await remember_checkbox.check()
                self.log.info("remember_device_checked")

            # Submit the 2FA form
            submit_btn = page.locator('button:has-text("Code controleren"), button[type="submit"]')
            await submit_btn.click()
            await page.wait_for_load_state("networkidle")

    async def _extract_amount(self, page, year: int, month: int) -> int | None:
        """Extract the invoice amount for the given month from the invoices page.

        Returns amount in euro cents, or None if not found.

        TODO: Selectors below are best guesses — need to be calibrated against
              the real /my/facturen page DOM after a successful login + 2FA.
              Run with headless=false and inspect the page to find the correct
              selectors for invoice rows and amounts.
        """
        # Dutch month names for matching
        dutch_months = [
            "", "januari", "februari", "maart", "april", "mei", "juni",
            "juli", "augustus", "september", "oktober", "november", "december",
        ]

        month_name = dutch_months[month]

        # TODO: These selectors are guesses. After completing 2FA successfully,
        # take a screenshot of /my/facturen and update these to match the real DOM.
        invoice_rows = page.locator(
            f'tr:has-text("{month_name}"), '
            f'div[class*="invoice"]:has-text("{month_name}"), '
            f'li:has-text("{month_name}")'
        )

        count = await invoice_rows.count()
        if count == 0:
            # Try with numeric month format
            invoice_rows = page.locator(
                f'tr:has-text("{month:02d}-{year}"), '
                f'div[class*="invoice"]:has-text("{month:02d}-{year}")'
            )
            count = await invoice_rows.count()

        if count == 0:
            return None

        # Get text content and extract euro amount
        row_text = await invoice_rows.first.text_content()
        if not row_text:
            return None

        # Match euro amounts: €45,23 or € 45,23 or €45.23
        match = re.search(r"€\s*([\d.,]+)", row_text)
        if not match:
            return None

        amount_str = match.group(1).replace(".", "").replace(",", ".")
        amount_eur = Decimal(amount_str)
        return int(amount_eur * 100)

    async def _download_invoice(
        self, page, session: BrowserSession, year: int, month: int
    ) -> Path:
        """Download the invoice PDF for the given month.

        TODO: Selectors below are guesses — need calibration after successful
              login. Inspect the download button/link on /my/facturen.
        """
        dutch_months = [
            "", "januari", "februari", "maart", "april", "mei", "juni",
            "juli", "augustus", "september", "oktober", "november", "december",
        ]

        month_name = dutch_months[month]

        # TODO: Update these selectors to match the real DOM
        download_btn = page.locator(
            f'a:has-text("Download"):near(:has-text("{month_name}")), '
            f'a:has-text("PDF"):near(:has-text("{month_name}")), '
            f'button:has-text("Download"):near(:has-text("{month_name}"))'
        ).first

        async with page.expect_download() as download_info:
            await download_btn.click()

        download = await download_info.value
        save_path = await session.save_download(download)

        self.log.info("invoice_downloaded", path=str(save_path))
        return save_path
