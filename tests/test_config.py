"""Tests for configuration loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from expensify_os.config import find_config_file, load_config


class TestFindConfigFile:
    def test_explicit_path_exists(self, tmp_path: Path):
        config = tmp_path / "config.yaml"
        config.write_text("expensify: {}")
        assert find_config_file(config) == config

    def test_explicit_path_missing(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            find_config_file(tmp_path / "nonexistent.yaml")

    def test_default_search(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        # No config files in any default location
        monkeypatch.chdir(tmp_path)
        with pytest.raises(FileNotFoundError, match="No config file found"):
            find_config_file()

    def test_finds_config_yaml_in_cwd(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        config = tmp_path / "config.yaml"
        config.write_text("test: true")
        assert find_config_file() == Path("config.yaml")


class TestLoadConfig:
    def test_load_valid_config(self, tmp_path: Path, config_yaml_content: str):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_yaml_content)

        config = load_config(config_file, resolve_secrets=False)

        assert config.expensify.partner_user_id == "test_user"
        assert config.expensify.employee_email == "test@example.com"
        assert config.plugins["anthropic"].enabled is True
        assert config.browser.headless is True

    def test_load_with_op_references_skipped(self, tmp_path: Path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""\
expensify:
  partner_user_id: "op://vault/item/field"
  partner_user_secret: "op://vault/item/secret"
  employee_email: "test@example.com"
""")

        # With resolve_secrets=False, op:// references are kept as-is
        config = load_config(config_file, resolve_secrets=False)
        assert config.expensify.partner_user_id == "op://vault/item/field"
