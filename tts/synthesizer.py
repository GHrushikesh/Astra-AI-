"""Text-to-speech synthesizer service for Astra.

Provides synchronous and stoppable speech generation using available backends:
1. pyttsx3 (if installed)
2. Windows SAPI (PowerShell System.Speech.Synthesis) as built-in fallback on Windows
3. Null backend fallback if no synthesis engine is available

Runs cleanly outside the UI thread and can be stopped at any time.
"""

from __future__ import annotations

import os
import platform
import subprocess
import threading
from typing import Optional

from tts.exceptions import (
    SpeakerNotFoundError,
    SynthesisError,
    SynthesizerUnavailableError,
    TTSError,
)


def enumerate_voices() -> list[str]:
    """Return list of available voice/speaker names.

    Always includes 'Default speaker'.
    """
    voices = ["Default speaker"]
    # Try pyttsx3 first
    try:
        import pyttsx3  # type: ignore

        engine = pyttsx3.init()
        for v in engine.getProperty("voices"):
            name = getattr(v, "name", None) or getattr(v, "id", None)
            if name and name not in voices:
                voices.append(str(name))
        try:
            engine.stop()
        except Exception:
            pass
        return voices
    except Exception:
        pass

    # On Windows, try System.Speech via PowerShell
    if platform.system() == "Windows":
        try:
            cmd = [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; $s.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo.Name }",
            ]
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    clean = line.strip()
                    if clean and clean not in voices:
                        voices.append(clean)
        except Exception:
            pass

    return voices


class SpeechSynthesizer:
    """Independent Text-to-Speech service.

    Args:
        voice_name: Voice/speaker identifier or 'Default speaker'.
        speed_wpm: Speed in words per minute (80 to 300, default 170).
    """

    def __init__(
        self,
        voice_name: str = "Default speaker",
        speed_wpm: int = 170,
    ) -> None:
        self.voice_name = voice_name
        self.speed_wpm = max(80, min(300, int(speed_wpm)))
        self._current_process: Optional[subprocess.Popen] = None
        self._pyttsx_engine: Optional[object] = None
        self._is_speaking = False
        self._lock = threading.Lock()

    @property
    def is_speaking(self) -> bool:
        """Check if currently synthesizing speech."""
        with self._lock:
            return self._is_speaking

    def speak(self, text: str) -> bool:
        """Synthesize and speak text.

        Blocks until finished or cancelled. Returns True if speech completed.
        Raises TTSError subclass on critical failure.
        """
        clean_text = (text or "").strip()
        if not clean_text:
            return True

        with self._lock:
            self._is_speaking = True

        try:
            # 1. Try pyttsx3 backend
            try:
                import pyttsx3  # type: ignore

                return self._speak_pyttsx3(clean_text, pyttsx3)
            except ImportError:
                pass

            # 2. Try Windows PowerShell System.Speech backend
            if platform.system() == "Windows":
                return self._speak_windows_powershell(clean_text)

            # 3. No synthesizer backend available
            raise SynthesizerUnavailableError(
                "No speech synthesizer engine found. Install pyttsx3: pip install pyttsx3"
            )
        finally:
            with self._lock:
                self._is_speaking = False

    def stop(self) -> None:
        """Cancel ongoing speech immediately."""
        with self._lock:
            if self._current_process:
                try:
                    self._current_process.terminate()
                except Exception:
                    pass
                self._current_process = None

            if self._pyttsx_engine:
                try:
                    self._pyttsx_engine.stop()  # type: ignore
                except Exception:
                    pass
                self._pyttsx_engine = None

            self._is_speaking = False

    def _speak_pyttsx3(self, text: str, pyttsx_module: object) -> bool:
        try:
            engine = pyttsx_module.init()  # type: ignore
            with self._lock:
                self._pyttsx_engine = engine

            # Configure rate
            try:
                engine.setProperty("rate", self.speed_wpm)
            except Exception:
                pass

            # Configure voice
            if self.voice_name and self.voice_name != "Default speaker":
                found = False
                for v in engine.getProperty("voices"):
                    name = getattr(v, "name", "")
                    vid = getattr(v, "id", "")
                    if self.voice_name in (name, vid):
                        engine.setProperty("voice", vid)
                        found = True
                        break
                if not found:
                    pass  # fall back to default voice gracefully

            engine.say(text)
            engine.runAndWait()
            return True
        except Exception as exc:
            raise SynthesisError(f"pyttsx3 failed to speak: {exc}") from exc
        finally:
            with self._lock:
                self._pyttsx_engine = None

    def _speak_windows_powershell(self, text: str) -> bool:
        """Use System.Speech via a hidden background PowerShell child process."""
        # Convert WPM (80-300) to System.Speech Rate (-10 to +10, 170 approx 0)
        # 170 -> 0; 80 -> -6; 300 -> +7
        rate_val = int(round((self.speed_wpm - 170) / 18.0))
        rate_val = max(-10, min(10, rate_val))

        # Safe escaping for PowerShell string literal
        escaped_text = text.replace("'", "''")

        voice_script = ""
        if self.voice_name and self.voice_name != "Default speaker":
            escaped_voice = self.voice_name.replace("'", "''")
            voice_script = f"""
            try {{
                $s.SelectVoice('{escaped_voice}')
            }} catch {{}}
            """

        script = f"""
        Add-Type -AssemblyName System.Speech
        $s = New-Object System.Speech.Synthesis.SpeechSynthesizer
        $s.Rate = {rate_val}
        {voice_script}
        $s.Speak('{escaped_text}')
        """

        cmd = [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            script,
        ]

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            with self._lock:
                self._current_process = proc

            _, stderr_bytes = proc.communicate()
            if proc.returncode != 0 and proc.returncode != 1:  # 1 can be term
                err_msg = stderr_bytes.decode(errors="replace").strip()
                if "SelectVoice" in err_msg:
                    raise SpeakerNotFoundError(f"Voice not found: {self.voice_name}")
                raise SynthesisError(f"TTS synthesis failed: {err_msg}")
            return True
        except Exception as exc:
            if isinstance(exc, TTSError):
                raise
            raise SynthesisError(f"Failed to run speech synthesizer: {exc}") from exc
        finally:
            with self._lock:
                self._current_process = None
