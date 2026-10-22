"""Microphone device enumeration for the Astra voice input service.

This module is intentionally UI-agnostic and has no Qt dependency.
It may be imported from the settings dialog to populate device dropdowns.
"""

from __future__ import annotations


def enumerate_microphones() -> list[str]:
    """Return the names of all available microphone input devices.

    The list always begins with ``"Default microphone"`` as a safe
    fallback.  Additional entries come from the PyAudio device enumeration
    provided by the ``SpeechRecognition`` library.  If ``SpeechRecognition``
    or ``PyAudio`` is not installed, only the default entry is returned —
    no exception is raised.

    Returns:
        Ordered list of device name strings, starting with the default.
    """
    devices: list[str] = ["Default microphone"]
    try:
        import speech_recognition as sr  # lazy — not required at import time

        names: list[str] = sr.Microphone.list_microphone_names()
        for name in names:
            if name not in devices:
                devices.append(name)
    except Exception:  # ImportError, OSError, or any PyAudio failure
        pass
    return devices
