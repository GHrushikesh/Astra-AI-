"""Windows notifications service package for Astra."""

from __future__ import annotations

from notifications.exceptions import (
    NotificationError,
    NotificationPermissionError,
    NotificationUnavailableError,
)
from notifications.service import NotificationService, NotificationType

__all__ = [
    "NotificationService",
    "NotificationType",
    "NotificationError",
    "NotificationPermissionError",
    "NotificationUnavailableError",
]
