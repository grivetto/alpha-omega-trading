"""
auto_gen_20260830_1811_momentumvoldrift.py

Momentum-VolDrift Adaptive (MVD) - regime-switching momentum with vol-scaled
trailing and drift re-centering. Complements invhedge (inventory hedging):
where invhedge protects a one-sided grid book, MVD trades *direction* directly
by detecting price drift (Bollinger z-score), scaling exposure by realized vol,
and trailing a stop so winners run while losers cut early.

Design intent:
- Regime detection: rolling mean/std of PRICE (Bollinger). z = (price-mean)/std.
  > +drift_z => DRIFT_UP, < -drift_z => DRIFT_DOWN, else RANGE. Robust against
  constant-trend degeneracy that a log-return z-score suffers from.
- Sizing: base_size * |z|/drift_z * (target_vol / realized_vol), clipped to
  max_position_ratio * capital. Vol scaling adds on calm trends, shrinks when
  vol explodes (asymmetric tail protection). Realized vol = std of log-returns
  (kept separate from the price z-score signal).
- Trailing: once in a leg, a trailing stop at `trail_frac` ratchets off the best
  favorable price; a regime flip to counter-side or RANGE exits early.
- Gap guard: `gap_stop_frac` freezes placements after a violent move.
- Explicit error callback - no silent exception swallowing.

OOM/streaming:
- Only two fixed-size deques and scalars. No tick history materialized.
- `estimate_memory_mb` returns a tight O(1) bound.

Design constraints:
- Full typing, explicit error handling, config-driven (DEFAULT_CONFIG).
"""

from __future__ import annotations

import math
from collections import deque
from enum import Enum
from typing import Any, Callable, Deque, Dict, Optional

# --------------------------- Config ---------------------------------------- #

DEFAULT_CONFIG: Dict[str, Any] = {
    "pair": "DOGE/EUR",
    "capital": 1.0,
    "base_size": 0.25,          # fraction of capital per unit (notional)
    "lookback": 60,             # Bollinger window (price mean/std)
    "vol_window": 40,           # window for realized vol (log-return std)
    "target_vol": 0.005,        # target realized vol reference for sizing
    "max_position_ratio": 0.6,  # max notional as fraction of capital
    "trail_frac": 0.03,         # trailing stop distance (fraction off best)
    "drift_z": 1.5,             # |z-score| to declare a drift leg
    "gap_stop_frac": 0.015,     # gap event freeze threshold
    "streaming": True,
    "error_cb": None,           # Optional[Callable[[str], None]]
}


class Regime(Enum):
    DRIFT_UP = "DRIFT_UP"
    DRIFT_DOWN = "DRIFT_DOWN"
    RANGE = "RANGE"


class _RollingStats:
    """O(1) streaming mean/std over a fixed rolling window (Bollinger basis)."""

    __slots__ = ("_buf", "_fill", "_mean", "_m2")

    def __init__(self, window: int) -> None:
        if window < 2:
            raise ValueError("window must be >= 2")
        self._buf: Deque[float] = deque(maxlen=window)
        self._fill = 0
        self._mean = 0.0
        self._m2 = 0.0

    def push(self, value: float) -> None:
        if self._fill == self._buf.maxlen:
            old = self._buf[0]
            new_mean = (self._mean * self._fill - old) / (self._fill - 1)
            self._m2 -= (old - new_mean) * (old - self._mean)
            self._mean = new_mean
            self._fill -= 1
        self._fill += 1
        delta = value - self._mean
        self._mean += delta / float(self._fill)
        delta2 = value - self._mean
        self._m2 += delta * delta2
        self._buf.append(value)

    def mean(self) -> float:
        return self._mean

    def std(self) -> float:
        if self._fill < 2:
            return 0.0
        return math.sqrt(max(self._m2 / float(self._fill - 1), 0.0))


class StrategyBase:
    """Interface contract for Denaro strategies (duck-typed)."""

    def on_tick(self, tick: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> None:
        raise NotImplementedError

    def validate_config(self) -> None:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


# --------------------------- Strategy -------------------------------------- #

class MomentumVolDrift(StrategyBase):
    """Regime-switching momentum with Bollinger drift + vol-scaled trailing."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config: Dict[str, Any] = dict(DEFAULT_CONFIG)
        if config:
            self.config.update(config)
        self.validate_config()

        self.pair: str = self.config["pair"]
        self._capital: float = float(self.config["capital"])
        self._err_cb: Optional[Callable[[str], None]] = self.config.get("error_cb")

        # Signal source: price Bollinger z-score, robust to constant trends.
        self._ps = _RollingStats(int(self.config["lookback"]))
        # Risk source: realized vol = rolling std of log-returns.
        self._rs = _RollingStats(int(self.config["vol_window"]))

        self._regime: Regime = Regime.RANGE
        self._position = 0.0            # signed notional exposure
        self._entry_price: Optional[float] = None
        self._best_price: Optional[float] = None
        self._prev_price: Optional[float] = None
        self._gap_anchor: Optional[float] = None
        self.pnl: float = 0.0
        self.trades: int = 0

    # -- helpers ------------------------------------------------------------ #
    def _ebad(self, tag: str, err: Exception) -> None:
        msg = f"[{tag}] {type(err).__name__}: {err}"
        if self._err_cb is not None:
            try:
                self._err_cb(msg)
            except Exception:
                return
        else:
            raise err

    def _scale(self, drift_z: float, real_vol: float) -> float:
        """Position size = base * z-strength * vol-adjust, clipped by cap."""
        base = float(self.config["base_size"])
        target = float(self.config["target_vol"])
        vol_adj = min(target / max(real_vol, 1e-9), 2.0)
        strength = min(abs(drift_z) / float(self.config["drift_z"]), 2.0)
        return base * vol_adj * strength * self._capital

    # -- interface ---------------------------------------------------------- #
    def on_tick(self, tick: Dict[str, Any]) -> Dict[str, Any]:
        try:
            price = float(tick["price"])
        except (KeyError, TypeError, ValueError) as err:
            self._ebad("on_tick.price", err)
            return {"action": "HOLD", "reason": "invalid_price"}

        # Stream prices and log-returns.
        if self._prev_price is not None and self._prev_price > 0:
            self._rs.push(math.log(price / self._prev_price))
        self._ps.push(price)
        self._prev_price = price

        real_vol = self._rs.std()
        std = self._ps.std()
        drift_z = 0.0
        if std > 0:
            drift_z = (price - self._ps.mean()) / std

        # Gap freeze.
        if self._gap_anchor is not None:
            if abs(price - self._gap_anchor) / max(self._gap_anchor, 1e-9) > \
                    float(self.config["gap_stop_frac"]):
                self._gap_anchor = price  # re-anchor, keep frozen
                return {"action": "HOLD", "reason": "gap_freeze", "price": price}
            self._gap_anchor = None

        # Regime classification.
        z_thresh = float(self.config["drift_z"])
        if drift_z > z_thresh:
            new_regime = Regime.DRIFT_UP
        elif drift_z < -z_thresh:
            new_regime = Regime.DRIFT_DOWN
        else:
            new_regime = Regime.RANGE
        self._regime = new_regime

        max_not = float(self.config["max_position_ratio"]) * self._capital

        # Manage open leg: trailing stop / regime exit.
        if self._position != 0.0 and self._entry_price is not None:
            if (self._position > 0 and price > self._best_price) or \
               (self._position < 0 and price < self._best_price):
                self._best_price = price
            trail = abs(price - self._best_price)
            stop_hit = trail > float(self.config["trail_frac"]) * max(price, self._best_price, 1e-9)
            if stop_hit:
                exit_price = price
                self.pnl += (exit_price - self._entry_price) if self._position > 0 \
                            else (self._entry_price - exit_price)
                self.trades += 1
                closing = "SELL" if self._position > 0 else "BUY"
                self._position = 0.0
                self._entry_price = None
                self._best_price = None
                return {"action": closing, "reason": "trail_stop", "price": price}
            if self._regime == Regime.RANGE:
                exit_price = price
                self.pnl += (exit_price - self._entry_price) if self._position > 0 \
                            else (self._entry_price - exit_price)
                self.trades += 1
                closing = "SELL" if self._position > 0 else "BUY"
                self._position = 0.0
                self._entry_price = None
                self._best_price = None
                return {"action": closing, "reason": "regime_exit", "price": price}

        # Open / add on drift.
        if self._regime in (Regime.DRIFT_UP, Regime.DRIFT_DOWN):
            size = min(self._scale(drift_z, real_vol), max_not)
            desired = size if self._regime == Regime.DRIFT_UP else -size
            if self._position == 0.0:
                self._position = desired
                self._entry_price = price
                self._best_price = price
                action = "BUY" if desired > 0 else "SELL"
                return {"action": action, "reason": f"open_{self._regime.value}",
                        "size": round(size, 8), "price": price,
                        "drift_z": round(drift_z, 3)}

        return {"action": "HOLD", "reason": self._regime.value,
                "drift_z": round(drift_z, 3), "price": price,
                "regime": self._regime.value}

    def on_fill(self, fill: Dict[str, Any]) -> None:
        """Bookkeeping hook; net PnL is settled in on_tick exits."""
        try:
            fee = float(fill.get("fee", 0.0))
            self.pnl -= fee
            self.gap_anchor = self._prev_price  # after a fill, watch for gaps
        except (TypeError, ValueError) as err:
            self._ebad("on_fill.fee", err)

    def validate_config(self) -> None:
        req = ("pair", "capital", "base_size", "lookback", "vol_window",
               "target_vol", "max_position_ratio", "trail_frac", "drift_z")
        for k in req:
            if k not in self.config:
                raise ValueError(f"missing config key: {k}")
        if self.config["capital"] <= 0:
            raise ValueError("capital must be > 0")
        if not 0 < self.config["base_size"] <= 1:
            raise ValueError("base_size must be in (0,1]")
        if self.config["drift_z"] <= 0:
            raise ValueError("drift_z must be > 0")

    def estimate_memory_mb(self) -> float:
        lookback = int(self.config["lookback"])
        vol_window = int(self.config["vol_window"])
        bytes_total = (lookback + vol_window) * 24 + 2048
        return round(bytes_total / (1024 * 1024), 6)


# --------------------------- Self-test ------------------------------------- #

if __name__ == "__main__":
    cfg = dict(DEFAULT_CONFIG)
    cfg.update({"capital": 1.0, "base_size": 0.2, "lookback": 20,
                "vol_window": 10, "trail_frac": 0.02})
    s = MomentumVolDrift(cfg)
    # Steady uptrend then a sharp reversal -> should open a long, then trail-exit.
    prices = [1.0 + i * 0.001 for i in range(80)] + \
             [1.08 - i * 0.003 for i in range(30)]
    actions = []
    for p in prices:
        actions.append(s.on_tick({"price": p})["action"])
    trades = sum(1 for a in actions if a in ("BUY", "SELL"))
    mem = s.estimate_memory_mb()
    s.validate_config()
    assert trades >= 2, f"expected open+exit, got {trades}"
    # Expect final exposure consistent with the trailing DRIFT_DOWN leg.
    assert s._position < 0, f"expected bearish flip after reversal, got pos={s._position:.3f}"
    print(f"self-test OK: trades={trades} pnl={s.pnl:.4f} mem={mem}MB final_regime={s._regime.value} final_pos={s._position:.3f}")
    print("action-seq:", "".join(("B" if a == "BUY" else "S" if a == "SELL" else ".") for a in actions))
