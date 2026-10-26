"""Unit tests for the Astra reminder service."""

from __future__ import annotations

import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from reminders.exceptions import (
    DuplicateReminderError,
    InvalidReminderTimeError,
    ReminderNotFoundError,
)
from reminders.models import Reminder
from reminders.service import ReminderService
from reminders.storage import ReminderStore


class TestReminders(unittest.TestCase):
    def test_schedule_valid_reminder(self):
        with TemporaryDirectory() as tmpdir:
            store = ReminderStore(Path(tmpdir) / "reminders.json")
            service = ReminderService(store=store)
            try:
                future = datetime.now() + timedelta(hours=2)
                r = service.schedule("Study DAA", future)
                self.assertEqual(r.task, "Study DAA")
                self.assertEqual(r.remind_at, future)
                self.assertFalse(r.triggered)

                active = service.list_active()
                self.assertEqual(len(active), 1)
                self.assertEqual(active[0].task, "Study DAA")
            finally:
                service.stop()

    def test_schedule_past_time_fails(self):
        with TemporaryDirectory() as tmpdir:
            store = ReminderStore(Path(tmpdir) / "reminders.json")
            service = ReminderService(store=store)
            try:
                past = datetime.now() - timedelta(minutes=5)
                with self.assertRaises(InvalidReminderTimeError):
                    service.schedule("Past task", past)
            finally:
                service.stop()

    def test_duplicate_reminder_rejected(self):
        with TemporaryDirectory() as tmpdir:
            store = ReminderStore(Path(tmpdir) / "reminders.json")
            service = ReminderService(store=store)
            try:
                future = datetime.now() + timedelta(minutes=30)
                service.schedule("Call home", future)
                with self.assertRaises(DuplicateReminderError):
                    service.schedule("Call home", future)
            finally:
                service.stop()

    def test_cancel_reminder(self):
        with TemporaryDirectory() as tmpdir:
            store = ReminderStore(Path(tmpdir) / "reminders.json")
            service = ReminderService(store=store)
            try:
                future = datetime.now() + timedelta(hours=1)
                r = service.schedule("Exercise", future)
                self.assertTrue(service.cancel(r.id))
                self.assertEqual(len(service.list_active()), 0)

                with self.assertRaises(ReminderNotFoundError):
                    service.cancel(r.id)
            finally:
                service.stop()

    def test_persistence_across_service_instances(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "reminders.json"
            store = ReminderStore(path)
            future = datetime.now() + timedelta(hours=4)

            s1 = ReminderService(store=store)
            s1.schedule("Read documentation", future)
            s1.stop()

            # Second instance loads from same file
            s2 = ReminderService(store=store)
            try:
                active = s2.list_active()
                self.assertEqual(len(active), 1)
                self.assertEqual(active[0].task, "Read documentation")
            finally:
                s2.stop()

    def test_trigger_callback(self):
        triggered = []

        def callback(r):
            triggered.append(r)

        with TemporaryDirectory() as tmpdir:
            store = ReminderStore(Path(tmpdir) / "reminders.json")
            service = ReminderService(store=store, notification_callback=callback)
            try:
                # Schedule very soon
                soon = datetime.now() + timedelta(seconds=1)
                service.schedule("Quick reminder", soon)
                time.sleep(2.2)

                self.assertGreaterEqual(len(triggered), 1)
                self.assertEqual(triggered[0].task, "Quick reminder")
            finally:
                service.stop()


if __name__ == "__main__":
    unittest.main()
