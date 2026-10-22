"""Astra voice input service (Phase 4).

Provides speech-to-text as a standalone, UI-agnostic service.
All public symbols are exported from this package for convenient import.

Minimal usage::

    from voice import SpeechListener
    text = SpeechListener().listen()   # blocks until phrase is captured

Run on a background thread to keep the UI responsive.
"""

from __future__ import annotations

from voice.devices import enumerate_microphones
from voice.exceptions import (
    ListenTimeoutError,
    MicrophoneNotFoundError,
    MicrophonePermissionError,
    RecognitionError,
    RecognitionServiceError,
    VoiceError,
)
from voice.listener import SpeechListener

__all__ = [
    "SpeechListener",
    "enumerate_microphones",
    # Exceptions
    "VoiceError",
    "MicrophoneNotFoundError",
    "MicrophonePermissionError",
    "ListenTimeoutError",
    "RecognitionError",
    "RecognitionServiceError",
]
