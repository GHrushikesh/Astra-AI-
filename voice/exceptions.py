"""Custom exceptions for the Astra voice input service.

All voice errors derive from VoiceError so callers can catch the
whole family with a single except clause when fine-grained handling
is not required.
"""

from __future__ import annotations


class VoiceError(Exception):
    """Base class for all voice input errors."""


class MicrophoneNotFoundError(VoiceError):
    """The requested microphone device could not be located."""


class MicrophonePermissionError(VoiceError):
    """The operating system denied access to the microphone."""


class ListenTimeoutError(VoiceError):
    """No speech was detected within the configured timeout period."""


class RecognitionError(VoiceError):
    """Audio was captured but the speech could not be understood."""


class RecognitionServiceError(VoiceError):
    """The speech recognition backend is unavailable or returned an error."""
