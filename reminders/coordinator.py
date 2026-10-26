"""Integration orchestrator connecting AI Core, Reminders, and Notifications."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from notifications.service import NotificationService
from reminders.models import Reminder
from reminders.service import ReminderService
from reminders.storage import ReminderStore
from ui.settings import SettingsStore


class NotificationReminderCoordinator:
    """Coordinates scheduled reminders and desktop notifications.

    When reminders trigger, dispatches formatted toast notifications
    honoring user preferences. Also provides helper functions for
    completed action and error notifications.
    """

    def __init__(
        self,
        settings_store: Optional[SettingsStore] = None,
        reminder_store: Optional[ReminderStore] = None,
    ) -> None:
        self.settings_store = settings_store or SettingsStore()
        self.notification_service = NotificationService(self.settings_store)
        self.reminder_service = ReminderService(
            store=reminder_store or ReminderStore(),
            notification_callback=self._on_reminder_triggered,
        )

    def _on_reminder_triggered(self, reminder: Reminder) -> None:
        """Triggered callback from ReminderService."""
        self.notification_service.notify_reminder(reminder.task)

    def schedule_reminder(self, task: str, remind_at: datetime) -> Reminder:
        """Schedule a structured task reminder."""
        return self.reminder_service.schedule(task, remind_at)

    def cancel_reminder(self, reminder_id: str) -> bool:
        """Cancel a reminder by ID."""
        return self.reminder_service.cancel(reminder_id)

    def notify_action_success(self, action_name: str, message: str) -> bool:
        """Send notification when an AI core action completes."""
        return self.notification_service.notify_action_completed(action_name, message)

    def notify_action_failure(self, action_name: str, error: str) -> bool:
        """Send notification on AI core action failure."""
        return self.notification_service.notify_error(f"{action_name} failed: {error}")

    def shutdown(self) -> None:
        """Cleanly stop reminder background worker."""
        self.reminder_service.stop()
