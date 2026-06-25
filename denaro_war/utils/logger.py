import json
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from typing import Optional


class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "filename": record.filename
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


def setup_logging(level: str = "DEBUG", log_file: str = None, json_format: bool = True):
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, level.upper(), logging.DEBUG))

    root = logging.getLogger()
    root.handlers.clear()

    if log_file is None:
        log_file = os.environ.get("DENARO_LOG_FILE", "logs/denaro_war.log")

    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper(), logging.DEBUG))
    console_handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    ))
    root.addHandler(console_handler)

    if log_file:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10485760,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, level.upper(), logging.DEBUG))
        if json_format:
            file_handler.setFormatter(JSONFormatter())
        else:
            file_handler.setFormatter(logging.Formatter(
                "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
            ))
        root.addHandler(file_handler)

    logging.info(f"Logging initialized at level {level}")