"""Astra Action & Tool Layer.

Provides Windows automation tools for application management, file handling,
system diagnostics, OS controls, and web actions.
"""

from actions.base import (
    ActionConfirmationRequired,
    ActionError,
    ActionResult,
    get_logger,
)
from actions.registry import (
    ActionRegistry,
    execute_action,
    get_action,
    get_action_metadata,
    list_actions,
)

__all__ = [
    "ActionResult",
    "ActionError",
    "ActionConfirmationRequired",
    "get_logger",
    "ActionRegistry",
    "execute_action",
    "get_action",
    "get_action_metadata",
    "list_actions",
]
