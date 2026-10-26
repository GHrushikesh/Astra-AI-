"""Persistence store for Astra reminders."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List

from reminders.models import Reminder


class ReminderStore:
    """Read and write reminders to local JSON storage."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or self.default_path()

    @staticmethod
    def default_path() -> Path:
        app_data = os.environ.get("LOCALAPPDATA")
        base = Path(app_data) if app_data else Path.home() / ".config"
        return base / "Astra" / "reminders.json"

    def load(self) -> List[Reminder]:
        """Load all reminders from storage."""
        if not self.path.exists():
            return []
        try:
            content = self.path.read_text(encoding="utf-8").strip()
            if not content:
                return []
            raw = json.loads(content)
            if not isinstance(raw, list):
                return []
            return [Reminder.from_dict(item) for item in raw if isinstance(item, dict)]
        except Exception:
            return []

    def save(self, reminders: List[Reminder]) -> None:
        """Atomically save reminders to storage."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_file = self.path.with_suffix(".tmp")
        data = [r.to_dict() for r in reminders]
        temp_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        temp_file.replace(self.path)
