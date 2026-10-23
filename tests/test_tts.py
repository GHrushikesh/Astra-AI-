"""Unit tests for the Astra TTS package."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from tts.exceptions import (
    SpeakerNotFoundError,
    SynthesisError,
    SynthesizerUnavailableError,
    TTSError,
)
from tts.synthesizer import SpeechSynthesizer, enumerate_voices


class TestTTS(unittest.TestCase):
    def test_exception_hierarchy(self):
        self.assertTrue(issubclass(SpeakerNotFoundError, TTSError))
        self.assertTrue(issubclass(SynthesizerUnavailableError, TTSError))
        self.assertTrue(issubclass(SynthesisError, TTSError))

    def test_enumerate_voices_always_contains_default(self):
        voices = enumerate_voices()
        self.assertIsInstance(voices, list)
        self.assertIn("Default speaker", voices)

    def test_speak_empty_text_returns_true(self):
        synth = SpeechSynthesizer()
        self.assertTrue(synth.speak(""))
        self.assertTrue(synth.speak("   "))

    def test_speed_clamped(self):
        synth = SpeechSynthesizer(speed_wpm=50)
        self.assertEqual(synth.speed_wpm, 80)
        synth_fast = SpeechSynthesizer(speed_wpm=500)
        self.assertEqual(synth_fast.speed_wpm, 300)

    @patch("tts.synthesizer.platform.system", return_value="Linux")
    @patch.dict("sys.modules", {"pyttsx3": None})
    def test_unavailable_backend_raises_error(self, mock_plat):
        synth = SpeechSynthesizer()
        with self.assertRaises(SynthesizerUnavailableError):
            synth.speak("Hello test")

    def test_stop_does_not_crash(self):
        synth = SpeechSynthesizer()
        synth.stop()
        self.assertFalse(synth.is_speaking)

    @patch("tts.synthesizer.platform.system", return_value="Windows")
    @patch("tts.synthesizer.subprocess.Popen")
    def test_speak_windows_powershell_mocked(self, mock_popen, mock_platform):
        process_mock = MagicMock()
        process_mock.communicate.return_value = (b"", b"")
        process_mock.returncode = 0
        mock_popen.return_value = process_mock

        synth = SpeechSynthesizer(voice_name="Microsoft David Desktop", speed_wpm=180)
        success = synth.speak("Hello world")
        self.assertTrue(success)
        mock_popen.assert_called_once()


if __name__ == "__main__":
    unittest.main()
