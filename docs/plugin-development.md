# Plugin Development Guide

This guide explains how to create a new expense source plugin for expensify-os.

## Plugin Interface

Every plugin must extend `ExpensePlugin` and implement two methods:

```python
from expensify_os.plugins.base import ExpensePlugin
from expensify_os.plugins.registry import register_plugin
from expensify_os.models import ExpenseData, PluginConfig

@register_plugin("my_source")
class MySourcePlugin(ExpensePlugin):
    name = "my_source"

    def __init__(self, config: PluginConfig) -> None:
        super().__init__(config)
        # Initialize HTTP clients, etc.

    async def fetch_expense(self, year: int, month: int, *, dry_run: bool = False) -> ExpenseData | None:
        """Fetch expense data for the given month.

        Returns:
            ExpenseData with receipt PDF, or None if no charge for the month.
        """
        ...

    async def validate_credentials(self) -> bool:
        """Check that credentials are valid."""
        ...

    async def cleanup(self) -> None:
        """Clean up resources (close HTTP clients, browser sessions, etc)."""
        ...
```

## ExpenseData Model

Your plugin must return an `ExpenseData` instance:

```python
ExpenseData(
    merchant="Service Name",        # Merchant name for Expensify
    amount=12345,                   # Amount in cents (12345 = $123.45)
    currency="USD",                 # ISO 4217 currency code
    date=date(2026, 1, 1),         # First of the billing month
    category="AI & ML Services",    # Category from plugin config
    comment="Usage for 2026-01",    # Optional description
    receipt_path=Path("path.pdf"),  # Downloaded receipt file
)
```

## Accessing Credentials

Credentials are available via `self.config.credentials`:

```python
api_key = self.config.credentials.get("api_key", "")
```

By the time your plugin runs, all `op://` references have been resolved to actual values.

## Plugin Types

### API-based plugins (e.g., Anthropic, OpenAI)

These plugins fetch cost data via REST APIs and download invoice PDFs via browser automation.

```python
async def fetch_expense(self, year, month, *, dry_run=False):
    # 1. Fetch cost from API
    total_cents = await self._fetch_cost_from_api(year, month)
    if total_cents == 0:
        return None

    # 2. Download PDF (skip in dry-run)
    if not dry_run:
        receipt_path = await self._download_invoice_via_browser(year, month)
    else:
        receipt_path = self._create_dry_run_placeholder(year, month)

    return ExpenseData(...)
```

### Browser-only plugins (e.g., Vodafone)

These plugins do everything through browser automation.

```python
async def fetch_expense(self, year, month, *, dry_run=False):
    async with BrowserSession(browser_config, "my_source") as session:
        page = await session.new_page()
        await self._login(page)
        amount = await self._extract_amount(page, year, month)
        receipt = await self._download_pdf(page, session, year, month)
        return ExpenseData(...)
```

## Browser Automation

Use `BrowserSession` for Playwright automation:

```python
from expensify_os.browser.automation import BrowserSession
from expensify_os.models import BrowserConfig

browser_config = BrowserConfig(headless=True, timeout=30000)

async with BrowserSession(browser_config, "my_source") as session:
    page = await session.new_page()
    await page.goto("https://example.com/login")

    # Download a file
    async with page.expect_download() as download_info:
        await page.click("#download-btn")
    download = await download_info.value
    path = await session.save_download(download)
```

`BrowserSession` automatically:
- Restores saved cookies (persistent login)
- Saves cookies after each session
- Captures error screenshots on failure

## Registration

1. Decorate your class with `@register_plugin("name")`
2. Add the import to `plugins/registry.py`:

```python
def discover_plugins() -> None:
    import expensify_os.plugins.my_source  # noqa: F401
```

## Configuration

Add your plugin to `config.example.yaml`:

```yaml
plugins:
  my_source:
    enabled: true
    credentials:
      api_key: "op://vault/item/api_key"
    category: "Category Name"
```

## Testing

Create `tests/test_plugins/test_my_source.py`:

```python
@pytest.fixture
def plugin():
    config = PluginConfig(credentials={"api_key": "test"}, category="Test")
    return MySourcePlugin(config)

@pytest.mark.asyncio
@respx.mock
async def test_fetch_expense_dry_run(plugin):
    # Mock API responses
    respx.get("https://api.example.com/billing").mock(...)
    expense = await plugin.fetch_expense(2026, 1, dry_run=True)
    assert expense.amount == expected_amount
```

## Logging

Use `self.log` (bound to the plugin name):

```python
self.log.info("fetching_costs", year=year, month=month)
self.log.error("api_failed", status=response.status_code)
```
