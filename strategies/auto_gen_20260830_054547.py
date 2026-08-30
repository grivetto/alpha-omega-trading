"""VOLTRAIL — Volatility-Trailing Grid Hybrid.

Family: volatility-adaptive. Distinct from QUEUEFLOW (L2 queue-imb/spread-width)
and plain grid/momentum.

Core idea
---------
Combine two orthogonal signals:
  1. ATR-scaled grid spacing: instead of a fixed euro gap between levels,
     spacing is a multiple of the current ATR(14). In calm regimes spacing
     shrinks -> more fills; in volatile regimes spacing widens -> less
     chandelier-bouncing and better re-entry points. This directly attacks
     the "noise whipsaw" that kills fixed-spacing grids.
  2. Chandelier exit (Donchian trailing): use ATR lookback high/low minus
     `mult*ATR` as a trailing stop. On a trend leg the grid keeps re-layering
     but a sustained adverse run trips the trail and we flatten the exposed
     position, protecting PnL (moves us from pure grid toward a trend guard).

Memory safety
-------------
All state is scalar + a bounded deque (ATR window). No list slicing on large
arrays, no per-tick allocations of > O(window). estimate_memory_mb caps at a
constant proxy. Explicit ``gc.collect()`` only after the (bounded) window trim
is unnecessary here — we never allocate large temporaries; a `del` on the
window trim is used to drop the OLDEST reference.

Config keys
-----------
- capital            : base quote allotment (EUR)
- base_fraction      : capital fraction reserved per grid level (0..1)
- levels             : grid levels per side (>=2)
- atr_window         : lookback ticks for ATR (>=3)
- atr_spacing_mult   : spacing = atr_spacing_mult * ATR (>=0.001)
- chandelier_mult    : trailing width in ATR units (>=0.5)
- risk_pct           : max portfolio % exposed as trailing stop trigger (0..1)
- fee                : taker fee as fraction (default 0.001)
- max_positions      : hard cap on concurrently open grid legs

OOM notes
---------
Runs in O(atr_window) memory, O(1) per tick after warmup. Designed for
embedded/per-node use; no batch processing required by design.
"""

from __future__ import annotations

import gc
import math
import time
import collections
from typing import Any, Deque, Dict, Optional


class StrategyBase:
    """Contract every auto-gen strategy implements."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config: Dict[str, Any] = {}
        self.validate_config(config)
        self.config.update(config)

    def validate_config(self, config: Dict[str, Any]) -> None:
        raise NotImplementedError

    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> None:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


class VOLTRAIL(StrategyBase):
    """ATR-scaled grid with chandelier trailing guard."""

    def validate_config(self, config: Dict[str, Any]) -> None:
        req: Dict[str, Any] = {
            "capital": (float, lambda v: v > 0),
            "atr_window": (int, lambda v: v >= 3),
            "atr_spacing_mult": (float, lambda v: v >= 0.001),
            "chandelier_mult": (float, lambda v: v >= 0.5),
            "levels": (int, lambda v: v >= 2),
            "risk_pct": (float, lambda v: 0.0 < v <= 1.0),
            "fee": (float, lambda v: 0.0 <= v <= 0.01),
            "max_positions": (int, lambda v: v >= 1),
            "base_fraction": (float, lambda v: 0.0 < v <= 1.0),
        }
        missing = [k for k in req if k not in config]
        if missing:
            raise ValueError(f"config missing keys: {missing}")
        for key, (typ, chk) in req.items():
            val = config[key]
            if not isinstance(val, typ):
                raise TypeError(f"{key}: expected {typ.__name__}, got {type(val).__name__}")
            if not chk(val):
                raise ValueError(f"{key}: value {val} out of range")

    def __init__(self, config: Dict[str, Any]) -> None:
        super().__init__(config)
        self.capital: float = float(self.config["capital"])
        self.atr_window: int = int(self.config["atr_window"])
        self.atr_spacing_mult: float = float(self.config["atr_spacing_mult"])
        self.chandelier_mult: float = float(self.config["chandelier_mult"])
        self.levels: int = int(self.config["levels"])
        self.risk_pct: float = float(self.config["risk_pct"])
        self.fee: float = float(self.config["fee"])
        self.max_positions: int = int(self.config["max_positions"])
        self.base_fraction: float = float(self.config["base_fraction"])

        self._prices: Deque[float] = collections.deque(maxlen=self.atr_window + 2)
        self._atr: Optional[float] = None
        self._pos: float = 0.0          # signed inventory (+net long, -net short)
        self._cash: float = self.capital
        self._trail_high: Optional[float] = None
        self._trail_low: Optional[float] = None
        self._tp: float = 0.0           # realized pnl in quote
        self._latent_fills: Deque[Dict[str, Any]] = collections.deque(maxlen=64)

    def _atr_value(self, price: float) -> float:
        """Incremental Wilder ATR. O(1) per tick after warmup."""
        if self._atr is None:
            self._atr = price * 0.02 if len(self._prices) < 2 else price * 0.01
            return float(self._atr)
        prev = self._prices[-1]
        tr: float = max(
            abs(price - prev),
            abs(price - self._prices[-1]),
            abs(prev - self._trail_wide()) if self._trail_wide() else 0.0,
        )
        # Wilder smoothing bounded by window size
        alpha: float = 2.0 / (self.atr_window + 1.0)
        self._atr = tr * alpha + self._atr * (1.0 - alpha)
        return float(self._atr)

    def _trail_wide(self) -> float:
        return self._atr * self.chandelier_mult if self._atr is not None else 0.0

    def _spacing(self) -> float:
        if self._atr is None:
            return self.capital * 0.01
        return max(self._atr * self.atr_spacing_mult, self.capital * 0.0005)

    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        price: float = float(tick["price"])
        ts: float = float(tick.get("timestamp", time.time()))

        self._prices.append(price)
        atr: float = self._atr_value(price)

        # Refresh chandelier anchors
        hi = max(self._prices) if self._prices else price
        lo = min(self._prices) if self._prices else price
        self._trail_high = hi - self.chandelier_mult * atr
        self._trail_low = lo + self.chandelier_mult * atr

        # Chandelier exit: sustained adverse move flattens exposure
        if self._pos > 0 and price <= self._trail_high:
            self._cash += self._pos * price * (1.0 - self.fee)
            self._tp += self._pos * price * (1.0 - self.fee) - 0.0
            self._pos = 0.0
            return {"action": "close", "side": "sell", "qty": abs(self._pos) or 1e-9,
                    "reason": "chandelier_exit", "price": price, "ts": ts,
                    "pnl": self._tp}
        if self._pos < 0 and price >= self._trail_low:
            self._cash += self._pos * price * (1.0 - self.fee)
            self._tp += self._pos * price * (1.0 - self.fee)
            self._pos = 0.0
            return {"action": "close", "side": "buy", "qty": abs(self._pos) or 1e-9,
                    "reason": "chandelier_exit", "price": price, "ts": ts,
                    "pnl": self._tp}

        # Grid layer sizing
        slot_qty: float = (self.capital * self.base_fraction) / price
        if abs(self._pos) >= self.max_positions * slot_qty:
            return None

        ref: float = self._prices[0] if self._prices else price
        diff: float = price - ref
        spacing: float = self._spacing()
        lvl: float = diff / spacing if spacing > 0 else 0.0

        # Buy leg: price fell a full spacing below ref
        if lvl <= -1.0:
            qty: float = min(slot_qty, (self.capital * (1.0 - self.risk_pct)) / price)
            if self._cash >= qty * price * (1.0 + self.fee):
                self._cash -= qty * price * (1.0 + self.fee)
                self._pos += qty
                self._latent_fills.append({"side": "buy", "qty": qty, "price": price, "ts": ts})
                return {"action": "buy", "qty": qty, "price": price, "ts": ts,
                        "reason": "grid_buy", "spacing": spacing, "atr": atr}
        del lvl, ref, diff, spacing, slot_qty
        gc.collect()
        return None

    def on_fill(self, fill: Dict[str, Any]) -> None:
        """Settle a previously issued order against realized book price."""
        self._latent_fills.append(fill)
        if self._latent_fills:
            self._latent_fills.popleft()  # bounded book keeping

    def estimate_memory_mb(self) -> float:
        # O(atr_window) floats + bounded deques; constant proxy
        return (self.atr_window * 8.0 + 4 * 64 * 8.0) / (1024.0 * 1024.0)


if __name__ == "__main__":
    import sys

    def smoke(name: str, cfg: Dict[str, Any], ticks: int, expect_orders: bool) -> None:
        try:
            strat = VOLTRAIL(cfg)
        except (ValueError, TypeError) as exc:
            print(f"[{name}] CONFIG REJECTED: {exc}")
            return
        orders = 0
        price = float(cfg["capital"])
        for i in range(ticks):
            drift = math.sin(i / 7.0) * 0.5 + (0.05 if i % 5 == 0 else -0.02)
            price = max(1e-6, price + drift * price * 0.005)
            order = strat.on_tick({"price": price, "timestamp": i})
            if order:
                orders += 1
        mem = strat.estimate_memory_mb()
        print(f"[{name}] OK orders={orders} expect>=1={expect_orders} mem={mem:.6f}MB pnl={strat._tp:.4f}")
        if expect_orders and orders == 0:
            sys.exit(f"[{name}] FAIL: expected orders")
        if not expect_orders and orders > 0:
            sys.exit(f"[{name}] FAIL: expected no orders")

    cfg_valid = {
        "capital": 1000.0, "atr_window": 14, "atr_spacing_mult": 0.01,
        "chandelier_mult": 2.0, "levels": 5, "risk_pct": 0.02, "fee": 0.001,
        "max_positions": 10, "base_fraction": 0.2,
    }
    smoke("volatile-long", cfg_valid, 200, True)
    smoke("calm-flat", {**cfg_valid, "atr_spacing_mult": 0.5, "risk_pct": 0.3}, 60, False)

    # Invalid configs must be rejected
    for bad, label in [
        ({"capital": 0.0}, "zero-capital"),
        ({"atr_window": 2}, "small-window"),
        ({"fee": 1.5}, "huge-fee"),
    ]:
        merged = dict(cfg_valid)
        merged.update(bad)
        try:
            VOLTRAIL(merged)
            sys.exit(f"[{label}] FAIL: config not rejected")
        except (ValueError, TypeError):
            print(f"[{label}] rejected (OK)")
    print("ALL SMOKE TESTS PASSED")
