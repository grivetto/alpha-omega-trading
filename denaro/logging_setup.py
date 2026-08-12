#!/usr/bin/env python3
"""Denaro v6 — logging + health-file helpers."""
from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(log_file: Path, level: str = "INFO") -> logging.Logger:
    """Rotating file + stdout logging on the shared 'kraken_v2' logger."""
    log = logging.getLogger("kraken_v2")
    log.setLevel(os.environ.get("LOG_LEVEL", level))
    if log.handlers:
        return log
    try:
        fh = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=3)
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(fh)
    except OSError:
        pass
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(sh)
    return log


def health_write(path: str = "/tmp/denaro.health") -> None:
    try:
        import time
        Path(path).write_text(f"{time.time():.1f}\n")
    except OSError:
        pass
