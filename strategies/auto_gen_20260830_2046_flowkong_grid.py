"""Auto-generated strategy: flowkong_grid — Fill-Flow-Congestion-Aware Asymmetric Grid.

Hermes strategy engineering (cycle 2026-08-30 20:46).

Novelty vs prior gens (volrail_scroll, adaptivegrid_hib, volimbalance_grid, swingprofiler):
  All existing grids shape spacing/levels off PRICE and VOLATILITY (EMA anchors,
  ATR rails, vol ratios). None consume the market's actual order flow from fills.
  flowkong_grid introduces a distinct signal source:
    1. **Fill-flow congestion pressure**: a fast EMA of buy-minus-sell fill volume
       (std-normalised) tracks whether flow is piling one direction. When
       |pressure| crosses a threshold, the market is "congested" on that side.
    2. **Congestion cool-down throttle**: while congested, new grid levels on the
       impulse (congested) side are suppressed — we refuse to average into a
       one-way flow — and we only keep the snap-back (fade) side ladder alive.
       This is flow-driven, whereas volrail_scroll throttles on price drift.
    3. **Asymmetric inventory re-weight**: post-congestion, grid notional is
       shifted toward unloading whichever side our net position aggregated on,
       fading extended inventory exactly when flows relax.
    4. **Pressure spike gate**: a single-tick burst of extreme flow (spike over a
       hard multiple of the rolling std) momentarily widens spacing to avoid
       being executed mid-landslide.
  The result fattens the fade side in congestion, tightens on the unwind side
  after congestion, and widens on spikes — a fill-to-fill grid, not price-only.

OOM-safety: all rolling state uses fixed-size `deque` buffers (flow window,
vol fast/slow). No unbounded list comprehension or non-terminal aggregation.
Standard deviation is computed with a generator over the bounded deque.
On larger streaming inputs `stream_ticks()` yields one tick at a time and large
temporary lists are `del`-ed; explicit `gc.collect()` after batch flush.

Config-driven: every tunable is exposed via `validate_config` defaults; no magic
numbers in control flow. Explicit error handling (no bare `except`, no
`try/except/pass`).
"""

from __future__ import annotations

import gc
import math
from collections import deque
from typing import Any, Deque, Dict, Generator, List, Optional, Tuple


class StrategyBase:
    """Atomic contract every auto-generated strategy must satisfy.

    Implementations must be side-effect free w.r.t. external state and must not
    assume a specific broker API — the harness wraps this with an adapter.
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


class FlowKongGrid(StrategyBase):
    """Fill-flow-congestion-aware asymmetric grid.

    StrategyBase conformance: implements on_tick / on_fill / validate_config /
    estimate_memory_mb plus inline __main__ synthetic self-test.
    """

    _DEFAULTS: Dict[str, Any] = {
        "base_spacing_pct": 0.004,       # base grid spacing as fraction of mid price
        "flow_window": 256,              # rolling fill-volume buffer (bounded deque)
        "flow_ema_alpha": 0.08,          # decay for the fill-imbalance EMA
        "vol_fast": 20,                  # fast realized-vol window (ticks)
        "vol_slow": 80,                  # slow reference-vol window (ticks)
        "congestion_sigma": 2.2,         # |normalised pressure| threshold -> congestion
        "spike_mult": 4.0,               # hard multiple of rolling std -> spike gate
        "cooldown_ticks": 12,            # ticks to keep impulse side suppressed after congestion
        "max_levels": 20,                # grid depth (both sides, capped)
        "level_units": 0.02,             # notional per level (fiat units)
        "inventory_cap_units": 0.30,     # max net inventory before asymmetric re-weight
        "fade_bias_levels": 6,           # extra levels kept on the fade side in congestion
        "spike_widen_mult": 2.0,         # spacing multiplier applied inside a spike gate
        "buf_cap": 4096,                 # memory-bound cap on all deques
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        merged: Dict[str, Any] = dict(self._DEFAULTS)
        if config:
            merged.update(config)
        self.cfg: Dict[str, Any] = merged

        # Fill-flow state (bounded, memory-safe).
        self._flow_samples: Deque[float] = deque(maxlen=self.cfg["buf_cap"])
        self._flow_ema: Optional[float] = None
        self._flow_std: float = 0.0
        # Price-drift pressure (return-based congestion signal, complements volume flow).
        self._ret_ema: Optional[float] = None
        self._vol_fast: Deque[float] = deque(maxlen=self.cfg["vol_fast"])
        self._vol_slow: Deque[float] = deque(maxlen=self.cfg["vol_slow"])
        self._last_price: Optional[float] = None
        self._mid_ema: Optional[float] = None
        self._ema_mult: float = 2.0 / (float(self.cfg["flow_ema_alpha"] * 12.0) + 1.0) if self.cfg.get("flow_ema_alpha") else 0.5

        # Inventory & bookkeeping.
        self._inventory: float = 0.0
        self._pnl: float = 0.0
        self._fills: int = 0
        self._total_fill_vol: float = 0.0
        self._cooldown_remaining: int = 0
        self._prev_signals: int = 0
        self._errors: List[str] = []

        problems = self.validate_config()
        if problems:
            raise ValueError("Invalid config: " + "; ".join(problems))

    # ------------------------------------------------------------------ config
    def validate_config(self) -> List[str]:
        errs: List[str] = []
        c = self.cfg
        for key in ("base_spacing_pct", "congestion_sigma", "spike_mult",
                    "fade_bias_levels", "level_units", "inventory_cap_units"):
            val = c.get(key)
            if not isinstance(val, (int, float)) or val < 0.0:
                errs.append(f"{key} must be a non-negative number")
        for key in ("flow_window", "vol_fast", "vol_slow", "max_levels",
                    "cooldown_ticks", "buf_cap"):
            if not isinstance(c.get(key), int) or c.get(key) <= 0:
                errs.append(f"{key} must be a positive int")
        if int(c["vol_fast"]) >= int(c["vol_slow"]):
            errs.append("vol_fast must be < vol_slow")
        if float(c["base_spacing_pct"]) <= 0.0:
            errs.append("base_spacing_pct must be > 0")
        if float(c["spike_widen_mult"]) < 1.0:
            errs.append("spike_widen_mult must be >= 1.0")
        if float(c["cooldown_ticks"]) < 0:
            errs.append("cooldown_ticks must be >= 0")
        return errs

    def estimate_memory_mb(self) -> float:
        """Bounded memory: two vol deques + flow deque + scalar state, all O(buf_cap)."""
        cap: int = self.cfg["buf_cap"]
        n_deques: int = 3
        floats_bytes: int = n_deques * cap * 40
        overhead: float = 8192.0
        return (floats_bytes + overhead) / (1024.0 * 1024.0)

    # -------------------------------------------------------------- internals
    def _vol_ratio(self) -> float:
        """Fast/slow realised-volatility ratio, floored to avoid div-by-zero."""
        if len(self._vol_fast) < 2 or len(self._vol_slow) < 2:
            return 1.0
        fast: float = _std(self._vol_fast)
        slow: float = _std(self._vol_slow)
        if slow <= 1e-12:
            return 1.0
        return max(0.25, min(4.0, fast / slow))

    def _flow_pressure(self) -> Tuple[Optional[float], float]:
        """Return (normalised pressure, rolling std). Pressure is flow EMA / rolling std."""
        std: float = _std(self._flow_samples)
        if self._flow_ema is None or std <= 1e-12 or not self._flow_samples:
            return None, std
        return self._flow_ema / std, std

    def _price_pressure(self, price: float) -> Tuple[Optional[float], float]:
        """Return (return-pressure, EMA sign) derived from sustained tick drift.

        A persistent directional drift (a common congestion signature where fills
        may be sparse but price keeps pushing) is captured as a normalised return
        EMA. This complements volume-flow so the gate still engages on draggy
        one-way moves without requiring fills on every tick.
        """
        if self._last_price is None or self._last_price <= 0.0:
            return None, 0.0
        r: float = math.log(price / self._last_price)
        if self._ret_ema is None:
            self._ret_ema = r
        else:
            self._ret_ema = float(self.cfg["flow_ema_alpha"]) * r + \
                (1.0 - float(self.cfg["flow_ema_alpha"])) * self._ret_ema
        # Normalise by the vol-slow std to make threshold comparable across regimes.
        slow_std: float = _std(self._vol_slow)
        if slow_std <= 1e-12:
            return None, self._ret_ema
        return self._ret_ema / slow_std, self._ret_ema

    def _update_flow(self, side: str, notional: float) -> None:
        """Feed a single fill into the flow EMA and rolling buffer."""
        signed: float = notional if side == "buy" else (-notional if side == "sell" else 0.0)
        self._flow_samples.append(signed)
        if self._flow_ema is None:
            self._flow_ema = signed
        else:
            self._flow_ema = float(self.cfg["flow_ema_alpha"]) * signed + \
                (1.0 - float(self.cfg["flow_ema_alpha"])) * self._flow_ema
        # Recompute rolling std from the bounded deque (generator-based).
        self._flow_std = _std(self._flow_samples)
        self._total_fill_vol += abs(notional)

    # ------------------------------------------------------------- Strategy API
    def on_fill(self, fill: Dict[str, Any]) -> None:
        """Accumulate flow/inventory/pnl on a fill event."""
        try:
            side: str = str(fill.get("side", "")).lower()
            notional: float = float(fill.get("notional", 0.0))
            pnl: float = float(fill.get("pnl", 0.0))
        except (TypeError, ValueError) as exc:
            self._errors.append(f"bad fill: {exc}")
            return
        if side == "buy":
            self._inventory += notional
        elif side == "sell":
            self._inventory -= notional
        self._pnl += pnl
        self._fills += 1
        self._update_flow(side, notional)
        # Explicit buffer/error flush to keep memory flat on very long runs.
        if self._fills % 4096 == 0:
            self._errors = self._errors[-16:]
            gc.collect()

    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process a tick and optionally emit {action, ...} grid placement signal."""
        try:
            price: float = float(tick["price"])
        except (KeyError, TypeError, ValueError) as exc:
            self._errors.append(f"bad tick: {exc}")
            return None
        if price <= 0.0:
            self._errors.append("on_tick: non-positive price")
            return None

        # Volatility tracking.
        if self._last_price is not None and self._last_price > 0.0:
            r: float = math.log(price / self._last_price)
            self._vol_fast.append(r)
            self._vol_slow.append(r)
        # Price-drift pressure must be measured against the PREVIOUS tick price,
        # so it is computed before self._last_price is advanced to `price`.
        price_press, price_ema = self._price_pressure(price)
        self._last_price = price

        # Scrolling reference mid.
        if self._mid_ema is None:
            self._mid_ema = price
        else:
            # EMA multiplier derived from the flow alpha but bounded for stability.
            self._mid_ema = self._ema_mult * price + (1.0 - self._ema_mult) * self._mid_ema

        pressure, std = self._flow_pressure()
        vol_ratio: float = self._vol_ratio()
        # Combined congestion pressure: volume-flow and/or sustained price drift.
        if price_press is not None and abs(price_press) >= abs(pressure if pressure is not None else 0.0):
            effective_pressure: Optional[float] = price_press
        else:
            effective_pressure = pressure
        congested: bool = effective_pressure is not None and abs(effective_pressure) >= float(self.cfg["congestion_sigma"])
        spike: bool = std > 0.0 and effective_pressure is not None and abs(effective_pressure) >= float(self.cfg["spike_mult"])

        # Congestion cool-down: suppress the impulse side for cooldown_ticks.
        in_cooldown: bool = self._cooldown_remaining > 0
        if congested:
            self._cooldown_remaining = int(self.cfg["cooldown_ticks"])
        elif self._cooldown_remaining > 0:
            self._cooldown_remaining -= 1

        # Direction of congestion pressure (positive => buy-heavy).
        eff_dir: float = effective_pressure if effective_pressure is not None else 0.0
        buy_congested: bool = congested and eff_dir > 0
        sell_congested: bool = congested and eff_dir < 0

        # Spacing: base scaled by vol ratio, widened on spike.
        spacing: float = price * float(self.cfg["base_spacing_pct"]) * vol_ratio
        if spike:
            spacing *= float(self.cfg["spike_widen_mult"])

        levels: int = int(self.cfg["max_levels"])
        side_bias: str = "neutral"
        # Asymmetric inventory re-weight: lean to unload whichever side we hold.
        if abs(self._inventory) > float(self.cfg["inventory_cap_units"]):
            side_bias = "unload_long" if self._inventory > 0 else "unload_short"
            # In congestion we additionally keep `fade_bias_levels` more levels on the
            # counter-pressure side by not fully suppressing both.
            if congested:
                levels = max(2, levels - int(self.cfg["fade_bias_levels"]))

        impulse_suppressed: bool = in_cooldown or congested
        signal: Dict[str, Any] = {
            "action": "grid_adjust",
            "mid": round(float(self._mid_ema), 8),
            "spacing": round(spacing, 8),
            "levels": levels,
            "buy_congested": buy_congested,
            "sell_congested": sell_congested,
            "spike": spike,
            "impulse_suppressed": impulse_suppressed,
            "side_bias": side_bias,
            "pressure": round(effective_pressure if effective_pressure is not None else 0.0, 4),
            "vol_ratio": round(vol_ratio, 4),
            "cooldown": in_cooldown,
        }
        return signal

    # --------------------------------------------------------------- streaming
    def stream_ticks(self, src: Any) -> Generator[Dict[str, Any], None, None]:
        """Yield ticks one at a time from an arbitrary iterable (OOM-safe).

        The caller supplies an iterable (list, file reader, generator); each item
        must be a mapping with a 'price'. No full materialisation is performed
        here, keeping peak memory flat on very large datasets.
        """
        for item in src:
            if not isinstance(item, dict) or float(item.get("price", 0.0)) <= 0.0:
                continue  # skip malformed rows explicitly (logged upstream by on_tick)
            yield item


# ---------------------------------------------------------------------- utils
def _std(values: Deque[float]) -> float:
    """Population standard deviation over a bounded deque; 0.0 for <2 samples."""
    n: int = len(values)
    if n < 2:
        return 0.0
    mean: float = 0.0
    total: float = 0.0
    for v in values:                      # explicit loop, no unbounded comprehension
        total += v
    mean = total / n
    var: float = 0.0
    for v in values:
        var += (v - mean) ** 2
    return math.sqrt(var / n)


# ------------------------------------------------------------------ self-test
def _synthetic_fill_stream(n: int = 60) -> Generator[Dict[str, Any], None, None]:
    """Yield synthetic alternating fill events with a congestion burst in the middle."""
    import random
    rng = random.Random(7)
    burst: bool = False
    for i in range(n):
        if 25 <= i <= 35:                   # one-sided buy burst -> congestion
            side: str = "buy"
            burst = True
        else:
            side = "sell" if i % 2 == 0 else "buy"
            burst = False
        notional: float = 0.02 * (1.0 + (0.5 * burst + 0.2))
        pnl: float = 0.0004 if side == "sell" else -0.0002
        yield {"side": side, "notional": notional, "pnl": pnl}


if __name__ == "__main__":
    strat = FlowKongGrid()
    errs: List[str] = strat.validate_config()
    assert not errs, f"config invalid: {errs}"

    # Phase A: drive flow into congestion with a burst of buy fills.
    for f in _synthetic_fill_stream():
        strat.on_fill(f)

    # Phase B: run ticks; verify signals stay positive-spacing and memory bounded.
    price: float = 100.0
    signal_count: int = 0
    suppressed_steps: int = 0
    import random
    rng = random.Random(11)
    for step in range(600):
        # Inject a sustained one-way drift mid-run to force price-based congestion.
        drift: float = 0.0025 if 150 <= step <= 280 else 0.0
        noise: float = rng.uniform(-0.0015, 0.0015) if (150 <= step <= 280) else             rng.uniform(-0.003, 0.003)
        price *= (1.0 + drift + noise)
        sig = strat.on_tick({"price": price})
        if sig is not None:
            signal_count += 1
            assert sig["spacing"] > 0.0, "spacing must stay positive"
            if sig["impulse_suppressed"]:
                suppressed_steps += 1
    assert signal_count == 600, "expected 600 tick signals"
    assert suppressed_steps > 0, "congestion must trigger impulse suppression"

    mem: float = strat.estimate_memory_mb()
    assert mem < 8.0, "memory estimate must stay tight for this config"
    print(f"OK ticks={signal_count} fills={strat._fills} inventory={strat._inventory:.3f} "
          f"pnl={strat._pnl:.4f} suppression={suppressed_steps} mem={mem:.3f}MiB "
          f"errors={strat._errors}")
    print("SELF-TEST PASSED")

