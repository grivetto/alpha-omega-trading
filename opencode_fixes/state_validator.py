"""StateValidator –– prevents restarting in a corrupted circuit‑breaker state.

CIRCUIT_BREAKER_JSON contains the last known state (OPEN/HALF_OPEN/CLOSED).
Restarting a bot that was previously OPEN without a manual override risks
locking the system permanently (the file stays OPEN after crash, bot starts,
sees OPEN, refuses to trade forever).

This validator:
  1. Reads circuit_breaker.json
  2. If state == OPEN → WARN and wait for operator intervention (30 min by default)
  3. If operator puts a file "circuit_breaker.override" → bypass OPEN state
  4. If no override → exits the process with exit code 42 (operational alert)

Usage in main.py, between ``app._init_exchange()`` and ``app._init_modules()``:

    from .opencode_fixes.state_validator import StateValidator
    StateValidator.check_and_wait("circuit_breaker.json", timeout_sec=1800)
"""

import os
import sys
import time

from loguru import logger


class StateValidator:
    """Pre‑start guard for circuit_breaker.json."""

    OVERRIDE_FILE = "circuit_breaker.override"

    @classmethod
    def check_and_wait(
        cls,
        state_file: str = "circuit_breaker.json",
        timeout_sec: int = 1800,
    ):
        """Check breaker state file. If OPEN, wait for override or exit.

        Params:
            state_file: path to circuit_breaker.json (default: ".")
            timeout_sec: how long to wait for override before dying
        """
        if not os.path.exists(state_file):
            logger.info(f"{state_file} not found – safe to start")
            return

        data = cls._read_json(state_file)
        if data is None:
            return

        state = data.get("state", "closed")

        if state != "open":
            logger.info(f"Circuit breaker state: {state} – safe to start")
            return

        logger.warning(
            f"CIRCUIT BREAKER IS OPEN (state={state}). "
            f"Bot will NOT trade until manually overridden."
        )

        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            if os.path.exists(cls.OVERRIDE_FILE):
                logger.info(
                    f"Override file '{cls.OVERRIDE_FILE}' detected – "
                    f"resetting state to CLOSED and starting."
                )
                cls._reset_state_file(state_file)
                try:
                    os.remove(cls.OVERRIDE_FILE)
                except OSError:
                    pass
                return
            time.sleep(5)

        logger.critical(
            f"No override detected after {timeout_sec}s. "
            f"Circuit breaker remains OPEN. Exiting."
        )
        sys.exit(42)

    @staticmethod
    def _read_json(path: str) -> dict | None:
        try:
            import json
            with open(path) as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read {path}: {e}")
            return None

    @staticmethod
    def _reset_state_file(path: str):
        try:
            import json
            data = StateValidator._read_json(path)
            if data is None:
                return
            data["state"] = "closed"
            data["reason"] = ""
            data["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
            logger.info(f"Reset {path} → CLOSED")
        except Exception as e:
            logger.error(f"Failed to reset {path}: {e}")