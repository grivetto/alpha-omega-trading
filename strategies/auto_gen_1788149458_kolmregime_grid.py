"""auto_gen_kolmregime_grid.py

Kolmogorov Permission-Entropy Grid (KPEG)
=========================================
A regime-aware grid that measures the *structural disorder* of the price series in
real time (permutation entropy) and reshapes the grid to the detected regime:

  - HIGH entropy  (efficient, random-like market)  -> WIDE spacing, fewer levels
    (trend-following alpha is thin; only wide levels survive the noise).
  - LOW entropy   (structurally ordered, trending or strongly mean-reverting)
    -> TIGHT spacing near the anchor, more levels (frequent fill/pullback harvest).

KPEG is distribution-free: permutation entropy uses ordinal patterns of the last
`window_ticks` closes and is computed streaming with O(1) memory via a bounded
deque and a fixed-size pattern counter.

Memory discipline (OOM safety)
------------------------------
- Streamed via `stream_ticks` generator; never materialises 100k+ rows.
- Bounded deques (maxlen) for closes and jumps; O(1) state.
- Pattern enumeration bounded by `order` (<=5 => at most 120 patterns).
- `gc.collect()` after periodic re-computes; explicit `del` of large locals.
- No `try/except: pass`; explicit error handling via StrategyError + logging.

Strategy contract
-----------------
  - class StrategyBase (ABC): on_tick, on_fill, validate_config, estimate_memory_mb.
  - config-driven; every tunable lives in KPEGConfig; zero hardcoded magic.
  - inline `__main__` self-test on small synthetic data.
"""

from __future__ import annotations

import gc
import logging
import math
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, Generator, List, Optional, Tuple

logger = logging.getLogger(__name__)


class StrategyError(RuntimeError):
    """Raised for invalid configuration or unsafe runtime states."""


def _permutation_entropy(window: Deque[float], order: int) -> float:
    """Distribution-free permutation entropy of the last `order` symbols.

    Counts ordinal patterns over the window; the entropy is estimated from the
    empirical pattern frequency via Shannon's formula, normalised by log2(order!).

    Returns float in [0,1]; 1.0 == maximal disorder (random), 0.0 == perfect order.
    """
    n: int = len(window)
    if n < order:
        return 1.0  # insufficient data: assume maximal uncertainty
    counts: Dict[Tuple[int, ...], int] = {}
    total: int = 0
    for start in range(n - order + 1):
        seg: List[float] = list(window)[start:start + order]
        ranked: Tuple[int, ...] = tuple(sorted(range(order), key=lambda k: seg[k]))
        counts[ranked] = counts.get(ranked, 0) + 1
        total += 1
    log2f: float = math.log2(math.factorial(order))
    if log2f <= 0.0:
        return 1.0
    ent: float = 0.0
    for c in counts.values():
        p: float = c / total
        ent -= p * math.log2(p)
    return max(0.0, min(1.0, ent / log2f))


@dataclass(frozen=True, slots=True)
class KPEGConfig:
    """Immutable, config-driven parameters. Every tunable lives here."""

    symbol: str
    capital_eur: float
    # ---- permutation-entropy sensing ----
    window_ticks: int = 60          # closes kept for entropy (deque maxlen)
    order: int = 4                  # ordinal-pattern length (2..5)
    recompute_every: int = 5        # ticks between entropy recomputes
    entropy_mid: float = 0.55       # regime blend midpoint in [0,1]
    entropy_slope: float = 6.0      # steepness of the regime logistic blend
    # ---- grid geometry ----
    min_spacing_pct: float = 0.008  # tightest half-interval as % of anchor
    max_spacing_pct: float = 0.06   # widest half-interval as % of anchor
    min_levels: int = 3
    max_levels: int = 9
    ema_span: int = 30              # trend-anchor EMA span
    # ---- risk / tail protection ----
    max_jump_pct: float = 0.06      # tick-to-tick move that trips the kill-switch
    jump_window: int = 5            # ticks averaged for the jump check
    cooloff_ticks: int = 200        # ticks before the switch re-arms
    stop_loss_pct: float = 0.05     # hard stop below the anchor


class StrategyBase(ABC):
    """Abstract base class every strategy implements."""

    @abstractmethod
    def on_tick(self, price: float, ts: Optional[float] = None) -> Dict[str, Any]:
        """Process one market tick. Return an action dict."""

    @abstractmethod
    def on_fill(self, side: str, price: float, qty: float) -> None:
        """Record an executed fill."""

    @abstractmethod
    def validate_config(self) -> bool:
        """Raise StrategyError if configuration is invalid."""

    @abstractmethod
    def estimate_memory_mb(self) -> float:
        """Return an upper-bound memory footprint estimate in MB."""


class KolmRegimeGrid(StrategyBase):
    """Regime-adaptive grid driven by permutation entropy of the price series."""

    def __init__(self, cfg: KPEGConfig) -> None:
        self.cfg: KPEGConfig = cfg
        self._closes: Deque[float] = deque(maxlen=cfg.window_ticks)
        self._jumps: Deque[float] = deque(maxlen=cfg.jump_window)
        self._ema: Optional[float] = None
        self._ema_k: float = 2.0 / (cfg.ema_span + 1.0)
        self._entropy: float = 1.0
        self._ticks_since_recompute: int = 0
        self._ticks: int = 0
        self._kill_until: int = 0
        self._last_anchor: float = 0.0
        self._spacing: float = cfg.min_spacing_pct * 1.0
        self._levels: int = cfg.min_levels
        self._buy_qty: float = 0.0
        self._sell_qty: float = 0.0
        self._realized_pnl: float = 0.0
        self.validate_config()

    # ---- interface ---------------------------------------------------------
    def on_tick(self, price: float, ts: Optional[float] = None) -> Dict[str, Any]:
        self._ticks += 1
        self._closes.append(price)

        # trend anchor (slow drift follower)
        if self._ema is None:
            self._ema = price
        else:
            self._ema = self._ema_k * price + (1.0 - self._ema_k) * self._ema

        # tail protection: rolling average of absolute tick jumps
        if len(self._closes) >= 2:
            prev: float = self._closes[-2]
            if prev > 0:
                self._jumps.append(abs(price - prev) / prev)
                if len(self._jumps) == self.cfg.jump_window:
                    avg_jump: float = sum(self._jumps) / self.cfg.jump_window
                    if avg_jump > self.cfg.max_jump_pct:
                        self._kill_until = self._ticks + self.cfg.cooloff_ticks

        # periodic entropy recompute + grid reshaping
        self._ticks_since_recompute += 1
        if self._ticks_since_recompute >= self.cfg.recompute_every:
            self._ticks_since_recompute = 0
            self._entropy = _permutation_entropy(self._closes, self.cfg.order)
            self._apply_regime()
            gc.collect()

        self._last_anchor = float(self._ema)
        return self._action()

    # ---- grid geometry ------------------------------------------------------
    def _apply_regime(self) -> None:
        cfg = self.cfg
        z: float = cfg.entropy_slope * (self._entropy - cfg.entropy_mid)
        regime: float = 1.0 / (1.0 + math.exp(-z))  # 1.0 == high entropy
        anchor: float = self._last_anchor if self._last_anchor > 0 else 1.0
        lo_sp: float = cfg.min_spacing_pct * anchor
        hi_sp: float = cfg.max_spacing_pct * anchor
        self._spacing = lo_sp + (hi_sp - lo_sp) * regime
        levels_f: float = cfg.max_levels - (cfg.max_levels - cfg.min_levels) * regime
        self._levels = int(round(levels_f))

    def _action(self) -> Dict[str, Any]:
        if self._ticks < self.cfg.window_ticks:
            return {"action": "hold", "reason": "warming_up"}
        if self._ticks < self._kill_until:
            return {"action": "halt", "reason": "kill_switch"}
        price: float = self._closes[-1]
        anchor: float = self._last_anchor
        if anchor <= 0.0 or self._spacing <= 0.0:
            return {"action": "hold", "reason": "no_anchor"}
        below: float = (price - anchor) / anchor
        n: int = self._levels
        if below <= -self.cfg.stop_loss_pct:
            return {"action": "stop_loss", "reason": "hard_stop", "levels": n}
        level_span: float = self._spacing / anchor
        if abs(below) < level_span:
            return {"action": "hold", "reason": "inside_inner", "levels": n}
        step: int = int(abs(below) / level_span)
        side: str = "buy" if below < 0 else "sell"
        return {
            "action": side,
            "reason": "grid_step",
            "levels": n,
            "spacing_pct": round(level_span, 5),
            "entropy": round(self._entropy, 3),
            "index": min(step, n),
        }

    # ---- fill bookkeeping ----------------------------------------------------
    def on_fill(self, side: str, price: float, qty: float) -> None:
        if side not in ("buy", "sell"):
            raise StrategyError(f"invalid fill side: {side!r}")
        if price <= 0.0 or qty <= 0.0:
            raise StrategyError(f"invalid fill price/qty: {price}, {qty}")
        if side == "buy":
            self._buy_qty += qty
            self._realized_pnl += (self._last_anchor - price) * qty
        else:
            self._sell_qty += qty

    # ---- config validation ----------------------------------------------------
    def validate_config(self) -> bool:
        cfg = self.cfg
        if cfg.capital_eur <= 0:
            raise StrategyError(f"capital_eur must be > 0, got {cfg.capital_eur}")
        if cfg.window_ticks < cfg.order:
            raise StrategyError("window_ticks must be >= order")
        if not (2 <= cfg.order <= 5):
            raise StrategyError("order must be in [2,5]")
        if cfg.min_spacing_pct >= cfg.max_spacing_pct:
            raise StrategyError("min_spacing_pct must be < max_spacing_pct")
        if cfg.min_levels > cfg.max_levels:
            raise StrategyError("min_levels must be <= max_levels")
        if not (0.0 < cfg.entropy_mid < 1.0):
            raise StrategyError("entropy_mid must be in (0,1)")
        return True

    # ---- memory estimate ---------------------------------------------------------
    def estimate_memory_mb(self) -> float:
        closes_bytes: float = self.cfg.window_ticks * 24.0
        jumps_bytes: float = self.cfg.jump_window * 24.0
        fixed_bytes: float = 4096.0
        return (closes_bytes + jumps_bytes + fixed_bytes) / (1024.0 * 1024.0)

    # ---- status ---------------------------------------------------------------
    def status(self) -> Dict[str, Any]:
        return {
            "symbol": self.cfg.symbol,
            "entropy": round(self._entropy, 3),
            "levels": self._levels,
            "spacing_pct": round(self._spacing / self._last_anchor, 4)
            if self._last_anchor > 0 else 0.0,
            "anchor": self._last_anchor,
            "knocked": self._ticks < self._kill_until,
            "ticks": self._ticks,
            "realized_pnl": round(self._realized_pnl, 6),
        }


def stream_ticks(prices: List[float]) -> Generator[float, None, None]:
    """Generator that yields one price at a time — never materialises a big list."""
    for p in prices:
        yield p
    del prices


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    import random

    cfg = KPEGConfig(
        symbol="DOGE/EUR",
        capital_eur=50.0,
        window_ticks=80,
        order=4,
        entropy_mid=0.55,
        min_spacing_pct=0.01,
        max_spacing_pct=0.05,
        min_levels=4,
        max_levels=8,
    )
    strat = KolmRegimeGrid(cfg)
    rng: random.Random = random.Random(42)

    synthetic: List[float] = []
    mid_v: float = 1.0
    for i in range(2000):
        if i < 800:
            # strong sustained drift + small wobble => LOW entropy (ordered/trending)
            mid_v += 0.004
            wob: float = (rng.random() - 0.5) * 0.006   # oscillation around anchor
        else:
            # pure random walk => HIGH entropy (efficient)
            mid_v += (rng.random() - 0.5) * 0.02
            wob = (rng.random() - 0.5) * 0.002
        synthetic.append(max(mid_v + wob, 1e-6))
    del mid_v

    trades: int = 0
    for tick in stream_ticks(synthetic):
        act = strat.on_tick(tick)
        if act["action"] in ("buy", "sell"):
            trades += 1
    del synthetic
    gc.collect()

    print("STATUS:", strat.status())
    print("TRADES:", trades)
    assert strat.validate_config()
    mem = strat.estimate_memory_mb()
    print(f"MEM: {mem:.4f} MB")
    assert mem < 1.0
    assert strat.status()["ticks"] == 2000 and trades > 0
    print("SELF-TEST OK")
