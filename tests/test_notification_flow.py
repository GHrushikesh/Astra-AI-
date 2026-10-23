"""Integration tests for notification and reminder flow (Phase 10)."""

from __future__ import annotations

import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from reminders.coordinator import NotificationReminderCoordinator
from reminders.storage import ReminderStore
from ui.settings import AstraSettings, SettingsStore


class TestNotificationReminderIntegration(unittest.TestCase):
    @patch("notifications.service.NotificationService.notify_reminder")
    def test_reminder_fires_notification(self, mock_notify):
        with TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            settings_store = SettingsStore(base / "settings.json")
            reminder_store = ReminderStore(base / "reminders.json")

            coord = NotificationReminderCoordinator(
                settings_store=settings_store,
                reminder_store=reminder_store,
            )
            try:
                soon = datetime.now() + timedelta(seconds=1)
                coord.schedule_reminder("Prepare presentation", soon)

                time.sleep(2.2)
                mock_notify.assert_called_with("Prepare presentation")
            finally:
                coord.shutdown()

    @patch("notifications.service.NotificationService.notify_action_completed")
    @patch("notifications.service.NotificationService.notify_error")
    def test_action_notifications(self, mock_err, mock_succ):
        with TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            settings_store = SettingsStore(base / "settings.json")
            reminder_store = ReminderStore(base / "reminders.json")

            coord = NotificationReminderCoordinator(
                settings_store=settings_store,
                reminder_store=reminder_store,
            )
            try:
                coord.notify_action_success("Open App", "Chrome launched")
                mock_succ.assert_called_with("Open App", "Chrome launched")

                coord.notify_action_failure("Open App", "Permission denied")
                mock_err.assert_called_with("Open App failed: Permission denied")
            finally:
                coord.shutdown()


if __name__ == "__main__":
    unittest.main()
