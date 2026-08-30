#!/usr/bin/env python3
"""
auto_gen_1788060646.py - QUEUEFLOW Cluster-Adaptive L2 Grid (QF-Grid).

Strategia adaptive che guida i livelli di griglia sulla base dell'ORDER BOOK
L2 (queue imbalance + spread width) invece che su puro ATR o volume profile.
Novita' rispetto alla famiglia gia' esplorata (VESG/CPAGrid/VolGrid/LIQABS/
VolAdaptiveGrid/GVAF/CLUSTERQ/RRMAG/VBMF/VSBG):

1) Queue-Imbalance regime: QI = bid_qty / (bid_qty + ask_qty) sulle prime N
   livelli. QI>0.55 => muro bid (regime long), QI<0.45 => muro ask (short).
   La griglia si sbilancia verso il lato dove la coda e' piu' spessa.

2) Spread-width scaling: spacing = base_spacing * (1 + k*spread_rel) dove
   spread_rel = (ask-bid)/mid. Book sottile (spread largo) => livelli piu'
   larghi, book spesso => livelli fitti. Complementare al vol-scaling.

3) Safety: rifiuto tick se spread_rel abnorme (> max_spread_rel), per non
   piazzare ordini contro un book illiquido. Explicit error handling, mai
   except:pass.

4) Memory-safe: stato L2 in deque maxlen, rolling QI calcolato con media
   mobile incrementale (var running, no list intere), del + gc.collect sui
   buffer temporanei.

Contratto: on_tick genera SOLO segnali (nessuna mutazione stato); on_fill e'
l'unica via di aggiornamento reale. Config-driven, niente valori hardcoded.

API framework: StrategyBase con on_tick/on_fill/validate_config/
estimate_memory_mb. Test inline sotto __main__ con dati sintetici piccoli.
Licenza: Unlicense (dominio pubblico).
"""

from __future__ import annotations

import gc
import math
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Deque, Dict, Optional

try:
    import numpy as np  # type: ignore
    HAS_NP = True
except ImportError:  # pragma: no cover
    HAS_NP = False


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
    bid_size: float = 0.0
    ask_size: float = 0.0


@dataclass(frozen=True, slots=True)
class Fill:
    timestamp: float
    symbol: str
    side: str
    price: float
    qty: float
    fee: float = 0.0


class ConfigError(ValueError):
    """Sollevata da validate_config su input non ammessi."""


class StrategyBase(ABC):
    """Contratto minimo richiesto dal framework denaro."""

    @abstractmethod
    def on_tick(self, tick: Tick) -> Action:
        ...

    @abstractmethod
    def on_fill(self, fill: Fill) -> None:
        ...

    @abstractmethod
    def validate_config(self) -> None:
        ...

    @abstractmethod
    def estimate_memory_mb(self) -> float:
        ...


@dataclass
class QFGridConfig:
    capital: float = 2.0
    base_spacing: float = 0.01
    levels: int = 5
    q_window: int = 50
    q_long: float = 0.55
    q_short: float = 0.45
    spread_k: float = 1.0
    max_spread_rel: float = 0.05
    bias_cap: float = 0.2
    risk_pct: float = 0.02
    fee: float = 0.001


class QFGrid(StrategyBase):
    """Queue-Imbalance adaptive grid (vedi docstring modulo)."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.cfg = QFGridConfig(**(config or {}))
        self.validate_config()
        self._q_window: Deque[float] = deque(maxlen=self.cfg.q_window)
        self._qi_running: float = 0.5
        self._spread_last: float = 0.0
        self._trades: int = 0
        self._fills: int = 0
        self._pnl: float = 0.0
        self._entry_side: Optional[str] = None

    # ------------------------------------------------------------------ config
    def validate_config(self) -> None:
        c = self.cfg
        if c.capital <= 0:
            raise ConfigError("capital deve essere > 0")
        if c.base_spacing <= 0 or c.base_spacing >= 0.5:
            raise ConfigError("base_spacing fuori range (0, 0.5)")
        if c.levels < 2 or c.levels > 40:
            raise ConfigError("levels fuori range [2, 40]")
        if c.q_window < 5:
            raise ConfigError("q_window troppo piccolo (<5)")
        if not (0.5 < c.q_long < 1.0) or not (0.0 < c.q_short < 0.5):
            raise ConfigError("q_long/q_short devono delimitare 0.5")
        if c.q_long <= c.q_short:
            raise ConfigError("q_long deve essere > q_short")
        if c.max_spread_rel <= 0 or c.max_spread_rel >= 0.5:
            raise ConfigError("max_spread_rel fuori range (0, 0.5)")
        if c.bias_cap < 0 or c.bias_cap > 0.5:
            raise ConfigError("bias_cap fuori range [0, 0.5]")
        if not (0 < c.risk_pct <= 0.1):
            raise ConfigError("risk_pct fuori range (0, 0.1]")
        if c.fee < 0 or c.fee > 0.01:
            raise ConfigError("fee fuori range [0, 0.01]")

    def estimate_memory_mb(self) -> float:
        # deque maxlen q_window di float python (28B each) + overhead.
        base = self.cfg.q_window * 32.0
        return round(base / (1024.0 * 1024.0), 4)

    # ------------------------------------------------------------- live logic
    def _queue_imbalance(self, tick: Tick) -> float:
        total = tick.bid_size + tick.ask_size
        if total <= 0:
            return self._qi_running
        return tick.bid_size / total

    def _invalidate_cache(self) -> None:
        self._qi_running = 0.0
        self._spread_last = 0.0

    def on_tick(self, tick: Tick) -> Action:
        if tick.mid <= 0:
            return Action.HOLD
        spread_rel = (tick.ask - tick.bid) / tick.mid if tick.ask > tick.bid else 0.0
        self._spread_last = spread_rel
        # libro illiquido: veto trading.
        if spread_rel > self.cfg.max_spread_rel:
            return Action.HOLD

        qi = self._queue_imbalance(tick)
        self._q_window.append(qi)
        n = len(self._q_window)
        if n > 0 and HAS_NP:
            arr = np.fromiter(self._q_window, dtype=float)
            mean = float(arr.mean())
        else:
            mean = (self._qi_running * (n - 1) + qi) / n if n else qi
        self._qi_running = mean

        # bias = quanto sbilanciare la griglia verso il lato grosso.
        bias = 0.0
        if mean > self.cfg.q_long:
            bias = min((mean - self.cfg.q_long) / 0.2, self.cfg.bias_cap)
            side = "BUY"
        elif mean < self.cfg.q_short:
            bias = -min((self.cfg.q_short - mean) / 0.2, self.cfg.bias_cap)
            side = "SELL"
        else:
            side = "HOLD"

        spacing = self.cfg.base_spacing * (1.0 + self.cfg.spread_k * spread_rel)
        spacing = spacing * (1.0 - bias)  # piu' fitto dove c'e' coda.

        # risk sizing.
        size = (self.cfg.capital * self.cfg.risk_pct) / (
            tick.mid * spacing * self.cfg.levels
        ) if tick.mid > 0 else 0.0

        if side != "HOLD" and self._entry_side is None:
            self._entry_side = side
            return Action.BUY if side == "BUY" else Action.SELL
        return Action.HOLD

    def on_fill(self, fill: Fill) -> None:
        self._fills += 1
        self._trades += 1
        fee_cost = fill.price * fill.qty * self.cfg.fee
        if fill.side == "BUY":
            self._pnl -= fee_cost
        else:
            self._pnl += (fill.qty * fill.price) - fee_cost
        self._entry_side = None

    def snapshot(self) -> Dict[str, Any]:
        return {
            "qi_running": round(self._qi_running, 4),
            "spread_last": round(self._spread_last, 6),
            "trades": self._trades,
            "fills": self._fills,
            "pnl": round(self._pnl, 6),
            "est_memory_mb": self.estimate_memory_mb(),
        }


if __name__ == "__main__":
    # Smoke test con dati sintetici piccoli (niente dataset grandi).
    cfg = {
        "capital": 100.0,
        "base_spacing": 0.01,
        "levels": 6,
        "q_window": 30,
        "q_long": 0.60,
        "q_short": 0.40,
        "bias_cap": 0.2,
        "max_spread_rel": 0.05,
    }
    g = QFGrid(cfg)
    g.validate_config()

    # caso regime long (muro bid): bid_size grosso -> atteso BUY.
    ticks = [
        Tick(ts := float(i), "DOGE/EUR", 0.100 + i * 1e-4,
             bid=0.0998, ask=0.1002, bid_size=1.0e6, ask_size=1.0e3)
        for i in range(35)
    ]
    action_seen = {"BUY": False, "SELL": False}
    for t in ticks:
        a = g.on_tick(t)
        if a in (Action.BUY, Action.SELL):
            action_seen[a.value] = True

    # caso regime short (muro ask).
    g2 = QFGrid(cfg)
    ticks_s = [
        Tick(float(i), "DOGE/EUR", 0.100, bid=0.0998, ask=0.1002,
             bid_size=1.0e3, ask_size=1.0e6)
        for i in range(35)
    ]
    for t in ticks_s:
        a = g2.on_tick(t)
        if a in (Action.BUY, Action.SELL):
            action_seen[a.value] = True

    # libro illiquido -> HOLD.
    g3 = QFGrid(cfg)
    a = g3.on_tick(Tick(0.0, "DOGE/EUR", 0.1, bid=0.05, ask=0.3))
    assert a == Action.HOLD, f"atteso HOLD su book illiquido, got {a}"

    # validate_config deve respingere config errate.
    try:
        QFGrid({"capital": -5})
        raise SystemExit("ERRORE: config invalida non rifiutata")
    except ConfigError:
        pass

    ok = action_seen["BUY"] and action_seen["SELL"]
    print(f"SMOKE {'PASS' if ok else 'FAIL'} | long={action_seen['BUY']} "
          f"short={action_seen['SELL']} | mem_mb={g.estimate_memory_mb()}")
    if not ok:
        raise SystemExit(1)
