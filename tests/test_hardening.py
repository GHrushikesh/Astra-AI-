"""Production hardening and resilience unit tests (Phase 11)."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ui.logger import get_logger
from ui.settings import AstraSettings, SettingsStore


class TestProductionHardening(unittest.TestCase):
    def test_structured_logger(self):
        logger = get_logger("astra.test")
        self.assertIsNotNone(logger)
        logger.info("Test log entry")

    def test_missing_settings_directory_created(self):
        with TemporaryDirectory() as tmpdir:
            deep_path = Path(tmpdir) / "subdir" / "nested" / "settings.json"
            store = SettingsStore(deep_path)
            store.save(AstraSettings(theme="Dark"))
            self.assertTrue(deep_path.exists())
            loaded = store.load()
            self.assertEqual(loaded.theme, "Dark")


if __name__ == "__main__":
    unittest.main()
