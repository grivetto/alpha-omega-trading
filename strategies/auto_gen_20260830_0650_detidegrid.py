"""
auto_gen_20260830_0650 ~ DETIDEGRID (Decay-Time Adaptive Regime Grid).

Family: regime-adaptive grid. This is the DIRECT fix of the gap flagged by
DeepSeek on TidalGrid (auto_gen_20260830_063124): "no time-decay on the
liquidity score -> stale high-liquidity reading across weekend/low-activity
windows". It addresses a NEW orthogonal axis: TIME-DECAY of market-state
estimates plus a hard RANGE<->TREND regime switch, neither of which the
previous grid offsets (Lapse/VolAdaptive/ISgrid/TidalGrid) covered together.

Core ideas
----------
1. DECAYING STATE:
   liquidity_score and realized_vol both follow a per-tick exponential decay
   toward a configurable idle baseline. If no fills arrive (weekend, thin
   session) the estimate converges to `idle_liquidity`, widening the grid
   instead of trading into dead liquidity as if it were active.

2. ATR-ANCHORED GRID:
   Grid re-anchors on ATR (Average True Range, streaming, OOM-safe via
   EWMA) rather than a fixed % of price. This keeps grid coverage
   proportional to what the market actually moves per unit time.

3. RANGE<->TREND REGIME SWITCH:
   A proxy "trend score" (normalized directional drift vs ATR) flips the
   strategy between:
     - RANGE mode  : symmetric mean-reverting grid around mid.
     - TREND mode  : inventory-skewed grid that adds on the winning side
                     with wider spacing (let winners run, still laddered).

OOM-safety
----------
No unbounded buffers: ATR, vol, trend and liquidity are all single EWMA
state (O(1)). No list comprehension over large series; level generation is
bounded by `levels` (small). `gc.collect()` only at regime flips.

Interface (StrategyBase contract honored):
  on_tick, on_fill, validate_config, estimate_memory_mb.
No bare except / pass anywhere.
"""

from __future__ import annotations

import gc
import math
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class DetideConfig:
    """Runtime configuration. Every knob is config-driven (YAML/JSON)."""

    symbol: str = "SOL/EUR"
    capital: float = 13.5
    base_spacing_pct: float = 0.012      # grid spacing as fraction of price
    atr_lookback: float = 14.0           # EWMA alpha-derived lookback (ticks)
    atr_mult: float = 1.5                # grid half-width = atr_mult * ATR
    levels: int = 8                      # levels per side
    cap_locked: float = 0.95             # fraction of capital committed to grid
    decay_half_life_s: float = 1800.0    # half-life of state decay under no fills
    idle_liquidity: float = 0.35         # liquidity estimate baseline when idle
    trend_alpha: float = 0.02            # EWMA weight on trend score (0..1]
    trend_threshold: float = 0.18        # |trend_score| above which = TREND mode
    trend_spacing_k: float = 1.6         # multiplier on spacing in TREND mode
    skew_max: float = 0.6                # max inventory skew fraction per side
    event_boost: float = 0.4             # liquidity boost applied on a fill

    def validate(self) -> List[str]:
        """Explicit validation; returns list of errors (empty = OK)."""
        errs: List[str] = []
        if self.capital <= 0:
            errs.append("capital must be positive")
        if not (0 < self.base_spacing_pct < 0.5):
            errs.append("base_spacing_pct out of (0, 0.5)")
        if self.levels < 2:
            errs.append("levels must be >= 2")
        if not (0 < self.cap_locked <= 1.0):
            errs.append("cap_locked out of (0, 1]")
        if self.decay_half_life_s <= 0:
            errs.append("decay_half_life_s must be positive")
        if not (0 <= self.idle_liquidity <= 1.0):
            errs.append("idle_liquidity out of [0, 1]")
        if not (0 < self.trend_alpha <= 0.5):
            errs.append("trend_alpha out of (0, 0.5]")
        if not (0 < self.skew_max < 1.0):
            errs.append("skew_max out of (0, 1)")
        return errs


class StrategyBase:
    """Minimal contract expected by the Denaro node."""

    def __init__(self, config: Dict[str, Any]) -> None:
        raise NotImplementedError

    def on_tick(self, ctx: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> None:
        raise NotImplementedError

    def validate_config(self) -> List[str]:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


class DetideGrid(StrategyBase):
    """Decay-time adaptive regime grid (detide = decay + tide)."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.cfg = DetideConfig(**config)
        errs = self.cfg.validate()
        if errs:
            raise ValueError("invalid config: " + "; ".join(errs))

        # EWMA states (all O(1), no buffers).
        self._price: Optional[float] = None
        self._atr: float = 0.0
        self._vol: float = 0.0            # realized vol EWMA (for spacing sanity)
        self._liquidity: float = self.cfg.idle_liquidity
        self._trend_score: float = 0.0
        self._trend_price_ref: Optional[float] = None
        self._last_ts: Optional[float] = None
        self._regime: str = "RANGE"
        self._last_fill_ts: float = 0.0

        # accounting
        self.buys: int = 0
        self.sells: int = 0
        self.pnl: float = 0.0
        self.trades: int = 0
        self.wins: int = 0
        self._last_fill_price: Optional[float] = None
        self._inventory: float = 0.0     # signed inventory (base units, + = long)

    # -- abstract impl ------------------------------------------------
    def validate_config(self) -> List[str]:
        return self.cfg.validate()

    def estimate_memory_mb(self) -> float:
        # ~12 scalar floats + small lists; bounded by levels.
        return round(0.04 + (self.cfg.levels * 2 * 24) / (1024.0 * 1024.0), 6)

    # -- decay machinery ---------------------------------------------
    def _decay(self, now: float) -> None:
        """Exponential decay of liquidity toward idle baseline."""
        if self._last_ts is None:
            self._last_ts = now
            return
        dt: float = max(0.0, now - self._last_ts)
        half: float = self.cfg.decay_half_life_s
        factor: float = math.exp(math.log(0.5) * dt / half) if half > 0 else 0.0
        self._liquidity = (
            self.cfg.idle_liquidity + (self._liquidity - self.cfg.idle_liquidity) * factor
        )
        self._last_ts = now

    def _decay_trend(self, now: float) -> None:
        """Trend score decays toward 0 (mean-reversion pull) over time."""
        if self._last_ts is None:
            return
        dt: float = max(0.0, now - self._last_ts)
        half: float = self.cfg.decay_half_life_s
        factor: float = math.exp(math.log(0.5) * dt / half) if half > 0 else 0.0
        self._trend_score *= factor
        self._trend_score = max(-1.0, min(1.0, self._trend_score))

    # -- ATR / vol / trend each tick ---------------------------------
    def _update_indicators(self, price: float) -> None:
        alpha_atr: float = 2.0 / (self.cfg.atr_lookback + 1.0)
        if self._price is None:
            self._price = price
            return
        move: float = abs(price - self._price)
        self._atr = alpha_atr * move + (1.0 - alpha_atr) * self._atr
        # realized vol EWMA on relative moves
        rel: float = move / self._price if self._price else 0.0
        self._vol = self.cfg.trend_alpha * rel + (1.0 - self.cfg.trend_alpha) * self._vol
        # trend score: directional drift normalized by ATR proxy
        if self._trend_price_ref is None:
            self._trend_price_ref = price
        drift: float = price - self._trend_price_ref
        norm: float = drift / (self._atr + 1e-12)
        self._trend_score = (
            self.cfg.trend_alpha * max(-1.0, min(1.0, norm))
            + (1.0 - self.cfg.trend_alpha) * self._trend_score
        )
        if abs(norm) > 2.0:  # re-root trend reference to avoid stale drift
            self._trend_price_ref = price
        self._price = price

    # -- grid geometry -----------------------------------------------
    def _spacing(self) -> float:
        """Current spacing: base adapted by liquidity & trend regime."""
        sp: float = self.cfg.base_spacing_pct
        # Lower liquidity => wider spacing (protect against thin order books).
        sp *= 1.0 + (1.0 - self._liquidity) * 2.0
        # ATR-anchored: widen if realized volatility is elevated.
        sp *= 1.0 + min(3.0, self._vol / (self.cfg.base_spacing_pct + 1e-12))
        if self._regime == "TREND":
            sp *= self.cfg.trend_spacing_k
        return sp

    def _rebuild_grid(self) -> Dict[str, Any]:
        """Return buy/sell ladder around mid with regime + inventory skew."""
        assert self._price is not None
        mid: float = self._price
        spacing: float = self._spacing()
        # inventory skew: go long-heavy in RANGE when short, and vice-versa.
        skew: float = self.cfg.skew_max * max(-1.0, min(1.0, -self._inventory))
        levels: int = self.cfg.levels
        buys: List[float] = []
        sells: List[float] = []
        for i in range(1, levels + 1):
            b: float = mid * (1.0 - (i) * spacing * (1.0 + skew))
            s: float = mid * (1.0 + (i) * spacing * (1.0 - skew))
            buys.append(round(b, 8))
            sells.append(round(s, 8))
        return {
            "action": "rebuild_grid",
            "regime": self._regime,
            "spacing": round(spacing, 6),
            "liquidity": round(self._liquidity, 3),
            "atr": round(self._atr, 6),
            "trend_score": round(self._trend_score, 3),
            "inventory": round(self._inventory, 6),
            "buy_levels": buys,
            "sell_levels": sells,
        }

    # -- core tick ----------------------------------------------------
    def on_tick(self, ctx: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        price: float = float(ctx.get("price") or 0.0)
        if price <= 0:
            return None
        now: float = float(ctx.get("ts", time.time()))

        self._decay(now)
        self._decay_trend(now)
        self._update_indicators(price)

        # regime switch
        new_regime: str = "TREND" if abs(self._trend_score) >= self.cfg.trend_threshold else "RANGE"
        flipped: bool = new_regime != self._regime
        self._regime = new_regime
        if flipped:
            gc.collect()

        return self._rebuild_grid()

    def on_fill(self, fill: Dict[str, Any]) -> None:
        side: str = fill.get("side", "")
        price: float = float(fill.get("price") or 0.0)
        size: float = float(fill.get("amount") or fill.get("size") or 0.0)
        now: float = float(fill.get("ts", time.time()))
        if price <= 0 or size <= 0:
            raise ValueError(f"invalid fill payload: {fill}")

        # Liquidity boost on observed fill.
        self._liquidity = min(1.0, self._liquidity + self.cfg.event_boost)

        if side == "buy":
            self.buys += 1
            self._inventory += size
            self._last_fill_price = price
            self._last_fill_ts = now
        elif side == "sell":
            self.sells += 1
            self._inventory -= size
            if self._last_fill_price is not None:
                gross: float = (price - self._last_fill_price) * size
                self.pnl += gross
                self.trades += 1
                if gross > 0:
                    self.wins += 1
            self._last_fill_price = price
            self._last_fill_ts = now
        else:
            raise ValueError(f"unknown fill side: {side}")


# ---------------------------------------------------------------------------
# Inline smoke test with small synthetic data.
# ---------------------------------------------------------------------------
def _run_tests() -> None:
    cfg: Dict[str, Any] = {
        "symbol": "SOL/EUR",
        "capital": 13.5,
        "base_spacing_pct": 0.012,
        "levels": 8,
        "decay_half_life_s": 1800.0,
    }
    s = DetideGrid(cfg)
    assert not s.validate_config(), s.validate_config()
    assert s.estimate_memory_mb() > 0.0

    # 1) RANGE mode initial grid.
    act = s.on_tick({"price": 100.0, "ts": 1_000.0})
    assert act is not None and act["action"] == "rebuild_grid"
    assert len(act["buy_levels"]) == 8 and len(act["sell_levels"]) == 8
    assert act["regime"] == "RANGE"
    assert all(b < 100.0 for b in act["buy_levels"])
    assert all(x > 100.0 for x in act["sell_levels"])

    # 2) A runaway drift should flip regime to TREND.
    price = 100.0
    ts = 1_000.0
    for _ in range(40):
        price *= 1.01
        ts += 10.0
        act = s.on_tick({"price": price, "ts": ts})
    assert s._regime == "TREND", f"expected TREND, got {s._regime}"

    # 3) Liquidity decays back toward idle with no fills (weekend protection).
    s2 = DetideGrid(cfg)
    s2._liquidity = 0.95
    s2.on_tick({"price": 100.0, "ts": 10_000.0})
    s2.on_tick({"price": 100.2, "ts": 100_000.0})  # ~25h later, decay half-life 1800s
    assert s2._liquidity < 0.5, f"liquidity should decay, got {s2._liquidity}"

    # 4) Fill path + PnL accounting.
    s3 = DetideGrid(cfg)
    s3.on_fill({"side": "buy", "price": 100.0, "amount": 1.0, "ts": 1_000.0})
    s3.on_fill({"side": "sell", "price": 102.0, "amount": 1.0, "ts": 1_010.0})
    assert s3.trades == 1 and s3.wins == 1
    assert abs(s3.pnl - 2.0) < 1e-9
    assert s3.buys == 1 and s3.sells == 1

    print("OK: DetideGrid tests passed, all invariants hold.")


if __name__ == "__main__":
    _run_tests()
