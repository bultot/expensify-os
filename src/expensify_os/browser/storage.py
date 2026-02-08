"""Browser session state management.

Stores and restores browser authentication state (cookies, localStorage)
so plugins don't need to re-authenticate every run.
"""

from __future__ import annotations

import json
from pathlib import Path

import structlog

logger = structlog.get_logger()

DEFAULT_STATE_DIR = Path.home() / ".config" / "expensify-os" / "browser_state"


def get_state_dir(plugin_name: str, base_dir: Path | None = None) -> Path:
    """Get (and create) the browser state directory for a plugin.

    Args:
        plugin_name: Plugin name used as subdirectory.
        base_dir: Override the default state directory.

    Returns:
        Path to the plugin's state directory.
    """
    base = base_dir or DEFAULT_STATE_DIR
    state_dir = base / plugin_name
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir


def save_cookies(plugin_name: str, cookies: list[dict], base_dir: Path | None = None) -> Path:
    """Save browser cookies to disk.

    Args:
        plugin_name: Plugin name for state isolation.
        cookies: List of cookie dicts from Playwright.
        base_dir: Override default state directory.

    Returns:
        Path to the saved cookies file.
    """
    state_dir = get_state_dir(plugin_name, base_dir)
    cookie_file = state_dir / "cookies.json"
    cookie_file.write_text(json.dumps(cookies, indent=2))
    logger.debug("cookies_saved", plugin=plugin_name, count=len(cookies))
    return cookie_file


def load_cookies(plugin_name: str, base_dir: Path | None = None) -> list[dict] | None:
    """Load previously saved cookies.

    Args:
        plugin_name: Plugin name for state isolation.
        base_dir: Override default state directory.

    Returns:
        List of cookie dicts, or None if no saved state exists.
    """
    state_dir = get_state_dir(plugin_name, base_dir)
    cookie_file = state_dir / "cookies.json"

    if not cookie_file.exists():
        logger.debug("no_saved_cookies", plugin=plugin_name)
        return None

    cookies = json.loads(cookie_file.read_text())
    logger.debug("cookies_loaded", plugin=plugin_name, count=len(cookies))
    return cookies
