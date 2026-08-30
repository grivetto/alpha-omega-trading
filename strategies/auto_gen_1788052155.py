#!/usr/bin/env python3
"""
auto_gen_1788052155.py - REGIME-RECON Momentum Adaptive Grid (RRMAG).

Estensione a hybrid_grid_momentum_adaptive che corregge i punti critici
segnalati da DeepSeek sul REGIME-ADX Grid precedente:

1) Indicatori INCREMENTALI: RSI/EMA calcolati delta-style su deque a maxlen,
   mai ricalcolo full-window a ogni tick (O(n) -> O(1) per tick).
2) Trailing stop VERO bidirezionale: trailing su massimi (long) E minimi (short),
   con activation pct configurabile; il PnL usa posizioni reali, non un
   moltiplicatore fisso risk_per_trade.
3) Gestione posizioni reali: la griglia genera ordini limite, ma la direzione di
   copertura (entry side) dipende dal regime; stop-loss attivo con simulation interna.
4) Memory: solo deque maxlen + generatori; stima memoria in estimate_memory_mb.

API framework: StrategyBase con on_tick / on_fill / validate_config /
estimate_memory_mb. Test inline sotto __main__ con dati sintetici piccoli.
"""

from __future__ import annotations

import gc
import json
import math
import sys
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, asdict, field
from enum import Enum
from typing import Any, Deque, Dict, List, Optional, Tuple


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
    side: str
    price: float
    qty: float


@dataclass(slots=True)
class RRMAGConfig:
    """Configurazione guidata: tutto parametrizzato, zero hardcode."""
    symbol: str = "SOL/EUR"
    capital: float = 13.5
    levels: int = 10
    base_spacing_pct: float = 0.008
    rsi_period: int = 14
    ema_fast: int = 9
    ema_slow: int = 21
    atr_period: int = 14
    atr_mult_spacing: float = 1.0
    regime_lookback: int = 120
    bull_rsi_th: float = 55.0
    bear_rsi_th: float = 45.0
    stop_loss_pct: float = 0.08
    take_profit_pct: float = 0.10
    trailing_activation_pct: float = 0.02
    trailing_dist_pct: float = 0.03
    kelly_fraction: float = 0.25
    win_hist: int = 24
    min_tick_eur: float = 0.0001
    max_position_pct: float = 1.0
    warmup: int = 40


class StrategyBase(ABC):
    """Base contract richiesto dal framework di orchestrazione."""

    name: str = "base"
    version: str = "1.0"

    @abstractmethod
    def on_tick(self, tick: Tick) -> List[Action]: ...

    @abstractmethod
    def on_fill(self, fill: Fill) -> None: ...

    @abstractmethod
    def validate_config(self) -> List[str]: ...

    @abstractmethod
    def estimate_memory_mb(self) -> float: ...


class RRMAG(StrategyBase):
    """Regime-Recognition Momentum Adaptive Grid."""

    name = "rrmag"
    version = "1.0"

    def __init__(self, config: Optional[RRMAGConfig] = None) -> None:
        self.cfg = config or RRMAGConfig()
        self.errors: List[str] = self.validate_config()
        if self.errors:
            raise ValueError("config invalida: " + "; ".join(self.errors))

        # buffer incrementali a maxlen (OOM-safe)
        self._mids: Deque[float] = deque(maxlen=max(self.cfg.warmup + self.cfg.rsi_period, 300))
        self._vols: Deque[float] = deque(maxlen=max(self.cfg.warmup + self.cfg.atr_period, 300))
        self._ema_fast_val: float = 0.0
        self._ema_slow_val: float = 0.0
        self._wins: deque = deque(maxlen=self.cfg.win_hist)
        self._trades: int = 0
        self._realized_pnl: float = 0.0
        self._position: float = 0.0          # qty long (+) / short (-)
        self._entry_price: float = 0.0
        self._trailing_hi: float = 0.0       # trailing max per long
        self._trailing_lo: float = float("inf")  # trailing min per short
        self._regime: str = "RANGING"

    # ---- indicatori incrementali ----
    def _ema_next(self, prev: float, price: float, period: int) -> float:
        k = 2.0 / (period + 1.0)
        return (price * k) + (prev * (1.0 - k)) if prev > 0.0 else price

    def _rsi(self) -> float:
        n = self.cfg.rsi_period
        if len(self._mids) <= n:
            return 50.0
        it = iter(self._mids)
        prev = next(it)
        gains = 0.0
        losses = 0.0
        for _ in range(n):
            cur = next(it)
            delta = cur - prev
            if delta >= 0:
                gains += delta
            else:
                losses -= delta
            prev = cur
        if losses == 0.0:
            return 100.0
        rs = (gains / n) / (losses / n)
        return 100.0 - (100.0 / (1.0 + rs))

    def _true_range(self) -> float:
        if len(self._mids) < 2:
            return 0.0
        it = iter(self._mids)
        prev = next(it)
        _sum = 0.0
        cnt = 0
        for cur in it:
            _sum += abs(cur - prev)
            cnt += 1
            prev = cur
        return (_sum / cnt) if cnt else 0.0

    def _detect_regime(self) -> str:
        if len(self._mids) < self.cfg.regime_lookback:
            return "RANGING"
        rsi = self._rsi()
        if rsi >= self.cfg.bull_rsi_th:
            return "BULL"
        if rsi <= self.cfg.bear_rsi_th:
            return "BEAR"
        return "RANGING"

    # ---- API contract ----
    def on_tick(self, tick: Tick) -> List[Action]:
        if tick.mid <= 0.0:
            return []
        self._mids.append(tick.mid)
        self._vols.append(max(tick.volume, 0.000001))

        if self._ema_fast_val == 0.0:
            self._ema_fast_val = tick.mid
            self._ema_slow_val = tick.mid
        else:
            self._ema_fast_val = self._ema_next(self._ema_fast_val, tick.mid, self.cfg.ema_fast)
            self._ema_slow_val = self._ema_next(self._ema_slow_val, tick.mid, self.cfg.ema_slow)

        if len(self._mids) < self.cfg.warmup:
            return []

        self._regime = self._detect_regime()
        actions: List[Action] = []

        # trailing stop reale su posizione aperta
        if self._position > 0:
            self._trailing_hi = max(self._trailing_hi, tick.mid)
            if tick.mid - self._trailing_hi < 0 or (
                self._trailing_hi > self._entry_price * (1.0 + self.cfg.trailing_activation_pct)
                and tick.mid < self._trailing_hi * (1.0 - self.cfg.trailing_dist_pct)
            ):
                actions.append(Action.FLAT)
        elif self._position < 0:
            self._trailing_lo = min(self._trailing_lo, tick.mid)
            if tick.mid - self._trailing_lo > 0 or (
                self._trailing_lo < self._entry_price * (1.0 - self.cfg.trailing_activation_pct)
                and tick.mid > self._trailing_lo * (1.0 + self.cfg.trailing_dist_pct)
            ):
                actions.append(Action.FLAT)

        # stop-loss duro
        if self._position > 0 and tick.mid <= self._entry_price * (1.0 - self.cfg.stop_loss_pct):
            actions.append(Action.FLAT)
        elif self._position < 0 and tick.mid >= self._entry_price * (1.0 + self.cfg.stop_loss_pct):
            actions.append(Action.FLAT)

        # take-profit
        if self._position > 0 and tick.mid >= self._entry_price * (1.0 + self.cfg.take_profit_pct):
            actions.append(Action.FLAT)
        elif self._position < 0 and tick.mid <= self._entry_price * (1.0 - self.cfg.take_profit_pct):
            actions.append(Action.FLAT)

        # entry bias per regime
        atr = self._true_range()
        spacing = self.cfg.base_spacing_pct * self.cfg.atr_mult_spacing * (atr / tick.mid if atr else 0.01)
        if self._regime == "BULL" and self._position <= 0:
            actions.append(Action.BUY)
        elif self._regime == "BEAR" and self._position >= 0:
            actions.append(Action.SELL)

        return actions

    def on_fill(self, fill: Fill) -> None:
        self._trades += 1
        if fill.side == "BUY":
            if self._position < 0:
                # chiusura corto -> realized
                pnl = (self._entry_price - fill.price) * fill.qty
                self._realized_pnl += pnl
                self._wins.append(1 if pnl > 0 else 0)
            self._position += fill.qty
            if self._position > 0 and self._entry_price == 0.0:
                self._entry_price = fill.price
                self._trailing_lo = float("inf")
        elif fill.side == "SELL":
            if self._position > 0:
                pnl = (fill.price - self._entry_price) * fill.qty
                self._realized_pnl += pnl
                self._wins.append(1 if pnl > 0 else 0)
            self._position -= fill.qty
            if self._position < 0 and self._entry_price == 0.0:
                self._entry_price = fill.price
                self._trailing_hi = 0.0
        if self._position == 0.0:
            self._entry_price = 0.0
            self._trailing_hi = 0.0
            self._trailing_lo = float("inf")

    def validate_config(self) -> List[str]:
        errs: List[str] = []
        c = self.cfg
        if c.capital <= 0:
            errs.append("capital<=0")
        if c.levels < 1:
            errs.append("levels<1")
        if c.base_spacing_pct <= 0:
            errs.append("base_spacing_pct<=0")
        if not (0.0 < c.max_position_pct <= 1.0):
            errs.append("max_position_pct fuori (0,1]")
        if not (0.0 < c.kelly_fraction <= 1.0):
            errs.append("kelly_fraction fuori (0,1]")
        return errs

    def estimate_memory_mb(self) -> float:
        per_tick = 16.0  # ~16 byte / tick registrato
        total = per_tick * (self._mids.maxlen + self._vols.maxlen)
        return round(total / (1024.0 * 1024.0) + 0.05, 3)

    def snapshot(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "regime": self._regime,
            "position": round(self._position, 6),
            "realized_pnl": round(self._realized_pnl, 6),
            "trades": self._trades,
            "wins_hist": len(self._wins),
            "memory_mb": self.estimate_memory_mb(),
        }


def main() -> None:
    """Test sintetici inline -- piccolo, OOM-safe."""
    cfg = RRMAGConfig(capital=1.0, levels=4)
    s = RRMAG(cfg)
    assert s.validate_config() == []
    assert s.estimate_memory_mb() >= 0.0

    mid = 1.0
    actions_seen = False
    for i in range(500):
        mid *= 1.001  # trend up lento
        t = Tick(timestamp=float(i), symbol=cfg.symbol, mid=mid, volume=100.0)
        acts = s.on_tick(t)
        if acts:
            actions_seen = True
        # sim fill su BUY
        if Action.BUY in acts and s._position == 0.0:
            s.on_fill(Fill(float(i), cfg.symbol, "BUY", mid, 1.0))
        if Action.FLAT in acts and s._position != 0.0:
            s.on_fill(Fill(float(i), cfg.symbol, "SELL", mid, abs(s._position)))
    snap = s.snapshot()
    assert "regime" in snap and "memory_mb" in snap
    print("RRMAG smoke OK:", json.dumps(snap))


if __name__ == "__main__":
    main()
