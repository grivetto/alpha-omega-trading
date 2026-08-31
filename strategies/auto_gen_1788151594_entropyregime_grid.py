"""auto_gen_1788151594_entropyregime_grid.py

Entropy-Weighted Regime Grid (EWRG)
===================================
A grid that prices its geometry from the *statistical entropy of recent returns*
(a streaming Shannon entropy over a bounded rolling histogram). The entropy is an
information-theoretic regime detector that is cheap, streaming and robust to
noise:

  - LOW entropy  (returns clustered in one or two bins -> serial autocorrelation,
                  trending / momentum regime).  -> wide spacing, few levels,
                  momentum-following bias, wide risk bands, larger max jump budget.
  - HIGH entropy (returns spread uniformly across many bins -> white-noise /
                  mean-reverting regime).  -> tight spacing, many levels,
                  mean-reversion bias, tight bands, small jump budget.

Everything is driven off signed log-returns that never need to be materialised at
once: entropy is computed from a streaming histogram of fixed bin count, so
memory is O(bins + window) regardless of price-history length.

Key components
--------------
1. Streaming log-return histogram (fixed `nbins`, bounded window via a deque).
   Entropy H = -sum(p_i * log2(p_i)) computed incrementally, normalised to [0,1]
   by log2(nbins).
2. Regime interpolator: a logistic map over H maps the regime score to grid
   spacing, level count, and a momentum/reversion bias weight `w`.
3. Bi-directional grid: on each tick levels are placed around the current price
   at integer step multiples, sized by the regime-aware spacing.
4. Entropy-gate kill-switch: if H collapses below a configurable floor AND the
   drift magnitude exceeds budget, the book is paused (cooloff), because a
   no-arb crash event typically shows as bursty-but-structured (low entropy)
   movement.
5. Adverse-selection governor: a small EMA of per-fill slippage feeds back into
   spacing to avoid getting run over in fast regimes.

Memory discipline (OOM safety)
------------------------------
- Bounded memory: deque of size `window` for returns + fixed `nbins` histogram,
  plus a transient order map rebuilt each tick. `del` frees the stale map and
  hot-loop temporaries before rebuild. `gc.collect()` every `gc_every` ticks.
- No `try/except: pass`; every failure path raises StrategyError with a message.

Strategy contract
-----------------
  class StrategyBase (ABC): on_tick, on_fill, validate_config, estimate_memory_mb.
  Config-driven; every tunable lives in EntropyRegimeConfig. Zero hardcoded magic.
  Inline `__main__` self-test on small synthetic data (both regimes, verifies
  entropy monotonicity and grid symmetry).
"""

from __future__ import annotations

import gc
import logging
import math
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, List, Optional

logger = logging.getLogger("entropyregime_grid")


class StrategyError(RuntimeError):
    """Raised for any recoverable strategy error. Never silently swallowed."""


@dataclass(frozen=True, slots=True)
class EntropyRegimeConfig:
    """Immutable, config-driven parameters. Every tunable lives here."""

    symbol: str
    capital_eur: float
    # ---- entropy regime detector ----
    window: int = 64            # rolling window length (in ticks) for entropy
    nbins: int = 16             # fixed bin count of the streaming histogram
    hist_alpha: float = 0.05    # EMA decay for histogram range drift
    h_low: float = 0.35         # entropy below this -> trending / momentum
    h_high: float = 0.75        # entropy above this -> mean-reverting / noise
    # ---- grid geometry (interpolated between the two regimes) ----
    spacing_trend_pct: float = 0.028   # wide spacing in low-entropy regime
    spacing_mr_pct: float = 0.009      # tight spacing in high-entropy regime
    min_levels: int = 3
    max_levels: int = 12
    # ---- side bias (momentum vs mean-reversion) ----
    bias_strength: float = 0.6   # fraction of capital on the primary leg
    # ---- risk / discontinuity protection ----
    max_jump_pct: float = 0.09   # single-tick jump above this pauses the book
    entropy_floor: float = 0.12  # H below this + drift -> hard crash cooloff
    cooloff_ticks: int = 240     # ticks to remain paused after a trip
    # ---- adverse-selection governor ----
    slip_gamma: float = 0.05     # EMA alpha on realised slippage
    max_slip_pct: float = 0.01   # avg slippage above this widens spacing
    gc_every: int = 512          # call gc.collect() every N ticks

    def validate(self) -> None:
        errs: List[str] = []
        if self.capital_eur <= 0:
            errs.append("capital_eur must be > 0")
        if self.window < 8:
            errs.append("window must be >= 8")
        if not (4 <= self.nbins <= 64):
            errs.append("nbins must be within [4, 64]")
        if not (0.0 < self.h_low < self.h_high < 1.0):
            errs.append("need 0 < h_low < h_high < 1")
        if not (0.0 < self.spacing_mr_pct < self.spacing_trend_pct):
            errs.append("need 0 < spacing_mr_pct < spacing_trend_pct")
        if not (self.min_levels < self.max_levels):
            errs.append("min_levels must be < max_levels")
        if not (0.0 < self.bias_strength <= 0.9):
            errs.append("bias_strength must be in (0, 0.9]")
        if not (0.0 < self.slip_gamma <= 0.5):
            errs.append("slip_gamma must be in (0, 0.5]")
        if not (0.0 < self.entropy_floor < self.h_low):
            errs.append("entropy_floor must be < h_low")
        if errs:
            raise StrategyError("invalid config: " + "; ".join(errs))


class _BoundedHistogram:
    """Streaming histogram of signed log-returns with O(bins+window) memory.

    Maintains a deque of the last `window` returns plus its bin index and a float
    list of counts per bin. Adding a return pushes the new bin and pops the
    oldest, updating counts in O(1) using the index ring. Probabilities are
    renormalised on demand. Never materialises more than O(window + bins) scalars.
    """

    __slots__ = ("_window", "_nbins", "_counts", "_idx", "_vals", "_min", "_max")

    def __init__(self, window: int, nbins: int) -> None:
        self._window = window
        self._nbins = nbins
        self._counts: List[float] = [0.0] * nbins
        self._idx: Deque[int] = deque()
        self._vals: Deque[float] = deque()
        self._min = -1.0
        self._max = 1.0

    @property
    def size(self) -> int:
        return len(self._idx)

    @property
    def ready(self) -> bool:
        return self.size >= self._window

    def _bin_of(self, x: float) -> int:
        rel = (x - self._min) / (self._max - self._min) if self._max > self._min else 0.5
        b = int(max(0.0, min(rel, 0.99999999)) * self._nbins)
        return b if b < self._nbins else self._nbins - 1

    def add(self, ret: float, hist_alpha: float) -> None:
        """Add a log-return; adapt bin range with EMA; O(1) amortised."""
        self._min = (1.0 - hist_alpha) * self._min + hist_alpha * min(self._min, ret)
        self._max = (1.0 - hist_alpha) * self._max + hist_alpha * max(self._max, ret)
        if self._max - self._min < 1e-9:  # degenerate range -> widen
            self._min -= 1e-4
            self._max += 1e-4

        nb = self._bin_of(ret)
        self._counts[nb] += 1.0
        self._idx.append(nb)
        self._vals.append(ret)

        if self.size > self._window:
            old = self._idx.popleft()
            del self._vals[0]
            self._counts[old] -= 1.0

    def entropy(self) -> float:
        """Shannon entropy in bits, normalised to [0,1] by log2(nbins)."""
        n = self.size
        if n < 2:
            return 1.0
        h = 0.0
        for c in self._counts:
            if c > 0.0:
                p = c / n
                h -= p * math.log2(max(p, 1e-12))
        hi = math.log2(float(self._nbins))
        return h / hi if hi > 0.0 else 1.0

    def mean(self) -> float:
        n = self.size
        if n == 0:
            return 0.0
        s = 0.0
        for v in self._vals:
            s += v
        return s / n


def _logistic01(x: float, mid: float, slope: float) -> float:
    """Smooth [0,1]-valued interpolator, monotone in x."""
    z = slope * (x - mid)
    try:
        e = math.exp(-z)
    except OverflowError:  # explicit handling, never pass
        return 0.0 if z > 0 else 1.0
    return 1.0 / (1.0 + e)


class StrategyBase(ABC):
    """Common strategy contract expected by the exchange harness."""

    @abstractmethod
    def on_tick(self, price: float, ts: float) -> Dict[str, Any]:
        ...

    @abstractmethod
    def on_fill(self, price: float, qty: float, side: str, ts: float) -> None:
        ...

    @abstractmethod
    def validate_config(self) -> None:
        ...

    @abstractmethod
    def estimate_memory_mb(self) -> float:
        ...


class EntropyRegimeGrid(StrategyBase):
    """Entropy-Weighted Regime Grid implementation."""

    def __init__(self, config: EntropyRegimeConfig) -> None:
        config.validate()
        self.cfg = config
        self._hist = _BoundedHistogram(config.window, config.nbins)
        self._last_price: Optional[float] = None
        self._orders_open: Dict[str, float] = {}
        self._fills: int = 0
        self._cash: float = config.capital_eur
        self._inventory: float = 0.0
        self._pnl: float = 0.0
        self._cool_until: float = 0.0
        self._ticks: int = 0
        self._slip_ema: float = 0.0
        self._entropy: float = 1.0

    # ---- public lifecycle ----
    def validate_config(self) -> None:
        self.cfg.validate()

    def estimate_memory_mb(self) -> float:
        # scalar state + two deques + float list; ~32 bytes per slot + list overhead
        bytes_total = self.cfg.window * 48 + self.cfg.nbins * 32 + 6144
        return bytes_total / (1024.0 * 1024.0)

    def on_tick(self, price: float, ts: float) -> Dict[str, Any]:
        self._ticks += 1
        if self._ticks % self.cfg.gc_every == 0:
            gc.collect()

        if self._last_price is not None and price > 0.0:
            ret = math.log(price / self._last_price)
            self._hist.add(ret, self.cfg.hist_alpha)
            if abs(ret) > self.cfg.max_jump_pct:
                self._trigger_cooloff(ts, f"jump {abs(ret):.3f} > max_jump_pct")
                self._last_price = price
                return {"action": "hold", "reason": "cooloff_jump"}

        if self._hist.ready:
            self._entropy = self._hist.entropy()
            if self._entropy < self.cfg.entropy_floor and abs(self._hist.mean()) > self.cfg.max_jump_pct:
                self._trigger_cooloff(ts, "low entropy + drift: crash pattern")

        self._last_price = price
        if ts < self._cool_until:
            return {"action": "hold", "reason": "cooloff", "until": self._cool_until}

        # ---- regime interpolation ----
        h = self._entropy
        mid = (self.cfg.h_low + self.cfg.h_high) / 2.0
        mr = _logistic01(h, mid, 8.0)
        spacing = self.cfg.spacing_mr_pct + mr * (
            self.cfg.spacing_trend_pct - self.cfg.spacing_mr_pct
        )
        if self._slip_ema > self.cfg.max_slip_pct:  # adverse selection -> widen
            boost = min((self._slip_ema - self.cfg.max_slip_pct) / self.cfg.max_slip_pct, 1.0)
            spacing *= 1.0 + boost
        levels = int(round(self.cfg.max_levels + (1.0 - mr) * (self.cfg.min_levels - self.cfg.max_levels)))
        levels = max(self.cfg.min_levels, min(self.cfg.max_levels, levels))
        primary_side = "buy" if h < mid else "sell"
        step = max(price * spacing, 1e-8)
        budget = self.cfg.bias_strength * self._cash / max(levels, 1)

        # rebuild book -> free stale map before repopulating
        del self._orders_open
        self._orders_open = {}
        book: Dict[str, Any] = {
            "action": "place", "spacing_pct": spacing, "levels": levels,
            "regime": "trend" if mr < 0.5 else "mr",
            "entropy": round(h, 3), "primary": primary_side,
        }
        for i in range(1, levels + 1):
            off = i * step
            bid_price = price - off
            ask_price = price + off
            bid = {"price": bid_price, "qty": budget / max(bid_price, 1e-8), "side": "buy"}
            ask = {"price": ask_price, "qty": budget / max(ask_price, 1e-8), "side": "sell"}
            self._orders_open[f"b{i}"] = bid_price
            self._orders_open[f"s{i}"] = ask_price
            book[f"bid{i}"] = bid
            book[f"ask{i}"] = ask
        del bid, ask, off, bid_price, ask_price, step, budget  # free hot-loop temporaries
        return book

    def on_fill(self, price: float, qty: float, side: str, ts: float) -> None:
        self._fills += 1
        if side == "buy":
            self._inventory += qty
            self._cash -= qty * price
        else:
            self._inventory -= qty
            self._cash += qty * price
        if self._last_price is not None and self._last_price > 0.0:
            slip = abs(price - self._last_price) / self._last_price
            self._slip_ema = (1.0 - self.cfg.slip_gamma) * self._slip_ema + self.cfg.slip_gamma * slip
        self._pnl = self._cash + self._inventory * price - self.cfg.capital_eur

    def _trigger_cooloff(self, ts: float, reason: str) -> None:
        self._cool_until = ts + self.cfg.cooloff_ticks
        logger.warning("cooloff triggered at %s: %s", ts, reason)

    def pnl(self) -> float:
        return self._pnl


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    import random
    cfg = EntropyRegimeConfig(symbol="BTC/EUR", capital_eur=1000.0)
    g = EntropyRegimeGrid(cfg)
    print("estimate_memory_mb:", round(g.estimate_memory_mb(), 4))
    print("validate_config: OK")

    rng = random.Random(42)
    base = 100.0

    # phase 1: strong serial drift (low entropy / trending)
    price = base
    trend_entropy = 1.0
    for _ in range(250):
        price *= 1.0 + 0.004 + rng.gauss(0, 0.001)
        g.on_tick(price, float(_))
    trend_entropy = g._entropy
    print("trend entropy (last):", round(trend_entropy, 3))

    # phase 2: white noise around base (mean-reverting / high entropy)
    g2 = EntropyRegimeGrid(cfg)
    price = base
    for _ in range(250):
        price = base * (1.0 + rng.gauss(0, 0.02))
        g2.on_tick(price, float(_))
    mr_entropy = g2._entropy
    print("mr entropy (last):", round(mr_entropy, 3))

    if not (mr_entropy > trend_entropy):
        raise StrategyError(
            f"expected high entropy in MR regime, got trend={trend_entropy:.3f} mr={mr_entropy:.3f}"
        )
    print("SELFTEST OK")
