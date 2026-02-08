"""Tests for the CLI."""

from __future__ import annotations

from click.testing import CliRunner

from expensify_os.cli import MONTH, cli


class TestMonthType:
    def test_valid_month(self):
        result = MONTH.convert("2026-01", None, None)
        assert result == (2026, 1)

    def test_valid_december(self):
        result = MONTH.convert("2025-12", None, None)
        assert result == (2025, 12)

    def test_invalid_format(self):
        import click
        import pytest

        with pytest.raises(click.exceptions.BadParameter):
            MONTH.convert("not-a-month", None, None)

    def test_invalid_month_number(self):
        import click
        import pytest

        with pytest.raises(click.exceptions.BadParameter):
            MONTH.convert("2026-13", None, None)


class TestCLI:
    def test_version(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Automated expense management" in result.output

    def test_run_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["run", "--help"])
        assert result.exit_code == 0
        assert "--month" in result.output
        assert "--dry-run" in result.output
        assert "--source" in result.output

    def test_validate_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["validate", "--help"])
        assert result.exit_code == 0

    def test_plugins_list(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["plugins"])
        assert result.exit_code == 0
        assert "Available plugins:" in result.output
        assert "anthropic" in result.output
        assert "openai" in result.output
        assert "vodafone" in result.output


class TestNotifications:
    def test_format_run_summary(self):
        from expensify_os.utils.notifications import format_run_summary

        results = [
            {"plugin": "anthropic", "status": "success", "amount": 5000, "currency": "USD"},
            {"plugin": "openai", "status": "success", "amount": 2500, "currency": "USD"},
            {"plugin": "vodafone", "status": "skipped"},
        ]

        summary = format_run_summary(results)
        assert "Anthropic" in summary or "anthropic" in summary
        assert "openai" in summary
        assert "vodafone" in summary
        assert "75.00" in summary  # total: 5000 + 2500 = 7500 cents = $75.00
