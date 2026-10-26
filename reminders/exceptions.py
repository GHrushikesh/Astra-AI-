"""Custom exceptions for Astra's reminder service."""

from __future__ import annotations


class ReminderError(Exception):
    """Base exception for all reminder operations."""


class InvalidReminderTimeError(ReminderError):
    """The specified reminder time is invalid or has already passed."""


class DuplicateReminderError(ReminderError):
    """A duplicate reminder already exists."""


class ReminderNotFoundError(ReminderError):
    """The requested reminder could not be found."""
