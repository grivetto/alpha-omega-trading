"""ATLAS Observability - Logging configuration."""
from __future__ import annotations

import logging
import sys


def configure_logging(json_output: bool = True, level: str = "INFO") -> None:
    """Configure root logging for ATLAS."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s"
    ))
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.addHandler(handler)
