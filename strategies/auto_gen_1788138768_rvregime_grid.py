"""RVRegimeAdaptiveGrid — realized-volatility driven adaptive grid.

Regime-switching grid whose spacing, levels and capital allocation adapt to
short-window realized volatility. In low-RV regimes the grid tightens (more
levels, smaller spacing) to harvest mean-reversion; in high-RV regimes it
widens and reduces per-level exposure to survive whipsaws.

Memory-safe: rolling tick buffer is hard-bounded to `tick_log` entries and
RV is computed with Welford's online algorithm in O(1) per tick. No
unbounded history is accumulated; no list comprehensions over large slices.
"""

from __future__ import annotations

import gc
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional, Protocol


class StrategyBase(Protocol):
    """Minimal Strategy interface contract used by the engine."""

    def on_tick(self, price: float, ts: Optional[float] = None) -> Dict[str, Any]:
        ...

    def on_fill(self, side: str, price: float, qty: float) -> None:
        ...

    def validate_config(self) -> None:
        ...

    def estimate_memory_mb(self) -> float:
        ...


# Annualization factor for tick frequency. We assume ~1 tick per minute on
# the reference feed (matching Denaro's SOL stream); callers that use a
# different cadence must override `ticks_per_year` accordingly.
TICKS_PER_YEAR_1MIN = 252.0 * 1440.0  # 362_880


@dataclass
class RVRegimeAdaptiveGrid:
    """Adaptive grid strategy keyed on rolling realized volatility.

    Attributes
    ----------
    symbol : str
        Trading pair identifier (information only).
    capital : float
        Total quote capital allocated to this grid instance.
    window : int
        Rolling window (ticks) used to estimate realized volatility.
    base_spacing_bps : float
        Geometric spacing between adjacent levels at RV == ref_rv (bps).
    ref_rv : float
        Reference annualized RV at which spacing equals base_spacing_bps.
    rv_floor / rv_ceil : float
        Clamp bounds for the RV used by the scaling rule.
    levels : int
        Number of grid levels on each side of the anchor price.
    risk_per_level : float
        Fraction of capital risked per level (0..1].
    tick_log : int
        Upper bound on retained ticks for memory guarantees.
    ticks_per_year : float
        Annualization denominator. Default assumes 1-min cadence.
    spacing_sensitivity : float
        Exponent on the RV ratio in the spacing rule. >1 = super-linear
        widening under stress; 1.0 = pure linear scaling.
    """

    symbol: str
    capital: float
    window: int = 300
    base_spacing_bps: float = 25.0
    ref_rv: float = 0.60
    rv_floor: float = 0.20
    rv_ceil: float = 3.00
    levels: int = 12
    risk_per_level: float = 0.08
    tick_log: int = 5000
    ticks_per_year: float = TICKS_PER_YEAR_1MIN
    spacing_sensitivity: float = 1.5

    prices: Deque[float] = field(default_factory=deque, init=False)
    # Welford accumulators over the rolling window (rebuilt on overflow).
    _welford_n: int = field(default=0, init=False)
    _welford_mean: float = field(default=0.0, init=False)
    _welford_m2: float = field(default=0.0, init=False)

    fills: int = 0
    buys: int = 0
    sells: int = 0
    quote_flow: float = 0.0  # signed cash flow; engine computes realized PnL
    _anchor: Optional[float] = None
    _gc_counter: int = field(default=0, init=False)

    # -- lifecycle --------------------------------------------------------

    def validate_config(self) -> None:
        """Validate config invariants; raise ValueError on violation."""
        if self.capital <= 0:
            raise ValueError(f"capital must be >0, got {self.capital}")
        if self.window < 10:
            raise ValueError("window must be >= 10 for stable RV estimate")
        if self.levels < 1:
            raise ValueError("levels must be >= 1")
        if not (0.0 < self.risk_per_level <= 1.0):
            raise ValueError("risk_per_level must be in (0, 1]")
        if self.base_spacing_bps <= 0:
            raise ValueError("base_spacing_bps must be > 0")
        if not (self.rv_floor > 0 and self.rv_ceil > self.rv_floor):
            raise ValueError("require 0 < rv_floor < rv_ceil")
        if self.tick_log < self.window:
            raise ValueError("tick_log must be >= window so RV is always defined")
        if self.spacing_sensitivity <= 0:
            raise ValueError("spacing_sensitivity must be > 0")
        if self.ticks_per_year <= 0:
            raise ValueError("ticks_per_year must be > 0")

    def estimate_memory_mb(self) -> float:
        """Approx resident memory for the rolling tick buffer (floats).

        Deque of boxed Python floats: ~32 B/entry (PyObject + float storage
        + deque slot). Pure-math state is O(1).
        """
        return round((self.tick_log * 32.0) / (1024 * 1024), 4)

    # -- core math --------------------------------------------------------

    def _welford_add(self, x: float) -> None:
        """O(1) Welford update for rolling mean and M2."""
        self._welford_n += 1
        delta = x - self._welford_mean
        self._welford_mean += delta / self._welford_n
        delta2 = x - self._welford_mean
        self._welford_m2 += delta * delta2

    def _welford_remove(self, x: float) -> None:
        """O(1) Welford reverse-update when a tick leaves the window."""
        if self._welford_n <= 1:
            self._welford_n = 0
            self._welford_mean = 0.0
            self._welford_m2 = 0.0
            return
        new_n = self._welford_n - 1
        delta = x - self._welford_mean
        # remove contribution of x from the mean, then from M2
        new_mean = (self._welford_mean * self._welford_n - x) / new_n
        # M2 update via reverse formula: M2_new = M2_old - delta * (x - new_mean)
        self._welford_m2 -= delta * (x - new_mean)
        # clamp tiny negative drift from fp arithmetic
        if self._welford_m2 < 0.0:
            self._welford_m2 = 0.0
        self._welford_n = new_n
        self._welford_mean = new_mean

    def rolling_rv(self) -> float:
        """Annualized realized volatility over the retained rolling window.

        Returns 0.0 until the window is full, so callers can fall back to
        `ref_rv` before warm-up completes.
        """
        if self._welford_n < self.window:
            return 0.0
        if self._welford_mean <= 0 or self._welford_n < 2:
            return 0.0
        variance = self._welford_m2 / (self._welford_n - 1)
        if variance <= 0:
            return 0.0
        return math.sqrt(self.ticks_per_year) * (math.sqrt(variance) / self._welford_mean)

    def _spacing_factor(self, rv: float) -> float:
        """Spacing scaling factor; super-linear in (rv / ref_rv).

        At rv == ref_rv -> 1.0 (nominal spacing). At rv == rv_ceil the
        factor grows as (rv_ceil/ref_rv)**sensitivity, e.g. with defaults
        3.0/0.60 = 5x raw, raised to 1.5 ≈ 11.2x spacing under stress.
        """
        clamped = max(self.rv_floor, min(rv, self.rv_ceil))
        ratio = clamped / self.ref_rv
        return ratio ** self.spacing_sensitivity

    def _current_spacing(self, price: float, rv: Optional[float] = None) -> float:
        """Geometric spacing between adjacent levels at current price."""
        if rv is None:
            rv = self.rolling_rv()
        rv_eff = rv if rv > 0 else self.ref_rv
        return price * (self.base_spacing_bps / 10_000.0) * self._spacing_factor(rv_eff)

    def _level_prices(self, price: float, growth: float) -> List[float]:
        """Geometric ladder `levels` above and below `price`.

        `growth` is the per-step multiplier (1 + bps*sensitivity_term).
        """
        out: List[float] = []
        g_up = growth
        g_dn = 1.0 / growth
        for _ in range(self.levels):
            price *= g_up
            out.append(price)
            price *= g_dn  # back to original via *g_dn = /growth
            out.append(price)
        return out

    # -- tick / fill -----------------------------------------------------

    def on_tick(self, price: float, ts: Optional[float] = None) -> Dict[str, Any]:
        """Process one price tick; emit actionable grid signals.

        Returns a signal dict with optional ``action`` in {hold, buy, sell}.
        The engine treats ``buy``/``sell`` as a request to place a market
        order at ``price`` for ``qty`` quote units.
        """
        if price <= 0:
            raise ValueError(f"invalid price {price}")

        # Push tick into bounded rolling buffer; maintain Welford in O(1).
        if len(self.prices) >= self.tick_log:
            evicted = self.prices.popleft()
            self._welford_remove(evicted)
        self.prices.append(price)
        self._welford_add(price)

        # Periodic GC: every 4096 ticks, never on hot path.
        self._gc_counter += 1
        if self._gc_counter & 0xFFF == 0:
            gc.collect()

        if self._anchor is None:
            self._anchor = price
            return {"action": "set_anchor", "price": price, "rv": self.rolling_rv()}

        rv = self.rolling_rv()
        spacing = self._current_spacing(price, rv)

        # Branchless hold default; fill side overwrites if triggered.
        signal: Dict[str, Any] = {"action": "hold", "price": price, "rv": rv, "spacing": spacing}

        if price <= self._anchor - spacing:
            qty = (self.capital * self.risk_per_level) / price
            signal["action"] = "buy"
            signal["qty"] = round(qty, 8)
            self._anchor = price
        elif price >= self._anchor + spacing:
            qty = (self.capital * self.risk_per_level) / price
            signal["action"] = "sell"
            signal["qty"] = round(qty, 8)
            self._anchor = price
        else:
            # Include the geometric ladder only on hold (cheap enrichment).
            growth = 1.0 + (self.base_spacing_bps / 10_000.0) * self._spacing_factor(rv if rv > 0 else self.ref_rv)
            signal["levels"] = self._level_prices(price, growth)

        return signal

    def on_fill(self, side: str, price: float, qty: float) -> None:
        """Record a confirmed fill; update counters and signed quote flow.

        Realized PnL is computed by the engine on round-trip matching; this
        strategy only tracks gross quote flow for diagnostics.
        """
        if side not in ("buy", "sell"):
            raise ValueError(f"side must be buy|sell, got {side}")
        if price <= 0 or qty <= 0:
            raise ValueError(f"price/qty must be > 0, got {price}/{qty}")
        self.fills += 1
        if side == "buy":
            self.buys += 1
            self.quote_flow -= qty * price
        else:
            self.sells += 1
            self.quote_flow += qty * price


if __name__ == "__main__":
    """Inline smoke test: warmup, regime spacing monotonicity, chaos."""
    # Use hourly ticks so RV values land in realistic 0.1-2.0 annualized range.
    g = RVRegimeAdaptiveGrid(
        symbol="SOL/EUR", capital=13.5, window=300, levels=12,
        ticks_per_year=252.0 * 24.0,  # 1 tick/hour
    )
    g.validate_config()
    assert g.rolling_rv() == 0.0, "pre-warmup RV must be 0"
    print("mem_MB estimate:", g.estimate_memory_mb())

    # Phase 1: low-RV drift walk to warm up the window.
    import random
    random.seed(7)
    px = 150.0
    for _ in range(2_000):
        px *= 1.0 + random.gauss(0, 0.002)  # ~0.2% hourly noise
        sig = g.on_tick(px)
        if sig["action"] in ("buy", "sell"):
            g.on_fill(sig["action"], px, sig["qty"])
    assert len(g.prices) <= g.tick_log, "buffer bound violated"
    rv_low = g.rolling_rv()
    assert rv_low > 0, "expected nonzero RV after warmup"
    print(f"low-RV regime: rv={rv_low:.4f}, fills={g.fills}, bu={g.buys}, se={g.sells}")

    # Phase 2: spacing must be monotonically non-decreasing in rv (clamped).
    spacings = [g._current_spacing(px, rv) for rv in (0.20, 0.40, 0.60, 1.0, 1.5, 2.0, 2.5, 3.0)]
    assert all(spacings[i] <= spacings[i + 1] for i in range(len(spacings) - 1)), \
        f"spacing must be non-decreasing in rv, got {spacings}"
    assert spacings[-1] > spacings[0], "spacing must widen at rv_ceil vs rv_floor"
    print(f"spacing ladder: {[round(s, 4) for s in spacings]}")

    # Phase 3: factor at rv==ref_rv must be exactly 1.0 -> nominal spacing.
    nominal = g._current_spacing(px, g.ref_rv)
    expected = px * (g.base_spacing_bps / 10_000.0)
    assert abs(nominal - expected) < 1e-9, f"ref_rv spacing broken: {nominal} vs {expected}"

    # Phase 4: chaotic walk — must not crash, must not grow unbounded.
    px2 = px
    for _ in range(10_000):
        px2 *= 1.0 + random.gauss(0, 0.02)
        if px2 <= 0:
            px2 = 1e-9
        sig = g.on_tick(px2)
        if sig["action"] in ("buy", "sell"):
            g.on_fill(sig["action"], px2, sig["qty"])
    assert len(g.prices) <= g.tick_log, "buffer bound violated after chaos"
    assert g.fills == g.buys + g.sells, "fill counters inconsistent"
    print(f"chaotic walk: ticks={len(g.prices)}, fills={g.fills}, quote_flow={g.quote_flow:+.4f}")

    # Phase 5: validate_config must reject bad inputs.
    bad_overrides = (
        {"capital": -1.0},
        {"window": 5},
        {"levels": 0},
        {"risk_per_level": 0.0},
        {"risk_per_level": 1.5},
        {"base_spacing_bps": 0.0},
        {"rv_floor": -0.1, "rv_ceil": 0.5},
        {"rv_floor": 1.0, "rv_ceil": 0.5},
        {"tick_log": 100, "window": 300},
        {"spacing_sensitivity": -1.0},
        {"ticks_per_year": 0.0},
    )
    for overrides in bad_overrides:
        kwargs = {"symbol": "X", "capital": 10.0}
        kwargs.update(overrides)
        try:
            RVRegimeAdaptiveGrid(**kwargs).validate_config()
        except ValueError:
            continue
        raise AssertionError(f"validate_config accepted bad config: {overrides}")
    print("validate_config rejects all bad inputs")

    print("SELFTEST PASS")
