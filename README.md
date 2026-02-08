# expensify-os

> Automated expense management — fetch invoices, download receipts, submit to Expensify.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.13%2B-3776AB.svg?logo=python&logoColor=white)](https://www.python.org)
[![uv](https://img.shields.io/badge/uv-package%20manager-DE5FE9.svg)](https://docs.astral.sh/uv/)

---

## Overview

**expensify-os** is a CLI tool that automates recurring business expense submissions to [Expensify](https://www.expensify.com). It fetches billing data from multiple sources (Anthropic, OpenAI, Vodafone, etc.), downloads PDF receipts, and submits individual expenses to Expensify via its Integration API.

Built for the workflow: many recurring monthly subscriptions, each requiring manual login to download invoices. This tool does it all automatically, orchestrated by [n8n](https://n8n.io) for monthly scheduling.

## Features

- **Plugin architecture** — each expense source is a self-contained plugin
- **API + browser automation** — fetches billing data via APIs where available, falls back to Playwright browser automation for invoice PDF downloads
- **Expensify Integration API** — creates expenses and uploads receipt attachments
- **Rate limiting** — respects Expensify's 5 req/10s and 20 req/60s limits
- **1Password integration** — all secrets managed via `op://` references, never stored on disk
- **Dry-run mode** — preview what would be submitted without making changes
- **Persistent browser sessions** — reuses authenticated cookies across runs
- **n8n ready** — designed to run as a scheduled job with Slack notifications

## Getting Started

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager
- [1Password CLI](https://1password.com/downloads/command-line/) (`op`)
- [Playwright browsers](https://playwright.dev/python/docs/intro) (for invoice downloads)

### Installation

```bash
git clone https://github.com/bultot/expensify-os.git
cd expensify-os
uv sync

# Install Playwright browsers
uv run playwright install chromium
```

### Configuration

1. Copy the example config:

```bash
cp config.example.yaml config.yaml
```

2. Update `config.yaml` with your 1Password secret references:

```yaml
expensify:
  partner_user_id: "op://work/expensify-api/partner_user_id"
  partner_user_secret: "op://work/expensify-api/partner_user_secret"
  employee_email: "your.email@company.com"

plugins:
  anthropic:
    enabled: true
    credentials:
      admin_api_key: "op://work/anthropic/admin_api_key"
    category: "AI & ML Services"
```

3. Validate your setup:

```bash
op run --env-file=.env.op -- uv run expensify-os validate
```

## Usage

```bash
# Run for previous month (all enabled plugins)
uv run expensify-os run

# Specific month
uv run expensify-os run --month 2026-01

# Specific sources only
uv run expensify-os run --source anthropic --source openai

# Preview without submitting
uv run expensify-os run --dry-run

# Validate config and credentials
uv run expensify-os validate

# List available plugins
uv run expensify-os plugins
```

### With 1Password

```bash
op run --env-file=.env.op -- uv run expensify-os run
```

## Configuration

### `config.yaml`

| Section | Description |
|---------|-------------|
| `expensify` | Expensify API credentials and employee email |
| `plugins.<name>` | Per-plugin config: `enabled`, `credentials`, `category` |
| `browser` | Playwright settings: `headless`, `timeout`, `screenshots_on_error` |

All credential values should be `op://` references (see [config.example.yaml](config.example.yaml)).

### Environment

The `.env.op` file contains 1Password references for environment variables, used with `op run --env-file=.env.op`.

## Architecture

```
expensify-os run
  │
  ├── Load config.yaml (resolve op:// secrets via 1Password CLI)
  ├── Discover plugins
  │
  ├── For each enabled plugin:
  │   ├── Fetch billing data (API or browser)
  │   ├── Download invoice PDF (browser automation)
  │   └── Submit expense + receipt to Expensify API
  │
  └── Report results (exit code + optional Slack notification)
```

### Plugin Types

| Plugin | Data Source | Invoice Download |
|--------|-----------|-----------------|
| Anthropic | Admin API (`/v1/organizations/cost_report`) | Console browser automation |
| OpenAI | Organization Costs API (`/v1/organization/costs`) | Platform browser automation |
| Vodafone | Browser automation (My Vodafone) | Browser automation |

### Project Structure

```
src/expensify_os/
├── cli.py                  # Click CLI entry point
├── config.py               # YAML config + 1Password injection
├── models.py               # Pydantic data models
├── expensify/
│   ├── client.py           # Expensify API client
│   └── rate_limiter.py     # Sliding-window rate limiter
├── plugins/
│   ├── base.py             # Abstract plugin interface
│   ├── registry.py         # Plugin discovery/registration
│   ├── anthropic.py        # Anthropic plugin
│   ├── openai.py           # OpenAI plugin
│   └── vodafone.py         # Vodafone plugin
├── browser/
│   ├── automation.py       # Playwright session wrapper
│   └── storage.py          # Cookie persistence
└── utils/
    ├── secrets.py           # 1Password CLI wrapper
    ├── logging.py           # structlog configuration
    └── notifications.py     # Slack webhook notifications
```

## Contributing

### Adding a new plugin

1. Create `src/expensify_os/plugins/your_source.py`
2. Implement the `ExpensePlugin` interface:

```python
from expensify_os.plugins.base import ExpensePlugin
from expensify_os.plugins.registry import register_plugin

@register_plugin("your_source")
class YourSourcePlugin(ExpensePlugin):
    name = "your_source"

    async def fetch_expense(self, year, month, *, dry_run=False):
        # Fetch billing data and download receipt
        ...

    async def validate_credentials(self):
        # Verify credentials are valid
        ...
```

3. Import the module in `plugins/registry.py`'s `discover_plugins()`
4. Add tests in `tests/test_plugins/test_your_source.py`

See [docs/plugin-development.md](docs/plugin-development.md) for the full guide.

### Running tests

```bash
uv run pytest -v
```

## n8n Integration

The tool is designed to run as a monthly scheduled job via n8n:

```
Schedule Trigger (1st of month, 9:00)
  → Execute Command: op run --env-file=.env.op -- uv run expensify-os run
  → Check exit code
  → Slack notification (success/failure)
```

An example n8n workflow is provided in [examples/n8n-workflow.json](examples/n8n-workflow.json). See [docs/n8n-integration.md](docs/n8n-integration.md) for setup instructions.

## License

[MIT](LICENSE)
