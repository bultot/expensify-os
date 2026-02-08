# n8n Integration Guide

This guide explains how to set up expensify-os as a monthly automated job using [n8n](https://n8n.io).

## Overview

```
Schedule Trigger (1st of month, 09:00)
  → Execute Command (expensify-os run)
  → Check exit code
  → Slack notification (success / failure)
```

## Prerequisites

- n8n instance (self-hosted or cloud)
- 1Password CLI (`op`) available on the n8n host
- expensify-os installed and configured on the n8n host
- Slack incoming webhook URL (optional, for notifications)

## Setup

### 1. Install expensify-os on the n8n host

```bash
git clone https://github.com/bultot/expensify-os.git /opt/expensify-os
cd /opt/expensify-os
uv sync
uv run playwright install chromium
cp config.example.yaml config.yaml
# Edit config.yaml with your op:// references
```

### 2. Import the n8n workflow

Import `examples/n8n-workflow.json` into your n8n instance:

1. Open n8n
2. Go to Workflows → Import from File
3. Select `examples/n8n-workflow.json`
4. Update the workflow:
   - **Execute Command node**: Update the working directory path
   - **Slack nodes**: Set your `SLACK_WEBHOOK_URL` environment variable

### 3. Configure the Execute Command node

The command should run with 1Password secret injection:

```bash
op run --env-file=/opt/expensify-os/.env.op -- uv run expensify-os run
```

Set the working directory to your installation path (e.g., `/opt/expensify-os`).

### 4. Set up Slack notifications

1. Create a [Slack Incoming Webhook](https://api.slack.com/messaging/webhooks)
2. Set the `SLACK_WEBHOOK_URL` environment variable in n8n
3. The workflow sends:
   - Success: summary of submitted expenses
   - Failure: error details and exit code

## Workflow Details

### Schedule Trigger

- Runs on the **1st of each month at 09:00**
- expensify-os automatically targets the **previous month** when no `--month` flag is given

### Execute Command

```bash
op run --env-file=.env.op -- uv run expensify-os run
```

Exit codes:
- `0`: All plugins succeeded
- `1`: One or more plugins failed

### Error Handling

If the command fails:
1. The "Check Exit Code" node routes to the failure Slack notification
2. stderr output is included in the Slack message for debugging
3. Check the n8n execution log for full output

## Testing

Test the workflow manually:

```bash
# Dry run first
op run --env-file=.env.op -- uv run expensify-os run --dry-run

# Then a real run for a specific source
op run --env-file=.env.op -- uv run expensify-os run --source anthropic --month 2026-01
```

## Troubleshooting

### 1Password not available

Ensure the n8n service user has access to 1Password CLI and is signed in:

```bash
op signin
op run --env-file=.env.op -- echo "1Password OK"
```

### Playwright browser not found

Install Chromium for the n8n service user:

```bash
uv run playwright install chromium
```

### Timeout issues

Increase browser timeout in `config.yaml`:

```yaml
browser:
  timeout: 60000  # 60 seconds
```
