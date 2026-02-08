"""Structured logging configuration using structlog."""

from __future__ import annotations

import logging
import sys

import structlog


def setup_logging(*, verbose: bool = False) -> None:
    """Configure structlog for console output.

    Args:
        verbose: If True, set log level to DEBUG. Otherwise INFO.
    """
    log_level = logging.DEBUG if verbose else logging.INFO

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.WriteLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=False,
    )

    # Also configure stdlib logging for libraries that use it
    logging.basicConfig(level=log_level, stream=sys.stderr, format="%(message)s")
