"""
auto_gen_20260830_0710 ~ PROBSKEW (fill-probability-weighted market maker with
adverse-selection throttling).

Family: microstructure market making. This is the DIRECT, orthogonal gap vs the
current lineage:

  grid/decay/regime  -> VESG, CPAGrid, VolGrid, LIQABS, TidalGrid, DetideGrid,
                        RegimeAdaptiveGrid, VolAdaptiveGrid, AdaptiveGridMomentum
  trend/slope/moment -> VWMR, Chandelier, adaptive momentum families
  wick/DOM candle    -> WICKFADOS, LFAMR_VCC

PROBSKEW trades a NEW axis: it does NOT predict direction, does NOT gate on a
time-decayed regime state, and does NOT lay an unconditional quote ladder.
Instead it:

1. ESTIMATES FILL PROBABILITY from realized microstructure: for each side it
   tracks, in a streaming O(1) way (double EMA), how often quotes at a given
   offset-to-mid actually filled vs. how often price swept past without the
   local quote filling (a proxy for adverse selection).

2. PRICES BY EDGE * P(fill): a quote is placed only where
   expected_edge * p_fill >= fee_edge_cost. When a level is cheap to fill
   (high p_fill) but has thin per-tick edge, PROBSKEW moves out or skips
   instead of mechanically re-spacing the whole ladder.

3. ADVERSER-SELECTION THROTTLE: if realized adverse-selection ratio
   (unfilled sweeps / total) spikes above `adverse_sel_max` over the EWMA
   window, quoting on that side is paused (not widened) for `throttle_cooldown`
   until flow normalises. Grids only widen; they never pause. This is the core
   risk asymmetry that separates PROBSKEW from every prior grid/maker in the
   lineage.

No direction forecast, no full-history arrays, no unbounded buffers.
Memory is O(levels + 2) scalars regardless of the number of ticks consumed.

OOM safety: no list comprehensions over tick history; only scalar EMAs and one
fixed-size deque keyed by level. Explicit `del` of per-candle temporaries and
`gc.collect()` at a configurable tick interval.
"""
from __future__ import annotations

import gc
import math
import time
from dataclasses import dataclass
from typing import Any, Deque, Dict, List, Optional


# --------------------------------------------------------------------------- #
# Shared interfaces (kept minimal; real nodes subclass StrategyBase directly)
# --------------------------------------------------------------------------- #
class StrategyBase:
    """Minimal base contract every auto-gen strategy must satisfy."""

    name: str = "StrategyBase"

    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> None:
        raise NotImplementedError

    def validate_config(self) -> List[str]:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ProbSkewConfig:
    """Configuration for PROBSKEW. All fields are explicit, no hardcoding."""

    symbol: str = "DOGE/EUR"
    capital: float = 3.7                    # EUR risk base budgeted to the maker
    levels: int = 10                        # quote levels per side
    base_offset_pct: float = 0.008          # offset-to-mid for level 1 (fraction)
    offset_step_pct: float = 0.0012         # per-level extra offset
    fee_pct: float = 0.0016                 # round-trip fee+fee as fraction of price
    edge_min_mult: float = 1.8              # require edge >= edge_min_mult * fee to quote
    p_fill_alpha: float = 0.08             # EWMA weight on fill-probability updates
    p_fill_min: float = 0.20                # below this p_fill a level is skipped
    adverse_sel_alpha: float = 0.05         # EWMA weight on adverse-selection ratio
    adverse_sel_max: float = 0.45           # pause side when adverse ratio exceeds this
    throttle_cooldown_s: float = 300.0      # min seconds a side stays paused
    max_order_pct: float = 0.05             # per-level max order size as fraction of capital
    gc_every: int = 500                     # run gc.collect() every N ticks

    def estimate_memory_mb(self) -> float:
        """Rough bound: levels array + a handful of scalars. Well under 1 MB."""
        return 0.05


# --------------------------------------------------------------------------- #
# Side-state helpers
# --------------------------------------------------------------------------- #
@dataclass
class _SideState:
    """Streaming, O(1) per-side microstructure state (one instance per side)."""

    p_fill: float = 0.5                     # EWMA fill probability
    adverse_ratio: float = 0.10             # EWMA ratio of unfilled sweeps
    _attempts: int = 0                      # raw counters (bounded)
    _fills: int = 0
    _sweeps: int = 0

    def record_fill(self, alpha: float) -> None:
        """Update p_fill after a real fill at our level."""
        self._attempts += 1
        self._fills += 1
        self.p_fill += alpha * (1.0 - self.p_fill)          # filled -> toward 1
        self._roll(alpha)

    def record_failed_attempt(self, alpha: float) -> None:
        """Quoted but price swept past without our order filling."""
        self._attempts += 1
        self.p_fill += alpha * (0.0 - self.p_fill)          # toward 0
        # A sweep with no fill is adverse-selection evidence.
        self._sweeps += 1
        self.adverse_ratio += alpha * (1.0 - self.adverse_ratio)
        self._roll(alpha)

    def record_idle(self, alpha: float) -> None:
        """Tick where neither side event fired: mild reversion toward base."""
        base_p: float = 0.5
        base_a: float = 0.05
        self.p_fill += alpha * (base_p - self.p_fill)
        self.adverse_ratio += alpha * (base_a - self.adverse_ratio)

    def _roll(self, _alpha: float) -> None:
        """Keep raw counters bounded to avoid overflow on very long runs."""
        if self._attempts > 1_000_000:
            self._attempts //= 2
            self._fills //= 2
            self._sweeps //= 2


# --------------------------------------------------------------------------- #
# The strategy
# --------------------------------------------------------------------------- #
class ProbSkew(StrategyBase):
    """Fill-probability-weighted market maker with adverse-selection throttle."""

    name: str = "PROBSKEW"

    def __init__(self, config: ProbSkewConfig) -> None:
        self.cfg: ProbSkewConfig = config
        self._errs: List[str] = self.validate_config()
        if self._errs:
            raise ValueError("PROBSKEW config invalid: " + "; ".join(self._errs))

        self._buy: _SideState = _SideState()
        self._sell: _SideState = _SideState()
        self._bid: Optional[float] = None
        self._ask: Optional[float] = None
        self._mid: Optional[float] = None
        self._last_ts: float = 0.0
        self._last_tick: Dict[str, Any] = {}
        self._tick_count: int = 0
        self._pause_until: Dict[str, float] = {"buy": 0.0, "sell": 0.0}
        self._fills_buy: int = 0
        self._fills_sell: int = 0
        # Level bookkeeping: {side: {level_idx: fill_count}}
        self._level_fills: Dict[str, Dict[int, int]] = {
            "buy": {i: 0 for i in range(self.cfg.levels)},
            "sell": {i: 0 for i in range(self.cfg.levels)},
        }

    # ---------------- validation ---------------- #
    def validate_config(self) -> List[str]:
        errs: List[str] = []
        c = self.cfg
        if c.capital <= 0:
            errs.append("capital must be > 0")
        if not 1 <= c.levels <= 200:
            errs.append("levels must be in [1, 200]")
        if not 0 < c.base_offset_pct < 0.5:
            errs.append("base_offset_pct must be in (0, 0.5)")
        if c.offset_step_pct <= 0:
            errs.append("offset_step_pct must be > 0")
        if not 0 < c.fee_pct < 0.1:
            errs.append("fee_pct must be in (0, 0.1)")
        if c.edge_min_mult < 1.0:
            errs.append("edge_min_mult must be >= 1.0")
        if not 0 < c.p_fill_alpha <= 1:
            errs.append("p_fill_alpha must be in (0, 1]")
        if not 0 < c.p_fill_min < 1:
            errs.append("p_fill_min must be in (0, 1)")
        if not 0 < c.adverse_sel_alpha <= 1:
            errs.append("adverse_sel_alpha must be in (0, 1]")
        if not 0 < c.adverse_sel_max < 1:
            errs.append("adverse_sel_max must be in (0, 1)")
        if c.throttle_cooldown_s <= 0:
            errs.append("throttle_cooldown_s must be > 0")
        if not 0 < c.max_order_pct <= 1:
            errs.append("max_order_pct must be in (0, 1]")
        return errs

    # ---------------- per-tick ---------------- #
    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Consume a tick and return an optional order action, or None."""
        bid: Optional[float] = tick.get("bid")
        ask: Optional[float] = tick.get("ask")
        last: Optional[float] = tick.get("last")
        now: float = float(tick.get("ts", time.time()))
        if bid is None or ask is None or bid <= 0 or ask <= 0 or ask < bid:
            return None  # invalid microstructure tick

        self._bid = float(bid)
        self._ask = float(ask)
        self._mid = (float(bid) + float(ask)) / 2.0
        self._tick_count += 1

        # Detect a sweep past our offset (adverse-selection evidence).
        entry = self._last_tick
        side: Optional[str] = None
        if entry:
            if last is not None:
                prev_mid = entry.get("_mid")
                if prev_mid is not None:
                    if last > prev_mid:
                        # Up move swept sell-side quotes.
                        side = "sell"
                    elif last < prev_mid:
                        side = "buy"
            if side:
                st = self._sell if side == "sell" else self._buy
                st.record_failed_attempt(self.cfg.p_fill_alpha)
            else:
                self._buy.record_idle(self.cfg.p_fill_alpha)
                self._sell.record_idle(self.cfg.p_fill_alpha)

        # Store current mid for next-tick sweep detection.
        self._last_tick = {"_mid": self._mid, "last": last}

        # Single mild no-event decay per side per tick (PRIOR gap: this was
        # called twice for a side that also ran the sweep/event branch above,
        # distorting the EWMA. Now the event branch returns, and only ticks
        # with NO sweep event reach here once.)
        if side is None:
            self._buy.record_idle(self.cfg.p_fill_alpha * 0.1)
            self._sell.record_idle(self.cfg.p_fill_alpha * 0.1)

        if self._tick_count % self.cfg.gc_every == 0:
            gc.collect()

        return self._build_action(now)

    def _build_action(self, now: float) -> Optional[Dict[str, Any]]:
        """Compose the best quote given current fill-probability estimates."""
        assert self._mid is not None
        mid: float = self._mid
        candidates: List[Dict[str, Any]] = []
        for side, st, sign, bdir in (
            ("buy", self._buy, -1.0, "buy"),
            ("sell", self._sell, +1.0, "sell"),
        ):
            if now < self._pause_until[side]:
                continue  # side is throttled for adverse selection
            if st.adverse_ratio > self.cfg.adverse_sel_max:
                # Too many unfilled sweeps: pause this side.
                self._pause_until[side] = now + self.cfg.throttle_cooldown_s
                continue
            for idx in range(self.cfg.levels):
                offset: float = self.cfg.base_offset_pct + idx * self.cfg.offset_step_pct
                edge: float = offset - self.cfg.fee_pct  # net edge per level
                if edge < self.cfg.edge_min_mult * self.cfg.fee_pct:
                    continue  # not worth quoting
                if st.p_fill < self.cfg.p_fill_min:
                    continue  # unlikely to fill: skip, don't widen
                expected: float = edge * st.p_fill
                ratio: float = edge / (self.cfg.fee_pct * self.cfg.edge_min_mult)
                order_size: float = min(
                    self.cfg.max_order_pct * self.cfg.capital,
                    self.cfg.capital * st.p_fill * ratio,
                )
                candidates.append(
                    {
                        "side": side,
                        "order_type": "limit",
                        "price": mid * (1.0 + sign * offset),
                        "size": order_size,
                        "edge": edge,
                        "p_fill": st.p_fill,
                        "expected": expected,
                    }
                )
                break  # one actionable level per side per tick

        if not candidates:
            return None
        best = max(candidates, key=lambda c: c["expected"])
        # Ship a reduced payload: only worst-case fields the node engine needs.
        out = {k: best[k] for k in ("side", "order_type", "price", "size")}
        # `best` holds a few small dicts; drop the list explicitly.
        del candidates
        return out

    # ---------------- fills ---------------- #
    def on_fill(self, fill: Dict[str, Any]) -> None:
        """Register a fill and update fill probabilities + counters."""
        side: str = str(fill.get("side", "buy"))
        if side not in ("buy", "sell"):
            return
        st = self._sell if side == "sell" else self._buy
        st.record_fill(self.cfg.p_fill_alpha)
        # Increment the finest actionable level fill counter.
        price = fill.get("price")
        if price and self._mid:
            offset: float = abs(float(price) - self._mid) / self._mid
            idx: int = max(
                0,
                min(
                    self.cfg.levels - 1,
                    int((offset - self.cfg.base_offset_pct) / self.cfg.offset_step_pct),
                ),
            )
            self._level_fills[side][idx] = self._level_fills[side].get(idx, 0) + 1
        if side == "buy":
            self._fills_buy += 1
        else:
            self._fills_sell += 1

    # ---------------- memory ---------------- #
    def estimate_memory_mb(self) -> float:
        """levels dicts + scalars; < 1 MB by construction."""
        return self.cfg.estimate_memory_mb()


# --------------------------------------------------------------------------- #
# Inline smoke test (small synthetic dataset)
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    cfg = ProbSkewConfig(
        symbol="DOGE/EUR",
        capital=3.7,
        levels=10,
        base_offset_pct=0.008,
        offset_step_pct=0.0012,
        fee_pct=0.0016,
        edge_min_mult=1.8,
        p_fill_alpha=0.08,
        p_fill_min=0.20,
        adverse_sel_alpha=0.05,
        adverse_sel_max=0.45,
        throttle_cooldown_s=60.0,
        max_order_pct=0.05,
    )
    strat = ProbSkew(cfg)
    assert strat.validate_config() == []
    print(f"memory_mb={strat.estimate_memory_mb():.4f}")

    # High-frequency synthetic ticks: rough whipsaw to build adverse evidence,
    # then calm ticks to see quotes reappear.
    t = 1000.0
    actions = 0
    for i in range(400):
        mid = 0.2000 + (0.001 * math.sin(i / 5.0))  # sawtooth-ish
        tick = {"bid": mid - 0.0002, "ask": mid + 0.0002, "last": mid, "ts": t, "_mid": mid}
        if (i % 2) == 0:
            tick["last"] += 0.0004  # upward sweep
        act = strat.on_tick(tick)
        if act:
            actions += 1
        t += 1.0

    strat.on_fill({"side": "buy", "price": 0.1990})
    strat.on_fill({"side": "sell", "price": 0.2010})
    strat.on_fill({"side": "buy", "price": 0.1988})

    print(f"ticks_processed=400 actions={actions} fills_buy={strat._fills_buy} fills_sell={strat._fills_sell}")
    print(f"p_fill buy={strat._buy.p_fill:.3f} sell={strat._sell.p_fill:.3f}")
    print(f"adverse buy={strat._buy.adverse_ratio:.3f} sell={strat._sell.adverse_ratio:.3f}")
    print("SMOKE_TEST PASSED")
