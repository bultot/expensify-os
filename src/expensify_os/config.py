"""YAML configuration loading with 1Password secret injection."""

from __future__ import annotations

from pathlib import Path

import structlog
import yaml

from expensify_os.models import AppConfig
from expensify_os.utils.secrets import resolve_secrets_in_dict

logger = structlog.get_logger()

DEFAULT_CONFIG_PATHS = [
    Path("config.yaml"),
    Path("config.yml"),
    Path.home() / ".config" / "expensify-os" / "config.yaml",
]


def find_config_file(config_path: Path | None = None) -> Path:
    """Find the configuration file.

    Args:
        config_path: Explicit path to config file. If None, searches default locations.

    Returns:
        Path to the configuration file.

    Raises:
        FileNotFoundError: If no configuration file is found.
    """
    if config_path is not None:
        if config_path.exists():
            return config_path
        raise FileNotFoundError(f"Config file not found: {config_path}")

    for path in DEFAULT_CONFIG_PATHS:
        if path.exists():
            logger.info("config_found", path=str(path))
            return path

    search_paths = ", ".join(str(p) for p in DEFAULT_CONFIG_PATHS)
    raise FileNotFoundError(
        f"No config file found. Searched: {search_paths}. "
        f"Create one from config.example.yaml."
    )


def load_config(config_path: Path | None = None, resolve_secrets: bool = True) -> AppConfig:
    """Load and validate application configuration.

    Args:
        config_path: Explicit path to config file.
        resolve_secrets: Whether to resolve 1Password secret references.
            Set to False for validation without 1Password access.

    Returns:
        Validated AppConfig instance.
    """
    path = find_config_file(config_path)
    logger.info("loading_config", path=str(path))

    raw = yaml.safe_load(path.read_text())

    if resolve_secrets:
        raw = resolve_secrets_in_dict(raw)

    return AppConfig.model_validate(raw)
