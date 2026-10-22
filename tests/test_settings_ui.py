"""Focused tests for the Phase 3 settings dialog."""

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    from ui.main_window import _SettingsDialog
    from ui.settings import AstraSettings, SettingsStore
except ImportError:
    QApplication = None


@unittest.skipIf(QApplication is None, "PySide6 is not installed")
class TestSettingsDialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_dialog_saves_all_preferences(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SettingsStore(Path(directory) / "settings.json")
            settings = AstraSettings()
            dialog = _SettingsDialog(settings, store)
            dialog.microphone.addItem("USB microphone")
            dialog.microphone.setCurrentText("USB microphone")
            dialog.speaker.addItem("Headphones")
            dialog.speaker.setCurrentText("Headphones")
            dialog.speech_speed.setValue(205)
            dialog.notifications.setChecked(False)
            dialog.theme.setCurrentText("Dark")
            dialog.start_with_windows.setChecked(True)
            dialog.compact_mode.setChecked(True)
            dialog._save()

            self.assertEqual(
                store.load(),
                AstraSettings(
                    microphone="USB microphone",
                    speaker="Headphones",
                    speech_speed=205,
                    notifications_enabled=False,
                    theme="Dark",
                    start_with_windows=True,
                    compact_messages=True,
                ),
            )
            dialog.close()


if __name__ == "__main__":
    unittest.main()
