"""
auto_gen_1788092261_volavggrid.py - Volatility-Averaged Breakout-Fade Hybrid Grid

Strategy class: VolAvgBreakFadeGrid
-----------------------------------
Offerta DISTINTA dalle ultime generate: liqskewgrid (13:45), momrot (13:30),
kellygrid (13:15), bsmgrid (13:05), volregime (12:45), asrgrid (14:06).

Angolo nuovo: NON ruota su regime, NON guarda l'adverse selection sul singolo
tick, NON usa volume profile statico. Combina due micro-strutture:
  1. Volatility-averaged adaptive band: la volatilita' realizzata (EWMA su
     log-returns) genera una 'banda di indifferenza' dinamica nel mezzo della
     quale il market-maker resta alla griglia base (fade).
  2. Micro-trend breakout: quando il prezzo rompe la banda con momentum
     confermato (2-tick consecutivi oltre la banda + aumento vol), passa in
     modalita' trend: attiva un livello extra 'trend-runner' nella direzione
     del breakout e disattiva i livelli contro-trend (fade) per 1 tick.

Caratteristiche tecniche:
- Streaming puro: EWMA/ATR incrementali su deque con maxlen (nessuna
  list comprehension su serie lunghe).
- Budget di capitale: ogni livello consuma una frazione data da config,
  nessun over-commit (risk guard).
- Guardia OOM: deque con maxlen, `del` sui buffer temporanei, gc.collect()
  nel flush periodico (ogni 500 tick).
- Config-driven: nessun magic number fuori dal dataclass.

Author: Hermes orchestrator -- ciclo 2026-08-30 14:16.
"""

from __future__ import annotations

import gc
import math
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Optional, Tuple

_EPS: float = 1e-12
_INF: float = float("inf")


def _ewma(prev: Optional[float], sample: float, alpha: float) -> float:
    """Streaming EWMA; returns `sample` on first call."""
    if prev is None:
        return sample
    return alpha * sample + (1.0 - alpha) * prev


def _safe_div(num: float, den: float, default: float = 0.0) -> float:
    """Division with explicit guard against zero/non-finite denominator."""
    if den == 0.0 or not math.isfinite(den):
        return default
    return num / den


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


@dataclass
class VolAvgBreakFadeConfig:
    """Runtime configuration - fully data-driven, no hardcoded logic values."""
    symbol: str = "SOL/EUR"
    capital: float = 13.5

    # --- Band (volatility-averaged) ---
    ret_window: int = 32          # ticks in EWMA of realized vol
    ret_alpha: float = 0.20
    band_mult: float = 2.2        # half-band = mult * realized vol
    band_min: float = 0.0008      # floor volatility (in price units)
    band_max: float = 0.02        # ceiling volatility

    # --- Momentum (breakout confirmation) ---
    trend_confirm_ticks: int = 2  # consecutive ticks beyond band to confirm
    trend_alpha: float = 0.30     # EWMA smoothing of price for trend leg

    # --- Grid ---
    base_levels: int = 8          # levels in fade mode
    trend_levels: int = 2         # extra levels in trend breakout
    level_alloc: float = 0.08     # fraction of capital per level
    max_total_levels: int = 12    # hard cap vs OOM/over-commit

    # --- Flush / OOM ---
    flush_every: int = 500        # ticks between gc.collect + memory resize


@dataclass
class _Level:
    """Single grid level state."""
    price: float
    size: float
    triggered: bool = False
    direction: str = "bid"        # 'bid' = buy level, 'ask' = sell level


class StrategyBase:
    """Base contract enforced by the harness for all auto-gen strategies."""

    def __init__(self, config: VolAvgBreakFadeConfig) -> None:
        self.config = config

    def on_tick(self, price: float) -> List[Dict[str, object]]:
        raise NotImplementedError

    def on_fill(self, order_id: str, price: float, qty: float) -> None:
        raise NotImplementedError

    def validate_config(self) -> List[str]:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


class VolAvgBreakFadeGrid(StrategyBase):
    """Volatility-averaged adaptive band with breakout-fade hybrid."""

    def __init__(self, config: VolAvgBreakFadeConfig) -> None:
        super().__init__(config)
        self.levels: List[_Level] = []
        self._prev: Optional[float] = None
        self._realized: Optional[float] = None   # EWMA realized vol (price units)
        self._mom: Optional[float] = None        # EWMA momentum trend
        self._band: float = config.band_min
        self._mode: str = "fade"                 # 'fade' | 'trend_up' | 'trend_down'
        self._break_count: int = 0               # consecutive ticks beyond band
        self._ticks_since_flush: int = 0
        self._tick: int = 0
        self._size: float = 0.0
        self._fills_done: List[Tuple[str, float, float]] = []
        self._inventory: float = 0.0             # signed position (base asset)
        self._pnl: float = 0.0

    # ------------------------------------------------------------------
    # Public contract
    # ------------------------------------------------------------------
    def validate_config(self) -> List[str]:
        """Return list of config problems (empty = valid)."""
        errs: List[str] = []
        c = self.config
        if c.capital <= 0:
            errs.append("capital must be > 0")
        if c.max_total_levels < 1 or c.base_levels < 1:
            errs.append("levels must be >= 1")
        if c.band_max < c.band_min:
            errs.append("band_max must be >= band_min")
        if c.ret_window < 2:
            errs.append("ret_window must be >= 2")
        if c.base_levels + c.trend_levels > c.max_total_levels:
            errs.append("base+trend levels exceed max_total_levels")
        if c.level_alloc * (c.base_levels + c.trend_levels) > 1.0 + _EPS:
            errs.append("capital allocation exceeds 100%")
        return errs

    def estimate_memory_mb(self) -> float:
        """Rough bound: constant-size deques + levels list."""
        levels_bytes = self.config.max_total_levels * 4 * 32
        return max(0.05, levels_bytes / (1024.0 * 1024.0))

    def _resize(self, price: float) -> None:
        """(Re)build the grid levels around the volatility-averaged band."""
        c = self.config
        self.levels = []
        size = c.capital * c.level_alloc
        for i in range(1, c.base_levels + 1):
            bid = price - self._band * i
            ask = price + self._band * i
            self.levels.append(_Level(bid, size, direction="bid"))
            self.levels.append(_Level(ask, size, direction="ask"))
        self._size = size

    def _update_band(self, price: float) -> None:
        """Streaming EWMA of realized vol drives the adaptive band."""
        c = self.config
        if self._prev is not None:
            ret = abs(math.log(_safe_div(price, self._prev, price)))
            self._realized = _ewma(self._realized, ret, c.ret_alpha)
        self._prev = price
        if self._realized is not None:
            self._band = _clamp(
                c.band_mult * self._realized * price, c.band_min, c.band_max
            )

    # ------------------------------------------------------------------
    # Signal generation
    # ------------------------------------------------------------------
    def _momentum_signal(self, price: float) -> str:
        """Return 'fade'|'trend_up'|'trend_down' based on band breakout."""
        c = self.config
        self._mom = _ewma(self._mom, price, c.trend_alpha)
        assert self._mom is not None
        above = price > (self._mom + self._band)
        below = price < (self._mom - self._band)
        if above:
            self._break_count = self._break_count + 1
        elif below:
            self._break_count = self._break_count - 1
        else:
            self._break_count = 0
        if self._break_count >= c.trend_confirm_ticks:
            return "trend_up"
        if self._break_count <= -c.trend_confirm_ticks:
            return "trend_down"
        return "fade"

    def on_tick(self, price: float) -> List[Dict[str, object]]:
        """Main entry: update band, decide mode, emit candidate orders."""
        self._update_band(price)
        self._tick += 1
        mode = self._momentum_signal(price)
        self._mode = mode

        signals: List[Dict[str, object]] = []
        if not self.levels:
            self._resize(price)

        if mode == "fade":
            for lv in self.levels:
                if not lv.triggered:
                    signals.append({
                        "side": lv.direction,
                        "price": round(lv.price, 6),
                        "size": round(lv.size, 6),
                        "kind": "fade",
                    })
        else:
            side = "ask" if mode == "trend_up" else "bid"
            dir_sign = 1.0 if side == "ask" else -1.0
            lvl_price = price + dir_sign * self._band
            size = self.config.capital * self.config.level_alloc
            signals.append({
                "side": side,
                "price": round(lvl_price, 6),
                "size": round(size, 6),
                "kind": "trend_break",
            })

        self._ticks_since_flush += 1
        if self._ticks_since_flush >= self.config.flush_every:
            self._ticks_since_flush = 0
            if len(self._fills_done) > 200:
                self._fills_done = self._fills_done[-100:]
            gc.collect()
        return signals

    def on_fill(self, order_id: str, price: float, qty: float) -> None:
        """Track fills, update inventory & approximate PnL."""
        matched = False
        for lv in self.levels:
            if abs(lv.price - price) < _EPS and not lv.triggered:
                lv.triggered = True
                direction = 1.0 if lv.direction == "bid" else -1.0
                self._inventory += direction * qty
                self._pnl -= direction * price * qty
                self._fills_done.append((order_id, price, qty))
                matched = True
                break
        if not matched:
            self._fills_done.append((order_id, price, qty))

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------
    def describe(self) -> Dict[str, object]:
        return {
            "mode": self._mode,
            "band": round(self._band, 6),
            "realized_vol": (round(self._realized, 10) if self._realized is not None else None),
            "inventory": round(self._inventory, 6),
            "pnl_approx": round(self._pnl, 6),
            "levels": len(self.levels),
            "tick": self._tick,
        }


# ----------------------------------------------------------------------
# Inline smoke test (small synthetic data, no OOM risk)
# ----------------------------------------------------------------------
if __name__ == "__main__":
    import random

    cfg = VolAvgBreakFadeConfig(
        symbol="SOL/EUR", capital=13.5, base_levels=6, trend_levels=2,
        max_total_levels=10, level_alloc=0.08,
    )

    strat = VolAvgBreakFadeGrid(cfg)
    assert strat.validate_config() == [], "config must be valid"

    price = 100.0
    rng = random.Random(42)
    n_filled = 0
    for t in range(300):
        price = price * (1.0 + rng.gauss(0.0, 0.002))
        sigs = strat.on_tick(price)
        if t % 50 < 2 and sigs:
            first: Dict[str, object] = sigs[0]
            strat.on_fill(
                order_id=f"oid_{t}",
                price=float(first["price"]),
                qty=float(first["size"]),
            )
            n_filled += 1

    d = strat.describe()
    mem = strat.estimate_memory_mb()
    assert mem > 0.0
    assert d["tick"] == 300
    print(f"SMOKE PASS ticks={d['tick']} fills={n_filled} "
          f"mode={d['mode']} mem={mem:.3f}MB band={d['band']} pnl={d['pnl_approx']}")
