"""Tests for browser storage and automation utilities."""

from __future__ import annotations

import json
from pathlib import Path

from expensify_os.browser.storage import (
    get_state_dir,
    load_cookies,
    save_cookies,
)


class TestBrowserStorage:
    def test_get_state_dir_creates_directory(self, tmp_path: Path):
        state_dir = get_state_dir("test_plugin", base_dir=tmp_path)
        assert state_dir.exists()
        assert state_dir == tmp_path / "test_plugin"

    def test_save_and_load_cookies(self, tmp_path: Path):
        cookies = [
            {"name": "session", "value": "abc123", "domain": ".example.com", "path": "/"},
            {"name": "token", "value": "xyz789", "domain": ".example.com", "path": "/"},
        ]

        save_cookies("test_plugin", cookies, base_dir=tmp_path)

        loaded = load_cookies("test_plugin", base_dir=tmp_path)
        assert loaded == cookies

    def test_load_cookies_no_state(self, tmp_path: Path):
        result = load_cookies("nonexistent_plugin", base_dir=tmp_path)
        assert result is None

    def test_save_cookies_overwrites(self, tmp_path: Path):
        save_cookies("test_plugin", [{"name": "old"}], base_dir=tmp_path)
        save_cookies("test_plugin", [{"name": "new"}], base_dir=tmp_path)

        loaded = load_cookies("test_plugin", base_dir=tmp_path)
        assert loaded == [{"name": "new"}]

    def test_cookies_file_is_valid_json(self, tmp_path: Path):
        cookies = [{"name": "test", "value": "val"}]
        save_cookies("test_plugin", cookies, base_dir=tmp_path)

        cookie_file = tmp_path / "test_plugin" / "cookies.json"
        parsed = json.loads(cookie_file.read_text())
        assert parsed == cookies
