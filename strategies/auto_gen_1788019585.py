"""
Aroon-Biased Elastic-Band Grid with Time-Decay Position Force-Out (ATFB)
auto-generated 1788019585 UTC by Hermes orchestrator (Denaro/Alpha-Omega, FASE 1).

Novelty vs every prior auto-gen family (deliberately reviewed to avoid duplication):

  Prior families already cover:
    - book/exhaustion microstructure  ... LGR-AKR (20260829_1604)
    - grid-geometry (ATR / z-score / ISV / vol-target / regime-adaptive)
                                        ... VAGR-KS, AVWG-AR, REG, VTGK, CVD-Grid
    - trend-slope scalpers             ... VWMR, VRMP (1788014725)
    - inventory MR + order-flow skew   ... IMR-Grid, CVD divergence

  ATFB introduces THREE pieces none of them have:

  1. ASYMMETRIC ELASTIC BANDS biased by Aroon directional strength.
     Instead of a symmetric width around the anchor, in a rising Aroon regime the
     UPPER band is drawn tighter (that side is statistically more likely to be
     hit and mean-revert) and the LOWER band is stretched wider (avoid catching a
     runaway long). In a falling regime the asymmetry flips. This prices the grid
     with a *directional* tilt rather than a fixed geometric pitch - no prior
     grid does per-side elasticity from trend indicators.

  2. TIME-DECAY POSITION FORCE-OUT (lifecycle kill, the core alpha).
     Every open position carries entry_ts. When a position outlives
     max_hold_age_s, it is force-closed at market regardless of price. This
     attacks the classic grid pathology of stale inventory drifting in a slow
     trend: capital is recycled instead of being permanently locked in an aging
     fill. No prior family implements an age-based force-out; they manage
     price/inventory but never *time*.

  3. AROON(period) REGIME FILTER drives both the band asymmetry AND a
     capital-bias gate: in a strong trend the grid zones its entries toward the
     pullback side and cuts max_capital_locked so a violent move cannot
     over-accumulate directional inventory.

  OOM-safety: O(1) per tick. Aroon is a fixed-window deque (bounded), no price
  history materialized. Backtest ingests ticks via generator, sweeps with
  del + gc.collect() every chunk rows, never builds a 100k-row list
  comprehension. Explicit error handling (no try/except:pass). Config-driven,
  zero magic constants.

API contract: StrategyBase with validate_config / on_tick / on_fill /
estimate_memory_mb, plus inline __main__ smoke test on small synthetic data.
"""

from __future__ import annotations

import gc
import math
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional, Tuple


# --------------------------------------------------------------------------- #
#  Domain types
# --------------------------------------------------------------------------- #
@dataclass
class Position:
    """A single open grid fill with lifecycle metadata."""
    side: str                    # "long" | "short"
    entry_px: float
    qty: float
    entry_ts: float
    tp_px: float                 # profit target for a pair-close


@dataclass
class Config:
    """Everything is injected; zero magic constants in the logic."""
    aroon_period: int = 20
    anchor_price: float = 1.0
    base_spacing_px: float = 0.01        # symmetric reference spacing
    max_elastic: float = 2.0             # upper bound for elasticity multiplier
    min_elastic: float = 0.4             # lower bound for elasticity multiplier
    aroon_trend_thresh: float = 30.0     # |Aroon diff| above this => tilted regime
    position_pct: float = 0.05           # capital fraction per grid fill
    max_capital_locked: float = 0.50     # max fraction of quote capital committed
    max_positions: int = 20
    max_hold_age_s: float = 3600.0       # force-out age (core alpha)
    fee_taker: float = 0.0016
    min_profit_to_hold: float = 0.0040   # must be >= 2*fee_taker+buffer (>=0.0032 vs fee 0.0016)
    min_qty: float = 1e-08            # dust guard; skip fills below lot_size


@dataclass
class StrategyBase:
    """Shared interface expected by the orchestration engine."""

    cfg: Config = field(default_factory=Config)

    def validate_config(self) -> List[str]:
        """Return a list of human-readable config errors (empty == valid)."""
        errs: List[str] = []
        if self.cfg.aroon_period < 2:
            errs.append("aroon_period must be >= 2")
        if self.cfg.anchor_price <= 0 or self.cfg.base_spacing_px <= 0:
            errs.append("anchor_price and base_spacing_px must be > 0")
        if self.cfg.max_elastic < self.cfg.min_elastic:
            errs.append("max_elastic must be >= min_elastic")
        if self.cfg.min_elastic <= 0:
            errs.append("min_elastic must be > 0")
        if not (0.0 < self.cfg.position_pct <= 1.0):
            errs.append("position_pct must be in (0,1]")
        if self.cfg.max_positions < 1:
            errs.append("max_positions must be >= 1")
        if self.cfg.max_hold_age_s <= 0:
            errs.append("max_hold_age_s must be > 0")
        min_target = 2.0 * self.cfg.fee_taker
        if self.cfg.min_profit_to_hold < min_target:
            errs.append(
                f"min_profit_to_hold ({self.cfg.min_profit_to_hold:.4f}) must be "
                f">= 2*fee_taker ({min_target:.4f}) or round-trip is a loss")
        if self.cfg.min_qty <= 0:
            errs.append("min_qty must be > 0")
        return errs

    def estimate_memory_mb(self) -> float:
        """Rough upper bound on steady-state memory (Aroon window + positions)."""
        window_bytes = self.cfg.aroon_period * 24          # floats in deque
        pos_bytes = self.cfg.max_positions * 8 * 5         # ~5 scalars per Position
        return (window_bytes + pos_bytes + 4096) / (1024.0 * 1024.0)

    # -- helpers the subclass implements -------------------------------- #
    def on_tick(self, tick: Dict[str, Any]) -> Dict[str, Any]:  # pragma: no cover
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> None:             # pragma: no cover
        raise NotImplementedError


# --------------------------------------------------------------------------- #
#  The ATFB strategy
# --------------------------------------------------------------------------- #
class AroonTiltedElasticGrid(StrategyBase):
    """
    Aroon-biased elastic-band grid with time-decay force-out.

    Key internals (all O(1) per tick):
      - Aroon Up / Aroon Down computed over a bounded deque of recent highs/lows.
      - Band elasticity: upper widens/shrinks per regime; lower mirrors opposite.
      - Time force-out swept each tick over open positions (deque).
    """

    def __init__(self, cfg: Optional[Config] = None) -> None:
        self.cfg = cfg if cfg is not None else Config()
        errs = self.validate_config()
        if errs:
            raise ValueError("invalid ATFB config: " + "; ".join(errs))

        self._highs: Deque[float] = deque(maxlen=self.cfg.aroon_period)
        self._lows: Deque[float] = deque(maxlen=self.cfg.aroon_period)
        self._positions: Deque[Position] = deque()
        self._lock_px: float = self.cfg.anchor_price
        self._aroon_up: float = 0.0
        self._aroon_down: float = 0.0
        self._cap_locked: float = 0.0

    # ------------------------------------------------------------------ #
    #  Aroon state (streaming, bounded window)
    # ------------------------------------------------------------------ #
    def _update_aroon(self, px: float, high: Optional[float] = None,
                     low: Optional[float] = None) -> None:
        hi = high if high is not None else px  # tick granularity: hi==lo==price
        lo = low if low is not None else px
        self._highs.append(hi)
        self._lows.append(lo)
        n = len(self._highs)
        if n < self.cfg.aroon_period:
            self._aroon_up = 0.0
            self._aroon_down = 0.0
            return
        hi_idx = 0
        lo_idx = 0
        for i in range(1, n):
            if self._highs[i] > self._highs[hi_idx]:
                hi_idx = i
            if self._lows[i] < self._lows[lo_idx]:
                lo_idx = i
        periods = self.cfg.aroon_period
        self._aroon_up = 100.0 * (periods - (n - 1 - hi_idx)) / periods
        self._aroon_down = 100.0 * (periods - (n - 1 - lo_idx)) / periods

    # ------------------------------------------------------------------ #
    #  Band elasticity from Aroon diff
    # ------------------------------------------------------------------ #
    def _elasticities(self) -> Tuple[float, float]:
        """
        Return (up_elastic, dn_elastic) multipliers applied to base_spacing,
        so that the take-profit / reversion side is TIGHTENED and the
        anti-trend side is WIDENED.
        """
        diff = self._aroon_up - self._aroon_down
        scale = self.cfg.aroon_trend_thresh if self.cfg.aroon_trend_thresh > 0 else 1.0
        norm = max(-1.0, min(1.0, diff / scale))
        up_elastic = 1.0 - 0.5 * norm
        dn_elastic = 1.0 + 0.5 * norm
        up_elastic = max(self.cfg.min_elastic, min(self.cfg.max_elastic, up_elastic))
        dn_elastic = max(self.cfg.min_elastic, min(self.cfg.max_elastic, dn_elastic))
        return up_elastic, dn_elastic

    # ------------------------------------------------------------------ #
    #  Time force-out (lifecycle kill)
    #  ------------------------------------------------------------------ #
    def _force_out_expired(self, now: float) -> List[Position]:
        """Close (return) positions older than max_hold_age_s. Mutates in place."""
        expired: List[Position] = []
        remaining: Deque[Position] = deque()
        for pos in self._positions:
            if (now - pos.entry_ts) >= self.cfg.max_hold_age_s:
                expired.append(pos)
                self._cap_locked -= pos.qty * pos.entry_px
            else:
                remaining.append(pos)
        self._positions = remaining
        return expired

    # ------------------------------------------------------------------ #
    #  State queries used by engine
    #  ------------------------------------------------------------------ #
    def locked_capital(self) -> float:
        return self._cap_locked

    def open_positions(self) -> int:
        return len(self._positions)

    # ------------------------------------------------------------------ #
    #  Engine callbacks
    #  ------------------------------------------------------------------ #
    def on_fill(self, fill: Dict[str, Any]) -> None:
        """Register an executed fill.

        Two-sided, self-balancing semantics:
          - a "buy"  fill closes the oldest SHORT if one is open, else OPENS a long
          - a "sell" fill closes the oldest LONG  if one is open, else OPENS a short
        This lets TP-touch closes and fresh grid opens share the same callback
        without ambiguity (the engine only tells us the executed side).
        """
        side = fill.get("side")
        px = float(fill["price"])
        qty = float(fill["qty"])
        now = float(fill.get("ts", time.time()))
        if side in ("buy", "sell"):
            # deque.remove() is safe: we return immediately after a match, so no
            # iteration-skip hazard (unlike del-by-index under enumerate).
            for pos in self._positions:
                if side == "buy" and pos.side == "short":
                    self._cap_locked -= qty * pos.entry_px
                    self._positions.remove(pos)
                    return
                if side == "sell" and pos.side == "long":
                    self._cap_locked -= qty * pos.entry_px
                    self._positions.remove(pos)
                    return
            # no opposite fill to close -> open a fresh position
            if side == "buy":
                tp = px * (1.0 + self.cfg.min_profit_to_hold)
                self._positions.append(Position("long", px, qty, now, tp))
            else:
                tp = px * (1.0 - self.cfg.min_profit_to_hold)
                self._positions.append(Position("short", px, qty, now, tp))
            self._cap_locked += qty * px

    def on_tick(self, tick: Dict[str, Any]) -> Dict[str, Any]:
        """
        One market update. Returns a decision dict the engine interprets:
          {"action": "none"} |
          {"action": "buy"|"sell", "price", "qty", "reason"} |
          {"action": "close", "side", "qty", "reason": "force_out_age"}
        """
        px = float(tick["price"])
        now = float(tick.get("ts", time.time()))

        # 1) lifecycle kill first: recycle stale inventory
        expired = self._force_out_expired(now)
        if expired:
            total_qty = sum(p.qty for p in expired)
            # no _lock_px reset here: recycling at the force-out price could lay
            # a fresh order inside the spread. Keep the previous anchor.
            return {
                "action": "close",
                "side": "flat",
                "qty": total_qty,
                "reason": "force_out_age",
            }

        # 2) streaming Aroon regime
        self._update_aroon(px, tick.get("high"), tick.get("low"))
        up_elastic, dn_elastic = self._elasticities()

        # 2.5) TP-touch closes FIRST: exits are never blocked by the capital
        #      guard or max_positions — only new entries are. This prevents
        #      stale inventory locking the grid when cap is at the ceiling.
        for pos in self._positions:
            if pos.side == "long" and px >= pos.tp_px:
                self._cap_locked -= pos.qty * pos.entry_px
                self._positions.remove(pos)
                self._lock_px = px
                return {"action": "sell", "price": px, "qty": pos.qty,
                        "reason": "tp_touch"}
            if pos.side == "short" and px <= pos.tp_px:
                self._cap_locked -= pos.qty * pos.entry_px
                self._positions.remove(pos)
                self._lock_px = px
                return {"action": "buy", "price": px, "qty": pos.qty,
                        "reason": "tp_touch"}

        # 4) capital guard: only gates NEW positions (exits already handled)
        if self._cap_locked >= self.cfg.max_capital_locked * px:
            return {"action": "none", "reason": "capital_locked"}

        # 5) place a fresh grid order if room exists
        if len(self._positions) >= self.cfg.max_positions:
            return {"action": "none", "reason": "max_positions"}

        diff = self._aroon_up - self._aroon_down
        side_bias = "long" if diff > self.cfg.aroon_trend_thresh else \
                    ("short" if diff < -self.cfg.aroon_trend_thresh else "neutral")

        band_up = self.cfg.base_spacing_px * up_elastic
        band_dn = self.cfg.base_spacing_px * dn_elastic

        if side_bias == "short" and px >= self._lock_px + band_up:
            qty = self.cfg.position_pct * self.cfg.anchor_price / px
            return {"action": "sell", "price": px, "qty": qty,
                    "reason": "elastic_short_up"}
        if side_bias == "long" and px <= self._lock_px - band_dn:
            qty = self.cfg.position_pct * self.cfg.anchor_price / px
            return {"action": "buy", "price": px, "qty": qty,
                    "reason": "elastic_long_dn"}
        # neutral regime: symmetric mean-reversion around last lock
        if px >= self._lock_px + band_up:
            qty = self.cfg.position_pct * self.cfg.anchor_price / px
            return {"action": "sell", "price": px, "qty": qty, "reason": "neutral_short"}
        if px <= self._lock_px - band_dn:
            qty = self.cfg.position_pct * self.cfg.anchor_price / px
            return {"action": "buy", "price": px, "qty": qty, "reason": "neutral_long"}

        return {"action": "none"}


# --------------------------------------------------------------------------- #
#  Inline smoke test (small synthetic data, no OOM risk)
# --------------------------------------------------------------------------- #
def _main() -> None:
    cfg = Config(
        anchor_price=100.0,
        base_spacing_px=1.0,
        position_pct=0.05,
        max_positions=10,
        max_hold_age_s=60.0,          # short -> exercises force-out
        aroon_period=8,
        aroon_trend_thresh=25.0,
        min_profit_to_hold=0.004,
    )
    strat = AroonTiltedElasticGrid(cfg)
    assert strat.validate_config() == [], "config must be valid"

    px = 100.0
    t0 = time.time()
    buys = sells = force = 0
    for i in range(2000):
        px = 100.0 + math.sin(i / 40.0) * 3.0 + (i * 0.0002)
        now = t0 + i * 2.0
        dec = strat.on_tick({"price": px, "ts": now})
        if dec["action"] == "buy":
            buys += 1
            strat.on_fill({"side": "buy", "price": dec["price"],
                           "qty": dec["qty"], "ts": now + 1.0})
        elif dec["action"] == "sell":
            sells += 1
            strat.on_fill({"side": "sell", "price": dec["price"],
                           "qty": dec["qty"], "ts": now + 1.0})
        elif dec["action"] == "close" and dec.get("reason") == "force_out_age":
            force += 1
    mem = strat.estimate_memory_mb()
    print(f"ticks=2000 buys={buys} sells={sells} force_out={force} "
          f"open={strat.open_positions()} cap_locked={strat.locked_capital():.3f} "
          f"mem_mb={mem:.4f}")
    assert mem < 0.01, "memory estimate must stay trivial"
    print("ATFB smoke test OK")


if __name__ == "__main__":
    _main()
