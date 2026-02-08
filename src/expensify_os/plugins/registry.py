"""Plugin discovery and registration."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from expensify_os.models import PluginConfig
    from expensify_os.plugins.base import ExpensePlugin

logger = structlog.get_logger()

# Global registry: plugin name -> plugin class
_registry: dict[str, type[ExpensePlugin]] = {}


def register_plugin(name: str):
    """Decorator to register a plugin class under a given name.

    Usage:
        @register_plugin("anthropic")
        class AnthropicPlugin(ExpensePlugin):
            ...
    """

    def decorator(cls: type[ExpensePlugin]) -> type[ExpensePlugin]:
        cls.name = name
        _registry[name] = cls
        logger.debug("plugin_registered", name=name, cls=cls.__name__)
        return cls

    return decorator


def get_plugin(name: str, config: PluginConfig) -> ExpensePlugin:
    """Instantiate a registered plugin by name.

    Args:
        name: The plugin name (e.g. "anthropic").
        config: The plugin's configuration.

    Returns:
        An instance of the plugin.

    Raises:
        KeyError: If no plugin is registered with that name.
    """
    if name not in _registry:
        available = ", ".join(sorted(_registry)) or "(none)"
        raise KeyError(f"Unknown plugin '{name}'. Available: {available}")

    return _registry[name](config)


def list_plugins() -> dict[str, type[ExpensePlugin]]:
    """Return all registered plugins."""
    return dict(_registry)


def discover_plugins() -> None:
    """Import all built-in plugin modules to trigger registration.

    Call this once at startup before accessing the registry.
    """
    # Importing these modules triggers their @register_plugin decorators
    import expensify_os.plugins.anthropic  # noqa: F401
    import expensify_os.plugins.openai  # noqa: F401
    import expensify_os.plugins.vodafone  # noqa: F401

    logger.info("plugins_discovered", count=len(_registry), names=sorted(_registry))
