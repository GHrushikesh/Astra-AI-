"""Phase 4 voice input tests — fully mocked, no real microphone required.

All ``speech_recognition`` interactions are replaced with in-memory stubs so
the test suite runs on any CI or developer machine regardless of audio hardware
or installed system libraries.
"""

from __future__ import annotations

import builtins
import sys
import types
import unittest
from unittest.mock import MagicMock


# ─────────────────────────────────────────────────────────────────────────────
# Shared stub factory
# ─────────────────────────────────────────────────────────────────────────────

def _build_sr_stub() -> tuple[types.ModuleType, MagicMock]:
    """Return (sr_module_stub, recognizer_instance_mock).

    The stub replicates the parts of ``speech_recognition`` that
    ``voice.listener`` and ``voice.devices`` touch.
    """
    sr = types.ModuleType("speech_recognition")

    # Exception types used by the recogniser
    class WaitTimeoutError(Exception):
        pass
    class UnknownValueError(Exception):
        pass
    class RequestError(Exception):
        pass

    sr.WaitTimeoutError = WaitTimeoutError
    sr.UnknownValueError = UnknownValueError
    sr.RequestError = RequestError

    # Recognizer instance
    recognizer = MagicMock()
    recognizer.energy_threshold = 300
    recognizer.dynamic_energy_threshold = True
    recognizer.adjust_for_ambient_noise = MagicMock()
    recognizer.listen = MagicMock(return_value=MagicMock(name="audio"))
    recognizer.recognize_google = MagicMock(return_value="hello astra")
    sr.Recognizer = MagicMock(return_value=recognizer)

    # Microphone context-manager
    mic_source = MagicMock(name="mic_source")
    mic_ctx = MagicMock(name="mic_context_manager")
    mic_ctx.__enter__ = MagicMock(return_value=mic_source)
    mic_ctx.__exit__ = MagicMock(return_value=False)
    sr.Microphone = MagicMock(return_value=mic_ctx)
    sr.Microphone.list_microphone_names = MagicMock(
        return_value=["Microphone (USB Audio)", "Headset Microphone"]
    )

    return sr, recognizer


# ─────────────────────────────────────────────────────────────────────────────
# SpeechListener tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSpeechListener(unittest.TestCase):
    """Tests for voice.listener.SpeechListener using a fully mocked sr backend."""

    def setUp(self) -> None:
        self.sr, self.recognizer = _build_sr_stub()
        sys.modules["speech_recognition"] = self.sr

    def tearDown(self) -> None:
        sys.modules.pop("speech_recognition", None)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _listener(self, microphone_name: str = "Default microphone"):
        from voice.listener import SpeechListener
        return SpeechListener(microphone_name=microphone_name)

    # ── happy path ────────────────────────────────────────────────────────────

    def test_listen_returns_transcript_on_success(self) -> None:
        """listen() returns the string produced by recognize_google."""
        self.recognizer.recognize_google.return_value = "open notepad"
        result = self._listener().listen()
        self.assertEqual(result, "open notepad")

    def test_default_microphone_passes_none_device_index(self) -> None:
        """Selecting 'Default microphone' opens sr.Microphone(device_index=None)."""
        self._listener("Default microphone").listen()
        self.sr.Microphone.assert_called_with(device_index=None)

    def test_named_microphone_resolves_to_correct_index(self) -> None:
        """A named device is looked up by position in list_microphone_names."""
        self._listener("Headset Microphone").listen()
        # "Headset Microphone" is index 1 in the stub list
        self.sr.Microphone.assert_called_with(device_index=1)

    def test_adjust_for_ambient_noise_is_called(self) -> None:
        """The recogniser calibrates ambient noise before recording."""
        self._listener().listen()
        self.recognizer.adjust_for_ambient_noise.assert_called_once()

    # ── timeout ───────────────────────────────────────────────────────────────

    def test_wait_timeout_raises_listen_timeout_error(self) -> None:
        """sr.WaitTimeoutError is converted to ListenTimeoutError."""
        self.recognizer.listen.side_effect = self.sr.WaitTimeoutError("timeout")
        from voice.exceptions import ListenTimeoutError
        with self.assertRaises(ListenTimeoutError):
            self._listener().listen()

    # ── recognition failures ──────────────────────────────────────────────────

    def test_unknown_value_raises_recognition_error(self) -> None:
        """Unintelligible audio raises RecognitionError."""
        self.recognizer.recognize_google.side_effect = self.sr.UnknownValueError()
        from voice.exceptions import RecognitionError
        with self.assertRaises(RecognitionError):
            self._listener().listen()

    def test_request_error_raises_recognition_service_error(self) -> None:
        """Google API failure raises RecognitionServiceError."""
        self.recognizer.recognize_google.side_effect = self.sr.RequestError("503")
        from voice.exceptions import RecognitionServiceError
        with self.assertRaises(RecognitionServiceError):
            self._listener().listen()

    # ── microphone errors ─────────────────────────────────────────────────────

    def test_unknown_device_name_raises_microphone_not_found(self) -> None:
        """A name absent from list_microphone_names raises MicrophoneNotFoundError."""
        from voice.exceptions import MicrophoneNotFoundError
        with self.assertRaises(MicrophoneNotFoundError):
            self._listener("Ghost Microphone").listen()

    def test_os_error_on_open_raises_microphone_not_found(self) -> None:
        """A generic OSError when opening the device raises MicrophoneNotFoundError."""
        self.sr.Microphone.return_value.__enter__.side_effect = OSError("device busy")
        from voice.exceptions import MicrophoneNotFoundError
        with self.assertRaises(MicrophoneNotFoundError):
            self._listener().listen()

    def test_permission_os_error_raises_microphone_permission_error(self) -> None:
        """An OSError containing 'permission' raises MicrophonePermissionError."""
        self.sr.Microphone.return_value.__enter__.side_effect = OSError("permission denied")
        from voice.exceptions import MicrophonePermissionError
        with self.assertRaises(MicrophonePermissionError):
            self._listener().listen()

    def test_access_denied_os_error_raises_microphone_permission_error(self) -> None:
        """An OSError containing 'access denied' raises MicrophonePermissionError."""
        self.sr.Microphone.return_value.__enter__.side_effect = OSError("access denied")
        from voice.exceptions import MicrophonePermissionError
        with self.assertRaises(MicrophonePermissionError):
            self._listener().listen()

    # ── service unavailable ───────────────────────────────────────────────────

    def test_missing_library_raises_recognition_service_error(self) -> None:
        """If SpeechRecognition is not installed, RecognitionServiceError is raised."""
        sys.modules.pop("speech_recognition", None)
        # Ensure subsequent import inside listen() fails
        real_import = builtins.__import__

        def _block_sr(name, *args, **kwargs):
            if name == "speech_recognition":
                raise ImportError("not installed")
            return real_import(name, *args, **kwargs)

        builtins.__import__ = _block_sr
        try:
            from voice.exceptions import RecognitionServiceError
            with self.assertRaises(RecognitionServiceError):
                self._listener().listen()
        finally:
            builtins.__import__ = real_import

    def test_list_microphone_names_failure_falls_back_to_default(self) -> None:
        """If device enumeration fails for a named mic, device_index=None is used."""
        self.sr.Microphone.list_microphone_names.side_effect = OSError("portaudio")
        # Should not raise — falls back to default (None index)
        self._listener("Headset Microphone").listen()
        self.sr.Microphone.assert_called_with(device_index=None)


# ─────────────────────────────────────────────────────────────────────────────
# enumerate_microphones tests
# ─────────────────────────────────────────────────────────────────────────────

class TestEnumerateMicrophones(unittest.TestCase):
    """Tests for voice.devices.enumerate_microphones."""

    def setUp(self) -> None:
        # Clear cached module so each test gets a fresh import
        sys.modules.pop("voice.devices", None)

    def tearDown(self) -> None:
        sys.modules.pop("speech_recognition", None)
        sys.modules.pop("voice.devices", None)

    def test_returns_default_plus_system_devices(self) -> None:
        """Detected devices are appended after 'Default microphone'."""
        sr, _ = _build_sr_stub()
        sys.modules["speech_recognition"] = sr
        from voice.devices import enumerate_microphones
        result = enumerate_microphones()
        self.assertEqual(result[0], "Default microphone")
        self.assertIn("Microphone (USB Audio)", result)
        self.assertIn("Headset Microphone", result)

    def test_returns_only_default_when_sr_unavailable(self) -> None:
        """When SpeechRecognition cannot be imported only the default is returned."""
        real_import = builtins.__import__

        def _block_sr(name, *args, **kwargs):
            if name == "speech_recognition":
                raise ImportError("not installed")
            return real_import(name, *args, **kwargs)

        builtins.__import__ = _block_sr
        try:
            from voice.devices import enumerate_microphones
            result = enumerate_microphones()
            self.assertEqual(result, ["Default microphone"])
        finally:
            builtins.__import__ = real_import

    def test_returns_only_default_when_pyaudio_raises(self) -> None:
        """An OSError from PyAudio during enumeration is swallowed gracefully."""
        sr, _ = _build_sr_stub()
        sr.Microphone.list_microphone_names.side_effect = OSError("portaudio error")
        sys.modules["speech_recognition"] = sr
        from voice.devices import enumerate_microphones
        result = enumerate_microphones()
        self.assertEqual(result, ["Default microphone"])

    def test_no_duplicate_default_entry(self) -> None:
        """'Default microphone' only appears once even if PyAudio lists it too."""
        sr, _ = _build_sr_stub()
        sr.Microphone.list_microphone_names.return_value = ["Default microphone", "USB Mic"]
        sys.modules["speech_recognition"] = sr
        from voice.devices import enumerate_microphones
        result = enumerate_microphones()
        self.assertEqual(result.count("Default microphone"), 1)


# ─────────────────────────────────────────────────────────────────────────────
# VoiceError hierarchy tests
# ─────────────────────────────────────────────────────────────────────────────

class TestVoiceExceptionHierarchy(unittest.TestCase):
    """All voice exceptions must be catchable as VoiceError."""

    def _assert_is_voice_error(self, exc_cls) -> None:
        from voice.exceptions import VoiceError
        instance = exc_cls("test")
        self.assertIsInstance(instance, VoiceError)

    def test_microphone_not_found_is_voice_error(self) -> None:
        from voice.exceptions import MicrophoneNotFoundError
        self._assert_is_voice_error(MicrophoneNotFoundError)

    def test_microphone_permission_is_voice_error(self) -> None:
        from voice.exceptions import MicrophonePermissionError
        self._assert_is_voice_error(MicrophonePermissionError)

    def test_listen_timeout_is_voice_error(self) -> None:
        from voice.exceptions import ListenTimeoutError
        self._assert_is_voice_error(ListenTimeoutError)

    def test_recognition_error_is_voice_error(self) -> None:
        from voice.exceptions import RecognitionError
        self._assert_is_voice_error(RecognitionError)

    def test_recognition_service_error_is_voice_error(self) -> None:
        from voice.exceptions import RecognitionServiceError
        self._assert_is_voice_error(RecognitionServiceError)


if __name__ == "__main__":
    unittest.main()
