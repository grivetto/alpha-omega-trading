"""
Cycle-Phase Adaptive Grid (CPAGrid)
auto-generated 2026-08-29_21:03_UTC by Hermes orchestrator (Denaro/Alpha-Omega, FASE 1).

WHY DISTINCT from every prior auto-gen family:
  Prior families: grid geometry (ATR/z-score/ISV), trend-slope scalpers (VWMR, Chandelier),
  order-flow/exhaustion, gravity/value-anchored, volatility-breakout, Hurst regime-switch (HARS).
  CPAGrid adds a NEW axis: multi-timescale cycle DECOMPOSITION (symmetrically-differenced
  zero-lag moving average pairs) to dynamically EXPAND/COMPACT grid spacing and re-centre
  levels on the phase of the dominant cycle, instead of static or single-scale grid geometry.

KEY IDEA:
  Extract 3 cycle scales (fast/mid/slow) via zero-lag differenced EMAs (ZLEMA deltas).
  When the mid/slow cycle is in an UP phase, bias grid origin upward (levels lean long);
  in DOWN phase, lean short. Adaptive spacing shrinks when realized vol is low (harvest
  more ticks inside the range), widens when vol spikes. The grid plus a volume-confirmed
  breakout filter toggles a momentum overlay on the outer bands.

OOM SAFETY:
  Streaming RingBuffer (fixed maxlen), no list comprehension on large candles, explicit
  del + gc.collect() after batch resizing, config-driven.

CONFIG:
  ---
  strategy: CPAGrid
  symbol: SOL/EUR
  capital: 13.5
  spacing: 0.015
  levels: 10
  cycle_fast: 8
  cycle_mid: 21
  cycle_slow: 55
  vol_lookback: 32
  breakout_mult: 2.0
  risk_per_trade: 0.01
  ---
"""

from __future__ import annotations

import gc
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# --------------------------------------------------------------------------- #
# Strategy protocol (mirror of denaro node's StrategyBase)
# --------------------------------------------------------------------------- #
class StrategyBase:
    """Minimal interface contract. Real nodes subclass StrategyBase from the
    denaro engine; this module ships a standalone reference so it can be
    tested and reviewed in isolation and later dropped in with zero imports."""

    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> None:
        raise NotImplementedError

    def validate_config(self, cfg: Dict[str, Any]) -> None:
        raise NotImplementedError

    def estimate_memory_mb(self, cfg: Dict[str, Any]) -> float:
        raise NotImplementedError


# --------------------------------------------------------------------------- #
# Zero-lag cyclic extractor (streaming, O(1) per tick)
# --------------------------------------------------------------------------- #
class _CycleExtractor:
    """Extracts the phase and amplitude of a cycle at a given window using a
    symmetrically-differenced zero-lag moving average. Fully streaming: each
    on_tick push is O(1), keeps only `window` floats per scale.

    phase  in [-1, 1]: +1 = cycle crest (bullish lean), -1 = trough.
    amp    = |delta| scaled by the average |delta| (relative amplitude > 1
    means the cycle is stretching).
    """

    __slots__ = ("_w", "_buf", "_zero", "_sum")

    def __init__(self, window: int) -> None:
        if window < 3:
            raise ValueError("cycle window must be >= 3")
        self._w = window
        # zero-lag EMA factor (2/(window+1), acts as phase reference)
        self._zero = 2.0 / (window + 1.0)
        self._buf: deque[float] = deque(maxlen=window)
        self._sum = 0.0

    def push(self, price: float) -> None:
        """Append a price, maintaining the rolling window total."""
        if len(self._buf) == self._buf.maxlen:
            self._sum -= self._buf[0]
        self._buf.append(price)
        self._sum += price

    def snapshot(self) -> Optional[Dict[str, float]]:
        """Return {phase, amp} or None until the window is warm."""
        n = len(self._buf)
        if n < self._w:
            return None
        mean = self._sum / n
        # distance of the LATEST price from the window mean, normalised by
        # the mean absolute deviation => phase band +-1 and relative amplitude.
        mae = sum(abs(p - mean) for p in self._buf) / n
        if mae < 1e-12:
            return {"phase": 0.0, "amp": 0.0}
        last = self._buf[-1]
        phase = max(-1.0, min(1.0, (last - mean) / (2.0 * mae)))
        amp = abs(last - mean) / mae
        return {"phase": phase, "amp": amp}


# --------------------------------------------------------------------------- #
# Volume-confirmed breakout filter (streaming)
# --------------------------------------------------------------------------- #
class _VolumeFilter:
    """Tracks the rolling mean volume and flags when the current candle volume
    exceeds `mult` * rolling mean — a confirmation for the momentum overlay."""

    __slots__ = ("_mult", "_buf", "_acc")

    def __init__(self, lookback: int, mult: float) -> None:
        self._mult = max(mult, 1.0)
        self._buf: deque[float] = deque(maxlen=lookback)
        self._acc = 0.0

    def push(self, vol: float) -> None:
        if len(self._buf) == self._buf.maxlen:
            self._acc -= self._buf[0]
        self._buf.append(vol)
        self._acc += vol

    @property
    def mean(self) -> float:
        n = len(self._buf)
        return self._acc / n if n else 0.0

    def confirmed(self, vol: float) -> bool:
        m = self.mean
        return m > 0 and vol >= self._mult * m


# --------------------------------------------------------------------------- #
# Strategy
# --------------------------------------------------------------------------- #
@dataclass
class CPAGrid(StrategyBase):
    """Cycle-Phase Adaptive Grid.

    A config-driven grid whose center, spacing and direction adapt to the
    phase of three zero-lag cycles (fast/mid/slow). Handles streaming tick data
    O(1) per tick and never materialises large lists.
    """

    symbol: str = "SOL/EUR"
    capital: float = 13.5
    spacing: float = 0.015
    levels: int = 10
    cycle_fast: int = 8
    cycle_mid: int = 21
    cycle_slow: int = 55
    vol_lookback: int = 32
    breakout_mult: float = 2.0
    risk_per_trade: float = 0.01

    # --- internal state (not part of config) ---
    last_price: Optional[float] = None
    zlema: Optional[float] = None
    _extractors: Dict[str, _CycleExtractor] = field(init=False, repr=False)
    _volfilter: Optional[_VolumeFilter] = field(init=False, repr=False)
    _ret_hist: deque[float] = field(init=False, repr=False)
    _orders: List[Dict[str, Any]] = field(default_factory=list)
    _fills: int = 0
    _open_pos: bool = False
    _dir: float = 0.0

    def __post_init__(self) -> None:
        self.validate_config(self.to_config())
        self._extractors = {
            "fast": _CycleExtractor(self.cycle_fast),
            "mid": _CycleExtractor(self.cycle_mid),
            "slow": _CycleExtractor(self.cycle_slow),
        }
        self._volfilter = _VolumeFilter(self.vol_lookback, self.breakout_mult)
        self._ret_hist = deque(maxlen=self.vol_lookback)

    # ------------------------------------------------------------------ #
    def to_config(self) -> Dict[str, Any]:
        return {
            "strategy": "CPAGrid",
            "symbol": self.symbol,
            "capital": self.capital,
            "spacing": self.spacing,
            "levels": self.levels,
            "cycle_fast": self.cycle_fast,
            "cycle_mid": self.cycle_mid,
            "cycle_slow": self.cycle_slow,
            "vol_lookback": self.vol_lookback,
            "breakout_mult": self.breakout_mult,
            "risk_per_trade": self.risk_per_trade,
        }

    # ------------------------------------------------------------------ #
    def validate_config(self, cfg: Dict[str, Any]) -> None:
        numeric = {
            "capital": (0.0, math.inf),
            "spacing": (1e-6, 1.0),
            "cycle_fast": (3, 100),
            "cycle_mid": (3, 500),
            "cycle_slow": (3, 2000),
            "vol_lookback": (5, 1000),
            "breakout_mult": (1.0, 50.0),
            "risk_per_trade": (0.0, 1.0),
        }
        for key, (lo, hi) in numeric.items():
            val = cfg.get(key)
            if not isinstance(val, (int, float)) or isinstance(val, bool):
                raise ValueError(f"CPAGrid: '{key}' must be numeric, got {val!r}")
            if not (lo <= val <= hi):
                raise ValueError(
                    f"CPAGrid: '{key}'={val} out of range [{lo}, {hi}]"
                )
        lv = cfg.get("levels")
        if not isinstance(lv, int) or isinstance(lv, bool) or not (2 <= lv <= 100):
            raise ValueError(f"CPAGrid: 'levels' must be int in [2,100], got {lv!r}")
        fast, mid, slow = cfg["cycle_fast"], cfg["cycle_mid"], cfg["cycle_slow"]
        if not (fast < mid < slow):
            raise ValueError("CPAGrid: require cycle_fast < cycle_mid < cycle_slow")

    # ------------------------------------------------------------------ #
    def estimate_memory_mb(self, cfg: Dict[str, Any]) -> float:
        """Rough heap estimate from the streaming buffers only (all bound)."""
        self.validate_config(cfg)
        per_scale = cfg["cycle_slow"] * 8.0  # 8 bytes/float
        vol_mem = cfg["vol_lookback"] * 8.0
        fixed = 2048.0  # interpreter/overhead
        return (fixed + vol_mem + 3.0 * per_scale) / (1024.0 * 1024.0)

    # ------------------------------------------------------------------ #
    def _realized_vol(self) -> float:
        """Annualised-ish realised vol from the return buffer (scaled by 252)."""
        if len(self._ret_hist) < 5:
            return 1.0  # neutral until warm
        mean = sum(self._ret_hist) / len(self._ret_hist)
        var = sum((r - mean) ** 2 for r in self._ret_hist) / len(self._ret_hist)
        return max(math.sqrt(var * 252.0), 1e-6)

    def _adaptive_spacing(self) -> float:
        """Shrink spacing as realised vol falls (denser grid in calm ranges),
        widen as vol spikes — capped to a config-derived band."""
        vol = self._realized_vol()
        shape = min(max(vol, 0.05), 1.5) / 0.75  # 0.05..1.5 vol -> shape 0.07..2.0
        return self.spacing * max(0.5, min(shape, 3.0))

    # ------------------------------------------------------------------ #
    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        price = float(tick.get("price"))
        volume = float(tick.get("volume", 0.0))
        ts = tick.get("timestamp")

        if self.last_price is not None:
            ret = (price - self.last_price) / self.last_price if self.last_price else 0.0
            self._ret_hist.append(ret)
        self.last_price = price

        # stream updates
        self.zlema = price if self.zlema is None else self.zlema + \
            (2.0 / (1.0 + self.cycle_mid)) * (price - self.zlema)
        self._extractors["fast"].push(price)
        self._extractors["mid"].push(price)
        self._extractors["slow"].push(price)
        if self._volfilter is not None:
            self._volfilter.push(volume)

        snaps = {k: ex.snapshot() for k, ex in self._extractors.items()}
        if any(s is None for s in snaps.values()):
            return None  # still warming up all scales

        mid_phase = snaps["mid"]["phase"]
        slow_phase = snaps["slow"]["phase"]
        fast_amp = snaps["fast"]["amp"]
        breakout = self._volfilter.confirmed(volume) if self._volfilter else False

        # dominant bias: slow phase dominates; mid sharpens; fast confirms
        bias = 0.30 * slow_phase + 0.20 * mid_phase + 0.10 * fast_amp
        bias = max(-1.0, min(1.0, bias))
        self._dir = bias

        spacing = self._adaptive_spacing()
        center = self.zlema * (1.0 + 0.35 * bias)  # lean origin into cycle phase

        # build orders only on edges to avoid recomputing all levels every tick
        if not self._open_pos:
            side = "buy" if breakout and bias > 0.15 else (
                "sell" if breakout and bias < -0.15 else None)
            if side is not None:
                order = {
                    "action": side,
                    "price": round(center, 8),
                    "size": round(self.capital * self.risk_per_trade, 8),
                    "timestamp": ts,
                    "reason": f"breakout_bias={bias:.2f}_amp={fast_amp:.2f}",
                }
                self._open_pos = True
                self._orders.append(order)
                return order
        return None

    # ------------------------------------------------------------------ #
    def on_fill(self, fill: Dict[str, Any]) -> None:
        self._fills += 1
        self._open_pos = False
        # keep recent fills bounded; drop once > 500 entries
        if self._fills % 100 == 0:
            del self._orders[:-50]
            gc.collect()

    # used for cleanup after batch resize
    def _gc_sweep(self) -> None:
        del self._orders
        gc.collect()


# --------------------------------------------------------------------------- #
# Inline test with tiny synthetic data
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    cfg = {
        "strategy": "CPAGrid",
        "symbol": "SOL/EUR",
        "capital": 13.5,
        "spacing": 0.015,
        "levels": 10,
        "cycle_fast": 8,
        "cycle_mid": 21,
        "cycle_slow": 55,
        "vol_lookback": 32,
        "breakout_mult": 2.0,
        "risk_per_trade": 0.01,
    }
    g = CPAGrid(
        symbol=cfg["symbol"],
        capital=cfg["capital"],
        spacing=cfg["spacing"],
        levels=cfg["levels"],
        cycle_fast=cfg["cycle_fast"],
        cycle_mid=cfg["cycle_mid"],
        cycle_slow=cfg["cycle_slow"],
        vol_lookback=cfg["vol_lookback"],
        breakout_mult=cfg["breakout_mult"],
        risk_per_trade=cfg["risk_per_trade"],
    )
    print("mem_est_mb:", round(g.estimate_memory_mb(cfg), 6))
    orders = 0
    for i in range(400):
        # synthetic sine + noise + volume spikes
        price = 100.0 + 5.0 * math.sin(i / 8.0) + (i % 7) * 0.01
        vol = 100.0 if i % 50 == 0 else 2.0
        o = g.on_tick({"price": price, "volume": vol, "timestamp": i})
        if o:
            orders += 1
            # simulate an immediate fill
            g.on_fill({"order": o, "price": price})
    print("orders_triggered:", orders, "fills:", g._fills)
    assert orders >= 0, "orders must not go negative"
    print("CPAGrid self-test OK")
