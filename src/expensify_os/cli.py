"""Click CLI for expensify-os."""

from __future__ import annotations

import asyncio
import datetime
import sys

import click
import structlog

from expensify_os import __version__
from expensify_os.utils.logging import setup_logging

logger = structlog.get_logger()


class MonthType(click.ParamType):
    """Click parameter type for YYYY-MM month strings."""

    name = "month"

    def convert(self, value, param, ctx):
        if isinstance(value, tuple):
            return value
        try:
            parts = value.split("-")
            year, month = int(parts[0]), int(parts[1])
            if not (1 <= month <= 12):
                raise ValueError
            return (year, month)
        except (ValueError, IndexError):
            self.fail(f"'{value}' is not a valid month (expected YYYY-MM)", param, ctx)


MONTH = MonthType()


@click.group()
@click.version_option(version=__version__)
@click.option("-v", "--verbose", is_flag=True, help="Enable debug logging.")
@click.option(
    "-c", "--config", "config_path", type=click.Path(exists=True), default=None,
    help="Path to config.yaml.",
)
@click.pass_context
def cli(ctx: click.Context, verbose: bool, config_path: str | None) -> None:
    """expensify-os — Automated expense management."""
    setup_logging(verbose=verbose)
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["config_path"] = config_path


@cli.command()
@click.option(
    "--month", "month", type=MONTH, default=None,
    help="Billing month as YYYY-MM. Defaults to previous month.",
)
@click.option(
    "--source", "sources", multiple=True,
    help="Specific plugin(s) to run. Omit for all enabled plugins.",
)
@click.option(
    "--dry-run", is_flag=True,
    help="Fetch data but don't submit to Expensify.",
)
@click.pass_context
def run(ctx: click.Context, month: tuple[int, int] | None, sources: tuple[str, ...], dry_run: bool) -> None:
    """Fetch expenses and submit to Expensify."""
    asyncio.run(_run_async(ctx, month, sources, dry_run))


async def _run_async(
    ctx: click.Context,
    month: tuple[int, int] | None,
    sources: tuple[str, ...],
    dry_run: bool,
) -> None:
    """Async implementation of the run command."""
    from pathlib import Path

    from expensify_os.config import load_config
    from expensify_os.expensify.client import ExpensifyClient
    from expensify_os.plugins.registry import discover_plugins, get_plugin, list_plugins

    config_path = ctx.obj.get("config_path")
    config = load_config(Path(config_path) if config_path else None)

    discover_plugins()

    # Determine target month
    if month:
        year, mon = month
    else:
        today = datetime.date.today()
        if today.month == 1:
            year, mon = today.year - 1, 12
        else:
            year, mon = today.year, today.month - 1

    click.echo(f"Target month: {year}-{mon:02d}")
    if dry_run:
        click.echo("DRY RUN — will not submit to Expensify")

    # Determine which plugins to run
    available = list_plugins()
    if sources:
        plugin_names = [s for s in sources if s in config.plugins and config.plugins[s].enabled]
    else:
        plugin_names = [name for name, pc in config.plugins.items() if pc.enabled and name in available]

    if not plugin_names:
        click.echo("No plugins to run. Check config and --source flags.", err=True)
        sys.exit(1)

    click.echo(f"Running plugins: {', '.join(plugin_names)}")

    results: list[dict] = []

    for name in plugin_names:
        plugin_config = config.plugins[name]
        plugin = get_plugin(name, plugin_config)

        try:
            click.echo(f"\n--- {name} ---")
            expense = await plugin.fetch_expense(year, mon, dry_run=dry_run)

            if expense is None:
                click.echo(f"  No charges for {year}-{mon:02d}")
                results.append({"plugin": name, "status": "skipped"})
                continue

            click.echo(
                f"  Amount: {expense.currency} {expense.amount_decimal:.2f}"
            )
            click.echo(f"  Receipt: {expense.receipt_path}")

            if not dry_run:
                async with ExpensifyClient(config.expensify) as client:
                    result = await client.submit_expense(expense)
                click.echo(f"  Submitted! Transaction: {result.get('transaction_id', 'N/A')}")
            else:
                click.echo("  [DRY RUN] Would submit to Expensify")

            results.append({
                "plugin": name,
                "status": "success",
                "amount": expense.amount,
                "currency": expense.currency,
            })

        except Exception as e:
            logger.error("plugin_failed", plugin=name, error=str(e), exc_info=True)
            click.echo(f"  ERROR: {e}", err=True)
            results.append({"plugin": name, "status": "error", "error": str(e)})

        finally:
            await plugin.cleanup()

    # Summary
    click.echo("\n=== Summary ===")
    success_count = sum(1 for r in results if r["status"] == "success")
    error_count = sum(1 for r in results if r["status"] == "error")
    click.echo(f"Submitted: {success_count}, Skipped: {len(results) - success_count - error_count}, Errors: {error_count}")

    if error_count > 0:
        sys.exit(1)


@cli.command()
@click.pass_context
def validate(ctx: click.Context) -> None:
    """Validate configuration and credentials."""
    asyncio.run(_validate_async(ctx))


async def _validate_async(ctx: click.Context) -> None:
    """Async implementation of the validate command."""
    from pathlib import Path

    from expensify_os.config import load_config
    from expensify_os.plugins.registry import discover_plugins, get_plugin

    config_path = ctx.obj.get("config_path")

    click.echo("Validating configuration...")
    try:
        config = load_config(Path(config_path) if config_path else None)
        click.echo("  Config: OK")
    except Exception as e:
        click.echo(f"  Config: FAILED — {e}", err=True)
        sys.exit(1)

    click.echo(f"  Expensify email: {config.expensify.employee_email}")
    click.echo(f"  Default currency: {config.expensify.default_currency}")

    discover_plugins()

    click.echo("\nValidating plugin credentials...")
    all_ok = True

    for name, plugin_config in config.plugins.items():
        if not plugin_config.enabled:
            click.echo(f"  {name}: disabled")
            continue

        try:
            plugin = get_plugin(name, plugin_config)
            ok = await plugin.validate_credentials()
            status = "OK" if ok else "INVALID"
            if not ok:
                all_ok = False
            click.echo(f"  {name}: {status}")
            await plugin.cleanup()
        except KeyError:
            click.echo(f"  {name}: UNKNOWN PLUGIN", err=True)
            all_ok = False

    if not all_ok:
        click.echo("\nSome validations failed.", err=True)
        sys.exit(1)

    click.echo("\nAll validations passed.")


@cli.command(name="plugins")
def list_plugins_cmd() -> None:
    """List all available plugins."""
    from expensify_os.plugins.registry import discover_plugins, list_plugins

    discover_plugins()
    plugins = list_plugins()

    if not plugins:
        click.echo("No plugins registered.")
        return

    click.echo("Available plugins:")
    for name, cls in sorted(plugins.items()):
        click.echo(f"  {name:15s} {cls.__module__}.{cls.__name__}")
