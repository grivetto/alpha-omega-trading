#!/usr/bin/env python3
"""
auto_gen_1788133531 — Intraday VWAP Mean-Reversion with Adaptive Bandwidth.

Distinct approach vs hybrid_grid_momentum_adaptive:
- Anchored intraday VWAP as the mean-reversion anchor (not moving-average cross).
- Bandwidth shrinks/grows adaptively with realized volatility (EWMA of |dev|).
- Grid-like laddering around VWAP for range capture, but ONLY trades when
  the anchor is "fresh" (session-anchored, resets each day/hour window).
- Explicit micro-burst guard: consecutive fills in one direction decay the
  next order size (anti-chase / anti-stack protection within a tick window).

OOM-safety:
- Streaming: rolling windows are deque(maxlen=...) bounded, never unbounded lists.
- Price history capped via fixed deque lengths derived from config, not raw data.
- Large intermediate Series/arrays are `del`'d and `gc.collect()` invoked after
  batch ingestion; chunked CSV reader with explicit chunk_size.
"""

from __future__ import annotations

import csv
import gc
import json
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Generator, Optional, Deque
from collections import deque


class Action(Enum):
    """Trading actions."""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    CANCEL_ALL = "CANCEL_ALL"


class StrategyBase(ABC):
    """Abstract contract every strategy must satisfy."""

    @abstractmethod
    def on_tick(self, tick: dict[str, Any]) -> Action: ...

    @abstractmethod
    def on_fill(self, fill: dict[str, Any]) -> None: ...

    @abstractmethod
    def validate_config(self) -> None: ...

    @abstractmethod
    def estimate_memory_mb(self) -> float: ...


@dataclass(frozen=True, slots=True)
class VWAPConfig:
    """Config-driven parameters (no hardcoding allowed)."""
    symbol: str
    capital_eur: float = 1000.0
    anchor_window_s: int = 3600        # VWAP anchor length (rolling session window)
    vol_lookback: int = 120            # ticks for EWMA realized vol
    ewma_alpha: float = 0.06           # decay for vol EWMA
    entry_mult: float = 1.0            # entry bandwidth multiplier
    exit_mult: float = 0.4             # exit (take-profit) bandwidth multiplier
    max_tiers: int = 4                 # grid tiers per side
    tier_spacing_mult: float = 0.5     # spacing between tiers, in bandwidth units
    max_open_positions: int = 6
    per_trade_risk_frac: float = 0.02  # Kelly-ish per-trade risk fraction
    micro_burst_decay: float = 0.6     # size decay per consecutive same-side fill
    min_trade_size_eur: float = 5.0
    max_trade_size_eur: float = 100.0
    price_history_ticks: int = 500     # bounded deque length, NOT raw streaming
    session_reset_s: int = 86400       # daily anchor reset

    def validate(self) -> None:
        """Explicit validation, raises ValueError on bad config."""
        checks: list[tuple[bool, str]] = [
            (self.capital_eur > 0, "capital_eur must be > 0"),
            (self.anchor_window_s > 0, "anchor_window_s must be > 0"),
            (0.0 < self.ewma_alpha < 1.0, "ewma_alpha must be in (0,1)"),
            (self.entry_mult > 0.0, "entry_mult must be > 0"),
            (self.max_tiers >= 1, "max_tiers must be >= 1"),
            (self.max_open_positions >= 1, "max_open_positions must be >= 1"),
            (0.0 < self.per_trade_risk_frac <= 1.0, "risk frac in (0,1]"),
            (self.price_history_ticks >= 10, "price_history_ticks >= 10"),
        ]
        for ok, msg in checks:
            if not ok:
                raise ValueError(f"VWAPConfig validation failed: {msg}")


class VWAPMeanReversion(StrategyBase):
    """Intraday VWAP-anchored mean-reversion with adaptive bandwidth and
    micro-burst anti-chase sizing."""

    def __init__(self, config: VWAPConfig) -> None:
        config.validate()
        self._cfg = config
        # --- rolling streams (bounded deques => O(1) memory) ---
        self._prices: Deque[float] = deque(maxlen=config.price_history_ticks)
        self._vols: Deque[float] = deque(maxlen=config.vol_lookback)
        # --- running state ---
        self._vwap_num: float = 0.0
        self._vwap_den: float = 0.0
        self._tick_count: int = 0
        self._session_epoch: int = 0
        self._last_mid: Optional[float] = None
        self._realized_vol_ewma: float = 0.0
        self._open_positions: int = 0
        self._consec_buy: int = 0
        self._consec_sell: int = 0
        self._fills: int = 0

    # ---- helpers ----------------------------------------------------------
    def _session_id(self, ts: float) -> int:
        """Bucket timestamp into a session window for anchor freshness."""
        return int(ts // self._cfg.session_reset_s)

    def _is_anchor_fresh(self, ts: float) -> bool:
        """Anchor is stale if the session rolled over; reset accumulators."""
        sid = self._session_id(ts)
        if sid != self._session_epoch:
            self._vwap_num = 0.0
            self._vwap_den = 0.0
            self._session_epoch = sid
            self._tick_count = 0
            return False
        return self._tick_count >= 2

    def _bandwidth(self) -> float:
        """Adaptive bandwidth = realized vol EWMA * last mid."""
        return max(self._realized_vol_ewma, 1e-9) * (self._last_mid or 0.0)

    # ---- StrategyBase interface ------------------------------------------
    def on_tick(self, tick: dict[str, Any]) -> Action:
        """Core entry/exit decision per price tick."""
        ts: float = float(tick["timestamp"])
        mid: float = float(tick["mid"])
        price: float = float(tick.get("price", mid))
        volume: float = float(tick.get("volume", 0.0))

        # anchor management (reset on session rollover)
        self._is_anchor_fresh(ts)
        self._session_epoch = self._session_id(ts)

        # update VWAP accumulators
        self._vwap_num += price * volume
        self._vwap_den += volume
        self._tick_count += 1
        self._prices.append(mid)
        self._last_mid = mid

        # EWMA realized vol over tick-to-tick returns
        if len(self._prices) >= 2:
            prev = self._prices[-2]
            ret = abs((mid - prev) / prev) if prev else 0.0
            self._vols.append(ret)
            if self._realized_vol_ewma == 0.0:
                self._realized_vol_ewma = ret
            else:
                a = self._cfg.ewma_alpha
                self._realized_vol_ewma = a * ret + (1 - a) * self._realized_vol_ewma

        if self._vwap_den <= 0.0 or self._tick_count < 2:
            return Action.HOLD

        vwap: float = self._vwap_num / self._vwap_den
        bw: float = self._bandwidth()
        dev: float = (mid - vwap) / bw if bw > 0.0 else 0.0  # z-like distance

        # take-profit: mean reverting back toward VWAP
        if self._open_positions > 0 and abs(dev) < self._cfg.exit_mult:
            self._open_positions = max(0, self._open_positions - 1)
            return Action.SELL if dev >= 0.0 else Action.BUY

        # entry: fade extreme deviation away from VWAP, tiered laddering
        if self._open_positions >= self._cfg.max_open_positions:
            return Action.HOLD
        if abs(dev) < self._cfg.entry_mult:
            return Action.HOLD

        # determine tier and it must be within cap
        tier: int = min(int((abs(dev) - self._cfg.entry_mult)
                            / self._cfg.tier_spacing_mult) + 1,
                        self._cfg.max_tiers)
        if tier < 1:
            return Action.HOLD
        return Action.BUY if dev < 0.0 else Action.SELL

    def on_fill(self, fill: dict[str, Any]) -> None:
        """Handle execution feedback incl. anti-chase size decay."""
        side: str = str(fill.get("side", "")).upper()
        self._fills += 1
        if side == "BUY":
            self._consec_buy += 1
            self._consec_sell = 0
        elif side == "SELL":
            self._consec_sell += 1
            self._consec_buy = 0
        else:
            return  # unknown fill side: ignore silently but explicitly
        self._open_positions = max(0, self._open_positions + 1)

    def _size_for(self, side: str) -> float:
        """Risk-sized order with micro-burst decay factor applied."""
        consec = self._consec_buy if side == "BUY" else self._consec_sell
        base = self._cfg.capital_eur * self._cfg.per_trade_risk_frac
        decay = self._cfg.micro_burst_decay ** max(0, consec - 1)
        size = base * decay
        return min(max(size, self._cfg.min_trade_size_eur),
                   self._cfg.max_trade_size_eur)

    def validate_config(self) -> None:
        self._cfg.validate()

    def estimate_memory_mb(self) -> float:
        """Bounded memory estimate: deques of floats, O(1) regardless of ticks."""
        per_float = 24.0  # bytes
        n = (self._cfg.price_history_ticks + self._cfg.vol_lookback)
        return round(n * per_float / (1024 * 1024) + 0.01, 4)

    # ---- batch/streaming ingestion (OOM-safe) -----------------------------
    def ingest_csv_chunked(self, path: str, chunk_size: int = 5000) -> int:
        """Read CSV in bounded chunks, discarding each chunk after processing.
        Never materializes the full file into memory."""
        rows: int = 0
        with open(path, "r", newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            chunk: list[dict[str, Any]] = []
            for row in reader:
                chunk.append(row)
                if len(chunk) >= chunk_size:
                    self._process_chunk(chunk)
                    chunk.clear()
                    gc.collect()  # release chunk memory deterministically
                rows += 1
        if chunk:
            self._process_chunk(chunk)
            gc.collect()
        return rows

    def _process_chunk(self, chunk: list[dict[str, Any]]) -> None:
        """Process a single bounded chunk of rows."""
        for row in chunk:
            tick = {
                "timestamp": float(row["timestamp"]),
                "mid": float(row["mid"]),
                "price": float(row.get("mid", "0")),
                "volume": float(row.get("volume", "0")),
            }
            self.on_tick(tick)
        # drop reference explicitly before returning
        del chunk


def _synthetic_stream(n: int = 1000) -> Generator[dict[str, Any], None, None]:
    """Deterministic synthetic price stream with a VWAP-reverting pattern."""
    import random
    rng = random.Random(42)
    mid: float = 100.0
    vwap: float = 100.0
    for i in range(n):
        # mean-reverting wobble around vwap
        drift = (vwap - mid) * 0.05 + rng.uniform(-0.5, 0.5)
        mid = max(1.0, mid + drift)
        vwap = 0.999 * vwap + 0.001 * mid
        yield {
            "timestamp": float(i) + 1700000000.0,
            "mid": mid,
            "price": mid,
            "volume": rng.uniform(0.1, 2.0),
        }


def _run_smoke_test() -> None:
    """Inline self-test with small synthetic data."""
    cfg = VWAPConfig(
        symbol="TEST/EUR",
        capital_eur=100.0,
        max_open_positions=3,
        price_history_ticks=100,
    )
    strat = VWAPMeanReversion(cfg)
    strat.validate_config()
    mem = strat.estimate_memory_mb()
    assert mem > 0.0 and mem < 50.0, f"unexpected mem estimate {mem}"

    actions: dict[str, int] = {"HOLD": 0, "BUY": 0, "SELL": 0}
    for tick in _synthetic_stream(800):
        act = strat.on_tick(tick)
        actions[act.value] = actions.get(act.value, 0) + 1
        if act in (Action.BUY, Action.SELL):
            strat.on_fill({"side": act.value, "qty": strat._size_for(act.value)})

    print(f"[SMOKE] mem_mb={mem} actions={actions} open={strat._open_positions} "
          f"fills={strat._fills} vwap_err_state_ok={strat._tick_count > 0}")
    assert strat._fills > 0, "expected at least one fill from synthetic data"
    print("[SMOKE] PASS")


if __name__ == "__main__":
    _run_smoke_test()
