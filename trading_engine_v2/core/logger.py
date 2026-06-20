"""Structured logging for the multi-agent system."""
from __future__ import annotations
import logging
import sys
from datetime import datetime
from pathlib import Path


class AgentLogger:
    """Structured logger with agent-level routing and file rotation."""

    _instances: dict[str, "AgentLogger"] = {}

    def __init__(self, name: str, log_dir: str = "logs", level: int = logging.DEBUG):
        self.name = name
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.logger = logging.getLogger(f"denaro.{name}")
        self.logger.setLevel(level)
        self.logger.handlers.clear()

        # Console handler
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(logging.INFO)
        console.setFormatter(logging.Formatter(
            "[%(asctime)s] %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))
        self.logger.addHandler(console)

        # File handler per agente
        fh = logging.FileHandler(
            self.log_dir / f"{name}_{datetime.utcnow().strftime('%Y%m%d')}.log"
        )
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))
        self.logger.addHandler(fh)

    @classmethod
    def get(cls, name: str) -> "AgentLogger":
        if name not in cls._instances:
            cls._instances[name] = cls(name)
        return cls._instances[name]

    def debug(self, msg: str, **extra):
        self._log(logging.DEBUG, msg, extra)

    def info(self, msg: str, **extra):
        self._log(logging.INFO, msg, extra)

    def warn(self, msg: str, **extra):
        self._log(logging.WARNING, msg, extra)

    def error(self, msg: str, **extra):
        self._log(logging.ERROR, msg, extra)

    def critical(self, msg: str, **extra):
        self._log(logging.CRITICAL, msg, extra)

    def _log(self, level: int, msg: str, extra: dict):
        extra_str = f" | {extra}" if extra else ""
        self.logger.log(level, f"{msg}{extra_str}")
