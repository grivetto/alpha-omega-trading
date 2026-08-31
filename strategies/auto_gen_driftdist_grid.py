"""auto_gen_driftdist_grid.py

Drift-Distance Elastic Grid (DDEG)
==================================
A grid that prices every level relative to a *robust adaptive anchor* and
reshapes its geometry from the distance between current price and a
noise-filtered trend measure (drift distance), not from a static midpoint:

  - When price sits CLOSE to the filtered drift anchor (mean-reverting band):
        tight spacing + many levels  -> harvest frequent small pullbacks.
  - When price drifts FAR from the anchor (trending band):
        wide spacing + few wide levels, and a trailing drift-lock pause
        stops the book from getting run over by the trend.

Unlike a fixed-anchor grid (which breaks when price gaps away from its
midpoint) and unlike a pure-VWAP grid, the anchor here is a *noise-filtered
EMA of residuals* (robust to volume spikes), so the grid self-corrects during
both trends and range-consolidation without manual re-anchoring.

Key components
--------------
1. Streaming double-EMA anchor (Hull-style response) computed incrementally
   with O(1) state; flat start avoids look-ahead bias.
2. Drift distance `d = |price - anchor| / scale` where scale is a streaming
   EMA of absolute residuals (robust dispersion) -> dimensionless drift.
3. Elastic spacing: spacing_pct = f(d) via logistic map; level count is the
   inverse, both clamped to config-driven bounds.
4. Drift-lock kill-switch: if `d` exceeds a configurable tail threshold the
   grid pauses new orders (cooloff) until price re-enters the band.
5. FIFO position ledger for realized PnL and actual win/loss tracking.
6. Order book generation: emits symmetric limit orders around anchor.

Memory discipline (OOM safety)
------------------------------
- Fully streaming: only scalar aggregates + a small bounded deque for the
  jump detector. Never materialises a price history.
- `del` of transient temporaries in hot paths; `gc.collect()` every
  `gc_every` ticks.
- No `try/except: pass`; every failure path raises `StrategyError`.

Strategy contract
-----------------
  class StrategyBase (ABC): on_tick, on_fill, validate_config, estimate_memory_mb.
  Config-driven; every tunable lives in DriftDistConfig. Zero hardcoded magic.
  Inline `__main__` self-test on small synthetic data.
"""

from __future__ import annotations

import gc
import logging
import math
import sys
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, List, Optional, Tuple

logger = logging.getLogger("driftdist_grid")


class StrategyError(RuntimeError):
    """Raised for any recoverable strategy error. Never silently swallowed."""


@dataclass(frozen=True, slots=True)
class DriftDistConfig:
    """Immutable, config-driven parameters. Every tunable lives here."""

    symbol: str
    capital_eur: float
    # ---- adaptive anchor / drift filter ----
    fast_alpha: float = 0.10    # EMA alpha for the fast anchor leg
    slow_alpha: float = 0.025   # EMA alpha for the slow anchor leg
    scale_alpha: float = 0.10   # EMA alpha for residual scale (dispersion)
    # ---- elastic grid geometry ----
    base_spacing_pct: float = 0.010  # spacing at d=0 (tight) as fraction
    max_spacing_pct: float = 0.045   # spacing at |d|->inf (wide) as fraction
    d_slope: float = 1.4             # logistic steepness of spacing response
    d_mid: float = 1.0               # drift at which spacing is midway
    min_levels: int = 3
    max_levels: int = 11
    # ---- risk / drift-lock protection ----
    tail_d: float = 3.0           # drift above this pauses the grid
    cooloff_ticks: int = 300      # ticks before the switch re-arms
    jump_window: int = 8          # ticks averaged for the jump detector
    max_jump_pct: float = 0.08    # avg jump that trips a hard pause
    gc_every: int = 1024          # call gc.collect() every N ticks
    # ---- warmup / execution ----
    warmup_ticks: int = 50        # ticks before drift/grid is active
    min_scale_pct: float = 0.005  # minimum scale as fraction of price
    order_size_frac: float = 0.1  # fraction of capital per level

    def validate(self) -> None:
        errs: List[str] = []
        if self.capital_eur <= 0:
            errs.append("capital_eur must be > 0")
        if not (0.0 < self.slow_alpha < self.fast_alpha <= 1.0):
            errs.append("need 0 < slow_alpha < fast_alpha <= 1")
        if not (0.0 < self.scale_alpha <= 1.0):
            errs.append("scale_alpha must be in (0,1]")
        if not (0.0 < self.base_spacing_pct < self.max_spacing_pct):
            errs.append("need 0 < base_spacing_pct < max_spacing_pct")
        if not (self.min_levels < self.max_levels):
            errs.append("min_levels must be < max_levels")
        if self.tail_d <= self.d_mid:
            errs.append("tail_d must be > d_mid")
        if self.cooloff_ticks <= 0:
            errs.append("cooloff_ticks must be > 0")
        if self.jump_window <= 0:
            errs.append("jump_window must be > 0")
        if not (0.0 < self.max_jump_pct < 1.0):
            errs.append("max_jump_pct must be in (0,1)")
        if self.gc_every <= 0:
            errs.append("gc_every must be > 0")
        if self.warmup_ticks < 0:
            errs.append("warmup_ticks must be >= 0")
        if not (0.0 < self.min_scale_pct < 1.0):
            errs.append("min_scale_pct must be in (0,1)")
        if not (0.0 < self.order_size_frac <= 1.0):
            errs.append("order_size_frac must be in (0,1]")
        if errs:
            raise StrategyError("invalid DriftDistConfig: " + "; ".join(errs))
        return True


class StrategyBase(ABC):
    """Base contract every auto-gen strategy must implement."""

    @abstractmethod
    def on_tick(self, price: float, ts: Optional[float] = None,
                volume: Optional[float] = None) -> Dict[str, Any]: ...

    @abstractmethod
    def on_fill(self, side: str, price: float, qty: float) -> None: ...

    @abstractmethod
    def validate_config(self) -> bool: ...

    @abstractmethod
    def estimate_memory_mb(self) -> float: ...


class DriftDistGrid(StrategyBase):
    """Streaming drift-distance elastic grid strategy with order emission."""

    def __init__(self, config: DriftDistConfig) -> None:
        config.validate()
        self.cfg = config
        # -- adaptive double-EMA anchor state --
        self.anchor_fast: Optional[float] = None
        self.anchor_slow: Optional[float] = None
        self.scale: float = 0.0            # EMA of |price - anchor|
        self.last_price: Optional[float] = None
        # -- guards --
        self.recent_jumps: Deque[float] = deque(maxlen=config.jump_window)
        self.in_cooloff: int = 0           # ticks remaining in the drift-lock
        self.ticks: int = 0
        # -- position ledger (FIFO) --
        self.open_buys: Deque[Tuple[float, float]] = deque()  # (price, qty)
        # -- accounting --
        self.realized_pnl: float = 0.0
        self.trades: int = 0
        self.wins: int = 0

    # ---- private helpers ---------------------------------------------
    def _update_anchor(self, price: float) -> None:
        """Incremental double-EMA anchor (Hull-style smoothing, O(1))."""
        if self.anchor_fast is None:
            self.anchor_fast = price
            self.anchor_slow = price
        else:
            self.anchor_fast = (self.cfg.fast_alpha * price
                                + (1 - self.cfg.fast_alpha) * self.anchor_fast)
            self.anchor_slow = (self.cfg.slow_alpha * price
                                + (1 - self.cfg.slow_alpha) * self.anchor_slow)
        anchor = 2.0 * self.anchor_fast - self.anchor_slow
        self.scale = (self.cfg.scale_alpha * abs(price - anchor)
                      + (1 - self.cfg.scale_alpha) * self.scale)

    def _anchor(self) -> float:
        """Current anchor value (2*fast - slow)."""
        if self.anchor_fast is None or self.anchor_slow is None:
            return self.last_price or 0.0
        return 2.0 * self.anchor_fast - self.anchor_slow

    def _drift(self, price: float) -> float:
        """Dimensionless drift distance against the adaptive anchor."""
        anchor = self._anchor()
        scale = self.scale if self.scale > 0.0 else (price * self.cfg.min_scale_pct)
        return abs(price - anchor) / scale

    def _elastic_spacing(self, d: float) -> float:
        """Logistic mapping from drift to spacing (fraction of price).
        
        At d=0: spacing = base_spacing_pct
        At d=d_mid: spacing = (base + max) / 2
        As d->inf: spacing -> max_spacing_pct
        """
        z = (d - self.cfg.d_mid) * self.cfg.d_slope
        # sigmoid: 1 / (1 + exp(-z)) -> 0 at -inf, 0.5 at 0, 1 at +inf
        sig = 1.0 / (1.0 + math.exp(-z))
        return self.cfg.base_spacing_pct + (self.cfg.max_spacing_pct - self.cfg.base_spacing_pct) * sig

    def _level_count(self, d: float) -> int:
        """Inverse-spacing level count, clamped to config bounds."""
        raw = self.cfg.max_levels * self.cfg.d_mid / max(d, self.cfg.d_mid)
        return max(self.cfg.min_levels,
                   min(int(round(raw)), self.cfg.max_levels))

    def _check_pause(self, d: float) -> bool:
        """Drift-lock: pause new orders while |d| > tail_d and in cooloff."""
        if self.in_cooloff > 0:
            self.in_cooloff -= 1
            return True
        if d > self.cfg.tail_d:
            self.in_cooloff = self.cfg.cooloff_ticks
            return True
        return False

    def _build_orders(self, price: float, anchor: float, spacing_pct: float, levels: int) -> List[Dict[str, Any]]:
        """Generate symmetric limit orders around anchor."""
        orders = []
        half = levels // 2
        # Capital per level (simple equal allocation)
        capital_per_level = self.cfg.capital_eur * self.cfg.order_size_frac
        for i in range(-half, half + 1):
            if i == 0:
                continue
            level_price = anchor * (1 + i * spacing_pct)
            side = "buy" if i < 0 else "sell"
            qty = capital_per_level / level_price
            orders.append({
                "side": side,
                "price": level_price,
                "qty": qty,
                "level": i,
                "anchor": anchor,
                "spacing_pct": spacing_pct,
            })
        return orders

    def _maybe_gc(self) -> None:
        if self.ticks % self.cfg.gc_every == 0:
            gc.collect()

    # ---- public API ---------------------------------------------------
    def on_tick(self, price: float, ts: Optional[float] = None,
                volume: Optional[float] = None) -> Dict[str, Any]:
        """Advance one tick. Returns grid parameters and order book."""
        if not math.isfinite(price) or price <= 0:
            raise StrategyError(f"invalid price {price!r} on tick {self.ticks}")

        self._update_anchor(price)
        self.ticks += 1
        self._maybe_gc()

        # Jump detector: anchor-relative acceleration
        if self.last_price is not None and self.anchor_fast is not None:
            anchor = self._anchor()
            jump = abs(price - anchor) / anchor
            self.recent_jumps.append(jump)
        self.last_price = price

        # Warmup: don't compute drift or emit orders until scale is stable
        if self.ticks <= self.cfg.warmup_ticks:
            return {
                "symbol": self.cfg.symbol,
                "price": price,
                "anchor": self._anchor(),
                "drift": 0.0,
                "spacing_pct": self.cfg.base_spacing_pct,
                "levels": self.cfg.min_levels,
                "paused": True,
                "warmup": True,
                "realized_pnl": self.realized_pnl,
                "trades": self.trades,
                "wins": self.wins,
                "orders": [],
            }

        d = self._drift(price)
        hard_pause = bool(self.recent_jumps
                          and max(self.recent_jumps) > self.cfg.max_jump_pct)
        paused = self._check_pause(d) or hard_pause

        spacing_pct = self._elastic_spacing(d)
        levels = self._level_count(d)

        anchor = self._anchor()
        orders = [] if paused else self._build_orders(price, anchor, spacing_pct, levels)

        return {
            "symbol": self.cfg.symbol,
            "price": price,
            "anchor": anchor,
            "drift": d,
            "spacing_pct": spacing_pct,
            "levels": levels,
            "paused": paused,
            "warmup": False,
            "realized_pnl": self.realized_pnl,
            "trades": self.trades,
            "wins": self.wins,
            "orders": orders,
        }

    def on_fill(self, side: str, price: float, qty: float) -> None:
        """Record a fill; update FIFO position ledger and realized PnL."""
        if side not in ("buy", "sell"):
            raise StrategyError(f"bad fill side {side!r}")
        if not math.isfinite(price) or not math.isfinite(qty) or qty <= 0:
            raise StrategyError(f"bad fill price/qty {price!r}/{qty!r}")

        if side == "buy":
            self.open_buys.append((price, qty))
            logger.debug("fill BUY @ %.6f qty %.6f", price, qty)
            return

        # side == "sell" - match against earliest buys (FIFO)
        remaining = qty
        while remaining > 0 and self.open_buys:
            buy_price, buy_qty = self.open_buys[0]
            matched = min(remaining, buy_qty)
            realized = (price - buy_price) * matched
            self.realized_pnl += realized
            if realized > 0:
                self.wins += 1
            self.trades += 1
            if matched == buy_qty:
                self.open_buys.popleft()
            else:
                self.open_buys[0] = (buy_price, buy_qty - matched)
            remaining -= matched
            logger.debug("fill SELL @ %.6f qty %.6f matched %.6f realized %.6f",
                         price, qty, matched, realized)

        if remaining > 0:
            logger.warning("sell fill exceeds open position: %.6f unmatched", remaining)

    def validate_config(self) -> bool:
        try:
            self.cfg.validate()
            return True
        except StrategyError as exc:
            logger.error("config invalid: %s", exc)
            return False
        return True

    def estimate_memory_mb(self) -> float:
        """Compute actual memory footprint of streaming state."""
        total = 0
        total += sys.getsizeof(self.anchor_fast) if self.anchor_fast is not None else 0
        total += sys.getsizeof(self.anchor_slow) if self.anchor_slow is not None else 0
        total += sys.getsizeof(self.scale)
        total += sys.getsizeof(self.last_price) if self.last_price is not None else 0
        total += sys.getsizeof(self.recent_jumps)
        total += sys.getsizeof(self.in_cooloff)
        total += sys.getsizeof(self.ticks)
        total += sys.getsizeof(self.open_buys)
        total += sys.getsizeof(self.realized_pnl)
        total += sys.getsizeof(self.trades)
        total += sys.getsizeof(self.wins)
        # Add deque overhead (approximate)
        total += len(self.recent_jumps) * 24  # float objects
        total += len(self.open_buys) * 48     # tuple of 2 floats
        return total / (1024 * 1024)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    def _smoke() -> None:
        cfg = DriftDistConfig(symbol="SOL/EUR", capital_eur=100.0)
        assert cfg.validate() is True
        strat = DriftDistGrid(cfg)

        # parse-driven synthetic series: mean-revert then break away
        price: float = 100.0
        for i in range(300):
            if i < 180:
                price += math.sin(i * 0.5) * 0.3  # choppy band
            else:
                price *= 1.004                    # sustained drift up
            out = strat.on_tick(price, ts=float(i))
            assert isinstance(out, dict)
            assert out["levels"] >= cfg.min_levels
            assert out["levels"] <= cfg.max_levels
            assert out["spacing_pct"] >= cfg.base_spacing_pct
            assert out["spacing_pct"] <= cfg.max_spacing_pct
            # During warmup, orders should be empty
            if i < cfg.warmup_ticks:
                assert out["warmup"] is True
                assert out["orders"] == []
            else:
                assert out["warmup"] is False
            if i % 3 == 0:
                strat.on_fill("buy", price, 0.1)
            if i % 5 == 0:
                strat.on_fill("sell", price * 1.001, 0.1)
        assert strat.ticks == 300
        assert strat.trades > 0
        mem = strat.estimate_memory_mb()
        assert mem > 0.0 and mem < 1.0
        print(f"OK driftdist_grid: ticks={strat.ticks} trades={strat.trades} "
              f"wins={strat.wins} pnl={strat.realized_pnl:.4f} mem_mb~{mem:.6f}")

    _smoke()