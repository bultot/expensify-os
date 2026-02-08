"""Abstract base class for expense source plugins."""

from __future__ import annotations

from abc import ABC, abstractmethod

import structlog

from expensify_os.models import ExpenseData, PluginConfig

logger = structlog.get_logger()


class ExpensePlugin(ABC):
    """Base class for all expense source plugins.

    Each plugin represents a single expense source (e.g. Anthropic, OpenAI, Vodafone)
    and knows how to fetch billing data and download a PDF receipt for a given month.
    """

    name: str = "unnamed"

    def __init__(self, config: PluginConfig) -> None:
        self.config = config
        self.log = logger.bind(plugin=self.name)

    @abstractmethod
    async def fetch_expense(
        self, year: int, month: int, *, dry_run: bool = False
    ) -> ExpenseData | None:
        """Fetch expense data and PDF receipt for the given billing month.

        Args:
            year: Billing year (e.g. 2026).
            month: Billing month (1-12).
            dry_run: If True, fetch data but skip downloads that would
                     have side effects (like browser logins).

        Returns:
            ExpenseData with receipt if an expense exists, or None
            if there was no charge for the given month.
        """

    @abstractmethod
    async def validate_credentials(self) -> bool:
        """Verify that the configured credentials are valid.

        Returns:
            True if credentials are valid and the source is reachable.
        """

    async def cleanup(self) -> None:
        """Clean up resources (browser contexts, temp files, etc).

        Override in subclasses that hold resources.
        """
