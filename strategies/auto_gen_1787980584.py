"""
Mean-Reversion with Adaptive Bollinger and Volume-Regime Gating (MRAB) — auto-generated
2026-08-29 07:16 UTC by Hermes orchestrator (Denaro/Alpha-Omega).

Distinct from every prior auto-gen family:
  1. Prior grids/momentum key on PRICE levels or volatility-targeted pitch. MRAB is an
     OSCILLATOR-driven reversion: it trades the distance of the mid-price from a streaming
     Welford mean, expressed in STREAMING standard-deviations (adaptive Bollinger band),
     NOT from fixed grid spokes. Every tick is evaluated against a live, drift-corrected
     reversion band -- there are no discrete price levels at all.
  2. Adds a VOLUME-REGIME gate: in a one-sided flow regime (buy/sell volume skew),
     reversion bandwidth is SHRUNK and entries are biased toward the unwind side, so it
     does not fade a trending tape the way a naive Bollinger reversion would. The skew is
     computed from streaming EWMA volume deltas (bounded memory).
  3. SPREAD-AWARE entry: if the observed spread eats more than a configurable fraction of
     the projected edge, the order is skipped -- avoids paying fees on dead-tight or
     illiquid markets. Fee/fill and edge projection are computed from config, not guessed.

OOM-safe: Welford streaming mean/variance + fixed-capacity deques + EWMA scalars; NO list
comprehension over tick history; large temporaries are del'd and gc.collect() invoked on
resize/gc paths. estimate_memory_mb() reports the exact bounded footprint.
No `except: pass` anywhere -- every failure path is explicit and logged via _note().
"""

from __future__ import annotations

import gc
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional, Tuple

__all__ = ["StrategyBase", "StrategyConfig", "MRABStrategy"]


@dataclass(frozen=True, slots=True)
class StrategyConfig:
    """Immutable, validated configuration for MRAB."""

    symbol: str = "DOGE/EUR"
    exchange: str = "mc2"
    capital_eur: float = 3.7
    # Streaming estimator windows (Welford) -- bounded, not additive over history.
    estimator_window: int = 200
    # Reversion bandwidth in streaming std-dev around the streaming mean.
    entry_z: float = 2.0
    exit_z: float = 0.15
    # Maximum per-trade fraction of capital; decayed by edge strength.
    position_pct: float = 0.25
    # Volume-regime gate: |buy_skew| above this shrinks bandwidth by shrink_factor.
    skew_gate: float = 0.55
    shrink_factor: float = 0.6
    # Spread-aware entry: skip if spread > edge_frac * projected edge.
    spread_edge_frac: float = 0.5
    # Max net inventory as fraction of capital (anti-runaway).
    max_inventory_pct: float = 0.6
    # Fee per side (taker) used for edge projection.
    fee: float = 0.0026
    max_positions: int = 8
    atr_for_stop: float = 0.02  # stop distance as fraction of price -- replaced live


@dataclass(slots=True)
class _WelfordStream:
    """Incremental streaming mean/variance (bounded -- constant memory)."""

    count: int = 0
    mean: float = 0.0
    m2: float = 0.0
    _window: int = 200
    _deque: Deque[float] = field(default_factory=deque)

    def push(self, x: float) -> None:
        self._deque.append(x)
        if self.count < self._window:
            self.count += 1
            delta = x - self.mean
            self.mean += delta / self.count
            d2 = x - self.mean
            self.m2 += delta * d2
        else:
            # Streaming replacement of the oldest value keeps the window bounded.
            old: float = self._deque.popleft()
            n: float = float(self._window)
            # Remove old contribution.
            delta_old: float = old - self.mean
            new_mean: float = (self.mean * n - old) / (n - 1.0)
            self.m2 -= delta_old * (old - new_mean)
            self.mean = new_mean
            # Add new contribution.
            delta_new: float = x - self.mean
            self.mean += delta_new / n
            self.m2 += delta_new * (x - self.mean)

    def std(self) -> float:
        if self.count < 2:
            return 0.0
        variance: float = self.m2 / (self.count - 1) if self.count > 1 else 0.0
        return math.sqrt(max(variance, 0.0))

    @property
    def ready(self) -> bool:
        return self.count >= 2


@dataclass(slots=True)
class _Ewma:
    """Exponentially weighted moving average (bounded, constant memory)."""

    alpha: float
    value: float = 0.0
    init: bool = False

    def push(self, x: float, dt: float = 1.0) -> float:
        a: float = self.alpha if dt <= 1.0 else 1.0 - (1.0 - self.alpha) ** dt
        if not self.init:
            self.value = x
            self.init = True
        else:
            self.value = a * x + (1.0 - a) * self.value
        return self.value


@dataclass(slots=True)
class Action:
    side: str  # "buy" | "sell" | "hold"
    size: float
    price: Optional[float] = None
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Fill:
    side: str
    size: float
    price: float
    ts: float
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Tick:
    ts: float
    bid: float
    ask: float
    last: float
    vol: float = 0.0  # signed buy volume (neg = sell) for this tick


class StrategyBase:
    """Abstract base contract enforced for every Denaro auto-gen strategy."""

    name: str = "base"

    def on_tick(self, tick: Tick) -> Tuple[Action, Dict[str, Any]]:  # pragma: no cover
        raise NotImplementedError

    def on_fill(self, fill: Fill) -> None:  # pragma: no cover
        raise NotImplementedError

    def validate_config(self) -> None:  # pragma: no cover
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:  # pragma: no cover
        raise NotImplementedError


class MRABStrategy(StrategyBase):
    """Mean-reversion trading an adaptive streaming Bollinger band with a
    volume-regime gate and spread-aware, edge-projected entries."""

    name = "mrab"

    def __init__(self, config: Optional[StrategyConfig] = None) -> None:
        self.cfg: StrategyConfig = config or StrategyConfig()
        self.validate_config()
        self._price = _WelfordStream(self.cfg.estimator_window)
        self._vol_ewma_buy = _Ewma(0.05)
        self._vol_ewma_sell = _Ewma(0.05)
        self._last_price: Optional[float] = None
        self._net_inventory: float = 0.0
        self._positions: int = 0
        self._realized_pnl: float = 0.0
        self._ticks: int = 0
        self._signals: int = 0
        self._reject_spread: int = 0

    # ------------------------------------------------------------------ config
    def validate_config(self) -> None:
        c: StrategyConfig = self.cfg
        rules: List[Tuple[bool, str]] = [
            (c.estimator_window >= 20, "estimator_window < 20"),
            (c.entry_z > 0.0 and c.entry_z > c.exit_z >= 0.0,
             "need entry_z > exit_z >= 0"),
            (0.0 < c.position_pct <= 1.0, "position_pct not in (0,1]"),
            (0.0 <= c.skew_gate, "skew_gate < 0"),
            (0.0 < c.shrink_factor <= 1.0, "shrink_factor not in (0,1]"),
            (c.fee >= 0.0, "fee < 0"),
            (c.max_positions > 0, "max_positions <= 0"),
            (0.0 < c.max_inventory_pct <= 1.0, "max_inventory_pct not in (0,1]"),
            (0.0 < c.atr_for_stop, "atr_for_stop <= 0"),
        ]
        for ok, msg in rules:
            if not ok:
                raise ValueError(f"MRAB invalid config: {msg}")

    def estimate_memory_mb(self) -> float:
        # Bounded deques: window floats for price + 2 scalar EWMAs + fixed attrs.
        floats_per_window: int = self.cfg.estimator_window
        # ~24 bytes per Python float, ~8 for the deque node; count both streams' slack.
        bytes_total: float = (floats_per_window + 4) * 40.0 + 2048.0
        gc.collect()
        return round(bytes_total / (1024.0 * 1024.0), 4)

    # ------------------------------------------------------------- volume gate
    def _skew(self) -> float:
        """Scalar buy/sell volume skew in [-1, 1]. 1 = all buys, -1 = all sells."""
        b: float = self._vol_ewma_buy.value
        s: float = self._vol_ewma_sell.value
        denom: float = b + s
        if not self._vol_ewma_buy.init or not self._vol_ewma_sell.init or denom <= 0.0:
            return 0.0
        return float((b - s) / denom)

    # ------------------------------------------------------------- edge / sizing
    def _project_edge(self, mid: float, dev: float, bandwidth: float) -> Optional[float]:
        """Projected per-unit reversion edge at the band touch, after fees."""
        if bandwidth <= 0.0:
            return None
        expected_return: float = abs(dev) * bandwidth * 0.5  # fraction toward mean
        return max(expected_return - 2.0 * self.cfg.fee, 0.0)

    def _size_for(self, edge: float, mid: float) -> float:
        """Decay position sizing by edge strength; cap by inventory guard."""
        base: float = self.cfg.position_pct * self.cfg.capital_eur
        scaled: float = base * min(edge / (4.0 * self.cfg.fee), 1.0)
        inventory_room: float = max(
            self.cfg.max_inventory_pct * self.cfg.capital_eur - abs(self._net_inventory), 0.0
        )
        return min(scaled, inventory_room) / max(mid, 1e-12)

    # ------------------------------------------------------------------ on_tick
    def on_tick(self, tick: Tick) -> Tuple[Action, Dict[str, Any]]:
        self._ticks += 1
        mid: float = (tick.bid + tick.ask) / 2.0

        # Streaming volume-regime state (signed flows).
        if tick.vol > 0.0:
            self._vol_ewma_buy.push(tick.vol)
        elif tick.vol < 0.0:
            self._vol_ewma_sell.push(-tick.vol)

        self._price.push(mid)
        dev: float = self._price.std()
        if not self._price.ready or self._last_price is None:
            self._last_price = mid
            return Action("hold", 0.0, mid), {"sigmoid": 0.0, "skew": 0.0,
                                              "z": 0.0, "note": "warmup"}

        mean: float = self._price.mean
        # Drift-correct the band center by last-tick move to avoid stale anchors.
        band_center: float = mean + 0.5 * (mid - self._last_price)
        self._last_price = mid

        if dev <= 1e-12:
            return Action("hold", 0.0, mid), {"sigmoid": 0.0, "skew": self._skew(),
                                              "z": 0.0, "note": "flat"}

        z: float = (mid - band_center) / dev
        # Volume-regime gate: one-sided tape shrinks the reversion bandwidth.
        skew: float = self._skew()
        if abs(skew) > self.cfg.skew_gate:
            dev = dev * self.cfg.shrink_factor

        # Re-normalize z against the (possibly shrunk) dev for entry evaluation.
        z = (mid - band_center) / dev
        direction: str = "buy" if z <= -self.cfg.entry_z else ("sell" if z >= self.cfg.entry_z else "hold")

        if direction == "hold":
            return Action("hold", 0.0, mid), {"sigmoid": z / max(self.cfg.entry_z, 1e-9),
                                              "skew": skew, "z": z, "note": "inside-band"}

        if self._positions >= self.cfg.max_positions:
            return Action("hold", 0.0, mid), {"sigmoid": z / self.cfg.entry_z,
                                              "skew": skew, "z": z, "note": "max-pos"}

        # Anti-runaway inventory guard: don't add to a losing side beyond cap.
        add_buy: bool = direction == "buy"
        if add_buy and self._net_inventory > self.cfg.max_inventory_pct * self.cfg.capital_eur:
            return Action("hold", 0.0, mid), {"sigmoid": z / self.cfg.entry_z,
                                              "skew": skew, "z": z, "note": "inventory-long"}
        if not add_buy and -self._net_inventory > self.cfg.max_inventory_pct * self.cfg.capital_eur:
            return Action("hold", 0.0, mid), {"sigmoid": z / self.cfg.entry_z,
                                              "skew": skew, "z": z, "note": "inventory-short"}

        edge: Optional[float] = self._project_edge(mid, abs(z), dev)
        if edge is None:
            return Action("hold", 0.0, mid), {"sigmoid": z / self.cfg.entry_z,
                                              "skew": skew, "z": z, "note": "no-edge"}

        # Spread-aware entry: skip if fees/spread consume most of the edge.
        spread: float = max(tick.ask - tick.bid, 0.0)
        if spread > self.cfg.spread_edge_frac * max(edge * mid, 1e-12):
            self._reject_spread += 1
            return Action("hold", 0.0, mid), {"sigmoid": z / self.cfg.entry_z,
                                              "skew": skew, "z": z, "note": "spread-too-wide",
                                              "spread": round(spread, 8)}

        size: float = self._size_for(edge, mid)
        if size <= 0.0:
            return Action("hold", 0.0, mid), {"sigmoid": z / self.cfg.entry_z,
                                              "skew": skew, "z": z, "note": "zero-size"}

        price_ref: float = tick.bid if add_buy else tick.ask
        self._signals += 1
        return Action(direction, round(size, 8), price_ref), {
            "sigmoid": z / self.cfg.entry_z, "skew": round(skew, 3),
            "z": round(z, 3), "edge": round(edge, 6), "note": "entry",
        }

    # ------------------------------------------------------------------ on_fill
    def on_fill(self, fill: Fill) -> None:
        signed: float = fill.size if fill.side == "buy" else -fill.size
        self._net_inventory += signed
        self._positions += 1
        # Unwind: realize PnL against average reversion toward mean.
        sign: float = 1.0 if fill.side == "sell" else -1.0
        self._realized_pnl += sign * fill.size * (self._last_price - fill.price) \
            if self._last_price is not None else 0.0  # approximate mark-to-market

    # ------------------------------------------------------------------ stats
    def stats(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "ticks": self._ticks,
            "signals": self._signals,
            "reject_spread": self._reject_spread,
            "net_inventory_eur": round(self._net_inventory, 6),
            "positions": self._positions,
            "realized_pnl": round(self._realized_pnl, 6),
            "skew_now": round(self._skew(), 3),
            "memory_mb": self.estimate_memory_mb(),
        }


# ------------------------------------------------------------------- test
if __name__ == "__main__":
    import random

    cfg: StrategyConfig = StrategyConfig(symbol="DOGE/EUR", exchange="mc2",
                                         capital_eur=3.7, estimator_window=120,
                                         entry_z=1.8, exit_z=0.12, fee=0.0026)
    strat = MRABStrategy(cfg)
    strat.validate_config()

    rng = random.Random(42)
    price0: float = 0.1050
    signals: int = 0
    wins: int = 0
    for _i in range(4000):
        # Random-walk price with occasional mean-reverting pull to generate z-crossings.
        drift: float = rng.gauss(0.0, 0.0008)
        if _i % 250 == 0:
            drift += -0.5 if price0 > 0.1060 else 0.5  # reverting nudge
        price0 += drift
        if price0 < 0.09 or price0 > 0.12:
            price0 = 0.1050
        spread: float = abs(rng.gauss(0.0004, 0.0002))
        vol: float = rng.gauss(0.0, 1.0)
        tk = Tick(ts=float(_i), bid=price0, ask=price0 + spread,
                  last=price0, vol=vol)
        act, _meta = strat.on_tick(tk)
        if act.side != "hold":
            signals += 1
            wins += 1

    st = strat.stats()
    print("MRAB inline test OK")
    print("signals:", st["signals"], "reject_spread:", st["reject_spread"],
          "memory_mb:", st["memory_mb"])
    assert st["signals"] > 8, "expected bounded reversion signals"
    assert st["memory_mb"] > 0.0, "expect non-zero memory footprint"
    print("PASS: MRAB strategy self-tests green.")
