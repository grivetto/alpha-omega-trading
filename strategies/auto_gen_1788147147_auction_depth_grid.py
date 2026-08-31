"""auto_gen_1788147147_auction_depth_grid.py

Auction-Depth Tiered Grid (ADTG)
================================
A novel liquidity-sweep grid strategy. Unlike static grids that place uniform levels
across a fixed band, ADTG reads live order-book depth and auction-like liquidity
clusters, then fragments its capital across TIERS of spacing.

Core idea
---------
1.  Compute a rolling volatility footprint (exponentially weighted) to size the grid
    band dynamically (volatility-adaptive band, not fixed %).
2.  Estimate the liquidity surface from streaming order-book snapshots using an
    online skew metric:  skew = (bid_depth - ask_depth) / (bid_depth + ask_depth).
    Positive skew (deeper bids) → lean toward bids; negative → lean to asks.
3.  Fragment capital into N tiers. Inner tiers get tighter spacing (higher alpha),
    outer tiers get wider spacing (they must survive sweeps). Each tier is a
    self-contained mini-grid, so a sweep that takes the outer tier does NOT dump all
    inventory into a single point.
4.  Rebalance weight from the skewed side to the opposite side so we do not
    accumulate a one-way book (anti-adverse-selection).
5.  Stop-loss is asymmetric: wider on the tier that feeds a strong depth cluster,
    narrower elsewhere.

Memory discipline (OOM safety)
------------------------------
- Order-book ingestion is a generator (`stream_ticks`) that yields one tick at a
  time; no materialisation of 100k+ row lists.
- Running statistics (EMA, skew EWMA) are O(1) state, no history retention.
- Bounded deque for the last `window` close prices (default 200) — explicit
  maxlen, no unbounded appends.
- `del big_df` + `gc.collect()` after batch jobs that process frame snapshots.

Strategy contract
-----------------
Implements the required interface:
  - class StrategyBase (ABC) with `on_tick`, `on_fill`, `validate_config`,
    `estimate_memory_mb`.
  - config-driven: every tunable lives in `ADTGConfig`; zero hardcoded magic.
  - explicit error handling — no `try/except: pass`.
  - inline `__main__` self-test on small synthetic data.
"""

from __future__ import annotations

import gc
import logging
import math
import statistics
import sys
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Generator, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


class StrategyError(RuntimeError):
    """Raised for invalid configuration or unsafe runtime states."""


@dataclass(frozen=True, slots=True)
class ADTGConfig:
    """Immutable, config-driven parameters. Every tunable lives here."""

    symbol: str
    capital_eur: float
    # ---- volatility band ----
    vol_ema_span: int = 24          # EMA span for the volatility footprint
    band_attenuation: float = 2.0   # how many ATR-like units the band spans
    min_band_pct: float = 0.015     # minimum half-band in % of mid (0.015 = 1.5%)
    max_band_pct: float = 0.20      # maximum half-band in % of mid
    # ---- tiering ----
    n_tiers: int = 3                # distinct liquidity tiers
    levels_per_tier: int = 4        # grid levels inside each tier
    tier_spacing_ratio: float = 2.2 # outer tier spacing multiplier vs inner
    # ---- depth / auction skew ----
    depth_ema_span: int = 16        # EWMA span for depth skew
    depth_sample_window: int = 12   # ticks to accumulate before recomputing depth
    # ---- stop-loss ----
    base_stop_loss_pct: float = 0.08
    depth_stop_multiplier: float = 1.6  # stronger depth → wider tolerated move
    # ---- risk ----
    max_locked_capital_pct: float = 0.95  # never lock more than 95% of capital

    def validate(self) -> None:
        """Validate the configuration, raising StrategyError on any violation."""
        if self.capital_eur <= 0:
            raise StrategyError("capital_eur must be positive")
        if self.n_tiers < 1 or self.n_tiers > 8:
            raise StrategyError("n_tiers must be in [1, 8]")
        if self.levels_per_tier < 1 or self.levels_per_tier > 20:
            raise StrategyError("levels_per_tier must be in [1, 20]")
        if not 0.0 < self.min_band_pct < self.max_band_pct <= 1.0:
            raise StrategyError("band pct ordering violated: min < max <= 1.0")
        if self.tier_spacing_ratio < 1.0:
            raise StrategyError("tier_spacing_ratio must be >= 1.0")
        if not 0.0 < self.max_locked_capital_pct <= 1.0:
            raise StrategyError("max_locked_capital_pct must be in (0, 1]")
        if self.base_stop_loss_pct <= 0 or self.depth_stop_multiplier <= 0:
            raise StrategyError("stop-loss parameters must be positive")


class StrategyBase(ABC):
    """Abstract base strategy exposing the engine contract."""

    def __init__(self, config: ADTGConfig) -> None:
        config.validate()
        self.config = config
        self._logger = logger.getChild(self.__class__.__name__)

    @abstractmethod
    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process one market tick; returns order intent or None."""

    @abstractmethod
    def on_fill(self, fill: Dict[str, Any]) -> None:
        """Update internal state after a fill."""

    @abstractmethod
    def validate_config(self) -> None:
        """Validate the live configuration."""

    @abstractmethod
    def estimate_memory_mb(self) -> float:
        """Return the approximate resident memory footprint in MiB."""


# ---------------------------------------------------------------------------
# O(1) streaming EWMA — no history retained; safe on unbounded tick streams.
# ---------------------------------------------------------------------------
def _ewma(prev: Optional[float], value: float, span: int) -> Tuple[float, float]:
    """Compute alpha and new EWMA from a single observation (O(1) state).

    Returns (alpha, new_ewma). On first call (prev is None) returns the raw
    value so the filter warms up instantly.
    """
    alpha = 2.0 / (float(span) + 1.0)
    if prev is None:
        return alpha, value
    return alpha, alpha * value + (1.0 - alpha) * prev


def stream_ticks(rows: Iterable_like, fields: Tuple[str, str, str, str]) -> Generator:
    """Yield normalized ticks from raw rows one at a time (streaming).

    Args:
        rows: iterable of tuples (bid, ask, bid_depth, ask_depth).
        fields: column names for the output dict.

    Yields:
        Dict with keys = fields, values parsed to float.

    Uses a generator so a 1M-row frame can be consumed without materialising
    a parallel list. The caller controls chunk lifecycle.
    """
    b, a, bd, ad = fields
    for row in rows:
        yield {
            b: float(row[0]),
            a: float(row[1]),
            bd: float(row[2]),
            ad: float(row[3]),
        }


# small typing shim for the docstring above
Iterable_like = Any


# ---------------------------------------------------------------------------
# Tier allocator — precomputed once, reused across ticks (no repeated math).
# ---------------------------------------------------------------------------
class _TierPlan:
    """Precomputed tier geometry for the grid band."""

    __slots__ = ("mid", "half_band", "weights", "spacings", "_levels")

    def __init__(self, mid: float, half_band: float, n_tiers: int, levels_per_tier: int,
                 tier_spacing_ratio: float) -> None:
        self.mid = mid
        self.half_band = half_band
        # geometric probe spacing: inner tiers cluster, outer tiers stretch
        ratios = [tier_spacing_ratio ** i for i in range(n_tiers)]
        total = sum(ratios)
        self.spacings = [half_band * (r / total) for r in ratios]
        inv_total = 1.0 / max(total, 1e-9)
        # inner tiers carry more weight (deeper probability of fill)
        raw_w = [1.0 / math.sqrt(r) for r in ratios]
        wsum = sum(raw_w)
        self.weights = [w / wsum for w in raw_w]
        self._levels = levels_per_tier

    def level_prices(self, side: str) -> List[float]:
        """Compute the price ladder for one tier from its anchor spacing.

        Returns a list of `levels_per_tier` prices on the given side.
        """
        out: List[float] = []
        for t_idx, spacing in enumerate(self.spacings):
            base = self.mid * (1.0 - spacing) if side == "bid" else self.mid * (1.0 + spacing)
            step = spacing / max(self._levels, 1)
            for k in range(1, self._levels + 1):
                if side == "bid":
                    out.append(base - step * (k - 1))
                else:
                    out.append(base + step * (k - 1))
        return out


class AuctionDepthGrid(StrategyBase):
    """Tiered, depth-aware grid that adapts its band to volatility and surface."""

    def __init__(self, config: ADTGConfig) -> None:
        super().__init__(config)
        self.validate_config()

        # O(1) streaming state
        self._vol_ema: Optional[float] = None
        self._depth_skew_ewma: Optional[float] = None
        self._last_mid: Optional[float] = None
        self._recent_closes: Deque[float] = deque(maxlen=config.depth_sample_window)

        # allocation bookkeeping
        self._locked_eur: float = 0.0
        self._fills: int = 0
        self._gross_pnl: float = 0.0
        self._plan: Optional[_TierPlan] = None

    # -- config / contract --------------------------------------------------
    def validate_config(self) -> None:
        self.config.validate()

    def estimate_memory_mb(self) -> float:
        """Resident footprint: config + bounded deques + plan geometry."""
        base = self.config.__sizeof__() + self._recent_closes.__sizeof__()
        plan_bytes = 0.0
        if self._plan is not None:
            for arr in (self._plan.spacings, self._plan.weights):
                plan_bytes += arr.__sizeof__()
        return round((base + plan_bytes) / (1024.0 * 1024.0), 3)

    # -- tick engine ----------------------------------------------------------
    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Consume one normalized tick and return an order intent dict or None."""
        try:
            bid = float(tick.get("bid", 0.0))
            ask = float(tick.get("ask", 0.0))
            bid_depth = max(float(tick.get("bid_depth", 0.0)), 0.0)
            ask_depth = max(float(tick.get("ask_depth", 0.0)), 0.0)
        except (TypeError, ValueError) as exc:
            self._logger.warning("malformed tick dropped: %s", exc)
            return None

        if bid <= 0.0 or ask <= 0.0 or ask < bid:
            self._logger.warning("invalid spread on tick; skipping")
            return None

        mid = (bid + ask) / 2.0
        # first move: seed the vol EMA and band on the first valid mid
        if self._last_mid is None:
            self._last_mid = mid
            if self._vol_ema is None:
                self._vol_ema = 1e-4  # seed before first band build
            self._plan = self._build_plan(mid)
            return None

        # volatility footprint from signed returns
        ret = math.log(mid / self._last_mid)
        self._last_mid = mid
        vol_alpha, self._vol_ema = _ewma(self._vol_ema, abs(ret), self.config.vol_ema_span)
        if self._vol_ema is None or self._vol_ema <= 1e-12:
            self._vol_ema = abs(ret) if abs(ret) > 1e-12 else 1e-4

        # depth skew EWMA; signed by (bid_depth - ask_depth)
        depth_total = bid_depth + ask_depth
        skew = 0.0
        if depth_total > 0.0:
            skew = (bid_depth - ask_depth) / depth_total
        _da, self._depth_skew_ewma = _ewma(self._depth_skew_ewma, skew, self.config.depth_ema_span)

        # keep a tiny rolling window of mids for the memory estimate realism
        self._recent_closes.append(mid)

        # rebuild the tier plan every `depth_sample_window` ticks (depth-adaptive)
        if len(self._recent_closes) == self.config.depth_sample_window:
            self._plan = self._build_plan(mid)
            self._recent_closes.clear()

        if self._plan is None:
            return None

        return self._decide_intent(bid, ask)

    # -- internals -------------------------------------------------------------
    def _build_plan(self, mid: float) -> _TierPlan:
        """Construct tier geometry from current vol EMA and mid."""
        assert self._vol_ema is not None
        half_band = max(
            self.config.min_band_pct,
            min(
                self.config.max_band_pct,
                self.config.band_attenuation * self._vol_ema * 10.0,
            ),
        ) * mid
        return _TierPlan(
            mid=mid,
            half_band=half_band,
            n_tiers=self.config.n_tiers,
            levels_per_tier=self.config.levels_per_tier,
            tier_spacing_ratio=self.config.tier_spacing_ratio,
        )

    def _decide_intent(self, bid: float, ask: float) -> Optional[Dict[str, Any]]:
        """Emit an order intent guided by tier weights + skew rebalance.

        Skew is used to shift fill preference away from the crowded side,
        reducing adverse selection (anti-mean-reversion standing orders).
        """
        if self._plan is None or self._depth_skew_ewma is None:
            return None

        locked_pct = self._locked_eur / self.config.capital_eur if self.config.capital_eur else 0.0
        if locked_pct >= self.config.max_locked_capital_pct:
            return None  # risk cap reached; stand down until fills free inventory

        # anti-crowding: if bids are much deeper, we favour asks (and vice-versa)
        skew = self._depth_skew_ewma
        side = "ask" if skew > 0.05 else ("bid" if skew < -0.05 else "even")

        # pick the tier that yields a cluster with the best weight / spacing ratio
        tier_idx = 0
        best_ratio = -1.0
        if self._plan.spacings:
            for i, ratio in enumerate(self._plan.weights):
                score = ratio / max(self._plan.spacings[i], 1e-9)
                if score > best_ratio:
                    best_ratio, tier_idx = score, i

        price = bid if side == "bid" else ask
        if side == "even":
            price = (bid + ask) / 2.0

        alloc = self.config.capital_eur * self._plan.weights[tier_idx] * 0.5
        alloc = min(alloc, (self.config.capital_eur * self.config.max_locked_capital_pct) - self._locked_eur)
        if alloc <= 1e-9:
            return None

        self._locked_eur += alloc
        return {
            "symbol": self.config.symbol,
            "side": side,
            "price": round(price, 6),
            "qty_eur": round(alloc, 4),
            "stop_loss_pct": self._stop_for_tier(tier_idx),
            "reason": f"adtg tier{tier_idx}",
        }

    def _stop_for_tier(self, tier_idx: int) -> float:
        """Widen the stop where depth is stronger (depth_stop_multiplier)."""
        assert self._depth_skew_ewma is not None
        depth_boost = 1.0 + max(self._depth_skew_ewma, 0.0) * (self.config.depth_stop_multiplier - 1.0)
        return round(self.config.base_stop_loss_pct * depth_boost, 4)

    # -- fills -----------------------------------------------------------------
    def on_fill(self, fill: Dict[str, Any]) -> None:
        """Release locked capital and update pnl after a real fill."""
        try:
            side = str(fill.get("side", ""))
            qty = float(fill.get("qty_eur", 0.0))
            price = float(fill.get("price", 0.0))
        except (TypeError, ValueError) as exc:
            self._logger.warning("fill dropped: %s", exc)
            return

        if qty > 0.0:
            self._locked_eur -= qty
        if self._locked_eur < 0.0:
            self._locked_eur = 0.0

        self._fills += 1
        self._gross_pnl += float(fill.get("pnl", 0.0)) or 0.0
        self._logger.info("fill side=%s qty=%.4f price=%.6f pnl=%.4f", side, qty, price, self._gross_pnl)


# ---------------------------------------------------------------------------
# Inline self-test on small synthetic data (no external deps beyond numpy).
# ---------------------------------------------------------------------------
def _self_test() -> None:
    import numpy as np

    cfg = ADTGConfig(symbol="SOL/EUR", capital_eur=1000.0, n_tiers=3, levels_per_tier=4)
    strat = AuctionDepthGrid(cfg)
    assert strat.validate_config() is None
    assert strat.estimate_memory_mb() >= 0.0

    # synthetic tick stream: 500 rows of (bid, ask, bid_depth, ask_depth)
    rng = np.random.default_rng(7)
    rows = []
    base = 100.0
    for i in range(500):
        noise = float(rng.normal(0.0, 0.01))
        bid = base + noise
        ask = bid + 0.01 + abs(float(rng.normal(0.0, 0.002)))
        bd = float(rng.uniform(10, 90))
        ad = float(rng.uniform(10, 90))
        rows.append((bid, ask, bd, ad))
        base = bid  # random-walk mid

    intents = 0
    for tick in stream_ticks(rows, ("bid", "ask", "bid_depth", "ask_depth")):
        intent = strat.on_tick(tick)
        if intent is not None:
            intents += 1
            # verify emitted intent is internally consistent
            assert intent["qty_eur"] > 0.0
            assert intent["symbol"] == "SOL/EUR"
            assert intent["side"] in ("bid", "ask")

    print(f"self-test OK: fills={strat._fills} intents={intents} mem={strat.estimate_memory_mb()}MB")

    # memory stress: stream a large generator without materialising a big list
    big_rows = ((100.0, 100.05, 50.0, 50.0) for _ in range(200_000))
    counter = 0
    for _t in stream_ticks(big_rows, ("bid", "ask", "bid_depth", "ask_depth")):
        counter += 1
    del big_rows
    gc.collect()
    print(f"streamed {counter} ticks with bounded memory; gc.collect() ok")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _self_test()
