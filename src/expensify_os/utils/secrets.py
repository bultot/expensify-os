"""1Password CLI integration for secret resolution."""

from __future__ import annotations

import subprocess

import structlog

logger = structlog.get_logger()

OP_PREFIX = "op://"


def is_secret_reference(value: str) -> bool:
    """Check if a string is a 1Password secret reference."""
    return isinstance(value, str) and value.startswith(OP_PREFIX)


def resolve_secret(reference: str) -> str:
    """Resolve a single 1Password secret reference using `op read`.

    Args:
        reference: A 1Password reference like "op://vault/item/field"

    Returns:
        The resolved secret value.

    Raises:
        RuntimeError: If `op` CLI fails or is not available.
    """
    if not is_secret_reference(reference):
        return reference

    try:
        result = subprocess.run(
            ["op", "read", reference],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        return result.stdout.strip()
    except FileNotFoundError:
        raise RuntimeError(
            "1Password CLI (`op`) is not installed or not in PATH. "
            "Install it from https://1password.com/downloads/command-line/"
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"Failed to resolve secret {reference}: {e.stderr.strip()}"
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"Timed out resolving secret {reference}. Is 1Password unlocked?"
        )


def resolve_secrets_in_dict(data: dict) -> dict:
    """Recursively resolve all 1Password references in a dictionary.

    Walks the dict tree and replaces any string value starting with "op://"
    with the resolved secret from 1Password CLI.
    """
    resolved = {}
    for key, value in data.items():
        if isinstance(value, dict):
            resolved[key] = resolve_secrets_in_dict(value)
        elif isinstance(value, str) and is_secret_reference(value):
            logger.debug("resolving_secret", key=key, reference=value[:30] + "...")
            resolved[key] = resolve_secret(value)
        else:
            resolved[key] = value
    return resolved
