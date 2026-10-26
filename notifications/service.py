"""Windows toast notification service for Astra.

Supports:
- Action completed notifications
- Reminder notifications
- Error alerts
- System status notifications
- Honoring the user's notification preference (enabled/disabled)
- Graceful degradation without crashing if notification backend is unavailable
"""

from __future__ import annotations

import os
import platform
import subprocess
from enum import Enum
from typing import Optional

from notifications.exceptions import (
    NotificationError,
    NotificationPermissionError,
    NotificationUnavailableError,
)
from ui.settings import AstraSettings, SettingsStore


class NotificationType(str, Enum):
    """Categorized notification types."""

    INFO = "info"
    REMINDER = "reminder"
    ACTION_COMPLETED = "action_completed"
    ERROR = "error"
    SYSTEM_ALERT = "system_alert"


class NotificationService:
    """Windows toast notification service.

    Args:
        settings_store: Optional SettingsStore to check notification preference.
    """

    def __init__(self, settings_store: Optional[SettingsStore] = None) -> None:
        self._store = settings_store or SettingsStore()

    def is_enabled(self) -> bool:
        """Check if desktop notifications are enabled in user settings."""
        try:
            settings = self._store.load()
            return bool(settings.notifications_enabled)
        except Exception:
            return True

    def notify(
        self,
        title: str,
        message: str,
        notification_type: NotificationType = NotificationType.INFO,
    ) -> bool:
        """Display a Windows desktop toast notification.

        Returns True if delivered or safely skipped because notifications are disabled.
        Raises NotificationError subclass on critical unexpected failure.
        """
        # Respect user settings
        if not self.is_enabled():
            return False

        clean_title = (title or "Astra").strip()
        clean_msg = (message or "").strip()
        if not clean_msg:
            return False

        # On non-Windows platforms, fallback cleanly
        if platform.system() != "Windows":
            return False

        return self._send_windows_toast(clean_title, clean_msg)

    def notify_action_completed(self, action_name: str, message: str) -> bool:
        """Send notification for a completed action."""
        title = f"Astra: {action_name}"
        return self.notify(title, message, NotificationType.ACTION_COMPLETED)

    def notify_reminder(self, task: str) -> bool:
        """Send notification for an active reminder."""
        return self.notify("Astra Reminder", task, NotificationType.REMINDER)

    def notify_error(self, message: str) -> bool:
        """Send error alert notification."""
        return self.notify("Astra Error", message, NotificationType.ERROR)

    def notify_system(self, title: str, message: str) -> bool:
        """Send system alert notification."""
        return self.notify(f"Astra: {title}", message, NotificationType.SYSTEM_ALERT)

    def _send_windows_toast(self, title: str, message: str) -> bool:
        """Deliver toast notification using Windows Runtime via PowerShell."""
        # Escape single quotes for PowerShell
        esc_title = title.replace("'", "''")
        esc_message = message.replace("'", "''")

        script = f"""
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
        [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
        
        $template = @"
<toast>
    <visual>
        <binding template="ToastGeneric">
            <text>{esc_title}</text>
            <text>{esc_message}</text>
        </binding>
    </visual>
</toast>
"@
        $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
        $xml.LoadXml($template)
        $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Astra.Assistant").Show($toast)
        """

        cmd = [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            script,
        ]

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=8,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if res.returncode != 0:
                err_text = res.stderr.strip()
                if "Access is denied" in err_text or "Permission" in err_text:
                    raise NotificationPermissionError(f"Permission denied: {err_text}")
                # Don't crash Astra if notifications fail on some Windows builds
                return False
            return True
        except Exception as exc:
            if isinstance(exc, NotificationError):
                raise
            return False
