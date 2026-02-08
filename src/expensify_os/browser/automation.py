"""Playwright browser automation utilities.

Provides a managed browser session wrapper with:
- Automatic screenshot capture on errors
- Cookie persistence for authenticated sessions
- Download handling for PDF receipts
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import structlog
from playwright.async_api import async_playwright

from expensify_os.browser.storage import load_cookies, save_cookies
from expensify_os.models import BrowserConfig

if TYPE_CHECKING:
    from playwright.async_api import BrowserContext, Page

logger = structlog.get_logger()


class BrowserSession:
    """Managed Playwright browser session with error handling.

    Usage:
        async with BrowserSession(config, "anthropic") as session:
            page = await session.new_page()
            await page.goto("https://console.anthropic.com")
            # ...
            pdf_path = await session.wait_for_download(page)
    """

    def __init__(
        self,
        config: BrowserConfig,
        plugin_name: str,
        download_dir: Path | None = None,
        state_dir: Path | None = None,
    ) -> None:
        self.config = config
        self.plugin_name = plugin_name
        self.download_dir = download_dir or Path("downloads") / plugin_name
        self.state_dir = state_dir
        self._playwright = None
        self._browser = None
        self._context: BrowserContext | None = None
        self.log = logger.bind(plugin=plugin_name)

    async def __aenter__(self) -> BrowserSession:
        self.download_dir.mkdir(parents=True, exist_ok=True)

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.config.headless,
        )
        self._context = await self._browser.new_context(
            accept_downloads=True,
        )
        self._context.set_default_timeout(self.config.timeout)

        # Restore saved cookies if available
        cookies = load_cookies(self.plugin_name, self.state_dir)
        if cookies:
            await self._context.add_cookies(cookies)
            self.log.info("session_restored")

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        # Save cookies for next run
        if self._context:
            try:
                cookies = await self._context.cookies()
                save_cookies(self.plugin_name, cookies, self.state_dir)
            except Exception:
                self.log.warning("failed_to_save_cookies", exc_info=True)

        # Capture screenshot on error
        if exc_type and self.config.screenshots_on_error:
            await self._capture_error_screenshot()

        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def new_page(self) -> Page:
        """Create a new page in the browser context."""
        if not self._context:
            raise RuntimeError("BrowserSession not started. Use `async with`.")
        return await self._context.new_page()

    async def wait_for_download(self, page: Page, timeout: float | None = None) -> Path:
        """Wait for a file download to complete and return the saved path.

        Args:
            page: The page where the download will be triggered.
            timeout: Override default timeout in milliseconds.

        Returns:
            Path to the downloaded file in the download directory.
        """
        t = timeout or self.config.timeout
        async with page.expect_download(timeout=t) as download_info:
            pass  # Caller should trigger the download before awaiting this

        download = await download_info.value
        filename = download.suggested_filename or f"{self.plugin_name}_receipt.pdf"
        save_path = self.download_dir / filename
        await download.save_as(save_path)

        self.log.info("download_complete", path=str(save_path))
        return save_path

    async def download_triggered(self, page: Page) -> Path:
        """Wait for an already-triggered download to complete.

        Call this AFTER the action that triggers the download. For example:

            async with page.expect_download() as download_info:
                await page.click("#download-btn")
            download = await download_info.value
            path = await session.save_download(download)
        """
        # This method is a convenience — most plugins will use the
        # expect_download context manager directly for precise control
        raise NotImplementedError("Use page.expect_download() directly for precise control")

    async def save_download(self, download) -> Path:
        """Save a Playwright Download object to the download directory.

        Args:
            download: A Playwright Download object.

        Returns:
            Path to the saved file.
        """
        filename = download.suggested_filename or f"{self.plugin_name}_receipt.pdf"
        save_path = self.download_dir / filename
        await download.save_as(save_path)
        self.log.info("download_saved", path=str(save_path))
        return save_path

    async def _capture_error_screenshot(self) -> None:
        """Capture a screenshot of all open pages for debugging."""
        if not self._context:
            return

        screenshots_dir = Path("screenshots")
        screenshots_dir.mkdir(exist_ok=True)

        for i, page in enumerate(self._context.pages):
            try:
                path = screenshots_dir / f"{self.plugin_name}_error_{i}.png"
                await page.screenshot(path=path, full_page=True)
                self.log.info("error_screenshot_captured", path=str(path))
            except Exception:
                self.log.warning("screenshot_capture_failed", page_index=i, exc_info=True)
