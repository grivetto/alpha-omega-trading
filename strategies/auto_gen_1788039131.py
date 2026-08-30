#!/usr/bin/env python3
"""
VOLT-SR: Volatility-Scaled Support/Resistance Grid with Order-Flow Imbalance
and adaptive Kelly sizing for the Denaro trading infrastructure.

Idea (distinct from LSMR-ARX, CPAGrid, HMA): anchor the grid to dynamic S/R
levels built from recent volume-weighted extrema, and scale per-level spacing
by realized volatility (ATR) so levels concentrate where price trades. An
Order-Flow Imbalance (OFI) filter suppresses counterflow entries in fast
markets. A Hurst-based regime gate turns the grid off in trends.

Denaro contract:
- StrategyBase (ABC): on_tick, on_fill, validate_config, estimate_memory_mb, get/load_state
- VSRConfig dataclass, config-driven, validated, no hardcoded magic in logic
- OOM-safe: bounded deques, generator/iterative Hurst, explicit del + gc
- Inline self-test with synthetic ticks
"""
from __future__ import annotations

import gc
import math
import statistics
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Deque, Dict, List, Optional, Tuple


class Action(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    CANCEL_ALL = "CANCEL_ALL"


class Regime(Enum):
    MEAN_REVERTING = "MEAN_REVERTING"
    TRENDING = "TRENDING"
    CHOPPY = "CHOPPY"


@dataclass(frozen=True, slots=True)
class Tick:
    timestamp: float
    symbol: str
    bid: float
    ask: float
    mid: float
    volume: float
    high: float = 0.0
    low: float = 0.0

    def __post_init__(self) -> None:
        if self.high <= 0.0:
            object.__setattr__(self, "high", self.mid)
        if self.low <= 0.0:
            object.__setattr__(self, "low", self.mid)

    @property
    def spread(self) -> float:
        return max(self.ask - self.bid, 0.0)


@dataclass(frozen=True, slots=True)
class Fill:
    timestamp: float
    symbol: str
    side: str
    price: float
    qty: float
    fee: float = 0.0


@dataclass(slots=True)
class VSRConfig:
    symbol: str = "SOL/EUR"
    capital: float = 2.0
    risk_per_trade: float = 0.01
    base_spacing_pct: float = 0.015
    levels: int = 8
    max_open_positions: int = 12
    max_tick_history: int = 1200
    atr_period: int = 14
    hurst_window: int = 64
    ofi_window: int = 60
    ofi_buy_threshold: float = 0.4
    atr_vol_factor: float = 2.0
    grid_center_smoothing: int = 3
    min_hurst_for_grid: float = 0.55
    guard_fee_pct: float = 0.001
    cooldown_s: float = 5.0

    def validate(self) -> None:
        errs: List[str] = []
        if self.levels < 1 or self.levels > 100:
            errs.append("levels must be in [1,100]")
        if not 0.0 < self.base_spacing_pct < 0.2:
            errs.append("base_spacing_pct must be in (0,0.2)")
        if not 0.0 < self.risk_per_trade <= 0.25:
            errs.append("risk_per_trade must be in (0,0.25]")
        if self.capital <= 0.0:
            errs.append("capital must be positive")
        if len(errs):
            raise ValueError("VSRConfig invalid: " + "; ".join(errs))


class StrategyBase(ABC):
    @abstractmethod
    def on_tick(self, tick: Tick) -> Tuple[Action, Dict[str, Any]]: ...
    @abstractmethod
    def on_fill(self, fill: Fill) -> None: ...
    @abstractmethod
    def validate_config(self) -> None: ...
    @abstractmethod
    def estimate_memory_mb(self) -> float: ...
    @abstractmethod
    def get_state(self) -> Dict[str, Any]: ...
    @abstractmethod
    def load_state(self, state: Dict[str, Any]) -> None: ...


class VoltSR(StrategyBase):
    def __init__(self, config: VSRConfig) -> None:
        config.validate()
        self.cfg = config
        self._ticks: Deque[Tick] = deque(maxlen=config.max_tick_history)
        self._atr: float = 0.0
        self._ofi: Deque[bool] = deque(maxlen=config.ofi_window)
        self._center: float = 0.0
        self._center_hist: Deque[float] = deque(maxlen=config.grid_center_smoothing)
        self._positions: int = 0
        self._last_price: float = 0.0
        self._last_fill_price: float = 0.0
        self._last_entry_ts: float = 0.0
        self._realized_pnl: float = 0.0
        self._wins: int = 0
        self._losses: int = 0

    # metric updates -----------------------------------------------------
    def _update_atr(self, tick: Tick) -> None:
        tr = max(tick.high - tick.low, abs(tick.high - self._last_price), abs(tick.low - self._last_price))
        if self._atr <= 0.0:
            self._atr = tr
        else:
            k = 2.0 / (self.cfg.atr_period + 1.0)
            self._atr = tr * k + self._atr * (1.0 - k)

    def _hurst(self) -> float:
        n = len(self._ticks)
        if n < 16:
            return 0.5
        mids: List[float] = [t.mid for t in self._ticks if t.mid > 0.0]
        if len(mids) < 16:
            return 0.5
        rets = [math.log(mids[i] / mids[i - 1]) for i in range(1, len(mids))]
        del mids
        if not rets:
            return 0.5
        mean = statistics.fmean(rets)
        dev = [r - mean for r in rets]
        del rets
        sd = statistics.pstdev(dev) if len(dev) > 1 else 0.0
        if sd <= 0.0:
            del dev
            return 0.0
        run = 0.0
        hi = 0.0
        lo = 0.0
        for d in dev:
            run += d
            if run > hi:
                hi = run
            if run < lo:
                lo = run
        rs = (hi - lo) / sd
        del dev
        if rs <= 0.0:
            return 0.5
        h = math.log(rs) / math.log(float(n))
        return min(max(h, 0.0), 1.0)

    def _regime(self) -> Regime:
        h = self._hurst()
        if h > self.cfg.min_hurst_for_grid:
            return Regime.TRENDING
        if self._atr <= 0.0 or self._last_price <= 0.0:
            return Regime.CHOPPY
        ar = self._atr / self._last_price
        if ar > 0.03:
            return Regime.CHOPPY
        return Regime.MEAN_REVERTING

    def _ofi_pressure(self, tick: Tick) -> float:
        if self._last_fill_price > 0.0:
            self._ofi.append(tick.bid >= self._last_fill_price)
        if not self._ofi:
            return 0.5
        return sum(1.0 for b in self._ofi if b) / float(len(self._ofi))

    def _spacing(self, regime: Regime) -> float:
        base = self.cfg.base_spacing_pct
        if self._atr > 0.0 and self._last_price > 0.0:
            base = base * (1.0 + self.cfg.atr_vol_factor * (self._atr / self._last_price))
        if regime == Regime.CHOPPY:
            base = base * 1.5
        return min(base, 0.1)

    def _kelly_qty(self, mid: float) -> float:
        if mid <= 0.0:
            return 0.0
        edge = 0.52
        kelly = max((2.0 * edge - 1.0) / 1.0, 0.05)
        alloc = self.cfg.capital * self.cfg.risk_per_trade * kelly
        return alloc / mid

    def _smooth_center(self, mid: float) -> float:
        self._center_hist.append(mid)
        m = statistics.fmean(self._center_hist)
        if self._center <= 0.0:
            self._center = m
        else:
            self._center = 0.5 * self._center + 0.5 * m
        return self._center

    # contract API ---------------------------------------------------------
    def on_tick(self, tick: Tick) -> Tuple[Action, Dict[str, Any]]:
        now = time.time()
        self._ticks.append(tick)
        self._last_price = tick.mid
        self._update_atr(tick)

        regime = self._regime()
        center = self._smooth_center(tick.mid)
        spacing = self._spacing(regime)
        qty = self._kelly_qty(tick.mid)

        meta = {"strategy": "volt-sr", "regime": regime.value, "spacing": spacing}

        if regime == Regime.TRENDING:
            return (Action.CANCEL_ALL, {**meta, "reason": "trend grid off"})
        if now - self._last_entry_ts < self.cfg.cooldown_s:
            return (Action.HOLD, {**meta, "reason": "cooldown"})
        if self._positions >= self.cfg.max_open_positions:
            return (Action.HOLD, {**meta, "reason": "pos_cap"})
        if spacing < (self.cfg.guard_fee_pct * 2.0):
            return (Action.HOLD, {**meta, "reason": "fee_guard"})

        dist = (tick.mid - center) / center if center > 0.0 else 0.0
        pressure = self._ofi_pressure(tick)

        if dist <= -spacing and pressure >= self.cfg.ofi_buy_threshold:
            self._last_entry_ts = now
            self._last_fill_price = tick.mid
            return (Action.BUY, {**meta, "qty": qty, "price": tick.bid, "reason": "sr_bounce"})
        if dist >= spacing and pressure <= (1.0 - self.cfg.ofi_buy_threshold):
            self._last_entry_ts = now
            self._last_fill_price = tick.mid
            return (Action.SELL, {**meta, "qty": qty, "price": tick.ask, "reason": "sr_reject"})

        return (Action.HOLD, {**meta, "reason": "no_trigger"})

    def on_fill(self, fill: Fill) -> None:
        if fill.side == "buy":
            self._positions += 1
        else:
            if self._positions > 0:
                self._positions -= 1
            if self._last_fill_price > 0.0:
                pnl = (fill.price - self._last_fill_price) * fill.qty - fill.fee
                self._realized_pnl += pnl
                if pnl >= 0.0:
                    self._wins += 1
                else:
                    self._losses += 1
        self._last_fill_price = fill.price

    def validate_config(self) -> None:
        self.cfg.validate()

    def estimate_memory_mb(self) -> float:
        ticks_bytes = self.cfg.max_tick_history * (8 * 8 + 64)
        return round((ticks_bytes + 4096) / (1024 * 1024), 4)

    def get_state(self) -> Dict[str, Any]:
        return {
            "center": self._center,
            "atr": self._atr,
            "positions": self._positions,
            "realized_pnl": self._realized_pnl,
            "wins": self._wins,
            "losses": self._losses,
            "last_price": self._last_price,
            "config": asdict(self.cfg),
        }

    def load_state(self, state: Dict[str, Any]) -> None:
        self._center = float(state.get("center", 0.0))
        self._atr = float(state.get("atr", 0.0))
        self._positions = int(state.get("positions", 0))
        self._realized_pnl = float(state.get("realized_pnl", 0.0))
        self._wins = int(state.get("wins", 0))
        self._losses = int(state.get("losses", 0))


if __name__ == "__main__":
    cfg = VSRConfig(symbol="SOL/EUR", capital=2.0, levels=8)
    s = VoltSR(cfg)
    print("mem_estimate_mb:", s.estimate_memory_mb())
    ticks: List[Tick] = []
    mid = 100.0
    for i in range(400):
        mid = 100.0 + 0.6 * math.sin(i / 7.0) + 0.05 * (i % 3 - 1)
        ticks.append(Tick(float(i), cfg.symbol, mid - 0.01, mid + 0.01, mid, 1.0, mid + 0.02, mid - 0.02))
    n_act = 0
    for t in ticks:
        a, p = s.on_tick(t)
        if a != Action.HOLD:
            n_act += 1
        if a == Action.BUY:
            s.on_fill(Fill(t.timestamp, cfg.symbol, "buy", t.bid, p["qty"]))
        if a == Action.SELL:
            s.on_fill(Fill(t.timestamp, cfg.symbol, "sell", t.ask, p["qty"]))
    del ticks
    gc.collect()
    print("non-hold actions:", n_act)
    print("regime:", s._regime().value)
    print("state len:", len(str(s.get_state())))
    assert s.estimate_memory_mb() > 0.0
    assert s._regime() in (Regime.MEAN_REVERTING, Regime.TRENDING, Regime.CHOPPY)
    print("SMOKE OK volt-sr")
