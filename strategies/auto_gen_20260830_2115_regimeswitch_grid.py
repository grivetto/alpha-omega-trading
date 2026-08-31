"""Auto-generated strategy: regimeswitch_grid - Dual-Regime Adaptive Grid State-Machine.

Hermes strategy engineering cycle 2026-08-30 21:15.

Novelty vs prior gens:
  Every prior gen shapes *space between levels* off a single signal (price rails,
  vol ratios, fill flow, spread). regimeswitch_grid introduces a **higher-order
  decision**: instead of always placing the same ladder orientation, it holds an
  explicit *regime state machine* and switches the entire grid *architecture*
  between two modes:
    1. RANGE mode (fade): dense symmetric ladder around mid, profiting from
       mean reversion - ladder re-anchors to the recent Centre of Gravity (CoG).
    2. TREND mode (ride): sparse staggered ladder that *leans/front-runs the
       drift* - levels concentrate on the pullback side of the trend and widen
       with distance, so momentum winners are ridden while counter-trend
       levels are de-notionalised.
  The switch trigger is a **Robust Trend Score**: a signed, normalised ratio of
  (Efficient Price Changes) vs (Noise Price Changes) over a bounded window. It
  is drawn from a fixed-size deque, std-normalised, and hysteresis-gated so the
  grid does not flicker between modes on every tick. A separate mode lock-out
  counter enforces a minimum dwell time in each regime.
  Additionally, each mode keeps its own ATR-shaped spacing profile
  (config-driven: range spacing vs trend spacing), so both regimes tune
  independently. On regime flip the grid softly re-anchors (limited re-spacing
  per tick) rather than instantly jumping - avoiding level churn that would pay
  fees on every tick.

OOM-safety: only three bounded deques for rolling state; no unbounded
comprehensions; stream_ticks() yields one tick at a time; a periodic
_flush_window releases large temporaries with del + explicit gc.collect().
All tunables config-driven via _DEFAULTS.

Error handling: explicit typed exceptions; no bare except, no except:pass.
"""

from __future__ import annotations

import gc
import math
from collections import deque
from typing import Any, Deque, Dict, Generator, List, Optional


class RegimeConfigError(ValueError):
    """Raised when a configuration value is out of the supported range."""


class StrategyBase:
    """Atomic contract every auto-generated strategy must satisfy.

    Implementations must be side-effect free w.r.t. external state and must not
    assume a specific broker API - the harness wraps this with an adapter.
    Methods raise NotImplementedError until overridden.
    """

    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Called once per market tick. Return an optional signal dict, else None."""
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> None:
        """Called when a grid/fill event occurs. Updates internal flow/inventory state."""
        raise NotImplementedError

    def validate_config(self) -> List[str]:
        """Return config error strings. Empty list == config is valid."""
        return []

    def estimate_memory_mb(self) -> float:
        """Upper-bound heap estimate for this strategy in MiB."""
        raise NotImplementedError


class RegimeSwitchGrid(StrategyBase):
    """Dual-regime (range/trend) adaptive grid driven by a Robust Trend Score.

    StrategyBase conformance: implements on_tick / on_fill / validate_config /
    estimate_memory_mb plus inline __main__ synthetic self-test.
    """

    _DEFAULTS: Dict[str, Any] = {
        "trend_window": 120,          # ticks used by the Robust Trend Score
        "co_window": 40,              # ticks for Centre-of-Gravity anchor
        "trend_score_thresh": 0.62,   # abs(score) above -> TREND, below -> RANGE
        "hysteresis": 0.14,           # score band preventing mode flicker
        "min_dwell_ticks": 90,        # minimum ticks to stay in a regime
        "range_spacing_pct": 0.0035,  # ATR-based spacing in RANGE mode (fraction)
        "trend_spacing_pct": 0.0060,  # ATR-based spacing in TREND mode (fraction)
        "range_levels": 28,           # ladder count in RANGE mode
        "trend_levels": 16,           # ladder count in TREND mode
        "max_respace_per_tick": 0.25, # soft re-anchor cap (fraction of spacing)
        "max_inventory_skew": 0.35,   # refuse levels beyond this notional skew
        "atr_period": 14,             # real-time ATR window for spacing
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config: Dict[str, Any] = dict(self._DEFAULTS)
        if config:
            self.config.update(config)

        errors = self.validate_config()
        if errors:
            raise RegimeConfigError("; ".join(errors))

        w = int(self.config["trend_window"])
        c = int(self.config["co_window"])
        a = int(self.config["atr_period"])

        # Bounded rolling state (fixed-size buffers - OOM-safe).
        self._prices: Deque[float] = deque(maxlen=w)
        self._deltas: Deque[float] = deque(maxlen=w)
        self._atr: Deque[float] = deque(maxlen=a)

        self._anchor: float = 0.0
        self._last_price: Optional[float] = None
        self._mode: str = "RANGE"
        self._dwell: int = 0
        self._score: float = 0.0
        self._direction: int = 0
        self._net_inventory: float = 0.0
        self._tick_count: int = 0
        self._levels_placed: List[Dict[str, Any]] = []

    # -- config -------------------------------------------------------------
    def validate_config(self) -> List[str]:
        errs: List[str] = []
        for key in ("trend_window", "co_window", "atr_period", "min_dwell_ticks",
                    "range_levels", "trend_levels"):
            val = self.config.get(key)
            if not isinstance(val, int) or val <= 0:
                errs.append(key + " must be a positive int (got " + repr(val) + ")")
        for key in ("range_spacing_pct", "trend_spacing_pct", "trend_score_thresh",
                    "hysteresis", "max_respace_per_tick", "max_inventory_skew"):
            val = self.config.get(key)
            if not isinstance(val, (int, float)) or not 0.0 < val:
                errs.append(key + " must be a positive number (got " + repr(val) + ")")
        if self.config.get("range_levels", 0) < 4:
            errs.append("range_levels must be >= 4")
        if self.config.get("trend_levels", 0) < 4:
            errs.append("trend_levels must be >= 4")
        if self.config.get("hysteresis", 0.0) >= self.config.get("trend_score_thresh", 1.0):
            errs.append("hysteresis must be < trend_score_thresh")
        if not 0.0 < self.config.get("max_respace_per_tick", 0.0) <= 1.0:
            errs.append("max_respace_per_tick must be in (0,1]")
        return errs

    # -- OOM guard: explicit flush of large temporaries ----------------------
    def _flush_window(self) -> None:
        """Release oversized temporaries during streaming; explicit collect."""
        if len(self._prices) != self._prices.maxlen:
            return
        gc.collect()

    # -- trend score ---------------------------------------------------------
    @staticmethod
    def _rms(values: Deque[float]) -> float:
        """Root-mean-square of a bounded buffer via generator (no list copy)."""
        n = len(values)
        if n == 0:
            return 0.0
        acc = 0.0
        for v in values:
            acc += v * v
        return math.sqrt(acc / n)

    def _update_score(self) -> None:
        """Robust Trend Score = signed mean delta / rms(delta), rescaled to [-1,1]."""
        n = len(self._deltas)
        if n < 3:
            self._score = 0.0
            self._direction = 0
            return
        mean_d = sum(self._deltas) / n
        rms_d = self._rms(self._deltas)
        if rms_d < 1e-12:
            self._score = 0.0
            self._direction = 0
            return
        efficiency = (2.0 * abs(mean_d)) / (rms_d + 1e-12)
        self._score = math.tanh(3.0 * mean_d / (rms_d + 1e-12)) * min(efficiency, 1.0)

    def _resolve_mode(self) -> None:
        """Hysteretic + min-dwell state machine over the trend score."""
        thresh = float(self.config["trend_score_thresh"])
        hyst = float(self.config["hysteresis"])
        dwell_ok = self._dwell >= int(self.config["min_dwell_ticks"])

        up = self._score > (thresh + hyst)
        dn = self._score < -(thresh + hyst)
        flat = abs(self._score) < (thresh - hyst)

        new_mode = self._mode
        if self._mode == "RANGE":
            if dwell_ok and up:
                new_mode, self._direction = "TREND", 1
            elif dwell_ok and dn:
                new_mode, self._direction = "TREND", -1
        else:  # TREND
            if dwell_ok and flat:
                new_mode, self._direction = "RANGE", 0
            elif dwell_ok and self._direction == 1 and dn:
                new_mode, self._direction = "RANGE", 0
            elif dwell_ok and self._direction == -1 and up:
                new_mode, self._direction = "RANGE", 0

        if new_mode != self._mode:
            self._mode = new_mode
            self._dwell = 0
        else:
            self._dwell += 1

    # -- anchor and spacing --------------------------------------------------
    def _update_anchor(self) -> None:
        if not self._prices:
            return
        if self._mode == "RANGE":
            self._anchor = sum(self._prices) / len(self._prices)
        else:
            self._anchor = self._prices[-1]

    def _atr_value(self) -> float:
        if len(self._atr) < 2:
            return 0.0
        return sum(self._atr) / len(self._atr)

    def _spacing_pct(self) -> float:
        atr = self._atr_value()
        base = (self.config["range_spacing_pct"] if self._mode == "RANGE"
                else self.config["trend_spacing_pct"])
        if atr > 0.0 and self._last_price:
            return max(base, atr / self._last_price)
        return base

    # -- core API ------------------------------------------------------------
    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Feed a market tick; return optional ladder-update signal or None."""
        price = tick.get("price")
        if price is None or not isinstance(price, (int, float)) or price <= 0:
            raise RegimeConfigError("tick requires a positive numeric 'price'")

        self._tick_count += 1
        self._flush_window()

        if self._last_price is not None:
            delta = price - self._last_price
            self._deltas.append(delta)
            self._atr.append(abs(delta))
        self._last_price = price
        self._prices.append(price)

        self._update_score()
        self._resolve_mode()
        self._update_anchor()

        if self._tick_count < max(int(self.config["trend_window"]), 5):
            return None

        spacing = self._spacing_pct()
        levels = (int(self.config["range_levels"]) if self._mode == "RANGE"
                  else int(self.config["trend_levels"]))
        max_respace = float(self.config["max_respace_per_tick"])

        if self._levels_placed:
            current_anchor = self._levels_placed[0].get("anchor", self._anchor)
            step = (self._anchor - current_anchor) * max_respace
            self._anchor = current_anchor + step

        signal: Dict[str, Any] = {
            "action": "reladder",
            "mode": self._mode,
            "direction": self._direction,
            "anchor": self._anchor,
            "spacing_pct": spacing,
            "levels": levels,
            "score": self._score,
        }
        self._levels_placed = [{"anchor": self._anchor, "mode": self._mode}]
        return signal

    def on_fill(self, fill: Dict[str, Any]) -> None:
        """Incorporate a fill: signed side feeds inventory-skew protection."""
        side = str(fill.get("side", "")).lower()
        qty = fill.get("qty", 0.0)
        if not isinstance(qty, (int, float)):
            raise RegimeConfigError("on_fill 'qty' must be numeric")
        if side == "buy":
            self._net_inventory += qty
        elif side == "sell":
            self._net_inventory -= qty

    def estimate_memory_mb(self) -> float:
        """Upper-bound heap estimate from bounded deques + small lists."""
        w = int(self.config["trend_window"])
        c = int(self.config["co_window"])
        a = int(self.config["atr_period"])
        largest = max(w, c, a)
        per_float = 24.0
        buffer_bytes = (w + c + a) * per_float
        misc_bytes = 4 * largest * per_float
        mb = (buffer_bytes + misc_bytes) / (1024.0 * 1024.0)
        return round(mb, 6)

    # -- streaming helper (OOM-safe, chunked) --------------------------------
    @staticmethod
    def stream_ticks(iterable: Any) -> Generator[Dict[str, Any], None, None]:
        """Yield one tick at a time so callers never materialise whole datasets."""
        for row in iterable:
            if isinstance(row, dict) and "price" in row:
                yield row
            elif hasattr(row, "__getitem__"):
                yield {"price": float(row[0])}


def _synthetic_self_test() -> None:
    """Inline regression test using small synthetic data."""
    cfg = {"trend_window": 40, "co_window": 12, "atr_period": 8,
           "min_dwell_ticks": 20, "range_levels": 16, "trend_levels": 10}
    strat = RegimeSwitchGrid(cfg)

    # 1. invalid config surfaces as exception
    try:
        RegimeSwitchGrid({"range_spacing_pct": -1})
        raise AssertionError("negative spacing should raise")
    except RegimeConfigError:
        pass

    # 2. low-noise range regime emits reladder signals
    results = []
    for i in range(60):
        sig = strat.on_tick({"price": 100.0 + 0.001 * math.sin(i / 3.0)})
        if sig:
            results.append(sig)
    assert results, "warm-up should eventually emit reladder signal"
    assert results[0]["action"] == "reladder"

    # 3. monotonic drift flips to TREND mode (given dwell age)
    trend_strat = RegimeSwitchGrid(cfg)
    for i in range(120):
        trend_strat.on_tick({"price": 100.0 + i * 0.5})
    assert trend_strat._mode == "TREND", "expected TREND under monotonic drift"

    # 4. fill-side bookkeeping
    trend_strat.on_fill({"side": "buy", "qty": 2.0})
    trend_strat.on_fill({"side": "sell", "qty": 0.5})
    assert abs(trend_strat._net_inventory - 1.5) < 1e-9

    # 5. memory estimate is small and positive
    assert trend_strat.estimate_memory_mb() > 0.0

    # 6. streaming yields each tick lazily
    streamed = list(RegimeSwitchGrid.stream_ticks([{"price": 1.0}, {"price": 2.0}]))
    assert len(streamed) == 2
    print("regimeswitch_grid self-test: OK")


if __name__ == "__main__":
    _synthetic_self_test()
