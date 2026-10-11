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

__all__ = [
    "ActionResult",
    "ActionError",
    "ActionConfirmationRequired",
    "get_logger",
]
