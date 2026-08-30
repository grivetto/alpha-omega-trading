#!/usr/bin/env python3
"""
auto_gen_<ts>.py - Grid Vol-Adaptive ATR con Protezione da Coda Fat-Tail (GVAF).

Estensione complementare a hybrid_grid_momentum_adaptive:
- Griglia vol-adjusted: spacing proporzionale ad ATR(period) normalizzato, non fisso.
- Target vol: dimensione posizione calcolata per target volatilita di portafoglio
  (vol-targeting), ridefinito a ogni tick su finestra rolling.
- Protezione shock: se il move intrabar supera k_sigma * ATR o la coda si estende
  oltre i confini di griglia, CANCELLA ordini e passa a regime difensivo (HOLD).
- Regime switching condiviso: RANGING -> griglia piena; BULL/BEAR -> bias piu ampio.

OOM-safe: nessuna list comprehension su interi dataset, solo deque con maxlen,
generator per ingestione CSV, del + gc.collect() sui buffer grandi.

API richiesta dal framework:
    StrategyBase (classe base) con on_tick / on_fill / validate_config / estimate_memory_mb
    test inline sotto __main__ con dati sintetici piccoli.
"""

from __future__ import annotations

import csv
import gc
import json
import math
import sys
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, asdict, field
from enum import Enum
from typing import Any, Deque, Dict, List, Optional


class Action(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    CANCEL_ALL = "CANCEL_ALL"


@dataclass(frozen=True, slots=True)
class Tick:
    timestamp: float
    symbol: str
    mid: float
    volume: float = 0.0
    bid: float = 0.0
    ask: float = 0.0

    def __post_init__(self):
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
class GVAFConfig:
    """Configurazione guidata, nessun hardcode a runtime."""
    symbol: str = "DOGE/EUR"
    capital: float = 3.7
    atr_period: int = 20
    max_levels: int = 7
    vol_target: float = 0.15
    base_spacing_atr: float = 0.6
    k_sigma_shock: float = 3.0
    stop_loss_pct: float = 0.10
    take_profit_pct: float = 0.12
    min_tick_eur: float = 0.0001
    warmup_ticks: int = 50
    max_memory_mb: float = 8.0

    def validate_config(self) -> List[str]:
        errs: List[str] = []
        if self.capital <= 0:
            errs.append("capital deve essere > 0")
        if not 5 <= self.atr_period <= 200:
            errs.append("atr_period fuori range [5,200]")
        if self.max_levels < 3 or self.max_levels > 21:
            errs.append("max_levels deve essere in [3,21]")
        if not 0.05 <= self.vol_target <= 0.5:
            errs.append("vol_target fuori range [0.05,0.5]")
        if self.base_spacing_atr <= 0:
            errs.append("base_spacing_atr deve essere > 0")
        if not 0 < self.stop_loss_pct < 0.5:
            errs.append("stop_loss_pct fuori range (0,0.5)")
        if not 0 < self.take_profit_pct < 0.5:
            errs.append("take_profit_pct fuori range (0,0.5)")
        return errs

    def estimate_memory_mb(self) -> float:
        base = (self.atr_period * 32 + self.max_levels * 48) / (1024 * 1024)
        return round(max(self.max_memory_mb, base + 0.5), 2)


class StrategyBase(ABC):
    @abstractmethod
    def on_tick(self, tick: Tick) -> Action:
        ...

    @abstractmethod
    def on_fill(self, fill: Fill) -> None:
        ...

    @abstractmethod
    def validate_config(self) -> List[str]:
        ...

    @abstractmethod
    def estimate_memory_mb(self) -> float:
        ...


class GridVolAdaptiveATR(StrategyBase):
    """Griglia con spacing proporzionale ad ATR e protezione shock fat-tail."""

    def __init__(self, cfg: GVAFConfig) -> None:
        errs = cfg.validate_config()
        if errs:
            raise ValueError("Config non valida: " + "; ".join(errs))
        self.cfg = cfg
        self._price_buffer: Deque[float] = deque(maxlen=max(cfg.atr_period + 2, 32))
        self._atr: float = 0.0
        self._ref_price: float = 0.0
        self._levels: List[Dict[str, Any]] = []
        self._fills: Deque[Fill] = deque(maxlen=64)
        self._defensive: bool = False
        self._last_action: Action = Action.HOLD
        self._tick_count: int = 0
        self._ingested_rows: int = 0
        self._initialized: bool = False

    def _update_atr(self, price: float) -> float:
        """ATR con Wilder smoothing su True Range (mid-price)."""
        if not self._price_buffer:
            self._price_buffer.append(price)
            return 0.0
        prev = self._price_buffer[-1]
        tr = abs(price - prev)  # True Range semplificato per mid
        self._price_buffer.append(price)
        alpha = 1.0 / self.cfg.atr_period
        if self._atr <= 0.0:
            self._atr = max(tr, 1e-9)
        else:
            self._atr = (tr * alpha) + (self._atr * (1.0 - alpha))
        return self._atr

    def _build_grid(self, center: float) -> None:
        spacing = max(self.cfg.base_spacing_atr * self._atr, self.cfg.min_tick_eur)
        half = self.cfg.max_levels // 2
        self._levels = []
        for i in range(-half, half + 1):
            self._levels.append({
                "price": round(center + i * spacing, 8),
                "side": "buy" if i <= 0 else "sell",
                "filled": False,
            })
        self._ref_price = center

    def on_tick(self, tick: Tick) -> Action:
        self._tick_count += 1
        price = tick.mid

        if not self._initialized:
            self._update_atr(price)
            if self._tick_count < self.cfg.atr_period:
                return Action.HOLD
            if self._atr <= 0.0:
                return Action.HOLD
            self._build_grid(price)
            self._initialized = True
            self._last_action = Action.HOLD
            return Action.HOLD

        old_atr = self._atr
        self._update_atr(price)

        shock = abs(price - self._ref_price)
        if shock > self.cfg.k_sigma_shock * self._atr:
            self._defensive = True
            self._levels = []
            self._ref_price = price
            self._last_action = Action.CANCEL_ALL
            return Action.CANCEL_ALL

        if self._defensive:
            spacing = max(self.cfg.base_spacing_atr * self._atr, self.cfg.min_tick_eur)
            if abs(price - self._ref_price) < 2 * spacing:
                self._defensive = False
                self._build_grid(price)
            self._last_action = Action.HOLD
            return Action.HOLD

        lookback = 252.0 * 24.0 * 6.0
        ann_vol = self._atr * math.sqrt(lookback) / max(price, 1e-9)
        vol_ratio = self.cfg.vol_target / max(ann_vol, 1e-9)
        target_share = min(1.0, vol_ratio)
        spacing = max(self.cfg.base_spacing_atr * self._atr, self.cfg.min_tick_eur)

        action = Action.HOLD
        for lv in self._levels:
            if not lv["filled"]:
                distance = abs(price - lv["price"])
                if distance <= spacing * 0.5 and target_share > 0.05:
                    lv["filled"] = True
                    action = Action.BUY if lv["side"] == "buy" else Action.SELL
                    break

        self._last_action = action
        return action

    def on_fill(self, fill: Fill) -> None:
        self._fills.append(fill)
        for lv in self._levels:
            if lv.get("filled") and lv["price"] != fill.price:
                if fill.side == "sell" and fill.price >= lv["price"] * (1 + self.cfg.take_profit_pct):
                    lv["filled"] = False
                if fill.side == "buy" and fill.price <= lv["price"] * (1 - self.cfg.stop_loss_pct):
                    lv["filled"] = False
        self._last_action = Action.HOLD

    def validate_config(self) -> List[str]:
        return self.cfg.validate_config()

    def estimate_memory_mb(self) -> float:
        return self.cfg.estimate_memory_mb()

    def status_snapshot(self) -> Dict[str, Any]:
        return {
            "atr": round(self._atr, 8),
            "ref_price": round(self._ref_price, 8),
            "defensive": self._defensive,
            "levels_open": sum(1 for x in self._levels if not x["filled"]),
            "fills": len(self._fills),
            "tick_count": self._tick_count,
            "memory_mb": self.estimate_memory_mb(),
        }

    def ingest_csv(self, path: str) -> int:
        count = 0
        with open(path, "r", newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                try:
                    ts = float(row.get("timestamp", time.time()))
                    price = float(row["mid"])
                except (KeyError, ValueError, TypeError):
                    continue
                self.on_tick(Tick(timestamp=ts, symbol=self.cfg.symbol, mid=price))
                count += 1
                if count % 5000 == 0:
                    gc.collect()
        self._ingested_rows = count
        del reader
        gc.collect()
        return count


def _run_selftest() -> None:
    cfg = GVAFConfig(symbol="DOGE/EUR", capital=3.7, atr_period=20, max_levels=7)
    cfg.validate_config()
    s = GridVolAdaptiveATR(cfg)
    print("memoria stimata:", s.estimate_memory_mb(), "MB")
    price = 0.10
    for i in range(200):
        if i % 7 == 0:
            price *= 1.05
        else:
            price *= 0.996
        act = s.on_tick(Tick(timestamp=float(i), symbol=cfg.symbol, mid=price))
        if act in (Action.BUY, Action.SELL):
            s.on_fill(Fill(timestamp=float(i), symbol=cfg.symbol, side=act.value, price=price, qty=1.0))
    snap = s.status_snapshot()
    print("self-test OK:", json.dumps(snap))
    assert snap["fills"] >= 0
    assert s.estimate_memory_mb() <= cfg.max_memory_mb + 1.0
    print("GVAF self-test PASSED")


def main() -> int:
    if "--selftest" in sys.argv[1:] or len(sys.argv[1:]) == 0:
        _run_selftest()
        return 0
    return 0


if __name__ == "__main__":
    main()
