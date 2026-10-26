"""Unit tests for Astra's notification service."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from notifications.exceptions import (
    NotificationError,
    NotificationPermissionError,
    NotificationUnavailableError,
)
from notifications.service import NotificationService, NotificationType
from ui.settings import AstraSettings, SettingsStore


class TestNotifications(unittest.TestCase):
    def test_exception_hierarchy(self):
        self.assertTrue(issubclass(NotificationPermissionError, NotificationError))
        self.assertTrue(issubclass(NotificationUnavailableError, NotificationError))

    def test_disabled_setting_skips_notification(self):
        with TemporaryDirectory() as tmpdir:
            store = SettingsStore(Path(tmpdir) / "settings.json")
            store.save(AstraSettings(notifications_enabled=False))

            service = NotificationService(store)
            result = service.notify("Test Title", "Test Message")
            self.assertFalse(result)

    def test_empty_message_returns_false(self):
        with TemporaryDirectory() as tmpdir:
            store = SettingsStore(Path(tmpdir) / "settings.json")
            service = NotificationService(store)
            self.assertFalse(service.notify("Title", ""))
            self.assertFalse(service.notify("Title", "   "))

    @patch("notifications.service.platform.system", return_value="Linux")
    def test_non_windows_skips_cleanly(self, mock_plat):
        with TemporaryDirectory() as tmpdir:
            store = SettingsStore(Path(tmpdir) / "settings.json")
            service = NotificationService(store)
            self.assertFalse(service.notify("Title", "Msg"))

    @patch("notifications.service.platform.system", return_value="Windows")
    @patch("notifications.service.subprocess.run")
    def test_send_toast_success(self, mock_run, mock_plat):
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_run.return_value = mock_res

        with TemporaryDirectory() as tmpdir:
            store = SettingsStore(Path(tmpdir) / "settings.json")
            service = NotificationService(store)
            result = service.notify("Astra", "Hello!")
            self.assertTrue(result)
            mock_run.assert_called_once()

    @patch("notifications.service.platform.system", return_value="Windows")
    @patch("notifications.service.subprocess.run")
    def test_convenience_methods(self, mock_run, mock_plat):
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_run.return_value = mock_res

        with TemporaryDirectory() as tmpdir:
            store = SettingsStore(Path(tmpdir) / "settings.json")
            service = NotificationService(store)
            self.assertTrue(service.notify_action_completed("App Open", "Notepad opened"))
            self.assertTrue(service.notify_reminder("Study DAA"))
            self.assertTrue(service.notify_error("Could not find file"))
            self.assertTrue(service.notify_system("Status", "Connected"))


if __name__ == "__main__":
    unittest.main()
