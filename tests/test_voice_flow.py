"""End-to-end integration tests for full voice interaction flow."""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    from ui.assistant_interface import AssistantInterface, AssistantResponse
    from ui.main_window import MainWindow
except ImportError:
    QApplication = None


class FakeVoiceAssistant(AssistantInterface):
    """Fake assistant implementation for testing voice-to-response flow."""

    def __init__(self) -> None:
        self.received_texts = []

    def process(self, user_text: str) -> AssistantResponse:
        self.received_texts.append(user_text)
        if "error" in user_text:
            return AssistantResponse(text="Failed", success=False, error="Intent error")
        return AssistantResponse(text=f"Executed: {user_text}", success=True)


@unittest.skipIf(QApplication is None, "PySide6 not installed")
class TestVoiceInteractionFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_voice_to_assistant_flow(self):
        assistant = FakeVoiceAssistant()
        window = MainWindow(assistant=assistant)
        try:
            # Simulate recognized voice text arriving via voice callback
            window._on_voice_text("Open Calculator")
            self.app.processEvents()

            # Wait for assistant worker to finish
            if window._worker is not None:
                window._worker.wait()
                self.app.processEvents()

            self.assertIn("Open Calculator", assistant.received_texts)
            self.assertEqual(window.status_label.text(), "Ready")
        finally:
            window.close()

    def test_voice_error_displays_cleanly(self):
        assistant = FakeVoiceAssistant()
        window = MainWindow(assistant=assistant)
        try:
            window._on_voice_error("Microphone timed out")
            self.app.processEvents()
            self.assertIn("Voice input failed", window.status_label.text())
        finally:
            window.close()


if __name__ == "__main__":
    unittest.main()
