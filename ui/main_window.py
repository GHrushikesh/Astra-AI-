"""Main Astra desktop window — polished light-theme redesign with sidebar."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QRect,
    QSize,
    QThread,
    Qt,
    Signal,
    Slot,
)
from PySide6.QtGui import (
    QColor,
    QFont,
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
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
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
# Worker thread
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


# ─────────────────────────────────────────────────────────────────────────────
# Voice worker thread
# ─────────────────────────────────────────────────────────────────────────────

class _VoiceWorker(QThread):
    """Record one phrase from the microphone on a background thread.

    Emits ``text_ready`` with the transcript on success, or
    ``error_occurred`` with a human-readable message on any failure.
    The worker never modifies the UI directly.
    """

    text_ready = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, listener: object) -> None:  # listener: _SpeechListener
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
# Avatar helper
# ─────────────────────────────────────────────────────────────────────────────

def _make_avatar_pixmap(letter: str, bg: str, fg: str, size: int = 32) -> QPixmap:
    """Render a crisp round avatar with a centred letter."""
    size = max(16, size)
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addEllipse(0, 0, size, size)
    p.fillPath(path, QColor(bg))
    p.setPen(QColor(fg))
    font_size = max(8, int(size * 0.38))
    p.setFont(QFont("Segoe UI", font_size, QFont.Weight.Bold))
    p.drawText(QRect(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, letter)
    p.end()
    return pix


# ─────────────────────────────────────────────────────────────────────────────
# Typing-indicator dots
# ─────────────────────────────────────────────────────────────────────────────

class _TypingDot(QWidget):
    """One animated dot for the typing indicator."""

    def __init__(self, delay_ms: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(8, 8)
        self._anim = QPropertyAnimation(self, b"geometry")
        self._anim.setDuration(700)
        self._anim.setLoopCount(-1)
        self._anim.setEasingCurve(QEasingCurve.Type.SineCurve)
        self._delay = delay_ms

    def start(self) -> None:
        geo = self.geometry()
        self._anim.setStartValue(QRect(geo.x(), geo.y(), 8, 8))
        self._anim.setEndValue(QRect(geo.x(), geo.y() - 6, 8, 8))
        self._anim.setStartDelay(self._delay)
        self._anim.start()

    def stop(self) -> None:
        self._anim.stop()
        # Reset position
        geo = self.geometry()
        self.setGeometry(QRect(geo.x(), geo.y(), 8, 8))

    def paintEvent(self, _event) -> None:  # type: ignore[override]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor("#347be8"))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(0, 0, 8, 8)


class _TypingIndicator(QWidget):
    """Three-dot bounce animation shown while Astra is thinking."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 8, 4, 8)
        layout.setSpacing(5)
        self._dots: list[_TypingDot] = []
        for delay in (0, 160, 320):
            dot = _TypingDot(delay, self)
            self._dots.append(dot)
            layout.addWidget(dot)
        layout.addStretch()
        self.setFixedHeight(30)

    def start(self) -> None:
        for d in self._dots:
            d.start()

    def stop(self) -> None:
        for d in self._dots:
            d.stop()


# ─────────────────────────────────────────────────────────────────────────────
# Message bubble
# ─────────────────────────────────────────────────────────────────────────────

class _MessageBubble(QWidget):
    """Chat message with avatar, sender name, body text, and timestamp."""

    def __init__(self, sender: str, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        is_user = sender == "user"
        is_error = sender == "error"

        labels = {"user": "You", "assistant": "Astra", "error": "Error"}
        display_name = labels.get(sender, sender.title())
        timestamp = datetime.now().strftime("%H:%M")

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Avatar
        av = QLabel()
        if is_user:
            av.setPixmap(_make_avatar_pixmap("Y", "#211d3d", "#ffffff"))
        elif is_error:
            av.setPixmap(_make_avatar_pixmap("!", "#e53e3e", "#ffffff"))
        else:
            av.setPixmap(_make_avatar_pixmap("A", "#347be8", "#ffffff"))
        av.setFixedSize(36, 36)
        av.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Card
        card = QFrame()
        card.setObjectName("userBubble" if is_user else ("errorBubble" if is_error else "astraBubble"))
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(14, 10, 14, 10)
        card_lay.setSpacing(3)

        # Header row: sender name + timestamp
        header_row = QHBoxLayout()
        header_row.setSpacing(8)
        name_lbl = QLabel(display_name)
        name_lbl.setObjectName("bubbleSender")
        time_lbl = QLabel(timestamp)
        time_lbl.setObjectName("bubbleTimestamp")
        header_row.addWidget(name_lbl)
        header_row.addWidget(time_lbl)
        header_row.addStretch()

        text_lbl = QLabel(text)
        text_lbl.setObjectName("bubbleText")
        if is_user:
            text_lbl.setObjectName("bubbleTextUser")
        text_lbl.setWordWrap(True)
        text_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        text_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        card_lay.addLayout(header_row)
        card_lay.addWidget(text_lbl)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(10)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(0, 0, 0, 16))
        card.setGraphicsEffect(shadow)

        # Layout: user → right-aligned, assistant/error → left-aligned
        if is_user:
            outer.setContentsMargins(60, 3, 4, 3)
            inner = QHBoxLayout()
            inner.setSpacing(10)
            inner.addStretch(1)
            inner.addWidget(card)
            inner.addWidget(av)
            outer.addLayout(inner)
        else:
            outer.setContentsMargins(4, 3, 60, 3)
            inner = QHBoxLayout()
            inner.setSpacing(10)
            inner.addWidget(av)
            inner.addWidget(card)
            inner.addStretch(1)
            outer.addLayout(inner)


# ─────────────────────────────────────────────────────────────────────────────
# Settings dialog
# ─────────────────────────────────────────────────────────────────────────────

_ASSETS_DIR = Path(__file__).resolve().parent / "assets"


def _ensure_ui_assets() -> None:
    """Ensure SVG icons required for clean UI elements exist."""
    _ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    check_file = _ASSETS_DIR / "check_white.svg"
    if not check_file.exists():
        check_file.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" '
            'stroke="#ffffff" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round">'
            '<polyline points="20 6 9 17 4 12"/></svg>',
            encoding="utf-8",
        )
    chevron_file = _ASSETS_DIR / "chevron_down.svg"
    if not chevron_file.exists():
        chevron_file.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" '
            'stroke="#64748b" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
            '<polyline points="6 9 12 15 18 9"/></svg>',
            encoding="utf-8",
        )


class _SettingsDialog(QDialog):
    """Modal settings panel backed by the persistent settings store."""

    def __init__(
        self,
        settings: AstraSettings,
        store: SettingsStore,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._store = store
        self.setWindowTitle("Astra · Settings")
        self.setModal(True)
        self.setMinimumWidth(380)
        self._build()
        self._style()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(16)

        # Title
        title = QLabel("Settings")
        title.setObjectName("settingsTitle")
        root.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setObjectName("settingsSep")
        root.addWidget(sep)

        # Google Gemini AI section
        root.addWidget(self._section_label("Google Gemini API"))
        ai_desc = QLabel("Enter your Google Gemini API key to activate AI intelligence and natural language controls.")
        ai_desc.setWordWrap(True)
        ai_desc.setStyleSheet("color: #64748b; font-size: 12px; padding: 2px 0 4px 0;")
        root.addWidget(ai_desc)

        ai_form = QFormLayout()
        ai_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        ai_form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        ai_form.setHorizontalSpacing(16)
        ai_form.setVerticalSpacing(10)

        self.llm_api_key = QLineEdit()
        self.llm_api_key.setObjectName("settingsInput")
        self.llm_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.llm_api_key.setPlaceholderText("Paste Gemini API key (AIzaSy...)")
        self.llm_api_key.setText(self._settings.llm_api_key)

        key_lbl = QLabel("Gemini API Key")
        key_lbl.setObjectName("settingsRowLabel")
        ai_form.addRow(key_lbl, self.llm_api_key)
        root.addLayout(ai_form)

        # Internal compatibility attributes
        self.llm_provider = QComboBox()
        self.llm_provider.addItems(["Google Gemini", "OpenAI", "Groq", "Ollama / Local", "Anthropic", "Custom"])
        self.llm_provider.setCurrentText(self._settings.llm_provider or "Google Gemini")
        self.llm_provider.hide()

        self.llm_model = QLineEdit()
        self.llm_model.setText(self._settings.llm_model or "gemini-1.5-flash")
        self.llm_model.hide()

        self.llm_endpoint = QLineEdit()
        self.llm_endpoint.setText(self._settings.llm_endpoint or "")
        self.llm_endpoint.hide()

        # Voice section
        root.addWidget(self._section_label("Voice"))
        voice_form = QFormLayout()
        voice_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        voice_form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        voice_form.setHorizontalSpacing(16)
        voice_form.setVerticalSpacing(10)

        # Microphone — populated from the voice service (real devices when available)
        self.microphone = QComboBox()
        mic_devices = _enumerate_microphones()
        for dev in mic_devices:
            self.microphone.addItem(dev)
        if self._settings.microphone not in mic_devices:
            self.microphone.addItem(self._settings.microphone)
        self.microphone.setCurrentText(self._settings.microphone)
        self.microphone.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        # Speaker — populated from TTS voice enumeration
        self.speaker = QComboBox()
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
        self.speech_speed.setSuffix(" words/min")
        speed_row.addWidget(self.speech_speed)
        voice_form.addRow(speed_row)

        root.addLayout(voice_form)

        # Appearance section
        root.addWidget(self._section_label("Appearance"))
        app_form = QFormLayout()
        app_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        app_form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        app_form.setHorizontalSpacing(16)
        app_form.setVerticalSpacing(10)

        theme_lbl = QLabel("Theme")
        theme_lbl.setObjectName("settingsRowLabel")
        self.theme = QComboBox()
        self.theme.addItems(["Light", "Dark", "System"])
        self.theme.setCurrentText(self._settings.theme)
        self.theme.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        app_form.addRow(theme_lbl, self.theme)

        self.compact_mode = QCheckBox("Compact message spacing")
        self.compact_mode.setObjectName("settingsCheck")
        self.compact_mode.setChecked(self._settings.compact_messages)
        app_form.addRow("", self.compact_mode)
        root.addLayout(app_form)

        # Notifications section
        root.addWidget(self._section_label("Notifications"))
        self.notifications = QCheckBox("Show desktop notifications")
        self.notifications.setObjectName("settingsCheck")
        self.notifications.setChecked(self._settings.notifications_enabled)
        root.addWidget(self.notifications)

        # Startup section
        root.addWidget(self._section_label("Startup"))
        self.start_with_windows = QCheckBox("Start Astra with Windows")
        self.start_with_windows.setObjectName("settingsCheck")
        self.start_with_windows.setChecked(self._settings.start_with_windows)
        root.addWidget(self.start_with_windows)

        root.addSpacing(8)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.setObjectName("settingsButtons")
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    @staticmethod
    def _section_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("settingsSection")
        return lbl

    def _style(self) -> None:
        _ensure_ui_assets()
        check_path = (_ASSETS_DIR / "check_white.svg").as_posix()
        chevron_path = (_ASSETS_DIR / "chevron_down.svg").as_posix()

        self.setStyleSheet(
            f"""
            QDialog {{
                background: #ffffff;
                font-family: 'Segoe UI', Arial, sans-serif;
            }}
            QLabel#settingsTitle {{
                font-size: 20px;
                font-weight: 700;
                color: #111a35;
            }}
            QFrame#settingsSep {{
                background: #eef1f5;
                border: none;
                max-height: 1px;
            }}
            QLabel#settingsSection {{
                font-size: 11px;
                font-weight: 700;
                color: #64748b;
                letter-spacing: 1px;
                text-transform: uppercase;
                padding-top: 6px;
            }}
            QLabel#settingsRowLabel {{
                font-size: 13px;
                font-weight: 500;
                color: #334155;
            }}
            QCheckBox#settingsCheck {{
                font-size: 13px;
                color: #1e293b;
                spacing: 10px;
            }}
            QCheckBox#settingsCheck::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 5px;
                border: 1.5px solid #cbd5e1;
                background: #ffffff;
            }}
            QCheckBox#settingsCheck::indicator:hover {{
                border-color: #347be8;
                background: #f0f6ff;
            }}
            QCheckBox#settingsCheck::indicator:checked {{
                background: #347be8;
                border-color: #347be8;
                image: url("{check_path}");
            }}
            QCheckBox#settingsCheck::indicator:checked:hover {{
                background: #2563c7;
                border-color: #2563c7;
                image: url("{check_path}");
            }}
            QSpinBox#settingsSpinBox {{
                background: #f8fafc;
                border: 1.5px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 10px;
                color: #0f172a;
                font-size: 13px;
                min-width: 140px;
            }}
            QSpinBox#settingsSpinBox:focus {{
                border-color: #347be8;
                background: #ffffff;
            }}
            QComboBox {{
                background: #f8fafc;
                border: 1.5px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 30px 6px 12px;
                color: #0f172a;
                font-size: 13px;
                min-width: 180px;
            }}
            QComboBox:focus, QComboBox:hover {{
                border-color: #347be8;
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 26px;
                border-left: none;
            }}
            QComboBox::down-arrow {{
                image: url("{chevron_path}");
                width: 12px;
                height: 12px;
                margin-right: 8px;
            }}
            QComboBox QAbstractItemView {{
                background-color: #ffffff;
                color: #0f172a;
                selection-background-color: #e0eafc;
                selection-color: #1d4ed8;
                border: 1.5px solid #cbd5e1;
                border-radius: 6px;
                padding: 4px;
                outline: none;
            }}
            QComboBox QAbstractItemView::item {{
                min-height: 28px;
                padding: 4px 8px;
                border-radius: 4px;
                color: #0f172a;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: #f1f5f9;
                color: #0f172a;
            }}
            QComboBox QAbstractItemView::item:selected {{
                background-color: #e0eafc;
                color: #1d4ed8;
            }}
            QLineEdit#settingsInput {{
                background: #f8fafc;
                border: 1.5px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 12px;
                color: #0f172a;
                font-size: 13px;
                min-width: 180px;
            }}
            QLineEdit#settingsInput:focus {{
                border-color: #347be8;
                background: #ffffff;
            }}
            QDialogButtonBox#settingsButtons QPushButton {{
                min-width: 88px;
                min-height: 34px;
                border-radius: 8px;
                font-weight: 600;
                font-size: 13px;
                padding: 0 16px;
            }}
            QDialogButtonBox#settingsButtons QPushButton[text="OK"] {{
                background: #347be8;
                color: #ffffff;
                border: none;
            }}
            QDialogButtonBox#settingsButtons QPushButton[text="OK"]:hover {{
                background: #2563c7;
            }}
            QDialogButtonBox#settingsButtons QPushButton[text="Cancel"] {{
                background: #ffffff;
                color: #475569;
                border: 1.5px solid #cbd5e1;
            }}
            QDialogButtonBox#settingsButtons QPushButton[text="Cancel"]:hover {{
                background: #f8fafc;
                color: #0f172a;
            }}
            """
        )

    def _save(self) -> None:
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
            llm_model=self.llm_model.text().strip(),
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
# Main window
# ─────────────────────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    """Astra's conversation window — light theme with sidebar and session history."""

    microphone_requested = Signal()
    message_submitted = Signal(str)

    # Accent colours mirrored in QSS so Python logic can stay in sync
    _ACCENT = "#347be8"
    _DARK   = "#211d3d"

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
        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.setWindowTitle("Astra")
        self.setMinimumSize(900, 600)
        self.resize(1180, 760)

        central = QWidget(self)
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Sidebar ────────────────────────────────────────────────────
        self.sidebar = QWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(210)
        sb = QVBoxLayout(self.sidebar)
        sb.setContentsMargins(14, 18, 14, 14)
        sb.setSpacing(4)

        # Sidebar header
        sb_header = QHBoxLayout()
        sb_logo = QLabel()
        sb_logo.setPixmap(_make_avatar_pixmap("A", self._ACCENT, "#ffffff", 28))
        sb_logo.setFixedSize(28, 28)
        sb_header.addWidget(sb_logo)
        sb_brand = QLabel("Astra")
        sb_brand.setObjectName("sidebarBrand")
        sb_header.addWidget(sb_brand)
        sb_header.addStretch()
        self._collapse_btn = QPushButton("◧")
        self._collapse_btn.setObjectName("sidebarIcon")
        self._collapse_btn.setFixedSize(26, 26)
        self._collapse_btn.setToolTip("Collapse sidebar")
        self._collapse_btn.clicked.connect(self._toggle_sidebar)
        sb_header.addWidget(self._collapse_btn)
        sb.addLayout(sb_header)
        sb.addSpacing(20)

        # New conversation button
        new_chat_btn = QPushButton("+  New Conversation")
        new_chat_btn.setObjectName("newChatButton")
        new_chat_btn.clicked.connect(self._start_new_chat)
        sb.addWidget(new_chat_btn)
        sb.addSpacing(6)

        # Search toggle
        self._search_btn = QPushButton("Search Conversations")
        self._search_btn.setObjectName("sidebarButton")
        self._search_btn.clicked.connect(self._toggle_chat_search)
        sb.addWidget(self._search_btn)

        self.chat_search = QLineEdit()
        self.chat_search.setObjectName("chatSearch")
        self.chat_search.setPlaceholderText("Search chats…")
        self.chat_search.textChanged.connect(self._filter_chat_history)
        self.chat_search.hide()
        sb.addWidget(self.chat_search)
        sb.addSpacing(14)

        # Chat history list
        history_lbl = QLabel("Recent")
        history_lbl.setObjectName("sidebarSection")
        sb.addWidget(history_lbl)

        self.chat_history = QListWidget()
        self.chat_history.setObjectName("chatHistory")
        self.chat_history.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.chat_history.itemClicked.connect(self._restore_chat)
        sb.addWidget(self.chat_history, 1)

        # Discover (placeholder)
        discover_btn = QPushButton("Discover")
        discover_btn.setObjectName("sidebarButton")
        sb.addWidget(discover_btn)

        sb.addStretch()

        # Bottom area
        settings_btn = QPushButton("Settings")
        settings_btn.setObjectName("sidebarButton")
        settings_btn.clicked.connect(self._show_settings)
        sb.addWidget(settings_btn)

        help_btn = QPushButton("Help Center")
        help_btn.setObjectName("sidebarButton")
        sb.addWidget(help_btn)

        account = QLabel("Astra Workspace")
        account.setObjectName("accountLabel")
        sb.addWidget(account)

        root.addWidget(self.sidebar)

        # ── Content panel ──────────────────────────────────────────────
        content = QWidget()
        content.setObjectName("contentPanel")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Header bar
        header_bar = QWidget()
        header_bar.setObjectName("headerBar")
        header_bar.setFixedHeight(58)
        hl = QHBoxLayout(header_bar)
        hl.setContentsMargins(20, 0, 20, 0)
        hl.setSpacing(12)

        self._expand_btn = QPushButton(">")
        self._expand_btn.setObjectName("ghostButton")
        self._expand_btn.setFixedSize(30, 30)
        self._expand_btn.setToolTip("Expand sidebar")
        self._expand_btn.clicked.connect(self._toggle_sidebar)
        self._expand_btn.hide()  # Hidden until sidebar is collapsed
        hl.addWidget(self._expand_btn)

        hdr_logo = QLabel()
        hdr_logo.setPixmap(_make_avatar_pixmap("A", self._ACCENT, "#ffffff", 30))
        hdr_logo.setFixedSize(30, 30)
        hl.addWidget(hdr_logo)

        hdr_col = QVBoxLayout()
        hdr_col.setSpacing(0)
        self._chat_title_lbl = QLabel("New conversation")
        self._chat_title_lbl.setObjectName("headerChatTitle")
        hdr_col.addWidget(self._chat_title_lbl)
        hl.addLayout(hdr_col)
        hl.addStretch()

        self.connection_label = QLabel("Ready")
        self.connection_label.setObjectName("pillReady")
        self.connection_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.connection_label.setFixedSize(68, 28)
        self.connection_label.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        hl.addWidget(self.connection_label)

        self.settings_button = QPushButton("Settings")
        self.settings_button.setObjectName("ghostButton")
        self.settings_button.setToolTip("Open Astra settings")
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

        # Welcome panel
        self.welcome_panel = QWidget()
        self.welcome_panel.setObjectName("welcomePanel")
        wl = QVBoxLayout(self.welcome_panel)
        wl.setContentsMargins(32, 56, 32, 24)
        wl.setSpacing(6)

        wlc_logo = QLabel()
        wlc_logo.setPixmap(_make_avatar_pixmap("A", self._ACCENT, "#ffffff", 52))
        wlc_logo.setFixedSize(52, 52)
        wl.addWidget(wlc_logo, 0, Qt.AlignmentFlag.AlignHCenter)
        wl.addSpacing(4)

        wlc_title = QLabel("Built to think.")
        wlc_title.setObjectName("welcomeTitle")
        wlc_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wl.addWidget(wlc_title)

        wlc_sub = QLabel("Designed to assist.")
        wlc_sub.setObjectName("welcomeSubtitle")
        wlc_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wl.addWidget(wlc_sub)

        wl.addSpacing(28)

        # Suggestion chips
        chips_lbl = QLabel("Try asking:")
        chips_lbl.setObjectName("chipsLabel")
        wl.addWidget(chips_lbl)

        chips_row = QHBoxLayout()
        chips_row.setSpacing(10)
        suggestions = [
            ("Generate Plan", "Generate a plan for my week"),
            ("Summarize Text", "Summarize the following text:"),
            ("Explain Concept", "Explain what machine learning is"),
            ("Open Application", "Open Notepad"),
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

        # Status bar
        self.status_label = QLabel("Ready  ·  Type a message to get started")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setContentsMargins(24, 4, 24, 4)
        content_layout.addWidget(self.status_label)

        # Composer
        composer_outer = QWidget()
        composer_outer.setObjectName("composerOuter")
        col = QHBoxLayout(composer_outer)
        col.setContentsMargins(20, 10, 20, 16)

        composer_frame = QFrame()
        composer_frame.setObjectName("composerFrame")
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setOffset(0, -3)
        shadow.setColor(QColor(0, 0, 0, 15))
        composer_frame.setGraphicsEffect(shadow)

        cmp = QHBoxLayout(composer_frame)
        cmp.setContentsMargins(14, 8, 8, 8)
        cmp.setSpacing(8)

        self.input = QLineEdit()
        self.input.setObjectName("messageInput")
        self.input.setPlaceholderText("Message Astra…")
        self.input.setClearButtonEnabled(True)
        self.input.returnPressed.connect(self._submit_from_input)
        cmp.addWidget(self.input, 1)

        self.microphone_button = QPushButton("Voice")
        self.microphone_button.setObjectName("iconButton")
        self.microphone_button.setFixedSize(56, 38)
        if _VOICE_AVAILABLE:
            self.microphone_button.setToolTip("Click to speak (voice input)")
            self.microphone_button.clicked.connect(self._start_voice_input)
        else:
            self.microphone_button.setToolTip(
                "Voice input unavailable — install SpeechRecognition and PyAudio"
            )
            self.microphone_button.setEnabled(False)
            self.microphone_button.clicked.connect(self.microphone_requested)
        cmp.addWidget(self.microphone_button)

        self.send_button = QPushButton("Send")
        self.send_button.setObjectName("sendButton")
        self.send_button.setFixedHeight(38)
        self.send_button.clicked.connect(self._submit_from_input)
        cmp.addWidget(self.send_button)

        col.addWidget(composer_frame)
        content_layout.addWidget(composer_outer)

        root.addWidget(content, 1)

        self._apply_settings()
        self._current_session = self._new_session("New conversation")
        self._add_message("assistant", "Hello! I'm Astra — how can I help you today?")
        if self._settings_load_error:
            self.status_label.setText("Settings could not be loaded; defaults are in use")

    # ── Stylesheet ────────────────────────────────────────────────────────────

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            /* ── Base ─────────────────────────────────────────── */
            QWidget {
                font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Arial, sans-serif;
                font-size: 13px;
            }
            QWidget#centralWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #f1f5f9, stop:0.4 #e8eef6, stop:1 #e2e8f0);
            }

            /* ── Sidebar - Frosted Glass ─────────────────────── */
            QWidget#sidebar {
                background: rgba(248, 250, 253, 0.78);
                border-right: 1px solid rgba(226, 232, 240, 0.75);
            }
            QLabel#sidebarBrand {
                color: #0f172a;
                font-size: 17px;
                font-weight: 700;
                letter-spacing: -0.3px;
            }
            QLabel#sidebarSection {
                color: #64748b;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 1.2px;
                padding: 6px 6px 2px 6px;
                text-transform: uppercase;
            }
            QListWidget#chatHistory {
                background: transparent;
                border: none;
                outline: none;
                color: #334155;
                font-size: 12px;
            }
            QListWidget#chatHistory::item {
                padding: 7px 10px;
                border-radius: 8px;
                margin: 2px 0;
            }
            QListWidget#chatHistory::item:hover {
                background: rgba(226, 232, 240, 0.6);
                color: #0f172a;
            }
            QListWidget#chatHistory::item:selected {
                background: rgba(219, 234, 254, 0.85);
                color: #1d4ed8;
                font-weight: 600;
            }
            QLineEdit#chatSearch {
                background: rgba(255, 255, 255, 0.8);
                border: 1px solid rgba(203, 213, 225, 0.7);
                border-radius: 8px;
                padding: 6px 10px;
                color: #0f172a;
                font-size: 12px;
            }
            QLineEdit#chatSearch:focus {
                border-color: #3b82f6;
                background: #ffffff;
            }
            QLabel#accountLabel {
                color: #475569;
                font-size: 11px;
                font-weight: 600;
                padding: 10px 6px;
                border-top: 1px solid rgba(226, 232, 240, 0.6);
            }
            QPushButton#sidebarButton {
                background: transparent;
                border: none;
                color: #334155;
                text-align: left;
                padding: 8px 10px;
                font-size: 12px;
                font-weight: 500;
                border-radius: 8px;
            }
            QPushButton#sidebarButton:hover {
                background: rgba(226, 232, 240, 0.6);
                color: #0f172a;
            }
            QPushButton#sidebarIcon {
                background: transparent;
                border: none;
                color: #64748b;
                font-size: 12px;
                font-weight: 700;
                border-radius: 6px;
            }
            QPushButton#sidebarIcon:hover {
                background: rgba(226, 232, 240, 0.6);
                color: #0f172a;
            }
            QPushButton#newChatButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #3b82f6, stop:1 #2563eb);
                border: none;
                border-radius: 9px;
                color: #ffffff;
                text-align: left;
                padding: 9px 12px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton#newChatButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #2563eb, stop:1 #1d4ed8);
            }

            /* ── Content Panel - Elevated Glass Card ──────────── */
            QWidget#contentPanel {
                background: rgba(255, 255, 255, 0.85);
                border: 1px solid rgba(255, 255, 255, 0.95);
                border-radius: 16px;
                margin: 8px 10px 8px 0;
            }

            /* ── Header ───────────────────────────────────────── */
            QWidget#headerBar {
                background: rgba(255, 255, 255, 0.6);
                border-bottom: 1px solid rgba(226, 232, 240, 0.6);
                border-top-left-radius: 16px;
                border-top-right-radius: 16px;
            }
            QFrame#headerSep {
                background: transparent;
                border: none;
            }
            QLabel#headerChatTitle {
                color: #0f172a;
                font-size: 14px;
                font-weight: 600;
            }

            /* ── Status Pills ─────────────────────────────────── */
            QLabel#pillReady {
                background: rgba(220, 252, 231, 0.8);
                color: #15803d;
                border: 1px solid rgba(187, 247, 208, 0.8);
                border-radius: 14px;
                padding: 0;
                font-size: 11px;
                font-weight: 600;
            }
            QLabel#pillThinking {
                background: rgba(254, 243, 199, 0.85);
                color: #b45309;
                border: 1px solid rgba(253, 230, 138, 0.8);
                border-radius: 14px;
                padding: 0;
                font-size: 11px;
                font-weight: 600;
            }
            QLabel#pillListening {
                background: rgba(219, 234, 254, 0.85);
                color: #1d4ed8;
                border: 1px solid rgba(191, 219, 254, 0.8);
                border-radius: 14px;
                padding: 0;
                font-size: 11px;
                font-weight: 600;
            }

            /* ── Welcome Panel ────────────────────────────────── */
            QWidget#chatWrapper { background: transparent; }
            QWidget#welcomePanel { background: transparent; }
            QLabel#welcomeTitle {
                color: #0f172a;
                font-size: 34px;
                font-weight: 600;
                letter-spacing: -0.5px;
            }
            QLabel#welcomeSubtitle {
                color: #94a3b8;
                font-size: 28px;
                font-weight: 300;
            }
            QLabel#chipsLabel {
                color: #64748b;
                font-size: 11px;
                font-weight: 600;
                letter-spacing: 0.8px;
                text-transform: uppercase;
            }
            QPushButton#suggestionButton {
                background: rgba(255, 255, 255, 0.75);
                border: 1px solid rgba(203, 213, 225, 0.7);
                border-radius: 20px;
                color: #334155;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: 500;
                text-align: center;
            }
            QPushButton#suggestionButton:hover {
                background: rgba(239, 246, 255, 0.95);
                border-color: #3b82f6;
                color: #1d4ed8;
            }

            /* ── Conversation List ────────────────────────────── */
            QListWidget#conversationList {
                background: transparent;
                border: none;
                padding: 14px 18px;
            }
            QListWidget#conversationList::item {
                background: transparent;
                border: none;
                padding: 0;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 6px;
                border-radius: 3px;
                margin: 4px 2px;
            }
            QScrollBar::handle:vertical {
                background: rgba(148, 163, 184, 0.4);
                border-radius: 3px;
                min-height: 28px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(100, 116, 139, 0.6);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }

            /* ── Message Bubbles ──────────────────────────────── */
            QFrame#astraBubble {
                background: rgba(248, 250, 252, 0.9);
                border: 1px solid rgba(226, 232, 240, 0.85);
                border-radius: 16px;
                border-top-left-radius: 4px;
            }
            QFrame#userBubble {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1e293b, stop:1 #0f172a);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 16px;
                border-top-right-radius: 4px;
            }
            QFrame#errorBubble {
                background: rgba(254, 242, 242, 0.9);
                border: 1px solid rgba(254, 202, 202, 0.85);
                border-radius: 16px;
            }
            QLabel#bubbleSender {
                color: #64748b;
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 0.8px;
            }
            QLabel#bubbleTimestamp {
                color: #94a3b8;
                font-size: 10px;
            }
            QLabel#bubbleText {
                color: #0f172a;
                font-size: 13px;
                line-height: 1.55;
            }
            QLabel#bubbleTextUser {
                color: #f8fafc;
                font-size: 13px;
                line-height: 1.55;
            }

            /* ── Status Bar ───────────────────────────────────── */
            QLabel#statusLabel {
                color: #64748b;
                font-size: 11px;
                background: transparent;
                padding: 4px 24px;
            }

            /* ── Composer ─────────────────────────────────────── */
            QWidget#composerOuter { background: transparent; }
            QFrame#composerFrame {
                background: rgba(255, 255, 255, 0.92);
                border: 1.5px solid rgba(203, 213, 225, 0.7);
                border-radius: 16px;
            }
            QFrame#composerFrame:focus-within {
                border: 1.5px solid #3b82f6;
                background: #ffffff;
            }
            QLineEdit#messageInput {
                background: transparent;
                border: none;
                padding: 8px 10px;
                color: #0f172a;
                font-size: 13px;
            }

            /* ── Buttons ──────────────────────────────────────── */
            QPushButton#sendButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #3b82f6, stop:1 #2563eb);
                color: #ffffff;
                border: none;
                padding: 0 18px;
                min-height: 36px;
                min-width: 72px;
                border-radius: 8px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton#sendButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #2563eb, stop:1 #1d4ed8);
            }
            QPushButton#sendButton:disabled {
                background: #cbd5e1;
                color: #64748b;
            }
            QPushButton#iconButton {
                background: rgba(241, 245, 249, 0.8);
                border: 1px solid rgba(203, 213, 225, 0.8);
                color: #334155;
                font-size: 12px;
                font-weight: 600;
                border-radius: 8px;
                padding: 0 12px;
            }
            QPushButton#iconButton:hover {
                background: rgba(239, 246, 255, 0.95);
                border-color: #3b82f6;
                color: #1d4ed8;
            }
            QPushButton#iconButtonActive {
                background: #fee2e2;
                border: 1.5px solid #ef4444;
                color: #ef4444;
                font-size: 12px;
                font-weight: 600;
                border-radius: 8px;
                padding: 0 12px;
            }
            QPushButton#ghostButton {
                background: transparent;
                border: 1px solid rgba(203, 213, 225, 0.7);
                border-radius: 8px;
                color: #334155;
                font-size: 12px;
                font-weight: 500;
                padding: 6px 12px;
            }
            QPushButton#ghostButton:hover {
                background: rgba(241, 245, 249, 0.8);
                color: #0f172a;
            }
            QPushButton:disabled { opacity: 0.45; }
            """
        )

    # ── Session management ────────────────────────────────────────────────────

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
        # Highlight the active session
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
            return  # Don't interrupt an ongoing request
        self._current_session = self._new_session("New conversation")
        self.conversation.clear()
        self.welcome_panel.show()
        self._chat_title_lbl.setText("New conversation")
        self._add_message("assistant", "Hello! I'm Astra — how can I help you today?")
        self.status_label.setText("Ready  ·  Type a message to get started")
        self._set_thinking_state(False)

    def _restore_chat(self, item: QListWidgetItem) -> None:
        session = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(session, dict):
            return
        self._current_session = session
        self.conversation.clear()
        messages: list = session.get("messages", [])  # type: ignore[assignment]
        has_user_msg = any(s == "user" for s, _ in (messages or []))
        self.welcome_panel.setVisible(not has_user_msg)
        self._chat_title_lbl.setText(str(session.get("title", "Conversation")))
        for sender, text in (messages or []):
            self._add_message(str(sender), str(text), record=False)
        self._sync_history_selection()

    # ── Sidebar collapse ──────────────────────────────────────────────────────

    def _toggle_sidebar(self) -> None:
        self._sidebar_collapsed = not self._sidebar_collapsed
        self.sidebar.setVisible(not self._sidebar_collapsed)
        self._expand_btn.setVisible(self._sidebar_collapsed)

    # ── Settings ──────────────────────────────────────────────────────────────

    def _show_settings(self) -> None:
        dialog = _SettingsDialog(self._settings, self._settings_store, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._apply_settings()

    def _apply_settings(self) -> None:
        """Apply active preferences to the running application."""
        # Spacing
        self.conversation.setSpacing(3 if self._settings.compact_messages else 6)
        # Theme
        if self._settings.theme == "Dark":
            self._apply_dark_style()
        else:
            self._apply_style()
        # Update TTS synthesizer settings
        if self._tts_synthesizer:
            self._tts_synthesizer.voice_name = self._settings.speaker
            self._tts_synthesizer.speed_wpm = self._settings.speech_speed
        # Update assistant settings if supported
        if hasattr(self._assistant, "update_settings"):
            self._assistant.update_settings(self._settings)

    def _apply_dark_style(self) -> None:
        """Dark theme stylesheet."""
        self.setStyleSheet(
            """
            QWidget {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
            }
            QWidget#centralWidget {
                background: #0f172a;
            }
            QWidget#sidebar {
                background: #1e293b;
                border-right: 1px solid #334155;
            }
            QLabel#sidebarBrand {
                color: #f8fafc;
                font-size: 16px;
                font-weight: 700;
            }
            QLabel#sidebarSection {
                color: #94a3b8;
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 1.5px;
                padding: 3px 4px 1px 4px;
            }
            QListWidget#chatHistory {
                background: transparent;
                border: none;
                outline: none;
                color: #cbd5e1;
                font-size: 12px;
            }
            QListWidget#chatHistory::item {
                padding: 6px 8px;
                border-radius: 7px;
                margin: 1px 0;
            }
            QListWidget#chatHistory::item:hover {
                background: #334155;
                color: #f8fafc;
            }
            QListWidget#chatHistory::item:selected {
                background: #2563eb;
                color: #ffffff;
            }
            QLineEdit#chatSearch {
                background: #0f172a;
                border: 1.5px solid #334155;
                border-radius: 7px;
                padding: 6px 10px;
                color: #f8fafc;
                font-size: 12px;
            }
            QLineEdit#chatSearch:focus {
                border-color: #3b82f6;
            }
            QLabel#accountLabel {
                color: #60a5fa;
                font-size: 11px;
                font-weight: 600;
                padding: 10px 4px 2px 4px;
                border-top: 1px solid #334155;
            }
            QPushButton#sidebarButton {
                background: transparent;
                border: none;
                color: #cbd5e1;
                text-align: left;
                padding: 8px 6px;
                font-size: 12px;
                border-radius: 7px;
            }
            QPushButton#sidebarButton:hover {
                background: #334155;
                color: #f8fafc;
            }
            QPushButton#sidebarIcon {
                background: transparent;
                border: none;
                color: #94a3b8;
                font-size: 14px;
                border-radius: 5px;
            }
            QPushButton#sidebarIcon:hover {
                background: #334155;
                color: #f8fafc;
            }
            QPushButton#newChatButton {
                background: #2563eb;
                border: none;
                border-radius: 8px;
                color: #ffffff;
                text-align: left;
                padding: 9px 10px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton#newChatButton:hover {
                background: #1d4ed8;
            }
            QWidget#contentPanel {
                background: #1e293b;
                border: 1px solid #334155;
                border-radius: 14px;
                margin: 8px 8px 8px 0;
            }
            QWidget#headerBar {
                background: #1e293b;
                border-top-left-radius: 14px;
                border-top-right-radius: 14px;
            }
            QFrame#headerSep {
                background: #334155;
                border: none;
            }
            QLabel#headerChatTitle {
                color: #f8fafc;
                font-size: 14px;
                font-weight: 600;
            }
            QLabel#pillReady {
                background: #064e3b;
                color: #6ee7b7;
                border: 1px solid #047857;
                border-radius: 12px;
                padding: 0;
                font-size: 11px;
                font-weight: 600;
            }
            QLabel#pillThinking {
                background: #7c2d12;
                color: #fdba74;
                border: 1px solid #9a3412;
                border-radius: 12px;
                padding: 0;
                font-size: 11px;
                font-weight: 600;
            }
            QLabel#pillListening {
                background: #1e3a8a;
                color: #93c5fd;
                border: 1px solid #2563eb;
                border-radius: 12px;
                padding: 0;
                font-size: 11px;
                font-weight: 600;
            }
            QWidget#chatWrapper { background: #1e293b; }
            QWidget#welcomePanel { background: #1e293b; }
            QLabel#welcomeTitle {
                color: #f8fafc;
                font-size: 36px;
                font-weight: 400;
            }
            QLabel#welcomeSubtitle {
                color: #64748b;
                font-size: 36px;
                font-weight: 400;
            }
            QLabel#chipsLabel {
                color: #94a3b8;
                font-size: 11px;
                font-weight: 600;
                letter-spacing: 0.5px;
            }
            QPushButton#suggestionButton {
                background: #0f172a;
                border: 1.5px solid #334155;
                border-radius: 9px;
                color: #cbd5e1;
                padding: 8px 12px;
                font-size: 12px;
                font-weight: 500;
                text-align: left;
            }
            QPushButton#suggestionButton:hover {
                background: #1e3a8a;
                border-color: #3b82f6;
                color: #ffffff;
            }
            QListWidget#conversationList {
                background: #1e293b;
                border: none;
                padding: 14px 16px;
            }
            QListWidget#conversationList::item {
                background: transparent;
                border: none;
                color: transparent;
                padding: 0;
            }
            QScrollBar:vertical {
                background: #0f172a;
                width: 6px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #475569;
                border-radius: 3px;
                min-height: 24px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
            QFrame#astraBubble {
                background: #0f172a;
                border: 1px solid #334155;
                border-radius: 14px;
                border-top-left-radius: 4px;
            }
            QFrame#userBubble {
                background: #2563eb;
                border: 1px solid #1d4ed8;
                border-radius: 14px;
                border-top-right-radius: 4px;
            }
            QFrame#errorBubble {
                background: #450a0a;
                border: 1px solid #7f1d1d;
                border-radius: 14px;
            }
            QLabel#bubbleSender {
                color: #94a3b8;
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 1px;
            }
            QLabel#bubbleTimestamp {
                color: #64748b;
                font-size: 10px;
            }
            QLabel#bubbleText {
                color: #f1f5f9;
                font-size: 13px;
                line-height: 1.55;
            }
            QLabel#bubbleTextUser {
                color: #ffffff;
                font-size: 13px;
                line-height: 1.55;
            }
            QLabel#statusLabel {
                color: #94a3b8;
                font-size: 11px;
                background: transparent;
                padding: 4px 24px;
            }
            QWidget#composerOuter { background: #1e293b; }
            QFrame#composerFrame {
                background: #0f172a;
                border: 1px solid #475569;
                border-radius: 14px;
            }
            QFrame#composerFrame:focus-within {
                border: 2px solid #60a5fa;
            }
            QLineEdit#messageInput {
                background: transparent;
                border: none;
                padding: 8px 6px;
                color: #f8fafc;
                font-size: 14px;
            }
            QPushButton#sendButton {
                background: #2563eb;
                color: #ffffff;
                border: none;
                padding: 0 20px;
                min-height: 36px;
                min-width: 90px;
            }
            QPushButton#sendButton:hover { background: #1d4ed8; }
            QPushButton#sendButton:disabled {
                background: #475569;
                color: #94a3b8;
            }
            QPushButton#iconButton {
                background: #0f172a;
                border: 1px solid #475569;
                color: #94a3b8;
                font-size: 16px;
                border-radius: 10px;
            }
            QPushButton#iconButton:hover {
                background: #1e3a8a;
                border-color: #60a5fa;
                color: #60a5fa;
            }
            QPushButton#iconButtonActive {
                background: #7f1d1d;
                border: 1.5px solid #ef4444;
                color: #fca5a5;
                font-size: 16px;
                border-radius: 10px;
            }
            QPushButton#ghostButton {
                background: transparent;
                color: #94a3b8;
                border: 1px solid #334155;
                padding: 0 14px;
                min-height: 30px;
                font-size: 12px;
            }
            QPushButton#ghostButton:hover {
                background: #334155;
                color: #f8fafc;
            }
            QPushButton:disabled { opacity: 0.45; }
            """
        )

    # ── Voice input ───────────────────────────────────────────────────────────

    def _start_voice_input(self) -> None:
        """Begin a microphone recording session on a background thread."""
        if not _VOICE_AVAILABLE:
            self._add_message(
                "error",
                "Voice input is unavailable. "
                "Install the required libraries: pip install SpeechRecognition PyAudio",
            )
            return
        # Prevent overlapping requests
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

        # Force Qt to re-evaluate objectName-based QSS rules
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
        """Handle a successfully recognised transcript.

        The text is placed in the input field and submitted automatically so the
        full flow — voice → AssistantInterface → response — happens seamlessly.
        """
        self._set_listening_state(False)
        self.input.setText(text)
        self.input.setFocus()
        # Submit immediately so the recognised phrase goes to the assistant
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
        # Force Qt to re-evaluate objectName-based QSS rules
        self.connection_label.style().unpolish(self.connection_label)
        self.connection_label.style().polish(self.connection_label)
        self.send_button.setEnabled(not thinking)
        self.input.setEnabled(not thinking)
        # Mic button is only available when voice is installed and nothing is active
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
        # Cancel any active TTS speech
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
            # Auto-title from first user message
            if sender == "user" and self._current_session.get("title") == "New conversation":
                new_title = text[:30] + ("…" if len(text) > 30 else "")
                self._current_session["title"] = new_title
                self._chat_title_lbl.setText(new_title)
                self._refresh_chat_history()

        bubble = _MessageBubble(sender, text)
        item = QListWidgetItem()
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        self.conversation.addItem(item)
        self.conversation.setItemWidget(item, bubble)

        # Size calculation
        list_w = self.conversation.viewport().width()
        bubble.setFixedWidth(max(list_w - 10, 200))
        bubble.adjustSize()
        item.setSizeHint(QSize(list_w - 10, bubble.sizeHint().height() + 6))
        self.conversation.scrollToBottom()

    # ── Resize: reflow bubble widths ──────────────────────────────────────────

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        list_w = self.conversation.viewport().width()
        for i in range(self.conversation.count()):
            item = self.conversation.item(i)
            widget = self.conversation.itemWidget(item)
            if widget:
                widget.setFixedWidth(max(list_w - 10, 200))
                widget.adjustSize()
                item.setSizeHint(QSize(list_w - 10, widget.sizeHint().height() + 6))

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
