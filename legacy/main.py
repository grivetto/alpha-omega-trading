#!/usr/bin/env python3
"""
DENARO v6 — launcher (backward-compatible entry point).

The engine now lives in the modular `denaro` package. This file preserves the
v5 launcher surface (env constants, TradingEngine, MOCK_MODE/SHADOW_MODE
semantics) so deploy scripts and mock_runner keep working unchanged.

Run:  python main.py            (reads .env / environment)
      python -m denaro          (same engine, package entry)
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from denaro.launcher import _load_dotenv, run_main

_load_dotenv()

# ─── Env surface (v5-compatible) ─────────────────────────────────────────────
SYMBOL      = os.environ.get("SYMBOL", "DOGE/EUR")
CAPITAL     = float(os.environ.get("CAPITAL", "100.0"))
LEVELS      = int(os.environ.get("LEVELS", "5"))
BASE_SPREAD = float(os.environ.get("SPREAD", "0.025"))
TAKE_PROFIT = float(os.environ.get("TAKE_PROFIT", "0.03"))
COOLDOWN    = int(os.environ.get("COOLDOWN", "30"))
MAX_DEPLOYED = float(os.environ.get("MAX_DEPLOYED", "0.50"))
MIN_ORDER_EUR = float(os.environ.get("MIN_ORDER_EUR", "1.0"))
SHADOW_MODE = os.environ.get("SHADOW_MODE", "1") == "1"
SHADOW_FACTOR = float(os.environ.get("SHADOW_FACTOR", "0.10"))
MOCK_MODE   = os.environ.get("MOCK_MODE", "0") == "1"
LOG_FILE    = Path(os.environ.get("LOG_FILE", str(Path(__file__).parent / "kraken_bot.log")))
CORE_STATE_FILE = Path(os.environ.get("CORE_STATE_FILE", str(Path(__file__).parent / "denaro_core_state.json")))
HEALTH_PORT = int(os.environ.get("HEALTH_PORT", "8909"))
BALANCE_CACHE_TTL = float(os.environ.get("BALANCE_CACHE_TTL", "15"))
ORDERS_CACHE_TTL = float(os.environ.get("ORDERS_CACHE_TTL", "10"))
LOCKOUT_RETRY_INTERVAL = float(os.environ.get("LOCKOUT_RETRY_INTERVAL", "60"))
DEEP_SLEEP_CYCLES = int(os.environ.get("DEEP_SLEEP_CYCLES", "5"))
STATE_SAVE_INTERVAL = float(os.environ.get("STATE_SAVE_INTERVAL", "30"))


def load_env(env_path: str) -> dict:
    r = {}
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    r[k.strip()] = v.strip().strip('"').strip("'")
    return r


def health_write() -> None:
    from denaro.logging_setup import health_write as _hw
    _hw()


def mode_label() -> str:
    return "SHADOW" if SHADOW_MODE else "MOCK" if MOCK_MODE else "LIVE"


def validate_config() -> list:
    """v5-compatible config warnings (now enforced inside denaro.config too)."""
    w = []
    if CAPITAL <= 0:
        sys.exit(1)
    if LEVELS < 1 or LEVELS > 20:
        w.append(f"LEVELS={LEVELS} outside [1,20]")
    if BASE_SPREAD < 0.001 or BASE_SPREAD > 0.5:
        w.append(f"SPREAD={BASE_SPREAD} outside [0.001,0.5]")
    if COOLDOWN < 5 or COOLDOWN > 300:
        w.append(f"COOLDOWN={COOLDOWN}s outside [5,300]")
    if SHADOW_FACTOR < 0.01 or SHADOW_FACTOR > 1.0:
        w.append(f"SHADOW_FACTOR={SHADOW_FACTOR} outside [0.01,1.0]")
    return w


def _module_config():
    """Build DenaroConfig honoring THIS module's (possibly runtime-mutated)
    flags — mock_runner sets `main_mod.SHADOW_MODE = False` before running."""
    from denaro.config import DenaroConfig
    cfg = DenaroConfig.from_env()
    cfg.symbol = SYMBOL
    cfg.capital = CAPITAL
    cfg.shadow_mode = SHADOW_MODE
    cfg.shadow_factor = SHADOW_FACTOR
    cfg.mock_mode = MOCK_MODE
    cfg.cooldown = COOLDOWN
    cfg.max_deployed = MAX_DEPLOYED
    cfg.min_order_eur = MIN_ORDER_EUR
    cfg.log_file = LOG_FILE
    cfg.core_state_file = CORE_STATE_FILE
    cfg.health_port = HEALTH_PORT
    cfg.balance_cache_ttl = BALANCE_CACHE_TTL
    cfg.orders_cache_ttl = ORDERS_CACHE_TTL
    cfg.lockout_retry_interval = LOCKOUT_RETRY_INTERVAL
    cfg.deep_sleep_cycles = DEEP_SLEEP_CYCLES
    cfg.state_save_interval = STATE_SAVE_INTERVAL
    return cfg


def main() -> None:
    for w in validate_config():
        print(f"Config warning: {w}")
    raise SystemExit(run_main(_module_config()))


# ─── Back-compat engine class (used by mock_runner) ──────────────────────────

class TradingEngine:
    """v5-compatible wrapper: TradingEngine(engine, core).run() per cycle.

    Delegates to DenaroOrchestrator with this module's live flags so that
    `main_mod.SHADOW_MODE = False` and friends behave exactly as before.
    """

    def __init__(self, engine, core):
        from denaro.orchestrator import DenaroOrchestrator
        self._impl = DenaroOrchestrator(engine, core, _module_config())
        # Expose v5 surface
        self.eng = engine
        self.core = core
        self.error_count = self._impl._error_count
        self._last_ohlcv_fetch = 0.0
        self._error_count = 0
        self._consecutive_api_failures = 0

    def run(self) -> None:
        self._impl.run()
        # Keep v5 attributes in sync for health/log consumers
        self.error_count = self._impl._error_count
        self._error_count = self._impl._error_count
        self._last_ohlcv_fetch = self._impl._last_ohlcv_fetch
        self._consecutive_api_failures = self._impl._consecutive_api_failures


if __name__ == "__main__":
    main()
