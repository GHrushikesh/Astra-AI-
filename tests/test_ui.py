"""Focused tests for the Phase 1 desktop UI."""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QLabel
    from ui.assistant_interface import AssistantResponse
    from ui.main_window import MainWindow
except ImportError:
    QApplication = None


@unittest.skipIf(QApplication is None, "PySide6 is not installed")
class TestMainWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    @classmethod
    def tearDownClass(cls):
        for widget in cls.app.topLevelWidgets():
            widget.close()
        cls.app.processEvents()
        cls.app.quit()

    @staticmethod
    def wait_for_status(window, status, timeout=1000):
        elapsed = 0
        while not window.status_label.text().startswith(status) and elapsed < timeout:
            QTest.qWait(25)
            elapsed += 25

    @staticmethod
    def wait_for_messages(window, count, timeout=1000):
        elapsed = 0
        while window.conversation.count() < count and elapsed < timeout:
            QTest.qWait(25)
            elapsed += 25

    @staticmethod
    def message_text(window, index):
        widget = window.conversation.itemWidget(window.conversation.item(index))
        labels = widget.findChildren(QLabel)
        return " ".join(label.text() for label in labels)

    def test_initial_conversation_is_displayed(self):
        window = MainWindow()
        self.assertEqual(window.conversation.count(), 1)
        self.assertIn("Astra", self.message_text(window, 0))
        window.close()

    def test_message_is_sent_to_injected_assistant(self):
        class FakeAssistant:
            def __init__(self):
                self.received = []

            def process(self, user_text):
                self.received.append(user_text)
                return AssistantResponse("Done.")

        assistant = FakeAssistant()
        window = MainWindow(assistant=assistant)
        window.input.setText("Check my tasks")
        window.send_button.click()
        self.wait_for_messages(window, 3)

        self.assertEqual(assistant.received, ["Check my tasks"])
        self.assertIn("You", self.message_text(window, 1))
        self.assertIn("Check my tasks", self.message_text(window, 1))
        self.assertIn("Done.", self.message_text(window, 2))
        self.assertTrue(window.status_label.text().startswith("Ready"))
        window.close()

    def test_assistant_failure_is_displayed_without_crashing(self):
        class FailingAssistant:
            def process(self, user_text):
                raise RuntimeError("core unavailable")

        window = MainWindow(assistant=FailingAssistant())
        window.input.setText("Hello")
        window.send_button.click()
        self.wait_for_messages(window, 3)

        self.assertTrue(window.status_label.text().startswith("Error"))
        self.assertIn("core unavailable", self.message_text(window, 2))
        window.close()

    def test_input_is_disabled_while_assistant_is_processing(self):
        import time

        class SlowAssistant:
            def process(self, user_text):
                time.sleep(0.1)
                return AssistantResponse("Finished.")

        window = MainWindow(assistant=SlowAssistant())
        window.input.setText("Wait for this")
        window.send_button.click()

        self.assertFalse(window.input.isEnabled())
        self.assertFalse(window.send_button.isEnabled())
        self.wait_for_messages(window, 3)
        self.assertTrue(window.input.isEnabled())
        self.assertTrue(window.status_label.text().startswith("Ready"))
        window.close()


if __name__ == "__main__":
    unittest.main()
