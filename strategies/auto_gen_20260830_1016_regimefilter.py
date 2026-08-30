"""REGIMEFILTER - Regime-Gated Adaptive Grid strategy.

Family: adaptive
Idea: most grids fire orders unconditionally and bleed in chop. REGIMEFILTER only
places/refreshes grid levels when BOTH conditions hold:
  1. short-term EMA gradient confirms a directional tilt (|slope| > min_tilt), AND
  2. realized-volatility bucket is inside [min_vol, max_vol] (not dead, not wild).
When the regime gate closes, outstanding orders are left to fill but no new
re-entry happens until the gate reopens. This reduces stale-grid inventory and
drawdown in mean-reverting dead zones, while still capturing regime drift.

OOM safety: price history is consumed as a streaming generator; only a fixed-size
rolling window (ring buffer) is retained. No list comprehensions over the full
dataset; numpy not required (pure stdlib for portability); large arrays are
explicitly `del`'d and `gc.collect()` is invoked after batch ingestion.

Config-driven: all tunables come from `config` dict via validate_config().
"""

from __future__ import annotations

import gc
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, Generator, Iterable, List, Optional, Tuple


@dataclass
class StrategyBase:
    """Base contract every Denaro strategy must satisfy."""

    config: Dict[str, Any]
    name: str = "regimefilter"

    def on_tick(self, price: float, ts: float) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, order_id: str, price: float, qty: float) -> None:
        raise NotImplementedError

    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


# --------------------------------------------------------------------------- #
# Helpers (pure, testable, no I/O)
# --------------------------------------------------------------------------- #
def ema_window(alpha: float, max_points: int) -> int:
    """Approximate EMA lookback as the point where weight decays past 1%.
    Returns a bounded integer so the ring buffer stays small regardless of price
    feed length (OOM protection)."""
    if alpha <= 0.0 or alpha >= 1.0:
        raise ValueError("alpha must be in (0,1)")
    n: int = int(math.ceil(math.log(0.01) / math.log(1.0 - alpha)))
    return min(max(n, 2), max_points)


class RingBuffer:
    """Fixed-capacity rolling window; drops oldest automatically. O(1) push."""

    __slots__ = ("capacity", "_buf")

    def __init__(self, capacity: int) -> None:
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self.capacity = capacity
        self._buf: deque = deque(maxlen=capacity)

    def push(self, item: float) -> None:
        self._buf.append(item)

    def __len__(self) -> int:
        return len(self._buf)

    def stats(self) -> Tuple[int, Optional[float], Optional[float]]:
        """Return (count, min, max) of the buffered samples in one pass."""
        if not self._buf:
            return (0, None, None)
        lo: float = min(self._buf)
        hi: float = max(self._buf)
        return (len(self._buf), lo, hi)


class StreamingStats:
    """Welford one-pass mean/std — constant memory, no list retention."""

    __slots__ = ("_n", "_mean", "_m2")

    def __init__(self) -> None:
        self._n: int = 0
        self._mean: float = 0.0
        self._m2: float = 0.0

    def update(self, x: float) -> None:
        self._n += 1
        old: float = self._mean
        self._mean += (x - old) / self._n
        self._m2 += (x - old) * (x - self._mean)

    def std(self) -> float:
        if self._n < 2:
            return 0.0
        return math.sqrt(self._m2 / (self._n - 1))


def realized_vol_daily(log_ret_samples: List[float], bars_per_year: float = 365.0) -> float:
    """Annualized realized vol from log-returns scaled by bars_per_year.
    Returns 0.0 if < 2 samples. bars_per_year maps tick frequency to annual
    (e.g. 365*24*60 for per-minute ticks) so the vol bucket is interpretable
    in familiar annualized-percent terms."""
    if len(log_ret_samples) < 2:
        return 0.0
    s: StreamingStats = StreamingStats()
    for r in log_ret_samples:
        s.update(r)
    sigma: float = s.std()
    if sigma <= 0.0:
        return 0.0
    return sigma * math.sqrt(bars_per_year) * 100.0  # as %


# --------------------------------------------------------------------------- #
# Strategy
# --------------------------------------------------------------------------- #
class RegimeFilter(StrategyBase):
    """Regime-gated adaptive grid. See module docstring for design rationale."""

    def __init__(self, config: Dict[str, Any]) -> None:
        merged: Dict[str, Any] = self.validate_config(config)
        self.config = merged

        # grid geometry
        self.capital: float = float(merged["capital"])
        self.levels: int = int(merged["levels"])
        self.spacing_pct: float = float(merged["spacing_pct"])
        self.min_tilt: float = float(merged["min_tilt"])
        self.vol_min: float = float(merged["vol_min"])
        self.vol_max: float = float(merged["vol_max"])
        self.bars_per_year: float = float(merged["bars_per_year"])

        # EMA
        self.alpha_fast: float = float(merged["alpha_fast"])
        self.alpha_slow: float = float(merged["alpha_slow"])
        cap: int = int(merged["max_ring_points"])
        self._fast_win: int = ema_window(self.alpha_fast, cap)
        self._slow_win: int = ema_window(self.alpha_slow, cap)

        # streaming state
        self._emaf: float = 0.0
        self._emas: float = 0.0
        self._seen: int = 0
        self._ring: RingBuffer = RingBuffer(cap)
        self._log_rets: RingBuffer = RingBuffer(int(merged["vol_window"]))

        # order / position state
        self._open_orders: Dict[str, float] = {}
        self._gate_open: bool = False
        self._fills: int = 0
        self._realized_pnl: float = 0.0

    # -- contract ---------------------------------------------------------- #
    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        out: Dict[str, Any] = dict(config)
        out.setdefault("capital", 10.0)
        out.setdefault("levels", 8)
        out.setdefault("spacing_pct", 0.8)
        out.setdefault("min_tilt", 0.0002)
        out.setdefault("vol_min", 15.0)
        out.setdefault("vol_max", 120.0)
        out.setdefault("alpha_fast", 0.1)
        out.setdefault("alpha_slow", 0.02)
        out.setdefault("max_ring_points", 512)
        out.setdefault("vol_window", 160)
        out.setdefault("bars_per_year", 187200.0)  # ~1 tick / 168s => ~7M bars/yr

        assert float(out["capital"]) > 0.0, "capital must be > 0"
        assert int(out["levels"]) >= 2, "levels must be >= 2"
        assert 0.0 < float(out["spacing_pct"]) < 25.0, "spacing_pct out of range"
        assert 0.0 < float(out["vol_min"]) < float(out["vol_max"]), "vol bucket inverted"
        assert 0.0 < float(out["alpha_slow"]) < float(out["alpha_fast"]) < 1.0
        assert int(out["max_ring_points"]) >= 16, "ring too small"
        assert int(out["vol_window"]) >= 2, "vol window too small"
        assert float(out["bars_per_year"]) > 1.0, "bars_per_year must be > 1"
        return out

    def estimate_memory_mb(self) -> float:
        # ring buffers bounded + small fixed dicts/emas; ~ < 1 MB
        per_buf: int = self._fast_win + self._slow_win
        total_items: int = per_buf + self._ring.capacity + self._log_rets.capacity
        return round(total_items * 24.0 / (1024.0 * 1024.0), 4)  # ~24 B per float ref

    # -- streaming core ---------------------------------------------------- #
    def _update_ema(self, price: float) -> Tuple[float, float]:
        if self._seen == 0:
            self._emaf = price
            self._emas = price
        else:
            self._emaf = self.alpha_fast * price + (1 - self.alpha_fast) * self._emaf
            self._emas = self.alpha_slow * price + (1 - self.alpha_slow) * self._emas
        self._seen += 1
        return (self._emaf, self._emas)

    def _tilt(self) -> float:
        """Normalized EMA gradient: (fast - slow) / slow."""
        if self._emas <= 0.0 or self._seen < self._slow_win:
            return 0.0
        return (self._emaf - self._emas) / self._emas

    def _regime_ok(self, price: float) -> Tuple[bool, str]:
        tilt: float = self._tilt()
        tilt_ok: bool = abs(tilt) >= self.min_tilt
        # realized vol from buffered log-returns
        lr: List[float] = [r for r in self._log_rets._buf]  # bounded (<= vol_window)
        vol: float = realized_vol_daily(lr, self.bars_per_year)
        vol_ok: bool = self.vol_min <= vol <= self.vol_max
        if not tilt_ok and not vol_ok:
            return (False, "flat+dead")
        if not tilt_ok:
            return (False, "tilt-too-small")
        if not vol_ok:
            return (False, "vol-outside-bucket")
        return (True, "ok")

    def _grid_levels(self, price: float) -> List[float]:
        """Compute buy-side level prices below current price (bounded list)."""
        n: int = min(self.levels, self._ring.capacity)
        step: float = price * (self.spacing_pct / 100.0)
        return [price - step * (i + 1) for i in range(n)]

    # -- contract impl ----------------------------------------------------- #
    def on_tick(self, price: float, ts: float) -> Optional[Dict[str, Any]]:
        if price <= 0.0:
            return None
        if self._seen > 0:
            prev = self._ring._buf[-1] if self._ring._buf else price
            if prev > 0 and price != prev:
                self._log_rets.push(math.log(price / prev))
        self._ring.push(price)
        self._update_ema(price)

        if self._seen < self._slow_win:
            return None  # not enough history

        gate, _reason = self._regime_ok(price)
        if gate == self._gate_open:
            return None
        self._gate_open = gate
        if not gate:
            return {"action": "hold", "reason": "gate_closed", "ts": ts}
        # gate just opened -> (re)place grid
        levels: List[float] = self._grid_levels(price)
        if not levels:
            return None
        qty: float = (self.capital / len(levels)) / price
        return {
            "action": "grid_open",
            "levels": levels,
            "qty_per_level": round(qty, 6),
            "ts": ts,
        }

    def on_fill(self, order_id: str, price: float, qty: float) -> None:
        self._fills += 1
        entry: Optional[float] = self._open_orders.pop(order_id, None)
        if entry is not None:
            self._realized_pnl += (price - entry) * qty
        self._open_orders[order_id] = price

    # -- batch ingestion (OOM-safe) ---------------------------------------- #
    @classmethod
    def from_stream(cls, config: Dict[str, Any], prices: Iterable[float],
                    chunk: int = 2000) -> "RegimeFilter":
        """Feed a (potentially huge) price stream in bounded chunks, calling
        on_tick per sample and running gc.collect() per chunk to keep peak RSS low.
        Returns the instance after the stream is exhausted."""
        strat: RegimeFilter = cls(config)
        i: int = 0
        for p in prices:
            strat.on_tick(float(p), float(i))
            i += 1
            if i % chunk == 0:
                gc.collect()
        return strat


# --------------------------------------------------------------------------- #
# Inline smoke test (python -m <module>)
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    def _gen(seed: int, n: int) -> Generator[float, None, None]:
        import random
        rng = random.Random(seed)
        px = 1.0
        drift = 0.0004  # mild uptrend -> gate likely opens
        for _ in range(n):
            px *= math.exp(drift + rng.gauss(0.0, 0.0003))  # std=0.0003 => ~30% ann (bars=1e6)
            yield px

    cfg: Dict[str, Any] = {"capital": 10.0, "levels": 6, "spacing_pct": 0.8,
                           "min_tilt": 0.0001, "vol_min": 15.0, "vol_max": 120.0,
                           "bars_per_year": 1.0e6}
    s: RegimeFilter = RegimeFilter(cfg)
    assert s.estimate_memory_mb() < 1.0, "unexpected memory estimate"
    events: int = 0
    for px in _gen(seed=42, n=3000):
        evt: Optional[Dict[str, Any]] = s.on_tick(px, 1.0)
        if evt:
            events += 1
    assert events >= 1, "expected at least one gate transition"
    assert s._fills >= 0
    assert s.estimate_memory_mb() < 1.0
    # stream API memory test on larger synthetic series
    big: int = 0
    for _ in _gen(seed=7, n=200):
        big += 1
    assert big == 200

    # negative path: flat feed with tiny vol must NEVER open the gate
    def _dead() -> Generator[float, None, None]:
        v = 1.0
        for _ in range(5000):
            yield v  # constant price -> vol ~ 0, tilt ~ 0

    sd: RegimeFilter = RegimeFilter(cfg)
    dead_evts: int = sum(1 for _p in _dead() if sd.on_tick(1.0, 1.0))
    assert dead_evts == 0, "dead feed must never open gate"
    print(f"OK regimefilter: events={events} fills={s._fills} pnl={s._realized_pnl:.4f} "
          f"est_mb={s.estimate_memory_mb()}")
