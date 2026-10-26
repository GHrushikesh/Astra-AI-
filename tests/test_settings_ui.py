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

    def test_dialog_saves_llm_preferences(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SettingsStore(Path(directory) / "settings.json")
            settings = AstraSettings()
            dialog = _SettingsDialog(settings, store)
            dialog.llm_provider.setCurrentText("Groq")
            dialog.llm_api_key.setText("gsk-secret-test-key")
            dialog.llm_model.setText("llama-3.3-70b-versatile")
            dialog.llm_endpoint.setText("https://api.groq.com/openai/v1")
            dialog._save()

            loaded = store.load()
            self.assertEqual(loaded.llm_provider, "Groq")
            self.assertEqual(loaded.llm_api_key, "gsk-secret-test-key")
            self.assertEqual(loaded.llm_model, "llama-3.3-70b-versatile")
            self.assertEqual(loaded.llm_endpoint, "https://api.groq.com/openai/v1")
            dialog.close()


if __name__ == "__main__":
    unittest.main()
