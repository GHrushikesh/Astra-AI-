"""Persistent, UI-independent settings for Astra."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class AstraSettings:
    """User preferences consumed by UI, voice, and notification services."""

    microphone: str = "Default microphone"
    speaker: str = "Default speaker"
    speech_speed: int = 170
    notifications_enabled: bool = True
    theme: str = "Light"
    start_with_windows: bool = False
    compact_messages: bool = False
    llm_provider: str = "Google Gemini"
    llm_api_key: str = ""
    llm_model: str = "gemini-2.5-flash-lite"
    llm_endpoint: str = ""


class SettingsStore:
    """Load and save Astra settings as a small JSON document."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or self.default_path()

    @staticmethod
    def default_path() -> Path:
        app_data = os.environ.get("LOCALAPPDATA")
        base = Path(app_data) if app_data else Path.home() / ".config"
        return base / "Astra" / "settings.json"

    def load(self) -> AstraSettings:
        if not self.path.exists():
            return AstraSettings()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Unable to read Astra settings: {exc}") from exc
        if not isinstance(raw, dict):
            raise ValueError("Astra settings must contain a JSON object.")
        return self._from_mapping(raw)

    def save(self, settings: AstraSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        try:
            temporary.write_text(
                json.dumps(asdict(settings), indent=2) + "\n",
                encoding="utf-8",
            )
            temporary.replace(self.path)
        except OSError as exc:
            raise OSError(f"Unable to save Astra settings: {exc}") from exc

    @staticmethod
    def _from_mapping(raw: dict[str, Any]) -> AstraSettings:
        defaults = AstraSettings()
        values: dict[str, Any] = {}
        for field in asdict(defaults):
            value = raw.get(field, getattr(defaults, field))
            expected_type = type(getattr(defaults, field))
            if type(value) is not expected_type:
                raise ValueError(f"Invalid Astra setting: {field}")
            values[field] = value
        if not 80 <= values["speech_speed"] <= 300:
            raise ValueError("speech_speed must be between 80 and 300.")
        if values["theme"] not in {"Light", "Dark", "System"}:
            raise ValueError("theme must be Light, Dark, or System.")
        return AstraSettings(**values)
