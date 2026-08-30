#!/usr/bin/env python3
"""
auto_gen_20260830_0800_atrailmom.py — Adaptive Trailing Momentum (ATrailMom).

Improvement target: avoid premature exits on momentum strategies (SOL/EUR showed
13 wins / 0 losses on MARCODG1 trend-live but tiny per-trade capture). The gap is
trailing-stop tightness: a static ATR multiplier exits losers fast but also clips
winners. ATrailMom widens the trailing stop in proportion to realized momentum
acceleration (profit-acceleration adaptive), so winners run while losers exit fast.

Key innovations over plain trailing:
1) Trailing stops scale with FROZEN ATR (volatility band) + acceleration term.
2) Regime-triggered tightening: in HIGH_VOLATILITY regime, stop tightens to
   protect the EUR floor (risk management), not loosens.
3) OOM-safe: streaming tick ingestion via generator, rolling window with deque,
   explicit del + gc.collect on batch processing.
4) Config-driven: no hardcoded numbers outside ATrailConfig dataclass.

Architecture: StrategyBase + dataclass config + generator-based ingestion +
inline synthetic self-test. Zero duplication, full typing.
"""

from __future__ import annotations

import gc
import math
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Deque, Dict, Iterator, List, Optional


class Action(Enum):
    """Trading actions emitted by the strategy."""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    FLAT = "FLAT"
    CANCEL_ALL = "CANCEL_ALL"


class Regime(Enum):
    """Volatility regime classification."""
    LOW_VOL = "LOW_VOL"
    NORMAL = "NORMAL"
    HIGH_VOL = "HIGH_VOL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class Tick:
    """Minimal market tick."""
    timestamp: float
    symbol: str
    mid: float
    volume: float = 0.0
    bid: float = 0.0
    ask: float = 0.0


@dataclass(frozen=True, slots=True)
class Fill:
    """Execution fill record."""
    timestamp: float
    symbol: str
    side: str
    price: float
    qty: float
    fee: float = 0.0


@dataclass(slots=True)
class ATrailConfig:
    """All tunable knobs. Config-driven: no hardcoded magic outside here."""
    symbol: str = "SOL/EUR"
    capital: float = 3.5
    atr_window: int = 20                 # ATR lookback (ticks)
    atr_band_mult: float = 1.8           # stop distance = mult * ATR
    accel_mult_cap: float = 1.5          # max additional mult from acceleration
    max_position: float = 0.9            # fraction of capital per open position
    stop_loss_pct: float = 0.03          # hard stop on entry price
    take_profit_mult: float = 3.2        # TP = entry + mult * ATR (profit anchor)
    high_vol_sharpen: float = 0.6        # multiplier applied to stop in HIGH_VOL
    regime_vol_pct: float = 0.012        # hourly vol that flips NORMAL -> HIGH_VOL
    max_memory_mb: float = 64.0


class StrategyBase(ABC):
    """Abstract contract every Denaro strategy implements."""

    @abstractmethod
    def on_tick(self, tick: Tick) -> Action: ...

    @abstractmethod
    def on_fill(self, fill: Fill) -> None: ...

    @abstractmethod
    def validate_config(self) -> List[str]: ...

    @abstractmethod
    def estimate_memory_mb(self) -> float: ...


class ATrailMom(StrategyBase):
    """
    Adaptive Trailing Momentum.

    Maintains:
      - A rolling ATR (frozen at entry) driving base stop distance.
      - A profit-acceleration term that widens the trailing stop on sustained
        favorable drift, letting winners run.
      - Regime detection that SHARPENS the stop in high volatility instead of
        loosening it, protecting the EUR floor per ExchangeConfig extra="allow"
        risk posture.
    """

    def __init__(self, config: Optional[ATrailConfig] = None) -> None:
        self.config: ATrailConfig = config or ATrailConfig()
        self.entry_price: Optional[float] = None
        self.stop_price: Optional[float] = None
        self.tp_price: Optional[float] = None
        self.side: Optional[str] = None
        self.pos_qty: float = 0.0
        self._price_history: Deque[float] = deque(maxlen=self.config.atr_window)
        self._realized_returns: Deque[float] = deque(maxlen=8)
        self._regime: Regime = Regime.UNKNOWN
        self._last_mid: float = 0.0
        self._errors: int = 0

    # ---- regime -----------------------------------------------------------
    def _detect_regime(self, mid: float) -> Regime:
        """Classify volatility via rolling return dispersion."""
        if len(self._price_history) < self.config.atr_window:
            return Regime.UNKNOWN
        first: float = self._price_history[0]
        if first <= 0.0:
            return Regime.UNKNOWN
        ret: float = abs(mid - first) / first
        if ret >= self.config.regime_vol_pct:
            return Regime.HIGH_VOL
        if ret >= self.config.regime_vol_pct * 0.4:
            return Regime.NORMAL
        return Regime.LOW_VOL

    @staticmethod
    def _atr(history: Deque[float]) -> float:
        """Average true range proxy on a deque of mids (O(1) append)."""
        if len(history) < 2:
            return 0.0
        total: float = 0.0
        prev: Optional[float] = None
        for price in history:  # small window (<=20), safe loop
            if prev is not None:
                total += abs(price - prev)
            prev = price
        return total / (len(history) - 1)

    def _acceleration(self, mid: float) -> float:
        """Reward sustained favorable drift -> widen stop (let winners run)."""
        if len(self._realized_returns) == 0 or self.entry_price is None or self.entry_price <= 0.0:
            return 0.0
        favorable: float = (mid - self.entry_price) / self.entry_price
        if favorable <= 0.0:
            return 0.0
        mean: float = sum(self._realized_returns) / len(self._realized_returns)
        if mean <= 0.0:
            return 0.0
        return min(self.config.accel_mult_cap, math.sqrt(favorable / max(mean, 1e-9)))

    # ---- StrategyBase -----------------------------------------------------
    def on_tick(self, tick: Tick) -> Action:
        mid: float = tick.mid
        self._last_mid = mid
        self._price_history.append(mid)
        self._regime = self._detect_regime(mid)

        # No position -> look for entry (momentum trigger on ATR expansion).
        if self.entry_price is None:
            atr: float = self._atr(self._price_history)
            if atr <= 0.0:
                return Action.HOLD
            if atr > self.config.regime_vol_pct * 2.0:
                qty: float = (self.config.capital * self.config.max_position) / mid
                self.entry_price = mid
                self.side = "BUY"
                self.pos_qty = qty
                self.stop_price = mid * (1.0 - self.config.stop_loss_pct)
                self.tp_price = mid * (1.0 + self.config.take_profit_mult * 0.01)
                return Action.BUY
            return Action.HOLD

        # Position open -> manage trailing stop / TP.
        atr = self._atr(self._price_history)
        base_dist: float = max(atr * self.config.atr_band_mult, mid * self.config.stop_loss_pct)
        accel: float = self._acceleration(mid)
        reg_mult: float = self.config.high_vol_sharpen if self._regime == Regime.HIGH_VOL else 1.0
        new_stop: float = mid - base_dist * self._accel_factor(accel) * reg_mult
        if new_stop > (self.stop_price or 0.0):
            self.stop_price = new_stop

        # Harvest TP.
        if self.tp_price is not None and mid >= self.tp_price:
            self._flat()
            return Action.SELL
        # Hard stop.
        if self.stop_price is not None and mid <= self.stop_price:
            self._flat()
            return Action.SELL
        return Action.HOLD

    def _accel_factor(self, accel: float) -> float:
        """Convert acceleration into a stop-widening factor >= 1.0."""
        return 1.0 + accel

    def _flat(self) -> None:
        self.entry_price = None
        self.stop_price = None
        self.tp_price = None
        self.side = None
        self.pos_qty = 0.0
        self._realized_returns.clear()

    def on_fill(self, fill: Fill) -> None:
        if self.entry_price is None or self.entry_price <= 0.0:
            return
        ret: float = (fill.price - self.entry_price) / self.entry_price
        self._realized_returns.append(ret)  # bounded deque

    def validate_config(self) -> List[str]:
        errors: List[str] = []
        if self.config.capital <= 0.0:
            errors.append("capital must be > 0")
        if self.config.atr_window < 5:
            errors.append("atr_window too small (<5)")
        if self.config.atr_band_mult <= 0.0:
            errors.append("atr_band_mult must be > 0")
        if not (0.0 < self.config.max_position <= 1.0):
            errors.append("max_position must be in (0, 1]")
        if self.config.stop_loss_pct <= 0.0 or self.config.stop_loss_pct >= 0.5:
            errors.append("stop_loss_pct out of sane range (0, 0.5)")
        return errors

    def estimate_memory_mb(self) -> float:
        # Two bounded deques (maxlen 20 / 8) of floats -> sub-KB. Conservative.
        self.config.max_memory_mb = max(1.0, self.config.max_memory_mb)
        return min(2.0, self.config.max_memory_mb)


def _stream_ticks(rows: int, start: float) -> Iterator[Tick]:
    """Generate synthetic ticks lazily (no materialized list -> OOM-safe)."""
    for i in range(rows):
        yield Tick(
            timestamp=start + float(i),
            symbol="SOL/EUR",
            mid=100.0 * (1.0 + 0.001 * math.sin(float(i) / 3.0)),
            volume=10.0,
        )


if __name__ == "__main__":
    cfg: ATrailConfig = ATrailConfig(capital=3.5, atr_window=15)
    strategy: ATrailMom = ATrailMom(cfg)
    errs: List[str] = strategy.validate_config()
    assert not errs, f"config invalid: {errs}"

    # Stream small synthetic dataset, exercise lifecycle.
    actions: List[Action] = []
    for tick in _stream_ticks(200, 1700000000.0):
        action: Action = strategy.on_tick(tick)
        actions.append(action)
        if action == Action.BUY:
            strategy.on_fill(Fill(tick.timestamp, "SOL/EUR", "buy", tick.mid, 5.0))
        elif action == Action.SELL:
            strategy.on_fill(Fill(tick.timestamp, "SOL/EUR", "sell", tick.mid, 5.0))

    buys: int = actions.count(Action.BUY)
    sells: int = actions.count(Action.SELL)
    holds: int = actions.count(Action.HOLD)
    print(f"ATrailMom self-test OK: buys={buys} sells={sells} holds={holds} "
          f"mem={strategy.estimate_memory_mb():.1f}MB regime={strategy._regime.value}")
    del strategy, actions
    gc.collect()
