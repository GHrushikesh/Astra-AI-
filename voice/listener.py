"""Speech-to-text listener for the Astra voice input service.

This module captures audio from a microphone and returns a plain text
transcript.  It performs no intent recognition, planning, or AI reasoning —
those concerns belong exclusively to the AI core.

Backend: Google Web Speech API (free, via the ``SpeechRecognition`` library).
The ``speech_recognition`` import is deferred to the ``listen()`` call so that
Astra starts correctly even when the library is not installed.
"""

from __future__ import annotations

from voice.exceptions import (
    ListenTimeoutError,
    MicrophoneNotFoundError,
    MicrophonePermissionError,
    RecognitionError,
    RecognitionServiceError,
)

# Sensible defaults — all overridable per call.
_DEFAULT_LISTEN_TIMEOUT: float = 5.0    # seconds to wait for speech to begin
_DEFAULT_PHRASE_TIMEOUT: float = 10.0   # max seconds to record one phrase
_DEFAULT_ENERGY_THRESHOLD: int = 300    # initial energy level for silence detection
_AMBIENT_NOISE_DURATION: float = 0.5   # seconds used to calibrate ambient noise


class SpeechListener:
    """Capture microphone audio and return a transcribed text string.

    This class is the single public entry-point for voice input.  The caller
    is responsible for running it on a background thread so the UI remains
    responsive.

    Args:
        microphone_name: Display name of the device to use, as returned by
            ``enumerate_microphones()``.  Pass ``"Default microphone"`` (or
            leave it empty) to use the system default.
        energy_threshold: Initial energy level for the silence detector.
            Higher values make the recogniser less sensitive to quiet sounds.
        dynamic_energy: When ``True`` (recommended) the recogniser adapts the
            energy threshold automatically after each recording.
    """

    def __init__(
        self,
        microphone_name: str = "Default microphone",
        energy_threshold: int = _DEFAULT_ENERGY_THRESHOLD,
        dynamic_energy: bool = True,
    ) -> None:
        self._microphone_name = microphone_name
        self._energy_threshold = energy_threshold
        self._dynamic_energy = dynamic_energy

    # ── Public API ─────────────────────────────────────────────────────────────

    def listen(
        self,
        timeout: float = _DEFAULT_LISTEN_TIMEOUT,
        phrase_timeout: float = _DEFAULT_PHRASE_TIMEOUT,
    ) -> str:
        """Record speech and return the recognised text.

        Args:
            timeout: Seconds to wait for the user to begin speaking before
                raising :class:`~voice.exceptions.ListenTimeoutError`.
            phrase_timeout: Maximum seconds to record a single phrase.

        Returns:
            Transcribed text string (never empty on success).

        Raises:
            RecognitionServiceError: ``SpeechRecognition`` is not installed.
            MicrophoneNotFoundError: The configured device does not exist or
                cannot be opened.
            MicrophonePermissionError: The OS denied microphone access.
            ListenTimeoutError: No speech began within *timeout* seconds.
            RecognitionError: Audio was captured but could not be understood.
            RecognitionServiceError: The Google STT API returned an error.
        """
        sr = self._import_sr()
        recognizer = self._make_recognizer(sr)
        device_index = self._resolve_mic_index(sr)
        audio = self._record(sr, recognizer, device_index, timeout, phrase_timeout)
        return self._transcribe(recognizer, audio, sr)

    # ── Private helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _import_sr():  # type: ignore[return]
        """Import speech_recognition lazily, raising a clear error if absent."""
        try:
            import speech_recognition as sr
            return sr
        except ImportError as exc:
            raise RecognitionServiceError(
                "The SpeechRecognition library is not installed. "
                "Run: pip install SpeechRecognition PyAudio"
            ) from exc

    def _make_recognizer(self, sr):  # type: ignore[return]
        """Create and configure a Recognizer instance."""
        recognizer = sr.Recognizer()
        recognizer.energy_threshold = self._energy_threshold
        recognizer.dynamic_energy_threshold = self._dynamic_energy
        return recognizer

    def _resolve_mic_index(self, sr) -> int | None:
        """Translate a device name to a PyAudio device index.

        Returns ``None`` for the system default microphone.
        Raises :class:`~voice.exceptions.MicrophoneNotFoundError` if the
        requested name is not found in the enumerated device list.
        """
        if self._microphone_name in ("Default microphone", ""):
            return None
        try:
            names: list[str] = sr.Microphone.list_microphone_names()
        except Exception:
            # PyAudio failure — fall back to the default device.
            return None
        for index, name in enumerate(names):
            if name == self._microphone_name:
                return index
        raise MicrophoneNotFoundError(
            f"Microphone '{self._microphone_name}' was not found. "
            f"Available devices: {names or ['(none)']}"
        )

    @staticmethod
    def _record(sr, recognizer, device_index: int | None, timeout: float, phrase_timeout: float):
        """Open the microphone, calibrate for noise, and capture one phrase."""
        try:
            with sr.Microphone(device_index=device_index) as source:
                recognizer.adjust_for_ambient_noise(source, duration=_AMBIENT_NOISE_DURATION)
                try:
                    audio = recognizer.listen(
                        source,
                        timeout=timeout,
                        phrase_time_limit=phrase_timeout,
                    )
                except sr.WaitTimeoutError as exc:
                    raise ListenTimeoutError(
                        "No speech was detected. Please try again."
                    ) from exc
        except OSError as exc:
            msg = str(exc).lower()
            if any(word in msg for word in ("permission", "access denied", "denied")):
                raise MicrophonePermissionError(
                    "Microphone access was denied. "
                    "Check your Windows privacy settings (Settings → Privacy → Microphone)."
                ) from exc
            raise MicrophoneNotFoundError(
                f"The microphone could not be opened: {exc}"
            ) from exc
        return audio

    @staticmethod
    def _transcribe(recognizer, audio, sr) -> str:
        """Send the captured audio to Google's STT and return the transcript."""
        try:
            return recognizer.recognize_google(audio)
        except sr.UnknownValueError as exc:
            raise RecognitionError(
                "Speech was captured but could not be understood. "
                "Please speak clearly and try again."
            ) from exc
        except sr.RequestError as exc:
            raise RecognitionServiceError(
                f"Speech recognition service unavailable: {exc}"
            ) from exc
