"""Astra Text-to-Speech (TTS) service package."""

from __future__ import annotations

from tts.exceptions import (
    SpeakerNotFoundError,
    SynthesisError,
    SynthesizerUnavailableError,
    TTSError,
)
from tts.synthesizer import SpeechSynthesizer, enumerate_voices

__all__ = [
    "SpeechSynthesizer",
    "enumerate_voices",
    "TTSError",
    "SpeakerNotFoundError",
    "SynthesizerUnavailableError",
    "SynthesisError",
]
