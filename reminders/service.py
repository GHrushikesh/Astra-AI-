"""Scheduler and manager for reminders.

Handles:
- Scheduling future reminders
- Canceling reminders
- Listing active reminders
- Triggering notification callbacks at exact scheduled times
- Persisting state across restarts
- Graceful shutdown
"""

from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Callable, List, Optional

from reminders.exceptions import (
    DuplicateReminderError,
    InvalidReminderTimeError,
    ReminderNotFoundError,
)
from reminders.models import Reminder
from reminders.storage import ReminderStore


class ReminderService:
    """Service to schedule, persist, and fire task reminders."""

    def __init__(
        self,
        store: Optional[ReminderStore] = None,
        notification_callback: Optional[Callable[[Reminder], None]] = None,
    ) -> None:
        self._store = store or ReminderStore()
        self._callback = notification_callback
        self._reminders: List[Reminder] = []
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None

        self._load_and_start()

    def _load_and_start(self) -> None:
        """Load stored reminders and start background timer worker."""
        with self._lock:
            self._reminders = self._store.load()

        self._worker_thread = threading.Thread(
            target=self._check_loop,
            daemon=True,
            name="AstraReminderWorker",
        )
        self._worker_thread.start()

    def schedule(self, task: str, remind_at: datetime) -> Reminder:
        """Schedule a new reminder.

        Raises:
            InvalidReminderTimeError: If remind_at is in the past or invalid.
            DuplicateReminderError: If an identical active reminder exists.
        """
        clean_task = (task or "").strip()
        if not clean_task:
            raise InvalidReminderTimeError("Reminder task description cannot be empty.")

        now = datetime.now()
        if remind_at <= now:
            raise InvalidReminderTimeError(
                f"Cannot schedule reminder in the past. Remind at: {remind_at}, current: {now}"
            )

        with self._lock:
            for r in self._reminders:
                if not r.triggered and r.task == clean_task and r.remind_at == remind_at:
                    raise DuplicateReminderError(
                        f"A reminder for '{clean_task}' at {remind_at} already exists."
                    )

            reminder = Reminder(task=clean_task, remind_at=remind_at)
            self._reminders.append(reminder)
            self._store.save(self._reminders)
            return reminder

    def cancel(self, reminder_id: str) -> bool:
        """Cancel an existing reminder by ID."""
        with self._lock:
            initial_len = len(self._reminders)
            self._reminders = [r for r in self._reminders if r.id != reminder_id]
            if len(self._reminders) < initial_len:
                self._store.save(self._reminders)
                return True
            raise ReminderNotFoundError(f"Reminder with ID '{reminder_id}' not found.")

    def list_active(self) -> List[Reminder]:
        """Return all upcoming untriggered reminders sorted by trigger time."""
        now = datetime.now()
        with self._lock:
            active = [r for r in self._reminders if not r.triggered and r.remind_at > now]
            return sorted(active, key=lambda r: r.remind_at)

    def list_all(self) -> List[Reminder]:
        """Return all reminders (active and triggered)."""
        with self._lock:
            return list(self._reminders)

    def stop(self) -> None:
        """Stop background worker cleanly."""
        self._stop_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)

    def _check_loop(self) -> None:
        """Background thread checking for due reminders."""
        while not self._stop_event.is_set():
            now = datetime.now()
            due: List[Reminder] = []

            with self._lock:
                for r in self._reminders:
                    if not r.triggered and r.remind_at <= now:
                        r.triggered = True
                        due.append(r)
                if due:
                    self._store.save(self._reminders)

            for reminder in due:
                if self._callback:
                    try:
                        self._callback(reminder)
                    except Exception:
                        pass

            self._stop_event.wait(timeout=1.0)
