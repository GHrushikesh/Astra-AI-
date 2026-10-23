"""Data model for structured reminders."""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict


@dataclass
class Reminder:
    """A scheduled task reminder for Astra.

    Args:
        task: Description of the task to be reminded about.
        remind_at: Future datetime when the reminder should trigger.
        id: Unique identifier for the reminder.
        created_at: When the reminder was created.
        triggered: Whether the reminder has already fired.
    """

    task: str
    remind_at: datetime
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    triggered: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize reminder to JSON-compatible dictionary."""
        return {
            "id": self.id,
            "task": self.task,
            "remind_at": self.remind_at.isoformat(),
            "created_at": self.created_at.isoformat(),
            "triggered": self.triggered,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Reminder:
        """Construct reminder from dictionary."""
        return cls(
            id=str(data["id"]),
            task=str(data["task"]),
            remind_at=datetime.fromisoformat(data["remind_at"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            triggered=bool(data.get("triggered", False)),
        )
