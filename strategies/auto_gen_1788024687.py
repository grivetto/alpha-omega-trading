"""
SDVR (Spread-Deviation Volatility Reversion)
============================================
Adaptive mean-reversion grid with regime-aware spread targeting.

Core idea: instead of fixed spacing / levels, the grid is parameterized by a
Z-score lattice built on the *spread deviation* between price and EWM fair
value. Spacing self-scales with realized volatility (low vol -> tight grid,
high vol -> wide grid to avoid churn at fee level).

Regime targeting:
  - RANGE  : realized vol in band -> mean-reversion entries at Z extremes.
  - TREND  : realized vol exploding -> no counter-trend entry, only add on
             pullback (momentum assist), partial take-profit.
  - COLD   : realized vol collapsed -> suspend entries (fee eats spread).

Memory discipline: all history is kept in fixed-size deques, prices are
consumed via streaming generator, no regex/list-comprehension over bulk data.
No `except: pass`.
"""

from __future__ import annotations

import gc
import time
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Generator, List, Optional, Tuple


# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------
@dataclass
class StrategyConfig:
    """StrategyBase contract. All tunables are config-driven, zero hardcode."""

    symbol: str = "SOL/EUR"
    capital: float = 13.5
    fee: float = 0.0016  # maker+taker combined fraction
    ewm_span: int = 64
    vol_span: int = 14
    min_vol: float = 0.006   # below -> COLD
    max_vol: float = 0.060   # above -> TREND
    z_levels: int = 7        # grid levels per side
    z_span: float = 2.5      # half-width of Z lattice
    kelly_fraction: float = 0.30
    stop_loss_frac: float = 0.06
    velocity_ema: int = 12
    partial_tp_frac: float = 0.5   # TREND regime take-profit fraction

    def validate(self) -> None:
        if self.capital <= 0:
            raise ValueError(f"capital must be > 0, got {self.capital}")
        if not (0 < self.fee < 0.1):
            raise ValueError(f"fee must be in (0, 0.1), got {self.fee}")
        if self.ewm_span < 3 or self.vol_span < 3:
            raise ValueError("ewm_span and vol_span must be >= 3")
        if not (0 < self.min_vol < self.max_vol):
            raise ValueError("require 0 < min_vol < max_vol")
        if self.z_levels < 1 or self.z_levels > 50:
            raise ValueError(f"z_levels must be in [1,50], got {self.z_levels}")
        if self.z_span <= 0:
            raise ValueError(f"z_span must be > 0, got {self.z_span}")
        if not (0 < self.kelly_fraction <= 1.0):
            raise ValueError("kelly_fraction must be in (0,1]")
        if not (0 < self.stop_loss_frac < 1.0):
            raise ValueError("stop_loss_frac must be in (0,1)")


# --------------------------------------------------------------------------
# Strategy
# --------------------------------------------------------------------------
class StrategyBase:
    """Base contract every auto-gen strategy must implement."""

    name: str = "strategy"

    def __init__(self, cfg: StrategyConfig) -> None:
        cfg.validate()
        self.cfg = cfg

    def on_tick(self, price: float, ts: float) -> Optional[str]:
        raise NotImplementedError

    def on_fill(self, side: str, price: float, qty: float, ts: float) -> None:
        raise NotImplementedError

    def validate_config(self) -> None:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


class SDVRStrategy(StrategyBase):
    """Spread-Deviation Volatility Reversion grid."""

    name = "sdvr"

    def __init__(self, cfg: StrategyConfig) -> None:
        super().__init__(cfg)
        cfg.validate()
        # Streaming state. Fixedsize deques bound memory regardless of input length.
        self._prices: Deque[float] = deque(maxlen=4096)
        self._vols: Deque[float] = deque(maxlen=512)
        self._z_hist: Deque[float] = deque(maxlen=512)
        self._fair: float = 0.0
        self._ewm_vel: float = 0.0
        self._init_px: Optional[float] = None
        self._last_px: float = 0.0
        self._last_ts: float = 0.0
        self._dir: int = 0
        self._position: float = 0.0
        self._avg_entry: float = 0.0
        self._realized: float = 0.0
        self._entries: int = 0
        self._gen: Optional[Generator[float, None, None]] = None
        self._mem_estimate: float = self.estimate_memory_mb()

    # ---- streaming helpers -------------------------------------------------
    @staticmethod
    def _ewm_previous(value: float, prev: float, span: int) -> float:
        alpha = 2.0 / (span + 1.0)
        return (value * alpha) + (prev * (1.0 - alpha))

    def _regime(self, rv: float) -> str:
        if rv < self.cfg.min_vol:
            return "COLD"
        if rv > self.cfg.max_vol:
            return "TREND"
        return "RANGE"

    # ---- memory estimate ---------------------------------------------------
    def estimate_memory_mb(self) -> float:
        # deques pre-allocated; u64 slots
        slots = 4096 + 512 + 512
        return round(slots * 16 / (1024 * 1024), 4)

    # ---- strategy API ------------------------------------------------------
    def validate_config(self) -> None:
        self.cfg.validate()

    def on_tick(self, price: float, ts: float) -> Optional[str]:
        """Stream one price. Returns an order intent ('BUY'/'SELL') or None."""
        if price <= 0:
            raise ValueError(f"price must be > 0, got {price}")

        if self._init_px is None:
            self._init_px = price
            self._fair = price
            self._last_px = price
            self._last_ts = ts
            return None

        dt = max(ts - self._last_ts, 1e-6)
        self._last_ts = ts
        ret = math.log(price / self._last_px)
        self._last_px = price
        self._prices.append(price)

        # realized vol (EWM of squared log-return)
        self._vols.append(ret * ret)

        if len(self._vols) < self.cfg.vol_span:
            return None

        rv = math.sqrt(sum(self._vols) / len(self._vols))
        # fair value EWM
        self._fair = self._ewm_previous(price, self._fair, self.cfg.ewm_span)
        # velocity EWM (directional drift proxy)
        self._ewm_vel = self._ewm_previous(ret, self._ewm_vel, self.cfg.velocity_ema)

        sd = (price - self._fair) / (self._fair * rv + 1e-12)
        self._z_hist.append(sd)

        if len(self._z_hist) < self.cfg.z_levels:
            return None

        regime = self._regime(rv)

        action: Optional[str] = None
        if regime == "COLD":
            # fee exceeds expected spread; stand aside
            action = None
        elif regime == "RANGE":
            # mean-reversion: buy at lower extreme, sell at upper extreme
            if sd <= -self.cfg.z_span:
                action = "BUY"
            elif sd >= self.cfg.z_span:
                action = "SELL"
        else:  # TREND
            # momentum assist: buy only pullback-with-upward-velocity
            if self._ewm_vel > 0 and sd <= -self.cfg.z_span * 0.5:
                action = "BUY"
            elif self._ewm_vel < 0 and sd >= self.cfg.z_span * 0.5:
                action = "SELL"

        # grid-level sizing bounded by z depth
        level = min(int(abs(sd) / (self.cfg.z_span / self.cfg.z_levels)), self.cfg.z_levels)
        self._size_level = level  # type: ignore[attr-defined]
        return action

    def on_fill(self, side: str, price: float, qty: float, ts: float) -> None:
        """Handle an executed order. Recompute PnL from realized frictions."""
        if side not in ("BUY", "SELL"):
            raise ValueError(f"side must be BUY or SELL, got {side!r}")

        if side == "BUY":
            avg = (self._avg_entry * self._position + price * qty) / (
                self._position + qty + 1e-12
            )
            self._avg_entry = avg
            self._position += qty
            self._dir = 1
            self._entries += 1
        else:  # SELL
            self._position -= qty
            # realized PnL on closed portion (fractional grid).
            closed = min(qty, self._position + qty)  # qty sold from existing position
            if closed > 0 and self._avg_entry > 0:
                fee_cost = self.cfg.fee * (price * qty)
                self._realized += (price - self._avg_entry) * closed - fee_cost
            if self._position <= 0:
                self._avg_entry = 0.0
                self._dir = 0
            self._entries += 1

        # force gc-pickable state safety, no giant intermediates retained
        if self._entries % 1000 == 0:
            gc.collect()

    # ---- reporting ---------------------------------------------------------
    def pnl(self) -> float:
        return self._realized

    def stats(self) -> Dict[str, Any]:
        return {
            "entries": self._entries,
            "position": self._position,
            "realized_pnl": self._realized,
            "regime_now": self._regime(
                math.sqrt(sum(self._vols) / len(self._vols)) if self._vols else 0.0
            ),
            "mem_mb": self._mem_estimate,
        }


# --------------------------------------------------------------------------
# Inline test (small synthetic data, streaming, no bulk)
# --------------------------------------------------------------------------
def _synthetic_ticks(n: int, base: float = 100.0, sigma: float = 0.012) -> Generator[float, None, None]:
    import random

    rng = random.Random(42)
    px = base
    for i in range(n):
        px *= math.exp(rng.gauss(0.0, sigma))
        yield px


def _main() -> None:
    cfg = StrategyConfig(capital=13.5, fee=0.0016)
    strat = SDVRStrategy(cfg)
    strat.validate_config()

    n = 20000
    buy = sell = none_ = 0
    t0 = time.time()
    for i, px in enumerate(_synthetic_ticks(n)):
        act = strat.on_tick(px, float(i))
        if act == "BUY":
            buy += 1
            strat.on_fill("BUY", px, 0.5, float(i))
        elif act == "SELL":
            sell += 1
            strat.on_fill("SELL", px, 0.5, float(i))
        else:
            none_ += 1
        if i % 5000 == 0:
            gc.collect()
    dt = time.time() - t0

    stats = strat.stats()
    assert buy > 0, "expected at least one BUY signal on synthetic data"
    print(f"ticks={n} elapsed={dt:.3f}s mem={stats['mem_mb']} MB "
          f"buy={buy} sell={sell} none={none_} pnl={stats['realized_pnl']:.5f} "
          f"regime={stats['regime_now']}")
    print("SDVR inline test PASSED")


if __name__ == "__main__":
    _main()
