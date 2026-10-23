"""Centralized structured logger and logging configuration for Astra."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Optional


def get_logger(name: str = "astra") -> logging.Logger:
    """Return a logger configured with standard Astra formatting."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # Console handler
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(formatter)
        logger.addHandler(console)

        # File handler in %LOCALAPPDATA%/Astra/logs
        try:
            app_data = os.environ.get("LOCALAPPDATA")
            base = Path(app_data) if app_data else Path.home() / ".config"
            log_dir = base / "Astra" / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / "astra.log"

            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception:
            pass

    return logger
