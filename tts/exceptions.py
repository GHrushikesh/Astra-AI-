"""Custom exceptions for Astra's Text-to-Speech (TTS) service."""

from __future__ import annotations


class TTSError(Exception):
    """Base class for all TTS errors."""


class SpeakerNotFoundError(TTSError):
    """The requested speaker or voice could not be found."""


class SynthesizerUnavailableError(TTSError):
    """The TTS backend is not available on this system."""


class SynthesisError(TTSError):
    """Failed to synthesize or output audio."""
