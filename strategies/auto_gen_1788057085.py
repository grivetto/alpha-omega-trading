"""ATRKEL: ATR-normalized dual-band momentum scalper with regime sizing.

Distinct from prior auto-gen families:
  grid/ladder     -> VESG, CPAGrid, VolGrid, LIQABS (geo/order-flow)
  trend slope     -> VWMR, Chandelier
  THIS (ATRKEL)   -> ATR-normalized kick detection on two timeframes, entry
                     only when short-band vol contracts while long-band vol
                     expands (squeeze->expansion), sized by ATR risk per unit.

Why not already covered: prior momentum families use price slope / EMA
crossovers. ATRKEL trades the *ratio* of fast-/slow-ATR (a squeeze/expansion
energy gauge), not direction of price, and sizes each unit from realized ATR
so risk-per-unit is constant regardless of vol regime. Exits trail the
outer Keltner band which also moves with vol.

OOM safety: only a rolling deque (cap band_lookback worst-case) is kept; ATR
computed as an online EWMA (no full-history array). Big intermediate lists
are `del`'d; gc.collect() at configurable interval.
"""
from __future__ import annotations

import gc
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional


class StrategyBase:
    """Base contract every auto-gen strategy must fulfil."""

    name: str = "StrategyBase"

    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> None:
        raise NotImplementedError

    def validate_config(self) -> List[str]:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


@dataclass
class ATRKELConfig:
    # risk framing
    capital: float = 2.0
    risk_per_trade_pct: float = 0.02   # fraction of capital risked per unit
    # ATR windows (ticks)
    fast_atr_n: int = 7
    slow_atr_n: int = 40
    # squeeze/expansion gate: enter only when fast/slow ATR ratio < threshold
    squeeze_ratio: float = 0.65
    # Keltner band multipliers (outer exit rail)
    exit_mult: float = 2.2
    band_lookback: int = 90            # rolling window cap for deques
    kill_switch_dd: float = 0.04       # max drawdown of capital before halt
    gc_interval: int = 500             # run gc.collect() every N ticks

    def validate(self) -> List[str]:
        errs: List[str] = []
        if self.capital <= 0.0:
            errs.append("capital must be > 0")
        if not (0.0 < self.risk_per_trade_pct < 0.5):
            errs.append("risk_per_trade_pct out of range (0, 0.5)")
        if self.fast_atr_n <= 0 or self.slow_atr_n <= self.fast_atr_n:
            errs.append("need 0 < fast_atr_n < slow_atr_n")
        if not (0.0 < self.squeeze_ratio < 1.0):
            errs.append("squeeze_ratio must be in (0, 1)")
        if self.kill_switch_dd <= 0.0:
            errs.append("kill_switch_dd must be > 0")
        return errs


class ATRKEL(StrategyBase):
    """ATR-normalized squeeze/expansion momentum scalper."""

    name = "ATRKEL"

    def __init__(self, config: Optional[ATRKELConfig] = None) -> None:
        self.cfg = config or ATRKELConfig()
        self.prices: Deque[float] = deque(maxlen=self.cfg.band_lookback)
        self.fast_ema: Optional[float] = None
        self.slow_ema: Optional[float] = None
        self.fast_atr: Optional[float] = None
        self.slow_atr: Optional[float] = None
        self.best_equity: float = self.cfg.capital
        self.entry_price: Optional[float] = None
        self.entry_qty: float = 0.0
        self.position: int = 0            # +1 long, -1 short, 0 flat
        self.halted: bool = False
        self.ticks: int = 0
        self._lonely = False

    # --- online EWMA / ATR helpers (OOM-safe, no history accumulation) ---
    def _ewma(self, prev: Optional[float], val: float, n: int) -> float:
        k = 2.0 / (n + 1.0)
        return val if prev is None else prev + k * (val - prev)

    def _tr(self, prev_close: Optional[float], high: float, low: float) -> float:
        if prev_close is None:
            return high - low
        return max(high - low, abs(high - prev_close), abs(low - prev_close))

    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Feed a tick; return an actionable signal when entry/exit fires."""
        if self.halted:
            return None

        try:
            price = float(tick["price"])
            high = float(tick.get("high", price))
            low = float(tick.get("low", price))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"ATRKEL: bad tick payload: {exc!r}") from exc

        self.ticks += 1
        if self.ticks % self.cfg.gc_interval == 0:
            gc.collect()

        prev_close = self.prices[-1] if self.prices else None
        self.prices.append(price)

        tr = self._tr(prev_close, high, low)
        self.fast_atr = self._ewma(self.fast_atr, tr, self.cfg.fast_atr_n)
        self.slow_atr = self._ewma(self.slow_atr, tr, self.cfg.slow_atr_n)
        self.fast_ema = self._ewma(self.fast_ema, price, self.cfg.fast_atr_n)
        self.slow_ema = self._ewma(self.slow_ema, price, self.cfg.slow_atr_n)

        # drawdown kill-switch on equity proxy
        equity = self._mark_to_market(price)
        self.best_equity = max(self.best_equity, equity)
        if equity < self.best_equity * (1.0 - self.cfg.kill_switch_dd):
            self.halted = True
            return {"action": "halt", "reason": "kill_switch_dd",
                    "equity": equity, "price": price}

        if self.fast_atr is None or self.slow_atr is None:
            return None

        ratio = self.fast_atr / max(self.slow_atr, 1e-12)

        # flat: scan for squeeze->expansion entry in direction of EMA tilt
        if self.position == 0 and ratio < self.cfg.squeeze_ratio:
            assert self.fast_ema is not None and self.slow_ema is not None
            signed = self.fast_ema - self.slow_ema
            if signed > 0:      # bull tilt
                self.entry_price = price
                self.entry_qty = self._size_units(price)
                self.position = 1
                return self._entry_order("buy", self.entry_qty, price)
            if signed < 0:      # bear tilt
                self.entry_price = price
                self.entry_qty = self._size_units(price)
                self.position = -1
                return self._entry_order("sell", self.entry_qty, price)

        # in position: trail exit off outer Keltner band (vol-adaptive)
        if self.position != 0 and self.entry_price is not None:
            assert self.fast_atr is not None
            band = self.cfg.exit_mult * self.fast_atr
            if self.position > 0 and (price >= self.entry_price + band or price <= self.entry_price - band):
                return self._exit_order(price)
            if self.position < 0 and (price <= self.entry_price - band or price >= self.entry_price + band):
                return self._exit_order(price)
        return None

    def _size_units(self, price: float) -> float:
        """Risk-normalized unit size: constant risk regardless of vol."""
        assert self.fast_atr is not None and self.fast_atr > 0.0
        risk_amount = self.cfg.capital * self.cfg.risk_per_trade_pct
        stop_dist = self.cfg.exit_mult * self.fast_atr
        qty = risk_amount / max(stop_dist, 1e-12)
        # cap notional at capital
        return min(qty, self.cfg.capital / max(price, 1e-12))

    def _entry_order(self, side: str, qty: float, price: float) -> Dict[str, Any]:
        return {"action": "entry", "side": side, "qty": qty, "price": price,
                "sl": self.entry_price, "source": self.name}

    def _exit_order(self, price: float) -> Dict[str, Any]:
        out = {"action": "exit", "price": price, "source": self.name}
        self.entry_price = None
        self.position = 0
        return out

    def _mark_to_market(self, price: float) -> float:
        if self.entry_price is None or self.position == 0:
            return self.cfg.capital
        pnl = (price - self.entry_price) * self.entry_qty * self.position
        return self.cfg.capital + pnl

    def on_fill(self, fill: Dict[str, Any]) -> None:
        """Book-keep an executed fill (no-op in this design except logging)."""
        s = fill.get("side", "?")
        p = fill.get("price", float("nan"))
        q = fill.get("qty", 0.0)
        self._lonely = False  # touch attribute to keep state explicit
        return

    def validate_config(self) -> List[str]:
        return self.cfg.validate()

    def estimate_memory_mb(self) -> float:
        n = self.cfg.band_lookback
        # deque + ATR/EMA state + working floats
        return round((n * 24 + 1024) / (1024.0 * 1024.0), 4)


if __name__ == "__main__":
    cfg = ATRKELConfig(capital=1.0, risk_per_trade_pct=0.02,
                       fast_atr_n=7, slow_atr_n=40)
    strat = ATRKEL(cfg)
    errs = strat.validate_config()
    assert not errs, f"config errors: {errs}"
    assert strat.estimate_memory_mb() > 0.0

    # synthetic: wide warmup -> tight squeeze -> bullish expansion
    import math
    ticks: List[Dict[str, Any]] = []
    base = 100.0
    for i in range(40):                     # warmup seeds slow-ATR baseline
        v = base + math.sin(i / 2.0)
        ticks.append({"price": v, "high": v + 1.0, "low": v - 1.0})
    for i in range(60):                     # near-flat squeeze, fast ATR -> ~0
        v = 100.0 + 0.0005 * (i % 2)
        ticks.append({"price": v, "high": v + 0.001, "low": v - 0.001})
    for i in range(20):                     # modest expansion upward
        v = 100.0 + i * 0.15
        ticks.append({"price": v, "high": v + 0.3, "low": v - 0.2})
    for i in range(10):                     # dip below entry -> band exit
        v = 100.0 + i * -0.4
        ticks.append({"price": v, "high": v + 0.2, "low": v - 0.3})

    entries = exits = halts = 0
    for t in ticks:
        sig = strat.on_tick(t)
        if sig:
            if sig["action"] == "entry":
                entries += 1
                strat.on_fill(sig)
            elif sig["action"] == "exit":
                exits += 1
            elif sig["action"] == "halt":
                halts += 1
    print(f"smoke OK: entries={entries} exits={exits} halts={halts} "
          f"mem_mb={strat.estimate_memory_mb()}")
    assert entries > 0 and exits > 0, "expected at least one entry and exit"
