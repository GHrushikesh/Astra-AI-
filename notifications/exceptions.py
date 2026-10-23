"""Custom exceptions for Astra's notification service."""

from __future__ import annotations


class NotificationError(Exception):
    """Base exception for all notification failures."""


class NotificationPermissionError(NotificationError):
    """Notification permission was denied or disabled."""


class NotificationUnavailableError(NotificationError):
    """Windows notification service is unavailable."""
