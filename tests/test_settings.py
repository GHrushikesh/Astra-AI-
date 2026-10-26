"""Tests for Astra's persistent settings service."""

import json
import tempfile
import unittest
from pathlib import Path

from ui.settings import AstraSettings, SettingsStore


class TestSettingsStore(unittest.TestCase):
    def test_missing_file_returns_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = SettingsStore(Path(directory) / "settings.json").load()
        self.assertEqual(settings, AstraSettings())

    def test_settings_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SettingsStore(Path(directory) / "settings.json")
            expected = AstraSettings(
                microphone="USB microphone",
                speaker="Headphones",
                speech_speed=190,
                notifications_enabled=False,
                theme="Dark",
                start_with_windows=True,
                compact_messages=True,
            )
            store.save(expected)
            self.assertEqual(store.load(), expected)

    def test_invalid_settings_are_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text(json.dumps({"speech_speed": 20}), encoding="utf-8")
            with self.assertRaises(ValueError):
                SettingsStore(path).load()


if __name__ == "__main__":
    unittest.main()
