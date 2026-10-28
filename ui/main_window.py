"""Main Astra desktop window — Apple-inspired, premium, fluid desktop experience."""

from __future__ import annotations

import math
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QRect,
    QSize,
    QThread,
    Qt,
    Signal,
    Slot,
)
from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPixmap,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ui.assistant_interface import AssistantInterface, AssistantResponse, EchoAssistant
from ui.settings import AstraSettings, SettingsStore

# TTS package
try:
    from tts.synthesizer import SpeechSynthesizer as _SpeechSynthesizer
    from tts.synthesizer import enumerate_voices as _enumerate_voices
    _TTS_AVAILABLE = True
except ImportError:
    _TTS_AVAILABLE = False
    _SpeechSynthesizer = None  # type: ignore[assignment,misc]

    def _enumerate_voices() -> list[str]:  # type: ignore[misc]
        return ["Default speaker"]

# Voice package — optional dependency (requires SpeechRecognition + PyAudio)
try:
    from voice.devices import enumerate_microphones as _enumerate_microphones
    from voice.exceptions import VoiceError as _VoiceError
    from voice.listener import SpeechListener as _SpeechListener
    _VOICE_AVAILABLE = True
except ImportError:
    _VOICE_AVAILABLE = False
    _SpeechListener = None        # type: ignore[assignment,misc]
    _VoiceError = Exception        # type: ignore[assignment,misc]

    def _enumerate_microphones() -> list[str]:  # type: ignore[misc]
        return ["Default microphone"]

# AI Core package
try:
    from ai.core import AstraAICore as _AstraAICore
    _AI_AVAILABLE = True
except ImportError:
    _AI_AVAILABLE = False
    _AstraAICore = None  # type: ignore[assignment,misc]


# ─────────────────────────────────────────────────────────────────────────────
# Reduced-Motion and System Theme Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _prefers_reduced_motion() -> bool:
    """Detect whether the user prefers reduced motion (Windows setting or env var)."""
    if os.environ.get("ASTRA_REDUCED_MOTION", "").strip().lower() in ("1", "true", "yes"):
        return True
    try:
        import ctypes
        # SPI_GETCLIENTAREAANIMATION = 0x1042
        enabled = ctypes.c_int(1)
        if ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(enabled), 0):
            return enabled.value == 0
    except Exception:
        pass
    return False


def _detect_system_dark_mode() -> bool:
    """Detect Windows system dark mode from registry."""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return val == 0
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# UI Assets Management
# ─────────────────────────────────────────────────────────────────────────────

_ASSETS_DIR = Path(__file__).resolve().parent / "assets"


def _ensure_ui_assets() -> None:
    """Ensure crisp vector SVGs required for Apple-grade UI elements exist."""
    _ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    assets = {
        "check_white.svg": (
            '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" '
            'stroke="#ffffff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">'
            '<polyline points="20 6 9 17 4 12"/></svg>'
        ),
        "chevron_down.svg": (
            '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" '
            'stroke="#86868b" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
            '<polyline points="6 9 12 15 18 9"/></svg>'
        ),
        "chevron_down_dark.svg": (
            '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" '
            'stroke="#a1a1a6" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
            '<polyline points="6 9 12 15 18 9"/></svg>'
        ),
        "search.svg": (
            '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" '
            'stroke="#86868b" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">'
            '<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>'
        ),
        "plus.svg": (
            '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" '
            'stroke="#ffffff" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">'
            '<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>'
        ),
        "sidebar_toggle.svg": (
            '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" '
            'stroke="#6e6e73" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            '<rect x="3" y="3" width="18" height="18" rx="4" ry="4"/><line x1="9" y1="3" x2="9" y2="21"/></svg>'
        ),
    }

    for name, content in assets.items():
        file_path = _ASSETS_DIR / name
        if not file_path.exists():
            file_path.write_text(content, encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# Avatar Helper
# ─────────────────────────────────────────────────────────────────────────────

def _make_avatar_pixmap(letter: str, bg: str, fg: str, size: int = 30, is_astra: bool = False) -> QPixmap:
    """Render a crisp, antialiased Apple-style avatar with geometry."""
    size = max(16, size)
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    path = QPainterPath()
    path.addEllipse(0, 0, size, size)

    if is_astra:
        # Refined Apple astral emblem
        grad = QLinearGradient(0, 0, size, size)
        grad.setColorAt(0.0, QColor("#0071e3"))
        grad.setColorAt(1.0, QColor("#005bb5"))
        p.fillPath(path, grad)

        # Draw an 8-point geometric star compass mark
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#ffffff"))
        center = size / 2.0
        r_outer = size * 0.32
        r_inner = size * 0.12
        star_path = QPainterPath()
        for i in range(16):
            angle = i * (math.pi / 8.0) - (math.pi / 2.0)
            r = r_outer if i % 2 == 0 else r_inner
            x = center + r * math.cos(angle)
            y = center + r * math.sin(angle)
            if i == 0:
                star_path.moveTo(x, y)
            else:
                star_path.lineTo(x, y)
        star_path.closeSubpath()
        p.drawPath(star_path)
    else:
        p.fillPath(path, QColor(bg))
        p.setPen(QColor(fg))
        font_size = max(9, int(size * 0.38))
        font = QFont("Segoe UI")
        font.setPixelSize(font_size)
        font.setWeight(QFont.Weight.DemiBold)
        p.setFont(font)
        p.drawText(QRect(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, letter)

    p.end()
    return pix


# ─────────────────────────────────────────────────────────────────────────────
# Worker Threads
# ─────────────────────────────────────────────────────────────────────────────

class _AssistantWorker(QThread):
    """Run one assistant request away from Qt's main thread."""

    response_ready = Signal(object)

    def __init__(self, assistant: AssistantInterface, user_text: str) -> None:
        super().__init__()
        self._assistant = assistant
        self._user_text = user_text

    def run(self) -> None:
        try:
            response = self._assistant.process(self._user_text)
            if not isinstance(response, AssistantResponse):
                response = AssistantResponse(
                    text="The assistant returned an invalid response.",
                    success=False,
                    error="Invalid AssistantResponse",
                )
        except Exception as exc:
            response = AssistantResponse(
                text="I couldn't process that request.",
                success=False,
                error=str(exc),
            )
        self.response_ready.emit(response)


class _VoiceWorker(QThread):
    """Record one phrase from the microphone on a background thread."""

    text_ready = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, listener: object) -> None:
        super().__init__()
        self._listener = listener

    def run(self) -> None:
        try:
            text: str = self._listener.listen()  # type: ignore[union-attr]
            self.text_ready.emit(text)
        except _VoiceError as exc:
            self.error_occurred.emit(str(exc))
        except Exception as exc:
            self.error_occurred.emit(f"Unexpected voice error: {exc}")


class _TTSWorker(QThread):
    """Run speech synthesis on a background thread."""

    speech_finished = Signal()

    def __init__(self, synthesizer: object, text: str) -> None:
        super().__init__()
        self._synthesizer = synthesizer
        self._text = text

    def run(self) -> None:
        try:
            if self._synthesizer:
                self._synthesizer.speak(self._text)  # type: ignore[union-attr]
        except Exception:
            pass
        finally:
            self.speech_finished.emit()

    def stop(self) -> None:
        try:
            if self._synthesizer:
                self._synthesizer.stop()  # type: ignore[union-attr]
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# Animated Typing Dots
# ─────────────────────────────────────────────────────────────────────────────

class _TypingDot(QWidget):
    """One animated dot for the typing indicator."""

    def __init__(self, delay_ms: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(6, 6)
        self._anim = QPropertyAnimation(self, b"geometry")
        self._anim.setDuration(600)
        self._anim.setLoopCount(-1)
        self._anim.setEasingCurve(QEasingCurve.Type.SineCurve)
        self._delay = delay_ms

    def start(self) -> None:
        geo = self.geometry()
        self._anim.setStartValue(QRect(geo.x(), geo.y(), 6, 6))
        self._anim.setEndValue(QRect(geo.x(), geo.y() - 4, 6, 6))
        self._anim.setStartDelay(self._delay)
        self._anim.start()

    def stop(self) -> None:
        self._anim.stop()
        geo = self.geometry()
        self.setGeometry(QRect(geo.x(), geo.y(), 6, 6))

    def paintEvent(self, _event) -> None:  # type: ignore[override]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor("#0071e3"))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(0, 0, 6, 6)


class _TypingIndicator(QWidget):
    """Three-dot bounce animation shown while Astra is thinking."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        self._dots: list[_TypingDot] = []
        for delay in (0, 140, 280):
            dot = _TypingDot(delay, self)
            self._dots.append(dot)
            layout.addWidget(dot)
        layout.addStretch()
        self.setFixedHeight(24)

    def start(self) -> None:
        for d in self._dots:
            d.start()

    def stop(self) -> None:
        for d in self._dots:
            d.stop()


# ─────────────────────────────────────────────────────────────────────────────
# Message Bubble
# ─────────────────────────────────────────────────────────────────────────────

class _MessageBubble(QWidget):
    """Refined Apple-inspired conversational message bubble."""

    def __init__(
        self,
        sender: str,
        text: str,
        is_dark: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        is_user = sender == "user"
        is_error = sender == "error"

        labels = {"user": "You", "assistant": "Astra", "error": "Error"}
        display_name = labels.get(sender, sender.title())
        timestamp = datetime.now().strftime("%H:%M")

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 2, 0, 2)
        outer.setSpacing(0)

        # Avatar
        av = QLabel()
        if is_user:
            av_bg = "#48484a" if is_dark else "#e5e5ea"
            av_fg = "#ffffff" if is_dark else "#1d1d1f"
            av.setPixmap(_make_avatar_pixmap("Y", av_bg, av_fg, 26))
        elif is_error:
            av.setPixmap(_make_avatar_pixmap("!", "#ff453a" if is_dark else "#ff3b30", "#ffffff", 26))
        else:
            av.setPixmap(_make_avatar_pixmap("A", "#0a84ff" if is_dark else "#0071e3", "#ffffff", 26, is_astra=True))
        av.setFixedSize(26, 26)
        av.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Card Frame
        card = QFrame()
        card.setObjectName("userBubble" if is_user else ("errorBubble" if is_error else "astraBubble"))
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(14, 10, 14, 10)
        card_lay.setSpacing(4)

        # Header row: sender name + timestamp
        header_row = QHBoxLayout()
        header_row.setSpacing(8)
        header_row.setContentsMargins(0, 0, 0, 0)
        name_lbl = QLabel(display_name)
        name_lbl.setObjectName("bubbleSender")
        time_lbl = QLabel(timestamp)
        time_lbl.setObjectName("bubbleTimestamp")
        header_row.addWidget(name_lbl)
        header_row.addWidget(time_lbl)
        header_row.addStretch()

        text_lbl = QLabel(text)
        text_lbl.setObjectName("bubbleTextUser" if is_user else ("bubbleTextError" if is_error else "bubbleText"))
        text_lbl.setWordWrap(True)
        text_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        text_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        card_lay.addLayout(header_row)
        card_lay.addWidget(text_lbl)

        # Alignment
        if is_user:
            outer.setContentsMargins(50, 1, 4, 1)
            inner = QHBoxLayout()
            inner.setSpacing(8)
            inner.addStretch(1)
            inner.addWidget(card)
            inner.addWidget(av)
            outer.addLayout(inner)
        else:
            outer.setContentsMargins(4, 1, 50, 1)
            inner = QHBoxLayout()
            inner.setSpacing(8)
            inner.addWidget(av)
            inner.addWidget(card)
            inner.addStretch(1)
            outer.addLayout(inner)


# ─────────────────────────────────────────────────────────────────────────────
# Settings Dialog (macOS Preferences Style)
# ─────────────────────────────────────────────────────────────────────────────

class _SettingsDialog(QDialog):
    """Modal preferences panel styled with Apple macOS System Settings aesthetics."""

    def __init__(
        self,
        settings: AstraSettings,
        store: SettingsStore,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._store = store
        self.setWindowTitle("Astra · Preferences")
        self.setModal(True)
        self.setMinimumWidth(440)
        self._build()
        is_dark = (
            self._settings.theme == "Dark"
            or (self._settings.theme == "System" and _detect_system_dark_mode())
        )
        self._style(is_dark=is_dark)

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        # Header
        title = QLabel("Preferences")
        title.setObjectName("settingsTitle")
        root.addWidget(title)

        subtitle = QLabel("Configure Google Gemini AI, audio devices, and Astra behavior.")
        subtitle.setObjectName("settingsSubtitle")
        root.addWidget(subtitle)

        # ── Group 1: Google Gemini AI ─────────────────────────────────
        card_ai = QFrame()
        card_ai.setObjectName("settingsCard")
        lay_ai = QVBoxLayout(card_ai)
        lay_ai.setContentsMargins(14, 12, 14, 12)
        lay_ai.setSpacing(8)

        ai_sec = QLabel("Google Gemini API")
        ai_sec.setObjectName("settingsSection")
        lay_ai.addWidget(ai_sec)

        ai_desc = QLabel("Enter your Google Gemini API key to activate natural language intelligence.")
        ai_desc.setObjectName("settingsCaption")
        ai_desc.setWordWrap(True)
        lay_ai.addWidget(ai_desc)

        ai_form = QFormLayout()
        ai_form.setHorizontalSpacing(12)
        ai_form.setVerticalSpacing(8)

        self.llm_api_key = QLineEdit()
        self.llm_api_key.setObjectName("settingsInput")
        self.llm_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.llm_api_key.setPlaceholderText("Paste Gemini API key (AIzaSy...)")
        self.llm_api_key.setText(self._settings.llm_api_key)

        key_lbl = QLabel("API Key")
        key_lbl.setObjectName("settingsRowLabel")
        ai_form.addRow(key_lbl, self.llm_api_key)
        lay_ai.addLayout(ai_form)
        root.addWidget(card_ai)

        # Hidden compatibility fields
        self.llm_provider = QComboBox()
        self.llm_provider.addItems(["Google Gemini", "OpenAI", "Groq", "Ollama / Local", "Anthropic", "Custom"])
        self.llm_provider.setCurrentText(self._settings.llm_provider or "Google Gemini")
        self.llm_provider.hide()

        initial_model = self._settings.llm_model or "gemini-2.5-flash-lite"
        if initial_model in ("gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash", "gemini-2.0-flash-exp", "gemini-2.5-flash", ""):
            initial_model = "gemini-2.5-flash-lite"
        self.llm_model = QLineEdit()
        self.llm_model.setText(initial_model)
        self.llm_model.hide()

        self.llm_endpoint = QLineEdit()
        self.llm_endpoint.setText(self._settings.llm_endpoint or "")
        self.llm_endpoint.hide()

        # ── Group 2: Audio & Voice ───────────────────────────────────
        card_audio = QFrame()
        card_audio.setObjectName("settingsCard")
        lay_audio = QVBoxLayout(card_audio)
        lay_audio.setContentsMargins(14, 12, 14, 12)
        lay_audio.setSpacing(8)

        voice_sec = QLabel("Voice & Speech")
        voice_sec.setObjectName("settingsSection")
        lay_audio.addWidget(voice_sec)

        voice_form = QFormLayout()
        voice_form.setHorizontalSpacing(12)
        voice_form.setVerticalSpacing(8)

        self.microphone = QComboBox()
        self.microphone.setObjectName("settingsCombo")
        mic_devices = _enumerate_microphones()
        for dev in mic_devices:
            self.microphone.addItem(dev)
        if self._settings.microphone not in mic_devices:
            self.microphone.addItem(self._settings.microphone)
        self.microphone.setCurrentText(self._settings.microphone)
        self.microphone.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.speaker = QComboBox()
        self.speaker.setObjectName("settingsCombo")
        spk_devices = _enumerate_voices()
        for spk in spk_devices:
            self.speaker.addItem(spk)
        if self._settings.speaker not in spk_devices:
            self.speaker.addItem(self._settings.speaker)
        self.speaker.setCurrentText(self._settings.speaker)
        self.speaker.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        mic_lbl = QLabel("Microphone")
        mic_lbl.setObjectName("settingsRowLabel")
        speaker_lbl = QLabel("Speaker")
        speaker_lbl.setObjectName("settingsRowLabel")
        voice_form.addRow(mic_lbl, self.microphone)
        voice_form.addRow(speaker_lbl, self.speaker)

        speed_row = QHBoxLayout()
        speed_lbl = QLabel("Speech speed")
        speed_lbl.setObjectName("settingsRowLabel")
        speed_row.addWidget(speed_lbl)
        speed_row.addStretch()
        self.speech_speed = QSpinBox()
        self.speech_speed.setObjectName("settingsSpinBox")
        self.speech_speed.setRange(80, 300)
        self.speech_speed.setValue(self._settings.speech_speed)
        self.speech_speed.setSuffix(" wpm")
        speed_row.addWidget(self.speech_speed)
        voice_form.addRow(speed_row)

        lay_audio.addLayout(voice_form)
        root.addWidget(card_audio)

        # ── Group 3: Appearance & System ──────────────────────────────
        card_app = QFrame()
        card_app.setObjectName("settingsCard")
        lay_app = QVBoxLayout(card_app)
        lay_app.setContentsMargins(14, 12, 14, 12)
        lay_app.setSpacing(8)

        app_sec = QLabel("Appearance & Behavior")
        app_sec.setObjectName("settingsSection")
        lay_app.addWidget(app_sec)

        app_form = QFormLayout()
        app_form.setHorizontalSpacing(12)
        app_form.setVerticalSpacing(8)

        theme_lbl = QLabel("Theme")
        theme_lbl.setObjectName("settingsRowLabel")
        self.theme = QComboBox()
        self.theme.setObjectName("settingsCombo")
        self.theme.addItems(["Light", "Dark", "System"])
        self.theme.setCurrentText(self._settings.theme)
        self.theme.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        app_form.addRow(theme_lbl, self.theme)

        self.compact_mode = QCheckBox("Compact message spacing")
        self.compact_mode.setObjectName("settingsCheck")
        self.compact_mode.setChecked(self._settings.compact_messages)
        app_form.addRow("", self.compact_mode)

        self.notifications = QCheckBox("Show desktop notifications")
        self.notifications.setObjectName("settingsCheck")
        self.notifications.setChecked(self._settings.notifications_enabled)
        app_form.addRow("", self.notifications)

        self.start_with_windows = QCheckBox("Start Astra with Windows")
        self.start_with_windows.setObjectName("settingsCheck")
        self.start_with_windows.setChecked(self._settings.start_with_windows)
        app_form.addRow("", self.start_with_windows)

        lay_app.addLayout(app_form)
        root.addWidget(card_app)

        root.addSpacing(4)

        # Action Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.setObjectName("settingsButtons")
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _style(self, is_dark: bool = False) -> None:
        _ensure_ui_assets()
        check_path = (_ASSETS_DIR / "check_white.svg").as_posix()
        chevron_path = (_ASSETS_DIR / ("chevron_down_dark.svg" if is_dark else "chevron_down.svg")).as_posix()

        bg_dlg = "#1c1c1e" if is_dark else "#f2f2f6"
        bg_card = "#28282c" if is_dark else "#ffffff"
        border_card = "#38383c" if is_dark else "#e5e5ea"
        text_title = "#f5f5f7" if is_dark else "#1d1d1f"
        text_sub = "#a1a1a6" if is_dark else "#86868b"
        text_lbl = "#f5f5f7" if is_dark else "#1d1d1f"
        input_bg = "#1e1e22" if is_dark else "#ffffff"
        input_border = "#3a3a3c" if is_dark else "#d2d2d7"
        accent = "#0a84ff" if is_dark else "#0071e3"

        self.setStyleSheet(
            f"""
            QDialog {{
                background: {bg_dlg};
                font-family: -apple-system, 'SF Pro Text', 'Segoe UI', Arial, sans-serif;
            }}
            QLabel#settingsTitle {{
                font-size: 18px;
                font-weight: 600;
                color: {text_title};
                letter-spacing: -0.2px;
            }}
            QLabel#settingsSubtitle {{
                font-size: 12px;
                color: {text_sub};
                padding-bottom: 2px;
            }}
            QFrame#settingsCard {{
                background: {bg_card};
                border: 1px solid {border_card};
                border-radius: 10px;
            }}
            QLabel#settingsSection {{
                font-size: 11px;
                font-weight: 600;
                color: {text_sub};
                letter-spacing: 0.8px;
                text-transform: uppercase;
            }}
            QLabel#settingsCaption {{
                font-size: 11.5px;
                color: {text_sub};
                line-height: 1.4;
            }}
            QLabel#settingsRowLabel {{
                font-size: 12.5px;
                font-weight: 500;
                color: {text_lbl};
            }}
            QLineEdit#settingsInput {{
                background: {input_bg};
                border: 1px solid {input_border};
                border-radius: 7px;
                padding: 6px 10px;
                font-size: 12.5px;
                color: {text_lbl};
            }}
            QLineEdit#settingsInput:focus {{
                border: 1.5px solid {accent};
            }}
            QComboBox#settingsCombo {{
                background: {input_bg};
                border: 1px solid {input_border};
                border-radius: 7px;
                padding: 5px 28px 5px 10px;
                font-size: 12.5px;
                color: {text_lbl};
            }}
            QComboBox#settingsCombo:focus {{
                border: 1.5px solid {accent};
            }}
            QComboBox#settingsCombo::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 24px;
                border-left: none;
            }}
            QComboBox#settingsCombo::down-arrow {{
                image: url("{chevron_path}");
                width: 10px;
                height: 10px;
                margin-right: 8px;
            }}
            QSpinBox#settingsSpinBox {{
                background: {input_bg};
                border: 1px solid {input_border};
                border-radius: 7px;
                padding: 4px 8px;
                font-size: 12px;
                color: {text_lbl};
            }}
            QCheckBox#settingsCheck {{
                font-size: 12.5px;
                color: {text_lbl};
                spacing: 8px;
            }}
            QCheckBox#settingsCheck::indicator {{
                width: 16px;
                height: 16px;
                border: 1px solid {input_border};
                border-radius: 4px;
                background: {input_bg};
            }}
            QCheckBox#settingsCheck::indicator:checked {{
                background: {accent};
                border-color: {accent};
                image: url("{check_path}");
            }}
            QDialogButtonBox#settingsButtons QPushButton {{
                border-radius: 7px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 500;
                min-width: 68px;
            }}
            QDialogButtonBox#settingsButtons QPushButton[text="OK"],
            QDialogButtonBox#settingsButtons QPushButton:default {{
                background: {accent};
                border: none;
                color: #ffffff;
                font-weight: 600;
            }}
            QDialogButtonBox#settingsButtons QPushButton[text="Cancel"] {{
                background: transparent;
                border: 1px solid {input_border};
                color: {text_lbl};
            }}
            """
        )

    def _save(self) -> None:
        raw_model = self.llm_model.text().strip()
        if not raw_model or raw_model in ("gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash", "gemini-2.0-flash-exp", "gemini-2.5-flash"):
            sanitized_model = "gemini-2.5-flash-lite"
        else:
            sanitized_model = raw_model

        settings = AstraSettings(
            microphone=self.microphone.currentText(),
            speaker=self.speaker.currentText(),
            speech_speed=self.speech_speed.value(),
            notifications_enabled=self.notifications.isChecked(),
            theme=self.theme.currentText(),
            start_with_windows=self.start_with_windows.isChecked(),
            compact_messages=self.compact_mode.isChecked(),
            llm_provider=self.llm_provider.currentText(),
            llm_api_key=self.llm_api_key.text().strip(),
            llm_model=sanitized_model,
            llm_endpoint=self.llm_endpoint.text().strip(),
        )
        try:
            self._store.save(settings)
        except OSError as exc:
            QMessageBox.critical(self, "Settings not saved", str(exc))
            return
        self._settings.__dict__.update(settings.__dict__)
        self.accept()


# ─────────────────────────────────────────────────────────────────────────────
# Main Window (Apple-Inspired Architecture)
# ─────────────────────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    """Astra desktop window — Apple-inspired, calm, premium interaction design."""

    microphone_requested = Signal()
    message_submitted = Signal(str)

    _ACCENT = "#0071e3"

    def __init__(
        self,
        assistant: Optional[AssistantInterface] = None,
        parent: Optional[QWidget] = None,
        settings_store: SettingsStore | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings_store = settings_store or SettingsStore()
        self._settings_load_error: str | None = None
        try:
            self._settings = self._settings_store.load()
        except ValueError as exc:
            self._settings = AstraSettings()
            self._settings_load_error = str(exc)

        if assistant is not None:
            self._assistant = assistant
        elif _AI_AVAILABLE and _AstraAICore is not None:
            self._assistant = _AstraAICore(settings_store=self._settings_store)
        else:
            self._assistant = EchoAssistant()

        self._worker: Optional[_AssistantWorker] = None
        self._voice_worker: Optional[_VoiceWorker] = None
        self._tts_worker: Optional[_TTSWorker] = None
        self._tts_synthesizer = _SpeechSynthesizer(
            voice_name=self._settings.speaker,
            speed_wpm=self._settings.speech_speed,
        ) if _TTS_AVAILABLE else None

        self._sessions: list[dict[str, object]] = []
        self._current_session: dict[str, object] = {}
        self._sidebar_collapsed = False
        self._sidebar_anim: Optional[QPropertyAnimation] = None

        _ensure_ui_assets()
        self._build_ui()

    def _build_ui(self) -> None:
        self.setWindowTitle("Astra")
        self.setMinimumSize(880, 580)
        self.resize(1140, 740)

        central = QWidget(self)
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Sidebar ───────────────────────────────────────────────────
        self.sidebar = QWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(220)
        sb = QVBoxLayout(self.sidebar)
        sb.setContentsMargins(12, 16, 12, 14)
        sb.setSpacing(6)

        # Brand header
        sb_header = QHBoxLayout()
        sb_header.setSpacing(8)
        sb_logo = QLabel()
        sb_logo.setPixmap(_make_avatar_pixmap("A", self._ACCENT, "#ffffff", 26, is_astra=True))
        sb_logo.setFixedSize(26, 26)
        sb_header.addWidget(sb_logo)

        sb_brand = QLabel("Astra")
        sb_brand.setObjectName("sidebarBrand")
        sb_header.addWidget(sb_brand)
        sb_header.addStretch()

        self._collapse_btn = QPushButton("◧")
        self._collapse_btn.setObjectName("sidebarIcon")
        self._collapse_btn.setFixedSize(26, 26)
        self._collapse_btn.setToolTip("Toggle sidebar")
        self._collapse_btn.clicked.connect(self._toggle_sidebar)
        sb_header.addWidget(self._collapse_btn)
        sb.addLayout(sb_header)

        sb.addSpacing(10)

        # New conversation button
        new_chat_btn = QPushButton("+  New Conversation")
        new_chat_btn.setObjectName("newChatButton")
        new_chat_btn.setFixedHeight(34)
        new_chat_btn.clicked.connect(self._start_new_chat)
        sb.addWidget(new_chat_btn)

        sb.addSpacing(4)

        # Spotlight search input
        self.chat_search = QLineEdit()
        self.chat_search.setObjectName("chatSearch")
        self.chat_search.setPlaceholderText("Search conversations…")
        self.chat_search.setFixedHeight(28)
        self.chat_search.textChanged.connect(self._filter_chat_history)
        sb.addWidget(self.chat_search)

        # Hidden search button maintained for API compatibility
        self._search_btn = QPushButton("Search")
        self._search_btn.setObjectName("sidebarButton")
        self._search_btn.clicked.connect(self._toggle_chat_search)
        self._search_btn.hide()

        sb.addSpacing(10)

        # Recent conversations section
        history_lbl = QLabel("Recent")
        history_lbl.setObjectName("sidebarSection")
        sb.addWidget(history_lbl)

        self.chat_history = QListWidget()
        self.chat_history.setObjectName("chatHistory")
        self.chat_history.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.chat_history.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.chat_history.customContextMenuRequested.connect(self._show_chat_context_menu)
        self.chat_history.itemClicked.connect(self._restore_chat)
        sb.addWidget(self.chat_history, 1)

        # Discover button
        discover_btn = QPushButton("Discover")
        discover_btn.setObjectName("sidebarButton")
        sb.addWidget(discover_btn)

        # Bottom section
        sb.addSpacing(4)
        sep_sb = QFrame()
        sep_sb.setObjectName("sidebarSep")
        sep_sb.setFrameShape(QFrame.Shape.HLine)
        sep_sb.setFixedHeight(1)
        sb.addWidget(sep_sb)

        settings_btn = QPushButton("Preferences…")
        settings_btn.setObjectName("sidebarButton")
        settings_btn.clicked.connect(self._show_settings)
        sb.addWidget(settings_btn)

        help_btn = QPushButton("Help & Support")
        help_btn.setObjectName("sidebarButton")
        sb.addWidget(help_btn)

        account = QLabel("Astra Assistant · v1.0")
        account.setObjectName("accountLabel")
        sb.addWidget(account)

        root.addWidget(self.sidebar)

        # ── Content Panel (Elevated Canvas) ───────────────────────────
        content = QWidget()
        content.setObjectName("contentPanel")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Header bar
        header_bar = QWidget()
        header_bar.setObjectName("headerBar")
        header_bar.setFixedHeight(50)
        hl = QHBoxLayout(header_bar)
        hl.setContentsMargins(18, 0, 18, 0)
        hl.setSpacing(10)

        self._expand_btn = QPushButton("◨")
        self._expand_btn.setObjectName("sidebarIcon")
        self._expand_btn.setFixedSize(26, 26)
        self._expand_btn.setToolTip("Show sidebar")
        self._expand_btn.clicked.connect(self._toggle_sidebar)
        self._expand_btn.hide()
        hl.addWidget(self._expand_btn)

        self._chat_title_lbl = QLabel("New conversation")
        self._chat_title_lbl.setObjectName("headerChatTitle")
        hl.addWidget(self._chat_title_lbl)
        hl.addStretch()

        self.connection_label = QLabel("● Ready")
        self.connection_label.setObjectName("pillReady")
        self.connection_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.connection_label.setFixedHeight(24)
        hl.addWidget(self.connection_label)

        self.settings_button = QPushButton("Preferences")
        self.settings_button.setObjectName("ghostButton")
        self.settings_button.setFixedHeight(26)
        self.settings_button.clicked.connect(self._show_settings)
        hl.addWidget(self.settings_button)

        content_layout.addWidget(header_bar)

        sep = QFrame()
        sep.setObjectName("headerSep")
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        content_layout.addWidget(sep)

        # Chat wrapper
        chat_wrapper = QWidget()
        chat_wrapper.setObjectName("chatWrapper")
        cwl = QVBoxLayout(chat_wrapper)
        cwl.setContentsMargins(0, 0, 0, 0)
        cwl.setSpacing(0)

        # Welcome panel (Apple Intelligence style centered hero)
        self.welcome_panel = QWidget()
        self.welcome_panel.setObjectName("welcomePanel")
        wl = QVBoxLayout(self.welcome_panel)
        wl.setContentsMargins(32, 44, 32, 20)
        wl.setSpacing(8)

        wlc_logo = QLabel()
        wlc_logo.setPixmap(_make_avatar_pixmap("A", self._ACCENT, "#ffffff", 44, is_astra=True))
        wlc_logo.setFixedSize(44, 44)
        wl.addWidget(wlc_logo, 0, Qt.AlignmentFlag.AlignHCenter)
        wl.addSpacing(2)

        wlc_title = QLabel("Astra")
        wlc_title.setObjectName("welcomeTitle")
        wlc_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wl.addWidget(wlc_title)

        wlc_sub = QLabel("How can I help you today?")
        wlc_sub.setObjectName("welcomeSubtitle")
        wlc_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wl.addWidget(wlc_sub)

        wl.addSpacing(20)

        chips_row = QHBoxLayout()
        chips_row.setSpacing(8)
        chips_row.addStretch()
        suggestions = [
            ("Create study plan", "Generate a focused weekly study plan"),
            ("Summarize text", "Summarize the key points of:"),
            ("Explain concept", "Explain how neural networks learn in simple terms"),
            ("Open application", "Open Notepad"),
        ]
        for chip_label, chip_value in suggestions:
            btn = QPushButton(chip_label)
            btn.setObjectName("suggestionButton")
            btn.clicked.connect(
                lambda _checked=False, v=chip_value: (
                    self.input.setText(v),
                    self.input.setFocus(),
                )
            )
            chips_row.addWidget(btn)
        chips_row.addStretch()
        wl.addLayout(chips_row)
        wl.addStretch()

        cwl.addWidget(self.welcome_panel)

        # Conversation list
        self.conversation = QListWidget()
        self.conversation.setObjectName("conversationList")
        self.conversation.setAccessibleName("Conversation")
        self.conversation.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.conversation.setSpacing(4)
        self.conversation.setUniformItemSizes(False)
        self.conversation.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.conversation.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        cwl.addWidget(self.conversation)
        content_layout.addWidget(chat_wrapper, 1)

        # Status text
        self.status_label = QLabel("Ready  ·  Type a message to get started")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setContentsMargins(20, 2, 20, 2)
        content_layout.addWidget(self.status_label)

        # Composer Capsule Frame
        composer_outer = QWidget()
        composer_outer.setObjectName("composerOuter")
        col = QHBoxLayout(composer_outer)
        col.setContentsMargins(18, 6, 18, 14)

        composer_frame = QFrame()
        composer_frame.setObjectName("composerFrame")
        composer_frame.setFixedHeight(46)

        cmp_lay = QHBoxLayout(composer_frame)
        cmp_lay.setContentsMargins(12, 4, 6, 4)
        cmp_lay.setSpacing(8)

        self.input = QLineEdit()
        self.input.setObjectName("messageInput")
        self.input.setPlaceholderText("Message Astra…")
        self.input.setClearButtonEnabled(True)
        self.input.returnPressed.connect(self._submit_from_input)
        cmp_lay.addWidget(self.input, 1)

        self.microphone_button = QPushButton("Voice")
        self.microphone_button.setObjectName("iconButton")
        self.microphone_button.setFixedSize(52, 32)
        if _VOICE_AVAILABLE:
            self.microphone_button.setToolTip("Click to speak (voice input)")
            self.microphone_button.clicked.connect(self._start_voice_input)
        else:
            self.microphone_button.setToolTip(
                "Voice input unavailable — install SpeechRecognition and PyAudio"
            )
            self.microphone_button.setEnabled(False)
            self.microphone_button.clicked.connect(self.microphone_requested)
        cmp_lay.addWidget(self.microphone_button)

        self.send_button = QPushButton("Send")
        self.send_button.setObjectName("sendButton")
        self.send_button.setFixedSize(54, 32)
        self.send_button.clicked.connect(self._submit_from_input)
        cmp_lay.addWidget(self.send_button)

        col.addWidget(composer_frame)
        content_layout.addWidget(composer_outer)

        root.addWidget(content, 1)

        self._apply_settings()
        self._current_session = self._new_session("New conversation")
        self._add_message("assistant", "Hello! I'm Astra — how can I help you today?")
        if self._settings_load_error:
            self.status_label.setText("Settings could not be loaded; defaults are in use")

    # ── Styling: Apple Light & Dark Themes ────────────────────────────────────

    def _apply_style(self) -> None:
        """Apply Apple-inspired Light theme (macOS silver & crisp neutrals)."""
        chevron_path = (_ASSETS_DIR / "chevron_down.svg").as_posix()
        search_path = (_ASSETS_DIR / "search.svg").as_posix()

        self.setStyleSheet(
            f"""
            /* ── Base ─────────────────────────────────────────── */
            QWidget {{
                font-family: -apple-system, 'SF Pro Text', 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
                color: #1d1d1f;
            }}
            QWidget#centralWidget {{
                background: #f2f2f6;
            }}

            /* ── Sidebar ──────────────────────────────────────── */
            QWidget#sidebar {{
                background: #ececf0;
                border-right: 1px solid #e1e1e6;
            }}
            QLabel#sidebarBrand {{
                color: #1d1d1f;
                font-size: 14.5px;
                font-weight: 600;
                letter-spacing: -0.2px;
            }}
            QLabel#sidebarSection {{
                color: #86868b;
                font-size: 10px;
                font-weight: 600;
                letter-spacing: 0.8px;
                padding: 4px 6px 2px 6px;
                text-transform: uppercase;
            }}
            QListWidget#chatHistory {{
                background: transparent;
                border: none;
                outline: none;
                color: #48484a;
                font-size: 12px;
            }}
            QListWidget#chatHistory::item {{
                padding: 6px 9px;
                border-radius: 6px;
                margin: 1px 0;
            }}
            QListWidget#chatHistory::item:hover {{
                background: rgba(0, 0, 0, 0.04);
                color: #1d1d1f;
            }}
            QListWidget#chatHistory::item:selected {{
                background: rgba(0, 113, 227, 0.12);
                color: #0071e3;
                font-weight: 600;
            }}
            QLineEdit#chatSearch {{
                background: #ffffff;
                border: 1px solid #d2d2d7;
                border-radius: 6px;
                padding: 3px 8px;
                color: #1d1d1f;
                font-size: 11.5px;
            }}
            QLineEdit#chatSearch:focus {{
                border: 1.5px solid #0071e3;
            }}
            QFrame#sidebarSep {{
                background: #e1e1e6;
                border: none;
            }}
            QLabel#accountLabel {{
                color: #86868b;
                font-size: 10.5px;
                padding: 6px 4px 2px 4px;
            }}
            QPushButton#sidebarButton {{
                background: transparent;
                border: none;
                color: #48484a;
                text-align: left;
                padding: 6px 8px;
                font-size: 12px;
                font-weight: 500;
                border-radius: 6px;
            }}
            QPushButton#sidebarButton:hover {{
                background: rgba(0, 0, 0, 0.04);
                color: #1d1d1f;
            }}
            QPushButton#sidebarIcon {{
                background: transparent;
                border: none;
                color: #6e6e73;
                font-size: 13px;
                border-radius: 5px;
            }}
            QPushButton#sidebarIcon:hover {{
                background: rgba(0, 0, 0, 0.06);
                color: #1d1d1f;
            }}
            QPushButton#newChatButton {{
                background: #0071e3;
                border: none;
                border-radius: 7px;
                color: #ffffff;
                text-align: left;
                padding: 0 12px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton#newChatButton:hover {{
                background: #0077ed;
            }}
            QPushButton#newChatButton:pressed {{
                background: #005bb5;
            }}

            /* ── Content Panel (Elevated Card) ────────────────── */
            QWidget#contentPanel {{
                background: #ffffff;
                border-left: 1px solid #e1e1e6;
            }}

            /* ── Header Bar ───────────────────────────────────── */
            QWidget#headerBar {{
                background: #ffffff;
            }}
            QFrame#headerSep {{
                background: #e5e5ea;
                border: none;
            }}
            QLabel#headerChatTitle {{
                color: #1d1d1f;
                font-size: 13.5px;
                font-weight: 600;
                letter-spacing: -0.1px;
            }}

            /* ── Status Indicator Pills ───────────────────────── */
            QLabel#pillReady {{
                background: rgba(52, 199, 89, 0.12);
                color: #248a3d;
                border: 1px solid rgba(52, 199, 89, 0.3);
                border-radius: 12px;
                padding: 2px 10px;
                font-size: 11px;
                font-weight: 600;
            }}
            QLabel#pillThinking {{
                background: rgba(255, 149, 0, 0.12);
                color: #c97500;
                border: 1px solid rgba(255, 149, 0, 0.3);
                border-radius: 12px;
                padding: 2px 10px;
                font-size: 11px;
                font-weight: 600;
            }}
            QLabel#pillListening {{
                background: rgba(0, 113, 227, 0.12);
                color: #0071e3;
                border: 1px solid rgba(0, 113, 227, 0.3);
                border-radius: 12px;
                padding: 2px 10px;
                font-size: 11px;
                font-weight: 600;
            }}

            /* ── Welcome Panel ────────────────────────────────── */
            QWidget#chatWrapper {{ background: transparent; }}
            QWidget#welcomePanel {{ background: transparent; }}
            QLabel#welcomeTitle {{
                color: #1d1d1f;
                font-size: 22px;
                font-weight: 600;
                letter-spacing: -0.3px;
            }}
            QLabel#welcomeSubtitle {{
                color: #86868b;
                font-size: 14px;
                font-weight: 400;
            }}
            QPushButton#suggestionButton {{
                background: #ffffff;
                border: 1px solid #d2d2d7;
                border-radius: 14px;
                color: #1d1d1f;
                padding: 6px 14px;
                font-size: 11.5px;
                font-weight: 500;
            }}
            QPushButton#suggestionButton:hover {{
                background: #f5f5f7;
                border-color: #0071e3;
                color: #0071e3;
            }}

            /* ── Conversation List ────────────────────────────── */
            QListWidget#conversationList {{
                background: transparent;
                border: none;
                padding: 10px 16px;
            }}
            QListWidget#conversationList::item {{
                background: transparent;
                border: none;
                padding: 0;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 6px;
                border-radius: 3px;
                margin: 4px 2px;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(0, 0, 0, 0.15);
                border-radius: 3px;
                min-height: 24px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: rgba(0, 0, 0, 0.28);
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}

            /* ── Message Cards ────────────────────────────────── */
            QFrame#astraBubble {{
                background: #ffffff;
                border: 1px solid #e5e5ea;
                border-radius: 14px;
                border-top-left-radius: 4px;
            }}
            QFrame#userBubble {{
                background: #0071e3;
                border: none;
                border-radius: 16px;
                border-top-right-radius: 4px;
            }}
            QFrame#errorBubble {{
                background: #fff5f5;
                border: 1px solid #ffd1d1;
                border-radius: 14px;
                border-top-left-radius: 4px;
            }}
            QLabel#bubbleSender {{
                color: #86868b;
                font-size: 10px;
                font-weight: 600;
                letter-spacing: 0.5px;
                text-transform: uppercase;
            }}
            QLabel#bubbleTimestamp {{
                color: #aeaeb2;
                font-size: 10px;
            }}
            QLabel#bubbleText {{
                color: #1d1d1f;
                font-size: 13.5px;
                line-height: 1.6;
            }}
            QLabel#bubbleTextUser {{
                color: #ffffff;
                font-size: 13.5px;
                line-height: 1.55;
            }}
            QLabel#bubbleTextError {{
                color: #d70015;
                font-size: 13.5px;
                line-height: 1.55;
            }}

            /* ── Status Bar ───────────────────────────────────── */
            QLabel#statusLabel {{
                color: #86868b;
                font-size: 11px;
                background: transparent;
            }}

            /* ── Composer Capsule ─────────────────────────────── */
            QWidget#composerOuter {{ background: transparent; }}
            QFrame#composerFrame {{
                background: #ffffff;
                border: 1px solid #d2d2d7;
                border-radius: 23px;
            }}
            QFrame#composerFrame:focus-within {{
                border: 1.5px solid #0071e3;
            }}
            QLineEdit#messageInput {{
                background: transparent;
                border: none;
                padding: 4px 8px;
                color: #1d1d1f;
                font-size: 13.5px;
            }}

            /* ── Controls ─────────────────────────────────────── */
            QPushButton#sendButton {{
                background: #0071e3;
                color: #ffffff;
                border: none;
                border-radius: 16px;
                font-weight: 600;
                font-size: 12px;
            }}
            QPushButton#sendButton:hover {{
                background: #0077ed;
            }}
            QPushButton#sendButton:disabled {{
                background: #e5e5ea;
                color: #a1a1a6;
            }}
            QPushButton#iconButton {{
                background: #f2f2f6;
                border: 1px solid #e1e1e6;
                color: #48484a;
                font-size: 11.5px;
                font-weight: 500;
                border-radius: 16px;
            }}
            QPushButton#iconButton:hover {{
                background: #e5e5ea;
                color: #1d1d1f;
            }}
            QPushButton#iconButtonActive {{
                background: #ff3b30;
                border: none;
                color: #ffffff;
                font-size: 11.5px;
                font-weight: 600;
                border-radius: 16px;
            }}
            QPushButton#ghostButton {{
                background: transparent;
                border: 1px solid #d2d2d7;
                border-radius: 6px;
                color: #48484a;
                font-size: 11.5px;
                font-weight: 500;
                padding: 0 10px;
            }}
            QPushButton#ghostButton:hover {{
                background: #f2f2f6;
                color: #1d1d1f;
            }}
            QPushButton:disabled {{ opacity: 0.4; }}

            /* ── Context Menu ─────────────────────────────────── */
            QMenu {{
                background: #ffffff;
                border: 1px solid #d2d2d7;
                border-radius: 8px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 14px;
                border-radius: 5px;
                color: #1d1d1f;
                font-size: 12px;
                font-weight: 500;
            }}
            QMenu::item:selected {{
                background: #0071e3;
                color: #ffffff;
            }}
            QMenu::separator {{
                height: 1px;
                background: #e5e5ea;
                margin: 4px 6px;
            }}
            """
        )

    def _apply_dark_style(self) -> None:
        """Apply Apple-inspired Dark theme (macOS layered slate and charcoal)."""
        chevron_path = (_ASSETS_DIR / "chevron_down_dark.svg").as_posix()
        search_path = (_ASSETS_DIR / "search.svg").as_posix()

        self.setStyleSheet(
            f"""
            /* ── Base ─────────────────────────────────────────── */
            QWidget {{
                font-family: -apple-system, 'SF Pro Text', 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
                color: #f5f5f7;
            }}
            QWidget#centralWidget {{
                background: #161618;
            }}

            /* ── Sidebar ──────────────────────────────────────── */
            QWidget#sidebar {{
                background: #1c1c1e;
                border-right: 1px solid #2c2c30;
            }}
            QLabel#sidebarBrand {{
                color: #f5f5f7;
                font-size: 14.5px;
                font-weight: 600;
                letter-spacing: -0.2px;
            }}
            QLabel#sidebarSection {{
                color: #86868b;
                font-size: 10px;
                font-weight: 600;
                letter-spacing: 0.8px;
                padding: 4px 6px 2px 6px;
                text-transform: uppercase;
            }}
            QListWidget#chatHistory {{
                background: transparent;
                border: none;
                outline: none;
                color: #a1a1a6;
                font-size: 12px;
            }}
            QListWidget#chatHistory::item {{
                padding: 6px 9px;
                border-radius: 6px;
                margin: 1px 0;
            }}
            QListWidget#chatHistory::item:hover {{
                background: rgba(255, 255, 255, 0.06);
                color: #f5f5f7;
            }}
            QListWidget#chatHistory::item:selected {{
                background: rgba(10, 132, 255, 0.2);
                color: #64d2ff;
                font-weight: 600;
            }}
            QLineEdit#chatSearch {{
                background: #242428;
                border: 1px solid #38383c;
                border-radius: 6px;
                padding: 3px 8px;
                color: #f5f5f7;
                font-size: 11.5px;
            }}
            QLineEdit#chatSearch:focus {{
                border: 1.5px solid #0a84ff;
            }}
            QFrame#sidebarSep {{
                background: #2c2c30;
                border: none;
            }}
            QLabel#accountLabel {{
                color: #6e6e73;
                font-size: 10.5px;
                padding: 6px 4px 2px 4px;
            }}
            QPushButton#sidebarButton {{
                background: transparent;
                border: none;
                color: #a1a1a6;
                text-align: left;
                padding: 6px 8px;
                font-size: 12px;
                font-weight: 500;
                border-radius: 6px;
            }}
            QPushButton#sidebarButton:hover {{
                background: rgba(255, 255, 255, 0.06);
                color: #f5f5f7;
            }}
            QPushButton#sidebarIcon {{
                background: transparent;
                border: none;
                color: #86868b;
                font-size: 13px;
                border-radius: 5px;
            }}
            QPushButton#sidebarIcon:hover {{
                background: rgba(255, 255, 255, 0.08);
                color: #f5f5f7;
            }}
            QPushButton#newChatButton {{
                background: #0a84ff;
                border: none;
                border-radius: 7px;
                color: #ffffff;
                text-align: left;
                padding: 0 12px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton#newChatButton:hover {{
                background: #2997ff;
            }}
            QPushButton#newChatButton:pressed {{
                background: #0066cc;
            }}

            /* ── Content Panel (Elevated Card) ────────────────── */
            QWidget#contentPanel {{
                background: #202024;
                border-left: 1px solid #2c2c30;
            }}

            /* ── Header Bar ───────────────────────────────────── */
            QWidget#headerBar {{
                background: #202024;
            }}
            QFrame#headerSep {{
                background: #2c2c30;
                border: none;
            }}
            QLabel#headerChatTitle {{
                color: #f5f5f7;
                font-size: 13.5px;
                font-weight: 600;
                letter-spacing: -0.1px;
            }}

            /* ── Status Indicator Pills ───────────────────────── */
            QLabel#pillReady {{
                background: rgba(52, 199, 89, 0.18);
                color: #30d158;
                border: 1px solid rgba(52, 199, 89, 0.35);
                border-radius: 12px;
                padding: 2px 10px;
                font-size: 11px;
                font-weight: 600;
            }}
            QLabel#pillThinking {{
                background: rgba(255, 159, 10, 0.18);
                color: #ff9f0a;
                border: 1px solid rgba(255, 159, 10, 0.35);
                border-radius: 12px;
                padding: 2px 10px;
                font-size: 11px;
                font-weight: 600;
            }}
            QLabel#pillListening {{
                background: rgba(10, 132, 255, 0.18);
                color: #64d2ff;
                border: 1px solid rgba(10, 132, 255, 0.35);
                border-radius: 12px;
                padding: 2px 10px;
                font-size: 11px;
                font-weight: 600;
            }}

            /* ── Welcome Panel ────────────────────────────────── */
            QWidget#chatWrapper {{ background: transparent; }}
            QWidget#welcomePanel {{ background: transparent; }}
            QLabel#welcomeTitle {{
                color: #f5f5f7;
                font-size: 22px;
                font-weight: 600;
                letter-spacing: -0.3px;
            }}
            QLabel#welcomeSubtitle {{
                color: #86868b;
                font-size: 14px;
                font-weight: 400;
            }}
            QPushButton#suggestionButton {{
                background: #28282c;
                border: 1px solid #38383c;
                border-radius: 14px;
                color: #f5f5f7;
                padding: 6px 14px;
                font-size: 11.5px;
                font-weight: 500;
            }}
            QPushButton#suggestionButton:hover {{
                background: #323236;
                border-color: #0a84ff;
                color: #64d2ff;
            }}

            /* ── Conversation List ────────────────────────────── */
            QListWidget#conversationList {{
                background: transparent;
                border: none;
                padding: 10px 16px;
            }}
            QListWidget#conversationList::item {{
                background: transparent;
                border: none;
                padding: 0;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 6px;
                border-radius: 3px;
                margin: 4px 2px;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(255, 255, 255, 0.15);
                border-radius: 3px;
                min-height: 24px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: rgba(255, 255, 255, 0.3);
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}

            /* ── Message Cards ────────────────────────────────── */
            QFrame#astraBubble {{
                background: #26262a;
                border: 1px solid #38383c;
                border-radius: 14px;
                border-top-left-radius: 4px;
            }}
            QFrame#userBubble {{
                background: #0a84ff;
                border: none;
                border-radius: 16px;
                border-top-right-radius: 4px;
            }}
            QFrame#errorBubble {{
                background: #2c1517;
                border: 1px solid #5c2427;
                border-radius: 14px;
                border-top-left-radius: 4px;
            }}
            QLabel#bubbleSender {{
                color: #86868b;
                font-size: 10px;
                font-weight: 600;
                letter-spacing: 0.5px;
                text-transform: uppercase;
            }}
            QLabel#bubbleTimestamp {{
                color: #636366;
                font-size: 10px;
            }}
            QLabel#bubbleText {{
                color: #f5f5f7;
                font-size: 13.5px;
                line-height: 1.6;
            }}
            QLabel#bubbleTextUser {{
                color: #ffffff;
                font-size: 13.5px;
                line-height: 1.55;
            }}
            QLabel#bubbleTextError {{
                color: #ff453a;
                font-size: 13.5px;
                line-height: 1.55;
            }}

            /* ── Status Bar ───────────────────────────────────── */
            QLabel#statusLabel {{
                color: #86868b;
                font-size: 11px;
                background: transparent;
            }}

            /* ── Composer Capsule ─────────────────────────────── */
            QWidget#composerOuter {{ background: transparent; }}
            QFrame#composerFrame {{
                background: #242428;
                border: 1px solid #3a3a3c;
                border-radius: 23px;
            }}
            QFrame#composerFrame:focus-within {{
                border: 1.5px solid #0a84ff;
            }}
            QLineEdit#messageInput {{
                background: transparent;
                border: none;
                padding: 4px 8px;
                color: #f5f5f7;
                font-size: 13.5px;
            }}

            /* ── Controls ─────────────────────────────────────── */
            QPushButton#sendButton {{
                background: #0a84ff;
                color: #ffffff;
                border: none;
                border-radius: 16px;
                font-weight: 600;
                font-size: 12px;
            }}
            QPushButton#sendButton:hover {{
                background: #2997ff;
            }}
            QPushButton#sendButton:disabled {{
                background: #3a3a3c;
                color: #636366;
            }}
            QPushButton#iconButton {{
                background: #2c2c30;
                border: 1px solid #3a3a3c;
                color: #a1a1a6;
                font-size: 11.5px;
                font-weight: 500;
                border-radius: 16px;
            }}
            QPushButton#iconButton:hover {{
                background: #38383c;
                color: #f5f5f7;
            }}
            QPushButton#iconButtonActive {{
                background: #ff453a;
                border: none;
                color: #ffffff;
                font-size: 11.5px;
                font-weight: 600;
                border-radius: 16px;
            }}
            QPushButton#ghostButton {{
                background: transparent;
                border: 1px solid #3a3a3c;
                border-radius: 6px;
                color: #a1a1a6;
                font-size: 11.5px;
                font-weight: 500;
                padding: 0 10px;
            }}
            QPushButton#ghostButton:hover {{
                background: #2c2c30;
                color: #f5f5f7;
            }}
            QPushButton:disabled {{ opacity: 0.4; }}

            /* ── Context Menu ─────────────────────────────────── */
            QMenu {{
                background: #242428;
                border: 1px solid #38383c;
                border-radius: 8px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 14px;
                border-radius: 5px;
                color: #f5f5f7;
                font-size: 12px;
                font-weight: 500;
            }}
            QMenu::item:selected {{
                background: #0a84ff;
                color: #ffffff;
            }}
            QMenu::separator {{
                height: 1px;
                background: #38383c;
                margin: 4px 6px;
            }}
            """
        )

    # ── Session Management ────────────────────────────────────────────────────

    def _new_session(self, title: str) -> dict[str, object]:
        session: dict[str, object] = {"title": title, "messages": []}
        self._sessions.insert(0, session)
        self._refresh_chat_history()
        return session

    def _refresh_chat_history(self) -> None:
        query = self.chat_search.text().strip().lower()
        self.chat_history.clear()
        for session in self._sessions:
            title = str(session.get("title", "Untitled"))
            if query and query not in title.lower():
                continue
            item = QListWidgetItem(title)
            item.setData(Qt.ItemDataRole.UserRole, session)
            self.chat_history.addItem(item)
        self._sync_history_selection()

    def _sync_history_selection(self) -> None:
        for i in range(self.chat_history.count()):
            item = self.chat_history.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) is self._current_session:
                self.chat_history.setCurrentItem(item)
                return

    def _toggle_chat_search(self) -> None:
        visible = not self.chat_search.isVisible()
        self.chat_search.setVisible(visible)
        if visible:
            self.chat_search.setFocus()
        else:
            self.chat_search.clear()
            self._refresh_chat_history()

    def _filter_chat_history(self, _text: str) -> None:
        self._refresh_chat_history()

    def _start_new_chat(self) -> None:
        if self._worker is not None:
            return
        self._current_session = self._new_session("New conversation")
        self.conversation.clear()
        self.welcome_panel.show()
        self._chat_title_lbl.setText("New conversation")
        self._add_message("assistant", "Hello! I'm Astra — how can I help you today?")
        self.status_label.setText("Ready  ·  Type a message to get started")
        self._set_thinking_state(False)

    def _show_chat_context_menu(self, pos: QPoint) -> None:
        item = self.chat_history.itemAt(pos)
        menu = QMenu(self)

        del_action = None
        target_session = None

        if item is not None:
            target_session = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(target_session, dict):
                del_action = menu.addAction("Delete Conversation")

        clear_all_action = None
        if len(self._sessions) > 1:
            if del_action is not None:
                menu.addSeparator()
            clear_all_action = menu.addAction("Clear All Past Chats")

        new_chat_action = None
        if del_action is None and clear_all_action is None:
            new_chat_action = menu.addAction("New Conversation")

        if not menu.actions():
            return

        global_pos = self.chat_history.viewport().mapToGlobal(pos)
        chosen = menu.exec(global_pos)

        if del_action and chosen == del_action and target_session:
            self._delete_session(target_session)
        elif clear_all_action and chosen == clear_all_action:
            self._clear_all_sessions()
        elif new_chat_action and chosen == new_chat_action:
            self._start_new_chat()

    def _delete_session(self, session: dict[str, object], confirm: bool = True) -> None:
        title = str(session.get("title", "this conversation"))
        if confirm:
            reply = QMessageBox.question(
                self,
                "Delete Conversation",
                f'Are you sure you want to delete "{title}"?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        if session in self._sessions:
            self._sessions.remove(session)

        if session is self._current_session:
            if self._sessions:
                self._restore_chat_by_session(self._sessions[0])
            else:
                self._start_new_chat()

        self._refresh_chat_history()
        self.status_label.setText("Conversation deleted")

    def _clear_all_sessions(self, confirm: bool = True) -> None:
        if confirm:
            reply = QMessageBox.question(
                self,
                "Clear All Past Chats",
                "Are you sure you want to delete all past conversations?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        self._sessions.clear()
        self._start_new_chat()
        self.status_label.setText("All conversations cleared")

    def _restore_chat_by_session(self, session: dict[str, object]) -> None:
        self._current_session = session
        self.conversation.clear()
        messages: list = session.get("messages", [])  # type: ignore[assignment]
        has_user_msg = any(s == "user" for s, _ in (messages or []))
        self.welcome_panel.setVisible(not has_user_msg)
        self._chat_title_lbl.setText(str(session.get("title", "Conversation")))
        for sender, text in (messages or []):
            self._add_message(str(sender), str(text), record=False)
        self._sync_history_selection()

    def _restore_chat(self, item: QListWidgetItem) -> None:
        session = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(session, dict):
            return
        self._restore_chat_by_session(session)

    # ── Sidebar Collapse (Smooth Animation) ───────────────────────────────────

    def _toggle_sidebar(self) -> None:
        self._sidebar_collapsed = not self._sidebar_collapsed
        target_w = 0 if self._sidebar_collapsed else 220
        start_w = self.sidebar.width()

        if _prefers_reduced_motion():
            self.sidebar.setFixedWidth(target_w)
            self.sidebar.setVisible(not self._sidebar_collapsed)
            self._expand_btn.setVisible(self._sidebar_collapsed)
            return

        if not self._sidebar_collapsed:
            self.sidebar.setVisible(True)
            self._expand_btn.setVisible(False)

        anim = QPropertyAnimation(self.sidebar, b"maximumWidth", self)
        anim.setDuration(180)
        anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        anim.setStartValue(start_w)
        anim.setEndValue(target_w)

        def on_finished() -> None:
            if self._sidebar_collapsed:
                self.sidebar.setVisible(False)
                self._expand_btn.setVisible(True)
            else:
                self.sidebar.setFixedWidth(220)

        anim.finished.connect(on_finished)
        anim.start()
        self._sidebar_anim = anim

    # ── Settings ──────────────────────────────────────────────────────────────

    def _show_settings(self) -> None:
        dialog = _SettingsDialog(self._settings, self._settings_store, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._apply_settings()

    def _apply_settings(self) -> None:
        """Apply active preferences to the running application."""
        self.conversation.setSpacing(2 if self._settings.compact_messages else 5)

        is_dark = (
            self._settings.theme == "Dark"
            or (self._settings.theme == "System" and _detect_system_dark_mode())
        )
        if is_dark:
            self._apply_dark_style()
        else:
            self._apply_style()

        if self._tts_synthesizer:
            self._tts_synthesizer.voice_name = self._settings.speaker
            self._tts_synthesizer.speed_wpm = self._settings.speech_speed

        if hasattr(self._assistant, "update_settings"):
            self._assistant.update_settings(self._settings)

    # ── Voice Input ───────────────────────────────────────────────────────────

    def _start_voice_input(self) -> None:
        """Begin a microphone recording session on a background thread."""
        if not _VOICE_AVAILABLE:
            self._add_message(
                "error",
                "Voice input is unavailable. "
                "Install the required libraries: pip install SpeechRecognition PyAudio",
            )
            return
        if self._worker is not None or self._voice_worker is not None:
            return

        listener = _SpeechListener(microphone_name=self._settings.microphone)  # type: ignore[misc]
        self._voice_worker = _VoiceWorker(listener)
        self._voice_worker.text_ready.connect(self._on_voice_text)
        self._voice_worker.error_occurred.connect(self._on_voice_error)
        self._voice_worker.finished.connect(self._voice_finished)
        self._voice_worker.start()
        self._set_listening_state(True)

    def _set_listening_state(self, listening: bool) -> None:
        """Toggle the UI between idle and actively-listening states."""
        if listening:
            self.status_label.setText("Listening…  Speak now")
            self.connection_label.setText("● Listening")
            self.connection_label.setObjectName("pillListening")
            self.microphone_button.setObjectName("iconButtonActive")
            self.microphone_button.setToolTip("Listening… (click will cancel after phrase ends)")
        else:
            self.status_label.setText("Ready  ·  Type a message to get started")
            self.connection_label.setText("● Ready")
            self.connection_label.setObjectName("pillReady")
            self.microphone_button.setObjectName("iconButton")
            self.microphone_button.setToolTip("Click to speak (voice input)")

        for widget in (self.connection_label, self.microphone_button):
            widget.style().unpolish(widget)
            widget.style().polish(widget)

        self.send_button.setEnabled(not listening)
        self.input.setEnabled(not listening)
        if _VOICE_AVAILABLE:
            self.microphone_button.setEnabled(not listening)

    @Slot()
    def _voice_finished(self) -> None:
        """Clean up the voice worker after it completes or errors."""
        worker = self._voice_worker
        self._voice_worker = None
        if worker is not None:
            worker.deleteLater()
        self._set_listening_state(False)

    def _on_voice_text(self, text: str) -> None:
        """Handle a successfully recognised transcript."""
        self._set_listening_state(False)
        self.input.setText(text)
        self.input.setFocus()
        self._submit_from_input()

    def _on_voice_error(self, message: str) -> None:
        """Display a voice error in the chat without crashing."""
        self._set_listening_state(False)
        self._add_message("error", f"Voice input: {message}")
        self.status_label.setText("Voice input failed — try again")
        self.input.setFocus()

    # ── Messaging ─────────────────────────────────────────────────────────────

    def _submit_from_input(self) -> None:
        text = self.input.text().strip()
        if not text or not self.send_button.isEnabled():
            return
        self.input.clear()
        self.welcome_panel.hide()
        self._add_message("user", text)
        self._set_thinking_state(True)
        self.message_submitted.emit(text)

        self._worker = _AssistantWorker(self._assistant, text)
        self._worker.response_ready.connect(self._show_response)
        self._worker.finished.connect(self._assistant_finished)
        self._worker.start()

    def _set_thinking_state(self, thinking: bool) -> None:
        if thinking:
            self.status_label.setText("Astra is thinking…")
            self.connection_label.setText("● Thinking")
            self.connection_label.setObjectName("pillThinking")
        else:
            self.status_label.setText("Ready  ·  Type a message to get started")
            self.connection_label.setText("● Ready")
            self.connection_label.setObjectName("pillReady")

        self.connection_label.style().unpolish(self.connection_label)
        self.connection_label.style().polish(self.connection_label)
        self.send_button.setEnabled(not thinking)
        self.input.setEnabled(not thinking)
        if _VOICE_AVAILABLE:
            self.microphone_button.setEnabled(not thinking)

    @Slot()
    def _assistant_finished(self) -> None:
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.deleteLater()

    def _show_response(self, response: AssistantResponse) -> None:
        self._set_thinking_state(False)
        if response.success:
            self._add_message("assistant", response.text)
            self.status_label.setText("Ready")
            self._speak_text(response.text)
        else:
            self._add_message("error", response.error or "The assistant is unavailable.")
            self.status_label.setText("Error — see message above for details")
        self.input.setFocus()

    def _speak_text(self, text: str) -> None:
        """Speak response text using TTS outside the UI thread."""
        if not _TTS_AVAILABLE or not self._tts_synthesizer or not text.strip():
            return
        if self._tts_worker is not None:
            self._tts_worker.stop()
            self._tts_worker.wait()
            self._tts_worker = None

        self._tts_worker = _TTSWorker(self._tts_synthesizer, text)
        self._tts_worker.speech_finished.connect(self._tts_finished)
        self._tts_worker.start()

    @Slot()
    def _tts_finished(self) -> None:
        worker = self._tts_worker
        self._tts_worker = None
        if worker is not None:
            worker.deleteLater()

    def _add_message(self, sender: str, text: str, record: bool = True) -> None:
        if record:
            messages = self._current_session.setdefault("messages", [])
            if isinstance(messages, list):
                messages.append((sender, text))
            if sender == "user" and self._current_session.get("title") == "New conversation":
                new_title = text[:30] + ("…" if len(text) > 30 else "")
                self._current_session["title"] = new_title
                self._chat_title_lbl.setText(new_title)
                self._refresh_chat_history()

        is_dark = (
            self._settings.theme == "Dark"
            or (self._settings.theme == "System" and _detect_system_dark_mode())
        )
        bubble = _MessageBubble(sender, text, is_dark=is_dark)

        # Smooth message appearance animation (160ms OutQuad opacity fade)
        if not _prefers_reduced_motion():
            opacity_fx = QGraphicsOpacityEffect(bubble)
            bubble.setGraphicsEffect(opacity_fx)
            anim = QPropertyAnimation(opacity_fx, b"opacity", bubble)
            anim.setDuration(160)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.Type.OutQuad)
            anim.start()
            bubble._fade_anim = anim  # prevent garbage collection

        item = QListWidgetItem()
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        self.conversation.addItem(item)
        self.conversation.setItemWidget(item, bubble)

        list_w = self.conversation.viewport().width()
        bubble.setFixedWidth(max(list_w - 10, 200))
        bubble.adjustSize()
        item.setSizeHint(QSize(list_w - 10, bubble.sizeHint().height() + 4))
        self.conversation.scrollToBottom()

    # ── Dynamic Resizing ──────────────────────────────────────────────────────

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        list_w = self.conversation.viewport().width()
        for i in range(self.conversation.count()):
            item = self.conversation.item(i)
            widget = self.conversation.itemWidget(item)
            if widget:
                widget.setFixedWidth(max(list_w - 10, 200))
                widget.adjustSize()
                item.setSizeHint(QSize(list_w - 10, widget.sizeHint().height() + 4))

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    @Slot()
    def show(self) -> None:
        super().show()
        self.input.setFocus()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self._tts_worker is not None:
            self._tts_worker.stop()
        for worker in (self._worker, self._voice_worker, self._tts_worker):
            if worker is not None:
                worker.blockSignals(True)
                if worker.isRunning():
                    worker.wait()
        self._worker = None
        self._voice_worker = None
        self._tts_worker = None
        event.accept()
