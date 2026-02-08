"""Notification utilities for reporting results via Slack webhooks."""

from __future__ import annotations

import httpx
import structlog

logger = structlog.get_logger()


async def send_slack_notification(
    webhook_url: str,
    text: str,
    *,
    username: str = "expensify-os",
) -> bool:
    """Send a notification to Slack via incoming webhook.

    Args:
        webhook_url: Slack incoming webhook URL.
        text: Message text (supports Slack markdown).
        username: Bot username to display.

    Returns:
        True if the message was sent successfully.
    """
    if not webhook_url:
        logger.debug("slack_notification_skipped", reason="no webhook URL")
        return False

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                webhook_url,
                json={"text": text, "username": username},
            )
            response.raise_for_status()
            logger.info("slack_notification_sent")
            return True
    except httpx.HTTPError:
        logger.warning("slack_notification_failed", exc_info=True)
        return False


def format_run_summary(results: list[dict]) -> str:
    """Format expense run results into a Slack message.

    Args:
        results: List of dicts with keys: plugin, status, amount, currency, error.

    Returns:
        Formatted Slack message string.
    """
    lines = [":receipt: *expensify-os Run Summary*\n"]

    successes = [r for r in results if r["status"] == "success"]
    failures = [r for r in results if r["status"] == "error"]
    skipped = [r for r in results if r["status"] == "skipped"]

    if successes:
        lines.append("*Submitted:*")
        for r in successes:
            amount = r.get("amount", 0) / 100
            currency = r.get("currency", "")
            lines.append(f"  • {r['plugin']}: {currency} {amount:.2f}")

    if skipped:
        lines.append("*No charges:*")
        for r in skipped:
            lines.append(f"  • {r['plugin']}")

    if failures:
        lines.append("*Failed:*")
        for r in failures:
            lines.append(f"  • {r['plugin']}: {r.get('error', 'unknown error')}")

    total = sum(r.get("amount", 0) for r in successes)
    if total:
        lines.append(f"\n*Total submitted:* {total / 100:.2f}")

    return "\n".join(lines)
