"""Base models, error definitions, and utilities for the Astra Action Layer."""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Optional


def get_logger(name: str = "astra.actions") -> logging.Logger:
    """Return a configured logger for the action layer.
    
    Uses NullHandler by default so that the host application or AI core
    can configure their own root logging handlers without interference.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())
    return logger


logger = get_logger("astra.actions")


@dataclass(frozen=True)
class ActionResult(Mapping[str, Any]):
    """Standardized result envelope returned by all action tools.
    
    Provides both attribute access (`result.success`) and dictionary
    access (`result["success"]`) for seamless integration with callers.
    """
    success: bool
    message: str
    data: Any = None
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert the result into a clean dictionary."""
        return asdict(self)

    @classmethod
    def ok(cls, message: str, data: Any = None) -> ActionResult:
        """Convenience constructor for successful actions."""
        return cls(success=True, message=message, data=data, error=None)

    @classmethod
    def fail(
        cls, message: str, error: Optional[str] = None, data: Any = None
    ) -> ActionResult:
        """Convenience constructor for failed actions."""
        return cls(
            success=False,
            message=message,
            data=data,
            error=error if error is not None else message,
        )

    # Implement Mapping protocol for dictionary-style access: result["success"]
    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def __iter__(self):
        yield "success"
        yield "message"
        yield "data"
        yield "error"

    def __len__(self) -> int:
        return 4


class ActionError(Exception):
    """Base exception for action layer operations."""


class ActionConfirmationRequired(ActionError):
    """Raised or referenced when a high-risk action requires explicit user confirmation."""

    def __init__(self, action_name: str, message: Optional[str] = None):
        self.action_name = action_name
        msg = (
            message
            or f"Action '{action_name}' requires explicit confirmation (confirmed=True)."
        )
        super().__init__(msg)
