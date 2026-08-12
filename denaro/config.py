#!/usr/bin/env python3
"""Denaro v6 — configuration.

Every runtime knob is env-driven with a safe default. `DenaroConfig.from_env()`
reads OS environment (already loaded from .env by the launcher) and validates
ranges so a misconfigured deployment fails fast instead of drifting.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


def _f(name: str, default: float) -> float:
    return float(os.environ.get(name, default))


def _i(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


def _s(name: str, default: str) -> str:
    return os.environ.get(name, default)


@dataclass
class DenaroConfig:
    # --- market / mode -------------------------------------------------------
    symbol: str = "DOGE/EUR"
    capital: float = 100.0
    shadow_mode: bool = True
    shadow_factor: float = 0.10
    mock_mode: bool = False

    # --- cycle ---------------------------------------------------------------
    cooldown: int = 30
    ohlcv_interval: int = 300          # sec between OHLCV/regime refreshes
    deep_sleep_cycles: int = 5
    lockout_retry_interval: float = 60.0
    state_save_interval: float = 30.0
    watchdog_cycle_s: float = 120.0    # cycle longer than this → watchdog trip

    # --- grid ----------------------------------------------------------------
    max_deployed: float = 0.50
    min_order_eur: float = 1.0
    grid_tp_floor: float = 0.008
    grid_tp_cap: float = 0.050

    # --- risk ----------------------------------------------------------------
    daily_loss_pct: float = 0.05
    max_drawdown_pct: float = 0.15
    max_consecutive_losses: int = 4
    compound_ratio: float = 0.5
    kelly_cap: float = 0.50

    # --- dump defense --------------------------------------------------------
    dump_threshold_mult: float = 2.5
    dump_volume_ratio: float = 1.8
    dump_recovery_cycles: int = 3

    # --- rebalancing ---------------------------------------------------------
    rebalance_interval: int = 10
    rebalance_tolerance: float = 0.05
    rebalance_max_pct: float = 0.25

    # --- paths / infra -------------------------------------------------------
    log_file: Path = field(default_factory=lambda: Path("kraken_bot.log"))
    core_state_file: Path = field(default_factory=lambda: Path("denaro_core_state.json"))
    health_port: int = 8909

    # --- exchange cache (passthrough) ----------------------------------------
    balance_cache_ttl: float = 15.0
    orders_cache_ttl: float = 10.0

    @classmethod
    def from_env(cls) -> "DenaroConfig":
        return cls(
            symbol=_s("SYMBOL", "DOGE/EUR"),
            capital=_f("CAPITAL", 100.0),
            shadow_mode=_s("SHADOW_MODE", "1") == "1",
            shadow_factor=_f("SHADOW_FACTOR", 0.10),
            mock_mode=_s("MOCK_MODE", "0") == "1",
            cooldown=_i("COOLDOWN", 30),
            ohlcv_interval=_i("OHLCV_INTERVAL", 300),
            deep_sleep_cycles=_i("DEEP_SLEEP_CYCLES", 5),
            lockout_retry_interval=_f("LOCKOUT_RETRY_INTERVAL", 60.0),
            state_save_interval=_f("STATE_SAVE_INTERVAL", 30.0),
            watchdog_cycle_s=_f("WATCHDOG_CYCLE_S", 120.0),
            max_deployed=_f("MAX_DEPLOYED", 0.50),
            min_order_eur=_f("MIN_ORDER_EUR", 1.0),
            grid_tp_floor=_f("GRID_TP_FLOOR", 0.008),
            grid_tp_cap=_f("GRID_TP_CAP", 0.050),
            daily_loss_pct=_f("MAX_DAILY_LOSS_PCT", 5.0) / 100.0,
            max_drawdown_pct=_f("MAX_DRAWDOWN_PCT", 15.0) / 100.0,
            max_consecutive_losses=_i("MAX_CONSECUTIVE_LOSSES", 4),
            compound_ratio=_f("COMPOUND_RATIO", 0.5),
            kelly_cap=_f("KELLY_CAP", 0.50),
            dump_threshold_mult=_f("DUMP_THRESHOLD_MULT", 2.5),
            dump_volume_ratio=_f("DUMP_VOLUME_RATIO", 1.8),
            dump_recovery_cycles=_i("DUMP_RECOVERY_CYCLES", 3),
            rebalance_interval=_i("REBALANCE_INTERVAL", 10),
            rebalance_tolerance=_f("REBALANCE_TOLERANCE", 0.05),
            rebalance_max_pct=_f("REBALANCE_MAX_PCT", 0.25),
            log_file=Path(_s("LOG_FILE", "kraken_bot.log")),
            core_state_file=Path(_s("CORE_STATE_FILE", "denaro_core_state.json")),
            health_port=_i("HEALTH_PORT", 8909),
            balance_cache_ttl=_f("BALANCE_CACHE_TTL", 15.0),
            orders_cache_ttl=_f("ORDERS_CACHE_TTL", 10.0),
        )

    def validate(self) -> List[str]:
        """Return a list of config warnings (non-fatal but worth logging)."""
        w: List[str] = []
        if self.capital <= 0:
            raise ValueError(f"CAPITAL={self.capital} must be > 0")
        if self.max_deployed <= 0 or self.max_deployed > 1.0:
            w.append(f"MAX_DEPLOYED={self.max_deployed} outside (0,1]")
        if self.min_order_eur <= 0:
            w.append(f"MIN_ORDER_EUR={self.min_order_eur} must be > 0")
        if not (0.001 <= self.daily_loss_pct <= 0.30):
            w.append(f"MAX_DAILY_LOSS_PCT={self.daily_loss_pct} outside [0.1%,30%]")
        if not (0.01 <= self.max_drawdown_pct <= 0.90):
            w.append(f"MAX_DRAWDOWN_PCT={self.max_drawdown_pct} outside [1%,90%]")
        if self.cooldown < 5 or self.cooldown > 600:
            w.append(f"COOLDOWN={self.cooldown}s outside [5,600]")
        if not (0.01 <= self.shadow_factor <= 1.0):
            w.append(f"SHADOW_FACTOR={self.shadow_factor} outside [0.01,1]")
        if self.watchdog_cycle_s < 10:
            w.append(f"WATCHDOG_CYCLE_S={self.watchdog_cycle_s} too small (<10s)")
        return w
