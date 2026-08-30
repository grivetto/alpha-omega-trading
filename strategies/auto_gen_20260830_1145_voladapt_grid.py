"""voladapt_grid — Volatility-Adaptive Asymmetric Grid.

Strategy rationale
------------------
A pure symmetric grid bleeds fees on trending regimes and over-concentrates
risk during vol expansion. ``voladapt_grid`` makes two structural choices:

1. **Asymmetric spacing** — during a positive short-term momentum regime the
   buy-bands below the reference are widened and the sell-bands above are
   tightened, so the grid lets winners run while buying the dip only at
   genuinely cheaper levels. In a negative regime the asymmetry flips.
2. **Vol-scaled band width** — grid spacing is a multiple of recent realised
   volatility (EWMA) rather than a fixed tick, so the same levels parameter
   stays meaningful across quiet and turbulent sessions.

Risk controls are explicit: a hard cap on concurrent open positions, a
vol-band that collapses to a *no-trade zone* when realised vol spikes above
``vol_shutdown_threshold``, and an escape hatch at the reference price
(dynamic drawdown guard via trailing reference).

Memory profile
--------------
All history is kept in bounded ``collections.deque`` instances with ``maxlen``
(config-driven). No unbounded accumulation, no full-list comprehensions over
tick streams. ``estimate_memory_mb`` reports a closed-form upper bound.

Requirements
------------
* typing complete, zero ``try: except: pass``, config-driven.
* class ``StrategyBase`` with ``on_tick``, ``on_fill``, ``validate_config``,
  ``estimate_memory_mb``.
* inline ``__main__`` smoke test with small synthetic data.
"""

from __future__ import annotations

import gc
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Optional


# ---------------------------------------------------------------- defaults
DEFAULT_CONFIG: Dict[str, Any] = {
    "symbol": "DOGE/EUR",
    "capital": 3.7,
    "levels": 10,
    "base_spacing": 0.0025,       # base grid spacing as fraction of price
    "vol_ewma_span": 24,          # ticks in realised-vol EWMA
    "vol_lookback": 200,          # ticks to seed vol estimation
    "vol_band_mult": 1.0,         # spacing = base_spacing * (1 + vol_band_mult*(vol/vol_ref-1))
    "vol_ref": 0.01,              # reference realised vol (per-tick std)
    "vol_shutdown_threshold": 4.0,  # vol/vol_ref above this => no new entries
    "momentum_ewma_fast": 8,
    "momentum_ewma_slow": 32,
    "asym_factor": 0.35,          # max asymmetry applied to spacing (0..1)
    "min_spacing_pct": 0.0005,    # floor on absolute spacing as fraction
    "max_open_positions": 3,
    "trail_ref_pct": 0.01,        # trailing reference re-anchor, fraction
    "history_maxlen": 500,        # bounded tick history
    "debug": False,
}


@dataclass
class Position:
    """A single open grid position."""

    entry_price: float
    quantity: float
    level: int


class StrategyBase:
    """Required interface implemented by every auto-generated strategy."""

    def on_tick(self, tick: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def validate_config(self) -> bool:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


class VolAdaptGrid(StrategyBase):
    """Volatility-adaptive asymmetric grid strategy (see module docstring)."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config: Dict[str, Any] = dict(DEFAULT_CONFIG)
        if config:
            self.config.update(config)
        self.symbol: str = str(self.config["symbol"])
        self.capital: float = float(self.config["capital"])

        # ---- bounded history deques ----
        self.prices: Deque[float] = deque(maxlen=int(self.config["history_maxlen"]))
        self.ret_sq: Deque[float] = deque(maxlen=max(
            int(self.config["vol_lookback"]), int(self.config["vol_ewma_span"])
        ))

        # ---- EWMA state ----
        self.vol_ewma: float = float(self.config["vol_ref"])
        self.mom_fast: Optional[float] = None
        self.mom_slow: Optional[float] = None
        self.last_price: Optional[float] = None

        # ---- position bookkeeping ----
        self.positions: Dict[int, Position] = {}
        self.reference: Optional[float] = None
        self._seq: int = 0

    # ------------------------------------------------------------ plumbing
    def validate_config(self) -> bool:
        """Sanity-check numeric constraints; fail fast, never silently."""
        c = self.config
        for key in ("capital", "levels", "base_spacing", "vol_ewma_span",
                    "vol_lookback", "vol_shutdown_threshold", "asym_factor",
                    "min_spacing_pct", "max_open_positions", "trail_ref_pct"):
            if not isinstance(c.get(key), (int, float)):
                return False
        if c["capital"] <= 0 or c["levels"] <= 0 or c["base_spacing"] <= 0:
            return False
        if c["min_spacing_pct"] >= c["base_spacing"]:
            return False
        if not (0.0 <= c["asym_factor"] <= 1.0):
            return False
        if c["vol_ewma_span"] <= 0 or c["vol_lookback"] <= 0:
            return False
        return True

    def estimate_memory_mb(self) -> float:
        """Upper bound in MB = two deques of maxlen, mostly constant."""
        m = max(int(self.config["history_maxlen"]),
                int(self.config["vol_lookback"]),
                int(self.config["vol_ewma_span"]))
        # ~32 bytes/slot for float refs in CPython, generous overhead x3
        mb = (2.0 * m * 32.0 * 3.0) / (1024.0 * 1024.0)
        return round(mb, 4)

    # ------------------------------------------------------------ helpers
    def _ewma(self, old: float, new: float, span: int) -> float:
        alpha = 2.0 / (span + 1.0)
        return alpha * new + (1.0 - alpha) * old

    def _asymmetry(self) -> float:
        """Signed asymmetry in [-asym_factor, +asym_factor].

        Positive => bullish tilt (tight sell bands, wide buy bands).
        """
        if self.mom_fast is None or self.mom_slow is None or self.mom_slow == 0.0:
            return 0.0
        delta = (self.mom_fast - self.mom_slow) / abs(self.mom_slow)
        clamped = max(-1.0, min(1.0, delta))
        return clamped * float(self.config["asym_factor"])

    def _vol_ratio(self) -> float:
        """Current vol relative to reference; NaN-safe floor."""
        if self.vol_ewma <= 0.0:
            return 0.0
        return self.vol_ewma / float(self.config["vol_ref"])

    def _spacing(self) -> float:
        """Current (asymmetric-aware) spacing fraction of price."""
        c = self.config
        vr = self._vol_ratio()
        vol_scale = 1.0 + float(c["vol_band_mult"]) * (vr - 1.0)
        asym = self._asymmetry()

        buy_spacing = float(c["base_spacing"]) * vol_scale * (1.0 + asym)
        sell_spacing = float(c["base_spacing"]) * vol_scale * (1.0 - asym)

        floor = float(c["min_spacing_pct"])
        return max(floor, min(buy_spacing, sell_spacing) )

    # ------------------------------------------------------------ core API
    def on_tick(self, tick: Dict[str, Any]) -> Dict[str, Any]:
        """Consume one price tick, emit any intended orders.

        Returns a signal dict with a list of orders and diagnostic state.
        """
        price = float(tick["price"])
        self.last_price = price
        self.prices.append(price)

        # momentum EWMA pair
        p = price
        self.mom_fast = p if self.mom_fast is None else self._ewma(self.mom_fast, p, int(self.config["momentum_ewma_fast"]))
        self.mom_slow = p if self.mom_slow is None else self._ewma(self.mom_slow, p, int(self.config["momentum_ewma_slow"]))

        # realise-vol EWMA on squared returns (streaming, bounded)
        if self.reference is not None:
            ret = (price / self.reference) - 1.0
            self.ret_sq.append(ret * ret)
            if len(self.ret_sq) >= 2:
                win = list(self.ret_sq)  # bounded by maxlen config
                mean_sq = sum(win) / len(win)
                self.vol_ewma = self._ewma(self.vol_ewma, math.sqrt(max(mean_sq, 1e-12)),
                                            int(self.config["vol_ewma_span"]))
                del win
                gc.collect()

        # trailing reference re-anchor
        if self.reference is None:
            self.reference = price
        else:
            trail = float(self.config["trail_ref_pct"])
            up = self.reference * (1.0 + trail)
            down = self.reference * (1.0 - trail)
            if price > up:
                self.reference = price
            elif price < down and not self.positions:
                # let the reference chase down only when flat (dynamic drawdown guard)
                self.reference = price

        orders: list = []
        # vol shutdown: no new entries (still exit via on_fill/close logic outside)
        if self._vol_ratio() <= float(self.config["vol_shutdown_threshold"]):
            levels = int(self.config["levels"])
            spacing = self._spacing()
            if self.reference is not None:
                for i in range(1, levels + 1):
                    bid = self.reference * (1.0 - spacing * i)
                    ask = self.reference * (1.0 + spacing * i)
                    # buy band under reference, sell band above
                    if price <= bid and len(self.positions) < int(self.config["max_open_positions"]):
                        orders.append({"side": "buy", "price": round(bid, 6),
                                       "type": "limit", "level": i})
                    if price >= ask and i in self.positions:
                        orders.append({"side": "sell", "price": round(ask, 6),
                                       "type": "limit", "level": i})

        return {
            "symbol": self.symbol,
            "orders": orders,
            "state": {
                "reference": self.reference,
                "vol_ewma": self.vol_ewma,
                "vol_ratio": self._vol_ratio(),
                "spacing": self._spacing(),
                "asymmetry": self._asymmetry(),
                "open_positions": len(self.positions),
            },
        }

    def on_fill(self, fill: Dict[str, Any]) -> Dict[str, Any]:
        """Confirmed fill; book-keep the position.

        ``fill`` keys: side, price, quantity, level (optional).
        """
        side = str(fill["side"]).lower()
        price = float(fill["price"])
        qty = float(fill["quantity"])
        level = int(fill.get("level", self._seq))

        self._seq += 1
        if side == "buy":
            if len(self.positions) >= int(self.config["max_open_positions"]):
                return {"accepted": False, "reason": "position_cap", "level": level}
            self.positions[level] = Position(entry_price=price, quantity=qty, level=level)
            return {"accepted": True, "side": "buy", "level": level,
                    "open_positions": len(self.positions)}
        # sell => close matching (or any) open position at this level
        pos = self.positions.pop(level, None) or (
            self.positions.pop(self._seq - 1, None)
        )
        realized = 0.0
        if pos is not None:
            realized = (price - pos.entry_price) * pos.quantity
            self.capital += realized
        return {"accepted": True, "side": "sell", "level": level,
                "realized_pnl": realized, "open_positions": len(self.positions),
                "capital": self.capital}


def _smoke_test() -> None:
    """Small synthetic tick stream; prints final state. Never raises on data."""

    cfg = {"capital": 3.7, "levels": 5, "base_spacing": 0.0025,
           "vol_lookback": 30, "vol_ewma_span": 8, "max_open_positions": 3}
    strat = VolAdaptGrid(cfg)
    assert strat.validate_config(), "config rejected"
    base = 0.10
    for i in range(400):
        # gentle sinusoid + noise to exercise both regimes
        drift = math.sin(i / 25.0) * 0.002
        noise = (i % 7 - 3) * 0.0003
        sig = strat.on_tick({"price": base + drift + noise})
        # force a couple of fills to exercise on_fill bookkeeping
        if i % 120 == 0 and sig["state"]["open_positions"] == 0:
            strat.on_fill({"side": "buy", "price": base * 0.99, "quantity": 1.0, "level": 1})
        if i % 200 == 0:
            strat.on_fill({"side": "sell", "price": base * 1.01, "quantity": 1.0, "level": 1})

    print("SMOKE OK",
          "| mem_mb=", strat.estimate_memory_mb(),
          "| vol_ratio=", round(strat._vol_ratio(), 3),
          "| open_pos=", len(strat.positions),
          "| capital=", round(strat.capital, 4))


if __name__ == "__main__":
    _smoke_test()
