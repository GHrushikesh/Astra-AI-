"""Small integration boundary between the UI and Astra's AI core."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class AssistantResponse:
    """User-facing response returned by an assistant implementation."""

    text: str
    success: bool = True
    error: str | None = None


class AssistantInterface(Protocol):
    """Interface the project lead's assistant implementation must provide."""

    def process(self, user_text: str) -> AssistantResponse:
        """Process user text and return a displayable response."""


class EchoAssistant:
    """Temporary UI-only assistant used to run Astra before AI core integration."""

    def process(self, user_text: str) -> AssistantResponse:
        return AssistantResponse(text=f"I received: {user_text}")
