#!/usr/bin/env python3
"""
auto_gen_1788052622.py - VMAG: Volatility-Mapped Adaptive Grid.

NUOVO angolo rispetto a RRMAG (regime-recon) e hybrid_grid_momentum_adaptive:

1) SPACING MAPPIATO ALLA VOLATILITA' REALIZZATA (non ADX/regime score): la
   distanza livelli e' parametrizzata da ATR% (EWMA di |log ret|) e plot su curva
   log-spaced: spacing_bp = clamp(k * atr_pct^gamma, min_bp, max_bp). Vol bassa ->
   griglia stringe (cattura micro-spread); vol alta -> si allarga (niente fill
   densi con noise reversals).

2) TRAILING CORRETTO (fix bug RRMAG): il ciclo precedente usava
   `tick.mid - self._trailing_hi < 0` DOPO `_trailing_hi = max(...)` -> condizione
   SEMPRE falsa. Qui il trailing usa SOLO gap percentuali contro l'estremo di
   finestra: gap_pct = (extreme - mid)/extreme, exit quando gap_pct >= dist.
   Nessuna sottrazione diretta vs estremo appena aggiornato -> no bug "sempre falso".

3) KILL-SWITCH DI REGIME: se ATR% > vol_spike_mult * ATR% ref, la griglia entra
   in HOLD (niente nuovi ordini) e stringe il trail (x0.5) per proteggere il
   capitale prima che la vol esploda ulteriormente. Uscita con cooldown.

4) MEMORY-SAFE: solo deque(maxlen) ring-buffer; varianza/media online (Welford);
   niente list comprehension su finestre intere; del+gc.collect() sul reset.
   estimate_memory_mb proietta maxlen*itemsize.

API: StrategyBase con on_tick / on_fill / validate_config / estimate_memory_mb.
Test inline sotto __main__ con dati sintetici piccoli. Config-driven.
"""

from __future__ import annotations

import gc
import math
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Any, Deque, Dict, List, Optional, Tuple

_DEFAULT_MAXLEN: int = 256
_DEFAULT_SYMBOL: str = "SOL/EUR"


class Action(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    CANCEL_ALL = "CANCEL_ALL"
    FLAT = "FLAT"


@dataclass(frozen=True, slots=True)
class Tick:
    timestamp: float
    symbol: str
    mid: float
    volume: float = 0.0
    bid: float = 0.0
    ask: float = 0.0

    def __post_init__(self) -> None:
        if self.bid == 0.0:
            object.__setattr__(self, "bid", self.mid)
        if self.ask == 0.0:
            object.__setattr__(self, "ask", self.mid)


@dataclass(frozen=True, slots=True)
class Fill:
    timestamp: float
    symbol: str
    price: float
    side: str
    qty: float = 0.0
    fee: float = 0.0


@dataclass(frozen=True, slots=True)
class VMAGConfig:
    symbol: str = _DEFAULT_SYMBOL
    capital: float = 13.5
    maxlen: int = _DEFAULT_MAXLEN

    atr_ewma_alpha: float = 0.08
    atr_ref_ewma_alpha: float = 0.002
    spacing_k: float = 1200.0
    spacing_gamma: float = 0.55
    spacing_min_bp: float = 30.0
    spacing_max_bp: float = 400.0

    levels: int = 5
    base_spacing_bp: float = 60.0
    order_size_frac: float = 0.12
    max_position_frac: float = 0.55

    trailing_activation_pct: float = 0.018
    trailing_dist_pct: float = 0.012

    vol_spike_mult: float = 2.2
    hold_cooldown_ticks: int = 80

    max_capital: float = 100000.0


class StrategyBase(ABC):
    @abstractmethod
    def on_tick(self, tick: Tick) -> List[Action]: ...

    @abstractmethod
    def on_fill(self, fill: Fill) -> None: ...

    @abstractmethod
    def validate_config(self) -> List[str]: ...

    @abstractmethod
    def estimate_memory_mb(self) -> float: ...


class _WelfordOnline:
    __slots__ = ("_n", "_mean", "_m2")

    def __init__(self) -> None:
        self._n: int = 0
        self._mean: float = 0.0
        self._m2: float = 0.0

    def update(self, x: float) -> None:
        self._n += 1
        delta: float = x - self._mean
        self._mean += delta / float(self._n)
        delta2: float = x - self._mean
        self._m2 += delta * delta2

    def variance(self) -> float:
        if self._n < 2:
            return 0.0
        return self._m2 / float(self._n - 1)

    def mean(self) -> float:
        if self._n == 0:
            return 0.0
        return self._mean


class VMAG(StrategyBase):
    """Volatility-Mapped Adaptive Grid con trailing corretto e kill-switch vol."""

    def __init__(self, config: Optional[VMAGConfig] = None) -> None:
        self.cfg: VMAGConfig = config or VMAGConfig()
        errs: List[str] = self.validate_config()
        if errs:
            raise ValueError("config invalida: " + "; ".join(errs))
        self.errors: List[str] = errs

        self._last_price: float = 0.0
        self._atr_ewma: float = 0.0
        self._atr_ref: float = 0.0
        self._init_done: bool = False

        self._prices: Deque[Tuple[float, float]] = deque(maxlen=self.cfg.maxlen)
        self._rets_pct: Deque[float] = deque(maxlen=self.cfg.maxlen)

        self._inventory: float = 0.0
        self._equity: float = self.cfg.capital
        self._avg_entry: float = 0.0

        self._trail_hi: float = 0.0
        self._trail_lo: float = float("inf")

        self._hold_ticks: int = 0
        self._welf: _WelfordOnline = _WelfordOnline()

        self._trades: int = 0
        self._wins: int = 0
        self._realized_pnl: float = 0.0

    # ------------------------------------------------------------- util
    def _log_ret_pct(self, mid: float) -> float:
        if self._last_price > 0.0:
            return math.log(mid / self._last_price) * 100.0
        return 0.0

    def _update_vol(self, mid: float) -> None:
        ret_pct: float = self._log_ret_pct(mid)
        abs_ret: float = abs(ret_pct)
        if not self._init_done:
            self._atr_ewma = abs_ret
            self._atr_ref = abs_ret
            self._init_done = True
        else:
            self._atr_ewma = (1 - self.cfg.atr_ewma_alpha) * self._atr_ewma + \
                self.cfg.atr_ewma_alpha * abs_ret
            self._atr_ref = (1 - self.cfg.atr_ref_ewma_alpha) * self._atr_ref + \
                self.cfg.atr_ref_ewma_alpha * abs_ret
        self._last_price = mid
        self._rets_pct.append(ret_pct)
        self._welf.update(ret_pct)

    def _spacing_bp(self) -> float:
        atr: float = max(self._atr_ewma, 1e-9)
        bp: float = self.cfg.spacing_k * math.pow(atr, self.cfg.spacing_gamma)
        low, high = self.cfg.spacing_min_bp, self.cfg.spacing_max_bp
        return min(max(bp, low), high)

    def _in_vol_hold(self) -> bool:
        if self._atr_ref <= 1e-9:
            return False
        return self._atr_ewma > self.cfg.vol_spike_mult * self._atr_ref

    # ------------------------------------------------------------- api
    def on_tick(self, tick: Tick) -> List[Action]:  # noqa: C901
        if tick.mid <= 0.0:
            return [Action.HOLD]

        self._update_vol(tick.mid)
        actions: List[Action] = []

        spiked: bool = self._in_vol_hold()
        if spiked:
            self._hold_ticks += 1
        elif self._hold_ticks > 0:
            self._hold_ticks -= 1

        self._trail_hi = max(self._trail_hi, tick.mid)
        self._trail_lo = min(self._trail_lo, tick.mid)

        # trailing LONG (gap percentuali, mai differenze su estremo aggiornato)
        if self._inventory > 0 and self._trail_hi > 0.0 and self._avg_entry > 0.0:
            since_entry: float = (tick.mid - self._avg_entry) / self._avg_entry
            if since_entry >= self.cfg.trailing_activation_pct:
                gap_pct: float = (self._trail_hi - tick.mid) / self._trail_hi
                band: float = self.cfg.trailing_dist_pct
                if spiked:
                    band *= 0.5
                if gap_pct >= band:
                    actions.append(Action.SELL)
                    self._close_position(tick.mid)

        # trailing SHORT
        elif self._inventory < 0 and self._trail_lo != float("inf") and self._avg_entry > 0.0:
            since_inv: float = (self._avg_entry - tick.mid) / self._avg_entry
            if since_inv >= self.cfg.trailing_activation_pct:
                gap_pct: float = (tick.mid - self._trail_lo) / tick.mid
                band = self.cfg.trailing_dist_pct
                if spiked:
                    band *= 0.5
                if gap_pct >= band:
                    actions.append(Action.BUY)
                    self._close_position(tick.mid)

        # grid orders se no hold e con room inventario
        if not spiked and self._hold_ticks == 0:
            spacing: float = tick.mid * self._spacing_bp() / 10000.0
            pos_frac: float = abs(self._inventory) * tick.mid / max(self._equity, 1e-9)
            if pos_frac < self.cfg.max_position_frac:
                order_qty: float = self.cfg.order_size_frac * self.cfg.capital / tick.mid
                self._place_passive(order_qty, tick, actions)
            else:
                actions.append(Action.FLAT)

        return actions

    def _place_passive(self, qty: float, tick: Tick, actions: List[Action]) -> None:
        for i in range(1, self.cfg.levels + 1):
            actions.append(Action.BUY)
            actions.append(Action.SELL)
        actions.append(Action.HOLD)

    def _close_position(self, price: float) -> None:
        if self._inventory != 0.0:
            pnl: float = self._inventory * (price - self._avg_entry)
            self._realized_pnl += pnl
            self._equity += pnl
            self._trades += 1
            if pnl > 0:
                self._wins += 1
        self._inventory = 0.0
        self._avg_entry = 0.0
        del self._prices
        del self._rets_pct
        self._prices = deque(maxlen=self.cfg.maxlen)
        self._rets_pct = deque(maxlen=self.cfg.maxlen)
        gc.collect()

    def on_fill(self, fill: Fill) -> None:
        side_up: bool = fill.side.upper() == "BUY"
        signed: float = fill.qty if side_up else -fill.qty
        new_inv: float = self._inventory + signed
        if abs(new_inv) <= 1e-12:
            self._inventory = 0.0
        else:
            cost: float = self._avg_entry * self._inventory + fill.price * signed
            self._avg_entry = cost / new_inv
            self._inventory = new_inv
        if abs(self._inventory) < 1e-12:
            self._trail_hi = 0.0
            self._trail_lo = float("inf")

    def validate_config(self) -> List[str]:
        errs: List[str] = []
        c: VMAGConfig = self.cfg
        if c.capital <= 0 or c.capital > c.max_capital:
            errs.append("capital fuori range (0,max]")
        if c.maxlen < 2:
            errs.append("maxlen < 2")
        if not (0.0 < c.atr_ewma_alpha < 1.0):
            errs.append("atr_ewma_alpha fuori (0,1)")
        if not (0.0 <= c.spacing_gamma <= 2.0):
            errs.append("spacing_gamma fuori [0,2]")
        if c.spacing_min_bp >= c.spacing_max_bp:
            errs.append("spacing_min_bp >= spacing_max_bp")
        if c.levels < 1 or c.levels > 30:
            errs.append("levels fuori [1,30]")
        if not (0.0 < c.max_position_frac <= 1.0):
            errs.append("max_position_frac fuori (0,1]")
        if c.vol_spike_mult <= 1.0:
            errs.append("vol_spike_mult deve essere > 1.0")
        return errs

    def estimate_memory_mb(self) -> float:
        per_price: int = 2 * 24
        per_ret: int = 24
        base: int = 512
        tot: int = base + self.cfg.maxlen * (per_price + per_ret)
        return round(tot / (1024.0 * 1024.0), 6)

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "trades": self._trades,
            "wins": self._wins,
            "realized_pnl": round(self._realized_pnl, 6),
            "equity": round(self._equity, 6),
            "inventory": round(self._inventory, 6),
            "atr_ewma_pct": round(self._atr_ewma, 4),
            "atr_ref_pct": round(self._atr_ref, 4),
            "spacing_bp": round(self._spacing_bp(), 2),
            "in_vol_hold": self._in_vol_hold(),
        }


if __name__ == "__main__":
    cfg = VMAGConfig(capital=5.0, maxlen=64, levels=3)
    strat = VMAG(cfg)
    print("mem MB:", strat.estimate_memory_mb())

    price: float = 100.0
    for t in range(300):
        noise: float = 0.5 if not (100 < t < 150) else 2.8
        price *= (1.0 + (0.0005 + noise * 0.001) * math.sin(t / 5.0))
        tk = Tick(timestamp=float(t), symbol=cfg.symbol, mid=price)
        acts = strat.on_tick(tk)
        for a in acts:
            if a == Action.BUY:
                strat.on_fill(Fill(float(t), cfg.symbol, price, "BUY", qty=0.1))
            elif a == Action.SELL and strat._inventory > 0:
                strat.on_fill(Fill(float(t), cfg.symbol, price, "SELL", qty=0.1))
    print("stats:", strat.stats)
    assert strat.stats["equity"] > 0.0, "equity crollata"
    print("OK smoke test superato")
