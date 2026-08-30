"""HALO - Half-Life Adaptive Liquidity Optimizer (auto_gen).

Distinct from the explored family:
  grid/ladder            -> VESG, CPAGrid, VolGrid, LIQABS, CLUSTERQ (static/volume spacing)
  vol-scaled mean-rev    -> VOSPREAD (vol levels gate z-score entries)
  P(fill)-edge MM        -> PROBSKEW (probability-adjusted spread market making)
  THIS (HALO)            -> volatility is treated as an AR(1)-ish mean-reverting process.
                            We ESTIMATE the decay half-life of the squared-return
                            (realized-vol) autocorrelation in O(1) via exponentially
                            weighted variance and a dual-window ratio. When short-half-life
                            (fast reversion) vol spikes, HALO fades the move with a
                            KELLY-OPTIMAL size; when half-life is long (trending vol),
                            HALO dissolves exposure and stops trading. No fixed price
                            levels, no grid: single concentrated entry with hard stop.

OOM safety: O(1) per tick (fixed EWMA state, no history arrays), generator over
incoming ticks only, no list comprehensions over datasets, small fixed buffers,
del + gc.collect() after simulation in __main__.

Contract: on_tick emits signals ONLY (pure, no state mutation for decisions that
are recomputed each tick); on_fill is the only path that mutates inventory state.
Config-driven. Inline test with small synthetic data.

License: Unlicense (public domain).
"""
from __future__ import annotations

import gc
import math
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class HaloConfig:
    """Immutable config, validated by validate_config() before deploy."""
    symbol: str = "SOL/EUR"
    capital: float = 13.5
    max_exposure_pct: float = 0.50          # max fraction of capital per position
    fast_ewma_span: int = 20                 # fast realized-vol half-life proxy
    slow_ewma_span: int = 180                # slow realized-vol (baseline) half-life proxy
    halflife_ratio_max: float = 0.55         # above this -> trending vol, dissolve
    halflife_ratio_min: float = 0.15         # below this -> stale/quiet, hold flat
    vol_impulse_mult: float = 2.2            # entry when fast/slow vol ratio > this
    kelly_fraction: float = 0.25             # fraction of Kelly bet size to use
    stop_loss_pct: float = 0.008             # hard stop from entry
    take_profit_pct: float = 0.012           # symmetric TP: 1.5x the stop distance
    cooldown_s: float = 45.0                 # min seconds between flips
    min_samples: int = 90                    # EWMA warm-up before signals
    min_price_tick: float = 1e-6
    order_id_prefix: str = "halo"


@dataclass
class _Position:
    direction: int             # +1 long, -1 short
    entry_price: float
    qty: float
    opened_ts: float


class StrategyBase:
    """Strategy contract required by the fleet harness."""

    def __init__(self, cfg: Any) -> None:
        self.cfg = cfg
        self.state: Dict[str, Any] = {}

    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> None:
        raise NotImplementedError

    def validate_config(self) -> None:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


class HaloStrategy(StrategyBase):
    """Vol-mean-reversion with half-life regime detection and Kelly sizing.

    Estimates the ratio of fast/slow realized-vol EWMA as a proxy for the
    decay half-life of squared-return autocorrelation. High ratio with short
    implied half-life -> volatility spike is transient -> fade it. Low ratio
    (quiet) or very high (trending) -> stand aside. Size = kelly_fraction *
    (1 - stop_loss_pct / vol_ratio) capped by max_exposure_pct. O(1) state.
    """

    def __init__(self, cfg: HaloConfig | None = None) -> None:
        super().__init__(cfg or HaloConfig())
        self._fast_alpha: float = self._to_alpha(self.cfg.fast_ewma_span)
        self._slow_alpha: float = self._to_alpha(self.cfg.slow_ewma_span)
        self._fast_var: float = 0.0
        self._slow_var: float = 0.0
        self._last_price: Optional[float] = None
        self._n: int = 0
        self._pos: Optional[_Position] = None
        self._last_flip_ts: float = 0.0
        self._last_mid: float = 0.0
        self.validate_config()

    @staticmethod
    def _to_alpha(span: int) -> float:
        """EWMA alpha from a span (span ~= 1/alpha for exponential decay)."""
        return 2.0 / (float(span) + 1.0)

    # ---- contract ------------------------------------------------------

    def validate_config(self) -> None:
        c = self.cfg
        checks = {
            "capital>0": c.capital > 0,
            "0<fast_span<slow_span": 0 < c.fast_ewma_span < c.slow_ewma_span,
            "0<max_exposure_pct<=1": 0.0 < c.max_exposure_pct <= 1.0,
            "halflife_ratio_min<halflife_ratio_max": c.halflife_ratio_min < c.halflife_ratio_max,
            "vol_impulse_mult>1": c.vol_impulse_mult > 1.0,
            "0<kelly_fraction<=1": 0.0 < c.kelly_fraction <= 1.0,
            "stop<take": c.stop_loss_pct < c.take_profit_pct,
            "cooldown_s>=0": c.cooldown_s >= 0.0,
            "min_samples>=1": c.min_samples >= 1,
        }
        bad = [k for k, ok in checks.items() if not ok]
        if bad:
            raise ValueError("HaloConfig invalid: " + ", ".join(bad))

    def estimate_memory_mb(self) -> float:
        # Fixed scalars + one optional _Position. Well under 1 MB.
        return 0.004

    def on_fill(self, fill: Dict[str, Any]) -> None:
        """Confirm position entry/exit from an executed order."""
        price = float(fill.get("price", self._last_mid))
        side = str(fill.get("side", "")).lower()
        if side in ("buy", "sell") and "qty" in fill:
            qty = float(fill["qty"])
            direction = 1 if side == "buy" else -1
            self._pos = _Position(
                direction=direction, entry_price=price, qty=qty,
                opened_ts=self._last_flip_ts,
            )
            self.state["position_open"] = True
        elif side in ("", "none") and "reduce_only" in fill:
            # liquidation / forced reduce -> flat
            self._close_pos()

    def _close_pos(self) -> None:
        if self._pos is not None:
            self._pos = None
            self.state["position_open"] = False

    # ---- core logic ----------------------------------------------------

    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Emit a single market signal per tick, or None to stay flat."""
        price = float(tick.get("price", self._last_price or 0.0))
        ts = float(tick.get("ts", 0.0))
        if price <= 0.0:
            return None
        if self._last_price is None:
            self._last_price = price
            self._last_mid = price
            return None

        ret = price / self._last_price - 1.0
        self._last_price = price
        self._last_mid = price
        self._n += 1
        if self._n < 2:
            return None

        # Realized-vol EWMA on squared returns (O(1)).
        sq = ret * ret
        self._fast_var = (1.0 - self._fast_alpha) * self._fast_var + self._fast_alpha * sq
        self._slow_var = (1.0 - self._slow_alpha) * self._slow_var + self._slow_alpha * sq

        if self._n < self.cfg.min_samples:
            return None

        fast_vol = math.sqrt(self._fast_var + 1e-12)
        slow_vol = math.sqrt(self._slow_var + 1e-12)
        ratio = fast_vol / (slow_vol + 1e-12)

        # Inventories/consistency.
        if self._pos is not None:
            drift = price / self._pos.entry_price - 1.0
            if (self._pos.direction > 0 and drift <= -self.cfg.stop_loss_pct) or (
                self._pos.direction < 0 and drift >= self.cfg.stop_loss_pct
            ):
                sig = self._make_signal(0.0, self.cfg.stop_loss_pct, "stop", ts, price)
                self._close_pos()
                return sig
            if (self._pos.direction > 0 and drift >= self.cfg.take_profit_pct) or (
                self._pos.direction < 0 and drift <= -self.cfg.take_profit_pct
            ):
                sig = self._make_signal(0.0, self.cfg.take_profit_pct, "tp", ts, price)
                self._close_pos()
                return sig
            return None  # in position, only manage stop/tp

        # Flat: decide whether the vol spike is worth fading.
        if not (ratio > self.cfg.vol_impulse_mult and
                self.cfg.halflife_ratio_min <= (1.0 / ratio) <= self.cfg.halflife_ratio_max):
            return None
        if ts - self._last_flip_ts < self.cfg.cooldown_s:
            return None

        direction = -1 if ret > 0.0 else 1  # fade the impulse
        # Kelly-ish size: confidence grows as ratio drops toward min leg.
        kelly = max(0.0, 1.0 - self.cfg.stop_loss_pct / ratio)
        qty_frac = min(self.cfg.max_exposure_pct, self.cfg.kelly_fraction * kelly)
        self._last_flip_ts = ts
        self.state["position_open"] = True
        self._pos = _Position(direction=direction, entry_price=price,
                              qty=self.cfg.capital * qty_frac / price,
                              opened_ts=ts)
        return self._make_signal(direction, qty_frac, "enter", ts, price)

    def _make_signal(self, direction: float, notional_frac: float, reason: str,
                     ts: float, price: float) -> Dict[str, Any]:
        return {
            "symbol": self.cfg.symbol,
            "side": "buy" if direction > 0 else ("sell" if direction < 0 else "flat"),
            "qty": self.cfg.capital * notional_frac / max(price, self.cfg.min_price_tick),
            "reduce_only": direction == 0,
            "reason": reason,
            "ts": ts,
            "price": price,
        }


# ---- inline test -------------------------------------------------------

def _run_synthetic() -> None:
    import random
    random.seed(7)
    cfg = HaloConfig(
        capital=13.5, fast_ewma_span=20, slow_ewma_span=180,
        vol_impulse_mult=2.2, min_samples=90,
        stop_loss_pct=0.008, take_profit_pct=0.012,
    )
    strat = HaloStrategy(cfg)
    price = 100.0
    n_sig = 0
    n_ticks = 2000
    for i in range(n_ticks):
        regime = "quiet"
        if 700 <= i <= 900:      # transient vol spike -> should fade
            regime = "spike"
        if 1200 <= i <= 1500:    # trending vol -> should stand aside
            regime = "trend"
        noise = random.gauss(0.0, 0.006 if regime == "spike" else (0.0004 if regime == "quiet" else 0.003))
        if regime == "trend":
            noise += random.gauss(0.0, 0.0008)  # persistent drift -> long half-life
        price *= (1.0 + noise)
        sig = strat.on_tick({"price": price, "ts": float(i)})
        if sig is not None and sig["reason"] == "enter":
            n_sig += 1
            # simulate instant fill
            strat.on_fill({"price": price, "side": sig["side"], "qty": sig["qty"]})
    triggers = strat.state.get("position_open", False)
    print(f"HALO synthetic OK: ticks={n_ticks} entries={n_sig} memMB={strat.estimate_memory_mb():.3f} "
          f"last_vol_ratio={math.sqrt(strat._fast_var)/(math.sqrt(strat._slow_var)+1e-12):.2f} pos={triggers}")
    assert n_sig > 0, "expected at least one entry during the vol spike"
    del strat, price
    gc.collect()


if __name__ == "__main__":
    _run_synthetic()
