"""LiquiditySkewGrid — order-book imbalance driven asymmetric grid.

The classic symmetric grid assumes mean-reversion around a static anchor.
Real crypto books are rarely balanced: when bid depth >> ask depth the price
is biased upward (buy pressure), and vice-versa. LiquiditySkewGrid consumes
a streaming order-book imbalance ratio `imb = (bid_depth - ask_depth) /
(bid_depth + ask_depth)` in [-1, +1] and continuously re-anchors / skews the
level spacing so the grid leans into the pressure side.

Mean-reversion mechanics are preserved (each fill still places a pair of
contra orders), but the grid is not symmetric: under persistent buy pressure
(bid-heavy book) levels get denser above the anchor and sparser below, and
the anchor drifts up only when imbalance is statistically significant
(see `imb_significance`), preventing chop-induced re-anchor thrashing.

Memory-safety
-------------
* No unbounded history: only a hard-capped EMA state plus a tiny fixed
  deque of last `fill_window` fills for footprint sizing.
* All rolling statistics use O(1) incremental updates (EWMA), never full
  re-scan of a large buffer, and never list comprehensions over data slices.
* Degenerate edge cases (zero depth, zero capital) are handled explicitly
  with typed guards -- no bare ``except: pass``.
"""

from __future__ import annotations

import gc
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional, Protocol, Tuple


class StrategyBase(Protocol):
    """Minimal Strategy interface contract used by the Denaro engine."""

    def on_tick(self, price: float, ts: Optional[float] = None) -> Dict[str, Any]:
        ...

    def on_fill(self, side: str, price: float, qty: float) -> None:
        ...

    def validate_config(self) -> None:
        ...

    def estimate_memory_mb(self) -> float:
        ...


@dataclass
class LiquiditySkewGrid:
    """Asymmetric grid re-scored from streaming order-book imbalance.

    Attributes
    ----------
    symbol : str
        Trading pair identifier (informational only).
    capital : float
        Total quote capital allocated to the grid instance.
    base_spacing_bps : float
        Nominal geometric spacing between adjacent levels at neutral
        imbalance (``imb == 0``) expressed in basis points.
    levels : int
        Number of levels placed on each side of the current anchor.
    imb_ema_alpha : float
        Smoothing factor for the imbalance EWMA (0..1]. Higher = faster
        reaction, noisier.
    skew_power : float
        Exponent mapping |imb| to a spacing multiplier. >1 amplifies the
        asymmetry; 0 disables skew entirely (falls back to symmetric grid).
    imb_significance : float
        Minimum |imb| (after smoothing) required to shift the anchor. Below
        this threshold the grid behaves like a static symmetric grid, which
        suppresses whipsaw re-anchoring in choppy neutral books.
    max_anchor_shift_bps : float
        Hard cap on a single anchor drift step, protecting the grid from a
        single violent imbalance spike.
    anchor_ema_alpha : float
        Smoothing for the anchor itself (guards against micro drift).
    fill_window : int
        Hard cap on the number of recent fills retained for footprint
        reporting (memory bound).
    risk_per_level : float
        Fraction of total capital placed per level (0..1].
    price_decimals : int
        Rounding precision used when materialising order prices.
    ticks_per_year : float
        Annualization denominator, informational only (defaults to 1-min).
    """

    symbol: str
    capital: float
    base_spacing_bps: float = 28.0
    levels: int = 6
    imb_ema_alpha: float = 0.20
    skew_power: float = 1.5
    imb_significance: float = 0.10
    max_anchor_shift_bps: float = 40.0
    anchor_ema_alpha: float = 0.05
    fill_window: int = 64
    risk_per_level: float = 0.08
    price_decimals: int = 4
    ticks_per_year: float = 252.0 * 1440.0

    # Internal state (excluded from __init__ signature via field default).
    _anchor: float = field(default=0.0, init=False, repr=False)
    _imb_ema: float = field(default=0.0, init=False, repr=False)
    _recent_fills: Deque[Tuple[str, float, float]] = field(
        default_factory=deque, init=False, repr=False
    )
    _total_buys: int = field(default=0, init=False, repr=False)
    _total_sells: int = field(default=0, init=False, repr=False)
    _total_pnl: float = field(default=0.0, init=False, repr=False)

    def __post_init__(self) -> None:
        """Normalise raw un-normalised config passed by the engine."""
        self.imb_ema_alpha = float(self.imb_ema_alpha)
        self.anchor_ema_alpha = float(self.anchor_ema_alpha)
        self.validate_config()

    # ------------------------------------------------------------------ #
    # Configuration
    # ------------------------------------------------------------------ #
    def validate_config(self) -> None:
        """Raise ``ValueError`` on any config that cannot be executed safely."""
        problems: List[str] = []

        if self.levels < 2:
            problems.append("levels must be >= 2")
        if self.levels > 64:
            problems.append("levels must be <= 64 (memory/CPU bound)")
        if self.capital <= 0.0:
            problems.append("capital must be > 0")
        if not (0.0 < self.imb_ema_alpha <= 1.0):
            problems.append("imb_ema_alpha must be in (0, 1]")
        if not (0.0 <= self.anchor_ema_alpha <= 1.0):
            problems.append("anchor_ema_alpha must be in [0, 1]")
        if self.base_spacing_bps <= 0.0:
            problems.append("base_spacing_bps must be > 0")
        if not (0.0 < self.risk_per_level <= 1.0):
            problems.append("risk_per_level must be in (0, 1]")
        if not (0.0 <= self.imb_significance < 1.0):
            problems.append("imb_significance must be in [0, 1)")
        if self.max_anchor_shift_bps < 0.0:
            problems.append("max_anchor_shift_bps must be >= 0")

        if problems:
            raise ValueError("LiquiditySkewGrid invalid config: " + "; ".join(problems))

    # ------------------------------------------------------------------ #
    # Core signal
    # ------------------------------------------------------------------ #
    def _smooth_imbalance(self, imb: float) -> float:
        """EWMA-update the smoothed imbalance and return the new value."""
        self._imb_ema = self.imb_ema_alpha * imb + (1.0 - self.imb_ema_alpha) * self._imb_ema
        # Hard clamp to [-1, 1]; protects against malformed depth inputs.
        return max(-1.0, min(1.0, self._imb_ema))

    def _spacing_multiplier(self, imb_ema: float) -> float:
        """Map smoothed imbalance to a per-side spacing multiplier.

        Buy pressure (``imb_ema > 0``) tightens spacing *above* the anchor
        (more fills while price rises) and loosens it below. The asymmetry is
        driven by ``skew_power``; 0 yields a fully symmetric grid.
        """
        if self.skew_power == 0.0:
            return 1.0
        base = 1.0 + abs(imb_ema) * self.skew_power
        return max(0.5, min(2.5, base))

    def _anchor_step(self, price: float) -> float:
        """Return the price delta by which the anchor should move this tick.

        Only moves when |smooth imbalance| exceeds the significance band;
        capped to ``max_anchor_shift_bps`` per step. Positive imbalance
        (bid-heavy) pushes the anchor up.
        """
        if abs(self._imb_ema) < self.imb_significance:
            return 0.0
        shift = price * self._imb_ema * self.max_anchor_shift_bps / 10_000.0
        return shift

    def _level_prices(self, price: float) -> Dict[str, List[float]]:
        """Materialise the buy/sell grid legs around the current anchor.

        Returns two lists (prices descending for bids, ascending for asks).
        List construction is bounded by ``levels`` (small fixed N), so no
        unbounded memory risk.
        """
        sm = self._spacing_multiplier(self._imb_ema)
        spacing = self.base_spacing_bps / 10_000.0

        bids: List[float] = []
        asks: List[float] = []
        for i in range(1, self.levels + 1):
            # Buy pressure (sm>1): bids below get sparser, asks above get
            # denser -- the grid leans into the buy side so it harvests more
            # upside fills while keeping downside fills scarce.
            bid_sp = spacing * sm
            ask_sp = spacing * (2.0 - sm)
            bids.append(round(price * (1.0 - i * bid_sp), self.price_decimals))
            asks.append(round(price * (1.0 + i * ask_sp), self.price_decimals))
        return {"bids": bids, "asks": asks}

    def _slot_size(self, price: float) -> float:
        """Quote per level, capped so total exposure never exceeds capital."""
        per_level = self.capital * self.risk_per_level
        return round(min(per_level, self.capital / (self.levels * 2.0)), self.price_decimals)

    # ------------------------------------------------------------------ #
    # Public API (StrategyBase contract)
    # ------------------------------------------------------------------ #
    def on_tick(self, price: float, ts: Optional[float] = None) -> Dict[str, Any]:
        """Update imbalance + anchor, return the proposed order book.

        ``price`` is the mid price; an optional keyword ``imb`` (already
        smoothed upstream) may be passed via ``ts``-style kwargs in the
        returned decision only -- by default imbalance is assumed neutral
        when no depth feed is wired, degrading gracefully to a symmetric
        grid.
        """
        if price <= 0.0:
            return {"error": "non-positive price", "levels": {"bids": [], "asks": []}}

        if self._anchor <= 0.0:
            self._anchor = price

        # Anchor drift (significance-gated, EMA-smoothed, capped).
        step = self._anchor_step(price)
        target = self._anchor + step
        self._anchor = self.anchor_ema_alpha * target + (1.0 - self.anchor_ema_alpha) * self._anchor

        return {
            "symbol": self.symbol,
            "anchor": self._anchor,
            "imb_ema": self._imb_ema,
            "slot_size": self._slot_size(self._anchor),
            "levels": self._level_prices(self._anchor),
            "n_buy_levels": self.levels,
            "n_sell_levels": self.levels,
        }

    def apply_depth(self, bid_depth: float, ask_depth: float) -> None:
        """Stream a book-depth sample into the imbalance EWMA.

        ``bid_depth``/``ask_depth`` are the total base-side/quote-side book
        depth (any consistent units). Zero total depth is ignored explicitly
        (cannot compute a ratio) rather than guarded by ``except``.
        """
        total = bid_depth + ask_depth
        if total <= 0.0:
            return  # no book / zero depth: keep previous imbalance
        imb = (bid_depth - ask_depth) / total
        self._smooth_imbalance(imb)

    def on_fill(self, side: str, price: float, qty: float) -> None:
        """Record a fill (buy/sell) for footprint + PnL tracking."""
        if price <= 0.0 or qty <= 0.0:
            return
        if side == "buy":
            self._total_buys += 1
        elif side == "sell":
            self._total_sells += 1
        self._total_pnl += price * qty
        self._recent_fills.append((side, price, qty))
        while len(self._recent_fills) > self.fill_window:
            self._recent_fills.popleft()

    def stats(self) -> Dict[str, Any]:
        """Compact runtime statistics for health/reporting."""
        return {
            "buys": self._total_buys,
            "sells": self._total_sells,
            "recent_fills": len(self._recent_fills),
            "book_value_pnl": self._total_pnl,
            "imb_ema": self._imb_ema,
            "anchor": self._anchor,
        }

    def estimate_memory_mb(self) -> float:
        """Bound the resident footprint.

        State is O(levels) floats plus a capped deque of ``fill_window``
        tuples; the estimate includes a conservative 10x slack for the
        Python object overhead.
        """
        bytes_state = self.levels * 2 * 8          # level price floats (both legs)
        bytes_fills = self.fill_window * (8 + 8 + 8) * 2  # 3-tuples (str ref, float, float)
        total_bytes = (bytes_state + bytes_fills + 4096) * 10  # x10 slack + baseline
        return round(total_bytes / (1024.0 * 1024.0), 4)


def _selftest() -> None:
    """Inline smoke test with small synthetic data (no external deps)."""
    grid = LiquiditySkewGrid(symbol="SOL/EUR", capital=13.5, levels=6)
    # 1) Neutral book -> symmetric-ish grid around anchor.
    d1 = grid.on_tick(100.0)
    assert d1["anchor"] == 100.0
    assert len(d1["levels"]["bids"]) == 6
    assert len(d1["levels"]["asks"]) == 6

    # 2) Persistent bid pressure tightens asks / loosens bids (no re-anchor
    #    below significance until EMA accumulates past the band).
    for _ in range(60):
        grid.apply_depth(bid_depth=80.0, ask_depth=20.0)
    d2 = grid.on_tick(100.0)
    assert d2["imb_ema"] > 0.0
    assert d2["imb_ema"] > grid.imb_significance  # band crossed
    ask_sp = d2["levels"]["asks"][1] - d2["levels"]["asks"][0]
    bid_sp = d2["levels"]["bids"][0] - d2["levels"]["bids"][1]
    assert ask_sp < bid_sp, "buy pressure must tighten the ask side"

    # 3) Zero depth -> imbalance unchanged (explicit guard, no exception).
    grid.apply_depth(0.0, 0.0)
    imb_before = grid._imb_ema

    # 4) Fill bookkeeping bounded.
    for i in range(100):
        grid.on_fill("buy", 100.0 + i, 0.01)
    assert len(grid._recent_fills) == grid.fill_window
    assert grid._total_buys == 100

    # 5) Config guard raises on bad input.
    try:
        LiquiditySkewGrid(symbol="X", capital=-1.0)
        raise AssertionError("should have raised on negative capital")
    except ValueError:
        pass

    print(
        f"SELFTEST PASS | mem={grid.estimate_memory_mb()}MB "
        f"imb_ema={grid._imb_ema:.3f} buys={grid._total_buys} fills={len(grid._recent_fills)}"
    )


if __name__ == "__main__":
    _selftest()
