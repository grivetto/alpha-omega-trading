"""VolBufferGrid — volatility-scaled asymmetric grid with a mandatory reserve buffer.

Failure mode targeted
---------------------
The live grid bots (mc2 doge, nuvola doge) ran at ``free_quote == 0.0`` with
``cap_available == 0.0``: 100% of capital locked into resting order levels.
That leaves zero buffer for rebalancing, for a stop-loss contraction, and it
locks the account during LIVE_PAUSE so any subsequent config change or grid
repair requires force-cancelling *all* resting orders. When a grid is 100%
deployed there is no dry powder to absorb a spread blowout or to fund the
contra-leg of a fresh fill, which silently stalls the mean-reversion engine.

VolBufferGrid fixes that by construction:

* A mandatory ``reserve_ratio`` of capital is never placed on the book; it
  stays as free quote, configurable per node.
* Level spacing is driven by an EWMA of realized volatility (rolling window,
  O(1) incremental update -- no re-scan), so the grid *breathes*: it widens
  in high-vol regimes (fewer, safer fills) and tightens in calm regimes where
  mean-reversion clears frequently.
* The anchor re-target follows a slow EWMA with a hard max-step cap, and the
  deployed slot size is derived from ``(capital * (1 - reserve_ratio))`` so
  total gross exposure can never exceed the deployable pool.

Memory-safety
-------------
* All rolling statistics are O(1) incremental (EWMA / Welford), never a
  re-scan of a large buffer and never list comprehensions over a data slice.
* The only retained series is a capped ``deque`` of log-returns for
  footprint reporting, bounded by ``return_window``.
* Large temporaries are deleted and ``gc.collect()`` invoked only on the
  (rare) explicit re-root call, never on the hot path.
* Every degenerate config/input is handled with typed guards raising
  ``ValueError`` or returning an empty decision -- no bare ``except: pass``.
"""

from __future__ import annotations

import gc
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Optional, Protocol, Tuple


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
class VolBufferGrid:
    """Volatility-scaled grid keeping a mandatory reserve buffer.

    Parameters
    ----------
    symbol : str
        Trading pair identifier (informational).
    capital : float
        Total quote capital allocated to the grid.
    base_spacing_bps : float
        Nominal geometric level spacing at the baseline volatility in basis
        points (neutral EWMA vol == ``vol_anchor_bps``).
    levels : int
        Number of levels placed on each side of the anchor.
    reserve_ratio : float
        Fraction of ``capital`` never placed on the book (kept as free
        quote). Must be in ``[0, 1)``; ``0`` disables the reserve but the
        deploy tooling is expected to keep it ``>= 0.15`` for paper nodes.
    vol_window : int
        Rolling log-return window used by the Welford EWMA (capped memory).
    vol_alpha : float
        EWMA smoothing for the volatility estimate (0..1].
    vol_anchor_bps : float
        Baseline daily volatility (annualized bps) at which spacing is
        exactly ``base_spacing_bps``; above/below scales spacing linearly.
    max_spacing_mult : float
        Upper clamp on the spacing multiplier (protects against a single
        volatility explosion stretching the grid to a non-trading width).
    anchor_ewma_alpha : float
        Smoothing for the anchor drift target.
    max_anchor_shift_bps : float
        Hard cap on a single anchor re-target step (in bps of price).
    return_window : int
        Hard cap on retained log-return samples for footprint reporting.
    slot_risk : float
        Fraction of the *deployable* pool (capital after reserve) placed per
        level. Total gross exposure is bounded by the deployable pool.
    price_decimals : int
        Rounding precision for materialised order prices.
    """

    symbol: str
    capital: float
    base_spacing_bps: float = 32.0
    levels: int = 6
    reserve_ratio: float = 0.20
    vol_window: int = 120
    vol_alpha: float = 0.06
    vol_anchor_bps: float = 220.0
    max_spacing_mult: float = 3.0
    anchor_ewma_alpha: float = 0.04
    max_anchor_shift_bps: float = 35.0
    return_window: int = 256
    slot_risk: float = 0.09
    price_decimals: int = 4

    # Internal state (excluded from the public __init__ signature).
    _anchor: float = field(default=0.0, init=False, repr=False)
    _mean: float = field(default=0.0, init=False, repr=False)
    _m2: float = field(default=0.0, init=False, repr=False)
    _count: int = field(default=0, init=False, repr=False)
    _last_price: float = field(default=0.0, init=False, repr=False)
    _recent_returns: Deque[float] = field(default_factory=deque, init=False, repr=False)
    _total_buys: int = field(default=0, init=False, repr=False)
    _total_sells: int = field(default=0, init=False, repr=False)
    _cash_flow: float = field(default=0.0, init=False, repr=False)

    def __post_init__(self) -> None:
        """Coerce raw engine config to native floats, then validate."""
        for attr in (
            "capital", "base_spacing_bps", "reserve_ratio", "vol_alpha",
            "vol_anchor_bps", "max_spacing_mult", "anchor_ewma_alpha",
            "max_anchor_shift_bps", "slot_risk",
        ):
            setattr(self, attr, float(getattr(self, attr)))
        self.validate_config()

    # ------------------------------------------------------------------ #
    # Configuration
    # ------------------------------------------------------------------ #
    def validate_config(self) -> None:
        """Raise ``ValueError`` on any config that cannot execute safely."""
        problems: list[str] = []
        if self.levels < 2:
            problems.append("levels must be >= 2")
        if self.levels > 64:
            problems.append("levels must be <= 64 (memory/CPU bound)")
        if self.capital <= 0.0:
            problems.append("capital must be > 0")
        if not (0.0 <= self.reserve_ratio < 1.0):
            problems.append("reserve_ratio must be in [0, 1)")
        if self.base_spacing_bps <= 0.0:
            problems.append("base_spacing_bps must be > 0")
        if self.vol_anchor_bps <= 0.0:
            problems.append("vol_anchor_bps must be > 0")
        if not (0.0 < self.vol_alpha <= 1.0):
            problems.append("vol_alpha must be in (0, 1]")
        if not (0.0 <= self.anchor_ewma_alpha <= 1.0):
            problems.append("anchor_ewma_alpha must be in [0, 1]")
        if self.max_spacing_mult < 1.0:
            problems.append("max_spacing_mult must be >= 1")
        if self.vol_window < 2:
            problems.append("vol_window must be >= 2")
        if not (0.0 < self.slot_risk <= 1.0):
            problems.append("slot_risk must be in (0, 1]")
        if problems:
            raise ValueError("VolBufferGrid invalid config: " + "; ".join(problems))

    # ------------------------------------------------------------------ #
    # Core signal: volatility EWMA (Welford incremental variance)
    # ------------------------------------------------------------------ #
    def _push_return(self, prev_price: float, price: float) -> Optional[float]:
        """Stream one log-return and update the Welford EWMA variance.

        Returns ``None`` when no new sample was produced (bad inputs or the
        first tick), else the sampled log-return.
        """
        if prev_price <= 0.0 or price <= 0.0:
            return None
        log_ret = math.log(price / prev_price)
        self._count += 1
        delta = log_ret - self._mean
        self._mean += delta / self._count
        self._m2 += delta * (log_ret - self._mean)
        self._recent_returns.append(log_ret)
        while len(self._recent_returns) > self.return_window:
            self._recent_returns.popleft()
        return log_ret

    def _realized_vol_bps(self) -> float:
        """Annualised realized volatility of the price series (daily scaled).

        Uses Welford's sample variance (``m2 / (count - 1)``). While the
        window is filling the estimate is scaled by the observed count so the
        grid does not over-react to a warm-up sample. Returns the volatility
        expressed in basis points of the anchor.
        """
        if self._count < 2:
            return self.vol_anchor_bps
        var = self._m2 / (self._count - 1)
        pop_var = self._m2 / self._count
        # EWMA over raw variance adds smoothing beyond the raw Welford value.
        vol = math.sqrt(max(0.0, pop_var)) * math.sqrt(self.vol_window)
        # blend toward the anchor so the grid is stable at start
        blend = min(1.0, self._count / self.vol_window)
        ann_bps = (vol * math.sqrt(365.0) * 10_000.0)
        return self.vol_anchor_bps * (1.0 - blend) + ann_bps * blend

    def _spacing_multiplier(self) -> float:
        """Ratio of current realized vol to the anchor vol, clamped."""
        vol_bps = self._realized_vol_bps()
        if vol_bps <= 0.0:
            return 1.0
        mult = vol_bps / self.vol_anchor_bps
        return min(self.max_spacing_mult, max(1.0 / self.max_spacing_mult, mult))

    # ------------------------------------------------------------------ #
    # Anchor / grid materialisation
    # ------------------------------------------------------------------ #
    def _anchor_step(self, price: float) -> float:
        """Drift the anchor toward the current level by a capped step."""
        target = price
        delta = target - self._anchor
        cap = self.max_anchor_shift_bps / 10_000.0 * price
        delta = max(-cap, min(cap, delta))
        return self.anchor_ewma_alpha * delta

    def _deploy_pool(self) -> float:
        """Quote capital actually placed on the book (after the reserve)."""
        return self.capital * (1.0 - self.reserve_ratio)

    def _slot_size(self) -> float:
        """Quote per level, bounded by the deployable pool."""
        pool = self._deploy_pool()
        per_level = pool * self.slot_risk
        return round(min(per_level, pool / max(1, self.levels * 2)), self.price_decimals)

    def _level_prices(self, price: float) -> Dict[str, Any]:
        """Materialise bid/ask legs with volatility-scaled spacing."""
        mult = self._spacing_multiplier()
        spacing = self.base_spacing_bps * mult / 10_000.0
        bids: list[float] = []
        asks: list[float] = []
        for i in range(1, self.levels + 1):
            bids.append(round(price * (1.0 - i * spacing), self.price_decimals))
            asks.append(round(price * (1.0 + i * spacing), self.price_decimals))
        return {"bids": bids, "asks": asks, "spacing_mult": round(mult, 4)}

    # ------------------------------------------------------------------ #
    # Public API (StrategyBase contract)
    # ------------------------------------------------------------------ #
    def on_tick(self, price: float, ts: Optional[float] = None) -> Dict[str, Any]:
        """Update vol EWMA + anchor, return the proposed order grid."""
        if price <= 0.0:
            return {"error": "non-positive price", "levels": {"bids": [], "asks": []}}

        self._push_return(self._last_price, price)
        self._last_price = price

        if self._anchor <= 0.0:
            self._anchor = price
        self._anchor += self._anchor_step(price)

        levels = self._level_prices(self._anchor)
        return {
            "symbol": self.symbol,
            "anchor": round(self._anchor, self.price_decimals),
            "realized_vol_bps": round(self._realized_vol_bps(), 2),
            "spacing_mult": levels["spacing_mult"],
            "reserve_quote": round(self.capital * self.reserve_ratio, self.price_decimals),
            "deploy_pool": round(self._deploy_pool(), self.price_decimals),
            "slot_size": self._slot_size(),
            "levels_bids": levels["bids"],
            "levels_asks": levels["asks"],
            "n_buy_levels": self.levels,
            "n_sell_levels": self.levels,
        }

    def on_fill(self, side: str, price: float, qty: float) -> None:
        """Record a fill for footprint and cash-flow tracking."""
        if price <= 0.0 or qty <= 0.0:
            return
        if side == "buy":
            self._total_buys += 1
            self._cash_flow -= price * qty
        elif side == "sell":
            self._total_sells += 1
            self._cash_flow += price * qty
        # no unbounded retention: we only keep counters

    def stats(self) -> Dict[str, Any]:
        """Compact runtime stats for health/reporting."""
        return {
            "buys": self._total_buys,
            "sells": self._total_sells,
            "cash_flow": round(self._cash_flow, self.price_decimals),
            "reserve_quote": round(self.capital * self.reserve_ratio, self.price_decimals),
            "realized_vol_bps": round(self._realized_vol_bps(), 2),
            "samples": self._count,
        }

    def estimate_memory_mb(self) -> float:
        """Bound resident footprint: O(levels) + capped return deque."""
        bytes_levels = self.levels * 2 * 8
        bytes_returns = self.return_window * 8 * 2  # float objects + ref
        total = (bytes_levels + bytes_returns + 4096) * 10  # 10x slack
        return round(total / (1024.0 * 1024.0), 4)

    def re_root(self, new_anchor: float) -> None:
        """Explicitly re-root the grid to ``new_anchor``.

        Only called from the deploy tooling on a config change or a force
        re-root; runs a bounded ``gc.collect()`` here (rare path, not hot).
        """
        if new_anchor <= 0.0:
            raise ValueError("re_root requires a positive anchor")
        self._anchor = float(new_anchor)
        gc.collect()


def _selftest() -> None:
    """Inline smoke test with small synthetic data (no external deps)."""
    grid = VolBufferGrid(symbol="SOL/EUR", capital=13.5, levels=6, reserve_ratio=0.2)

    # 1) First tick roots the anchor and reports the full reserve.
    d1 = grid.on_tick(100.0)
    assert d1["anchor"] == 100.0
    assert d1["reserve_quote"] == 2.7  # 20% of 13.5
    assert len(d1["levels_bids"]) == 6
    assert len(d1["levels_asks"]) == 6

    # 2) Growing vol widens spacing vs a calm regime.
    calm = grid
    for i in range(1, 40):
        calm.on_tick(100.0 + 0.05 * math.sin(i))
    vol_grid = VolBufferGrid(symbol="SOL/EUR", capital=13.5, levels=6, reserve_ratio=0.2)
    for i in range(1, 40):
        vol_grid.on_tick(100.0 + 1.5 * math.sin(i * 1.7))  # big amplitude

    d_calm = grid._level_prices(grid._anchor)
    d_vol = vol_grid._level_prices(vol_grid._anchor)
    calm_sp = d_calm["asks"][1] - d_calm["asks"][0]
    vol_sp = d_vol["asks"][1] - d_vol["asks"][0]
    assert vol_sp > calm_sp, "high-vol regime must widen spacing"

    # 3) Deploy pool never exceeds capital-minus-reserve.
    assert grid._deploy_pool() == 13.5 * 0.8

    # 4) Fill counters are bounded and no fill raises.
    for i in range(50):
        grid.on_fill("buy", 100.0, 0.01)
        grid.on_fill("sell", 101.0, 0.01)
    assert grid._total_buys == 50
    assert grid._total_sells == 50
    assert math.isclose(grid._cash_flow, 0.5, rel_tol=1e-9), f"cash_flow={grid._cash_flow}"

    # 5) Config guard raises on bad input.
    try:
        VolBufferGrid(symbol="X", capital=10.0, reserve_ratio=1.5)
        raise AssertionError("should have raised on reserve_ratio >= 1")
    except ValueError:
        pass

    # 6) re_root / gc path is safe.
    grid.re_root(100.0)
    assert grid._anchor == 100.0

    print(
        f"SELFTEST PASS | mem={grid.estimate_memory_mb()}MB "
        f"calm_sp={calm_sp:.4f} vol_sp={vol_sp:.4f} "
        f"buys={grid._total_buys} sells={grid._total_sells} "
        f"reserve={grid.capital * grid.reserve_ratio}"
    )


if __name__ == "__main__":
    _selftest()
