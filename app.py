"""Launch the Astra desktop application."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from ai.core import AstraAICore
from ui.main_window import MainWindow
from ui.settings import SettingsStore


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Astra")
    store = SettingsStore()
    assistant = AstraAICore(settings_store=store)
    window = MainWindow(assistant=assistant, settings_store=store)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
