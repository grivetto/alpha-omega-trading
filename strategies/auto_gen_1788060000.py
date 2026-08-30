#!/usr/bin/env python3
"""
auto_gen_1788060000.py - VOL-SCALED Breakout Grid (VSBG).

Strategia adaptive che adatta la griglia alla volatilità corrente invece di
usare spacing fisso. Idea chiave: in regime di volatility expansion la griglia
si allarga (meno livelli, cattura i movimenti grossi), in compression si
restringe (più livelli, sfrutta il scalping).

Novità rispetto ai gen precedenti:
1) Volatility-driven grid: spacing = base_spacing * (ATR / ref_atr)^decay,
   calcolata incrementalmente con EWMA (nessun ricalcolo full window).
2) Collar di drawdown: se il PnL scende sotto threshold, la griglia si
   "arresta" (spacing z-fold, livelli dimezzati) fino a regime recovery.
3) Memory-safe: solo deque maxlen + generatori, nessuna list comprehension
   su dataset grandi, del su buffer temporanei + gc.collect().
4) Config-driven: tutto parametrico, niente valori hardcoded.

API framework: StrategyBase con on_tick / on_fill / validate_config /
estimate_memory_mb. Test inline sotto __main__ con dati sintetici piccoli.
"""

from __future__ import annotations

import gc
import json
import math
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Any, Deque, Dict, List, Optional


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


@dataclass(frozen=True, slots=True)
class Fill:
    timestamp: float
    symbol: str
    side: str       # BUY | SELL
    price: float
    qty: float
    fee: float = 0.0


class StrategyBase(ABC):
    """Contratto minimo richiesto dal framework Denaro."""

    @abstractmethod
    def on_tick(self, tick: Tick) -> List[Dict[str, Any]]:
        """Processa un tick, ritorna lista di azioni (ordini/cancella)."""

    @abstractmethod
    def on_fill(self, fill: Fill) -> None:
        """Aggiorna stato interno su esecuzione di un ordine."""

    @abstractmethod
    def validate_config(self) -> List[str]:
        """Ritorna lista errori di config (vuota se valida)."""

    @abstractmethod
    def estimate_memory_mb(self) -> float:
        """Stima footprint RAM in MB."""


class VolScaledBreakoutGrid(StrategyBase):
    """Griglia breakout adattiva per volatilità."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config: Dict[str, Any] = dict(config)
        self.errors: List[str] = self.validate_config()
        if self.errors:
            raise ValueError("; ".join(self.errors))

        # --- parametri config-driven ---
        self.symbol: str = str(self.config.get("symbol", "SOL/EUR"))
        self.capital: float = float(self.config["capital"])
        self.base_spacing: float = float(self.config["base_spacing"])
        self.levels: int = int(self.config["levels"])
        self.vol_decay: float = float(self.config["vol_decay"])
        self.atr_period: int = int(self.config.get("atr_period", 14))
        self.ref_atr: float = float(self.config.get("ref_atr", 0.02))
        self.dd_collar: float = float(self.config.get("dd_collar", -0.03))
        self.numeraire_vol: float = float(self.config.get("numeraire_vol", 0.5))
        self.max_qty: float = float(self.config.get("max_qty", 1.0))

        # --- stato interno (O(1) per tick) ---
        self._prices: Deque[float] = deque(maxlen=self.atr_period)
        self._ewma_vol: float = self.ref_atr
        self._realized_pnl: float = 0.0
        self._peak_pnl: float = 0.0
        self._collared: bool = False
        self._last_mid: Optional[float] = None
        self._nr_trades: int = 0

    # ------------------------------------------------------------------
    def _ewma_atr(self, mid: float) -> float:
        """Aggiorna EWMA della volatilità (range normalizzato). O(1)."""
        if self._last_mid is not None and self._last_mid > 0.0:
            ret: float = abs(mid - self._last_mid) / self._last_mid
            alpha: float = 2.0 / (self.atr_period + 1.0)
            self._ewma_vol = alpha * ret + (1.0 - alpha) * self._ewma_vol
        self._prices.append(mid)
        self._last_mid = mid
        return self._ewma_vol

    def _effective_spacing(self) -> float:
        """Spacing scelto in base a volatilità (e collar drawdown)."""
        ratio: float = self._ewma_vol / self.ref_atr if self.ref_atr else 1.0
        vol_factor: float = ratio ** self.vol_decay
        base: float = self.base_spacing * vol_factor
        if self._collared:
            base *= self.numeraire_vol
        return max(base, self.base_spacing * 0.1)

    # ------------------------------------------------------------------
    def on_tick(self, tick: Tick) -> List[Dict[str, Any]]:
        if self.errors:
            return []
        mid: float = tick.mid
        self._ewma_atr(mid)

        # aggiorna peak/collar sul PnL realizzato
        if self._realized_pnl > self._peak_pnl:
            self._peak_pnl = self._realized_pnl
        dd: float = self._realized_pnl - self._peak_pnl
        if dd <= self.dd_collar and not self._collared:
            self._collared = True
        elif dd > 0.0 and self._collared:
            self._collared = False  # recovery

        spacing: float = self._effective_spacing()
        n_levels: int = self.levels
        if self._collared:
            n_levels //= 2

        actions: List[Dict[str, Any]] = [{"action": Action.HOLD.value, "symbol": self.symbol}]
        # generatore esplicito, niente comprehension su scale grandi
        for i in range(n_levels):
            level_price: float = mid * (1.0 + spacing * float(i + 1))
            actions.append({
                "action": Action.SELL.value, "symbol": self.symbol,
                "price": round(level_price, 8), "qty": self.max_qty,
            })
            level_buy: float = mid * (1.0 - spacing * float(i + 1))
            actions.append({
                "action": Action.BUY.value, "symbol": self.symbol,
                "price": round(level_buy, 8), "qty": self.max_qty,
            })
        del level_price, level_buy
        gc.collect()
        return actions

    # ------------------------------------------------------------------
    def on_fill(self, fill: Fill) -> None:
        self._nr_trades += 1
        cost: float = fill.price * fill.qty
        fee_cost: float = fill.fee
        if fill.side == "SELL":
            self._realized_pnl += cost - fee_cost
        else:
            self._realized_pnl -= cost + fee_cost

    # ------------------------------------------------------------------
    def validate_config(self) -> List[str]:
        errs: List[str] = []
        if float(self.config.get("capital", 0.0)) <= 0.0:
            errs.append("capital deve essere > 0")
        if float(self.config.get("base_spacing", 0.0)) <= 0.0:
            errs.append("base_spacing deve essere > 0")
        if int(self.config.get("levels", 0)) <= 0:
            errs.append("levels deve essere > 0")
        if float(self.config.get("vol_decay", 0.0)) < 0.0:
            errs.append("vol_decay non puo' essere negativo")
        return errs

    # ------------------------------------------------------------------
    def estimate_memory_mb(self) -> float:
        # deque maxlen atr_period di float (~24B each) + overhead trascurabile
        return round((self.atr_period * 24.0) / (1024.0 * 1024.0), 6)


if __name__ == "__main__":
    cfg: Dict[str, Any] = {
        "symbol": "SOL/EUR", "capital": 13.5, "base_spacing": 0.015,
        "levels": 4, "vol_decay": 0.7, "atr_period": 14, "ref_atr": 0.02,
        "dd_collar": -0.03, "numeraire_vol": 0.5, "max_qty": 0.5,
    }
    grid = VolScaledBreakoutGrid(cfg)
    print("config errors:", grid.validate_config())
    # simulazione piccola: onde di volatilità variabile
    synthetic: List[float] = [100.0 + 0.2 * math.sin(i / 3.0)
                              + (0.05 if i % 25 < 12 else 0.45)
                              for i in range(120)]
    acc: List[Dict[str, Any]] = []
    for i, px in enumerate(synthetic):
        acts = grid.on_tick(Tick(timestamp=float(i), symbol="SOL/EUR", mid=px))
        if i == 40:
            grid.on_fill(Fill(timestamp=float(i), symbol="SOL/EUR",
                              side="SELL", price=px, qty=0.5))
        acc.extend(acts)
    del synthetic
    gc.collect()
    print("azioni emesse:", len(acc))
    print("snapshot:", json.dumps({
        "ewma_vol": round(grid._ewma_vol, 6),
        "spacing": round(grid._effective_spacing(), 6),
        "collared": grid._collared,
        "realized_pnl": round(grid._realized_pnl, 6),
        "trades": grid._nr_trades,
        "mem_mb": grid.estimate_memory_mb(),
    }))
    print("ok")
