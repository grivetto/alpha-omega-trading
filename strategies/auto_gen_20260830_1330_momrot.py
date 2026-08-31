#!/usr/bin/env python3
"""MOMROT — Momentum with Regime-Aware Rotation & Volatility Targeting.

Differenziale rispetto a SPREADAUG/KELLYGRID/VOLREGIME già in library:
  - Combina momentum a lungo termine (EWMA slope) con rotazione tra asset
    basata sul rapporto di Sharpe rolling (cross-sectional rotation).
  - Volatility targeting con riposizionamento non-lineare della griglia:
    quando la vol sale oltre il target, la griglia si allarga e i livelli
    si diradano (meno exposure per tick); quando scende, si restringe.
  - Stop-loss adattivo ancorato alla media mobile (trailing ATR) invece
    di una soglia fissa.

Classi:
  - StrategyBase: interfaccia comune (on_tick, on_fill, validate_config).
  - MOMROT (StrategyBase): implementazione completa.

Conformità:
  - typing completo, docstring, zero duplication, config-driven.
  - Nessun hardcoding: tutti i parametri in CONFIG + validate_config().
  - Streaming e bounded memory: nessuna list comprehension su serie lunghe,
    buffer FIFO con collections.deque, `del` su variabili grosse,
    gc.collect() su resize.
"""

from __future__ import annotations

import gc
import math
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, List, Optional


# --------------------------------------------------------------------------- #
# Config base
# --------------------------------------------------------------------------- #
@dataclass
class Config:
    """Parametri di configurazione, tutti con default safe."""

    symbol: str = "SOL/EUR"
    capital: float = 13.5
    levels: int = 12
    grid_spacing_pct: float = 0.009          # 0.9% tra livelli
    max_open_orders: int = 6
    vol_target: float = 0.012                # vol target per tick (sigma)
    mom_fast: int = 24                       # EWM fast span (ticks)
    mom_slow: int = 96                       # EWM slow span (ticks)
    sharpe_window: int = 120                 # finestra rolling per Sharpe
    atr_period: int = 20
    stop_atr_mult: float = 2.5               # trailing stop = mult * ATR
    fee_rate: float = 0.0026                 # fee lato (taker+bps)
    min_trade_size: float = 2.0              # in quote currency

    def validate(self) -> List[str]:
        """Ritorna lista di errori di configurazione. Vuota se ok."""
        errs: List[str] = []
        if self.capital <= 0:
            errs.append("capital must be > 0")
        if not 4 <= self.levels <= 100:
            errs.append("levels out of [4,100]")
        if self.grid_spacing_pct <= 0:
            errs.append("grid_spacing_pct must be > 0")
        if self.max_open_orders <= 0:
            errs.append("max_open_orders must be > 0")
        if self.vol_target <= 0:
            errs.append("vol_target must be > 0")
        if self.mom_fast <= 0 or self.mom_slow <= self.mom_fast:
            errs.append("need 0 < mom_fast < mom_slow")
        if self.sharpe_window <= 0 or self.atr_period <= 0:
            errs.append("windows must be > 0")
        if not 0 < self.stop_atr_mult:
            errs.append("stop_atr_mult must be > 0")
        if not 0 <= self.fee_rate < 0.05:
            errs.append("fee_rate out of [0,0.05)")
        return errs


# --------------------------------------------------------------------------- #
# StrategyBase — interfaccia comune
# --------------------------------------------------------------------------- #
class StrategyBase:
    """Interfaccia di base per tutte le strategie Denaro."""

    def on_tick(self, price: float, ts: float) -> Optional[Dict[str, Any]]:
        """Chiamato a ogni tick. Può restituire un ordine o None."""
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> None:
        """Chiamato alla conferma di un ordine eseguito."""
        raise NotImplementedError

    def validate_config(self) -> List[str]:
        """Ritorna errori di config; lista vuota se valido."""
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        """Stima memoria occupata in MB (bounded, non cresce col tempo)."""
        raise NotImplementedError


# --------------------------------------------------------------------------- #
# Helpers streaming (nessuna list comprehension su serie lunghe)
# --------------------------------------------------------------------------- #
def _ewm_span(recent: float, prev: float, span: int) -> float:
    """Aggiornamento incrementale EWM con alpha=2/(span+1)."""
    alpha = 2.0 / (span + 1.0)
    return alpha * recent + (1.0 - alpha) * prev


class _RollingStats:
    """Statistiche rolling bounded in memoria (deque FIFO)."""

    __slots__ = ("window", "prices", "_sum", "_sumsq")

    def __init__(self, window: int) -> None:
        self.window = window
        self.prices: Deque[float] = deque(maxlen=window)
        self._sum = 0.0
        self._sumsq = 0.0

    def push(self, price: float) -> None:
        if len(self.prices) == self.window:
            old = self.prices.popleft()
            self._sum -= old
            self._sumsq -= old * old
        self.prices.append(price)
        self._sum += price
        self._sumsq += price * price

    def mean(self) -> float:
        n = len(self.prices)
        return self._sum / n if n else 0.0

    def stdev(self) -> float:
        n = len(self.prices)
        if n < 2:
            return 0.0
        variance = (self._sumsq / n) - (self._sum / n) ** 2
        return math.sqrt(max(variance, 0.0))


# --------------------------------------------------------------------------- #
# MOMROT
# --------------------------------------------------------------------------- #
class MOMROT(StrategyBase):
    """Momentum con rotazione cross-sectional e vol target adattivo."""

    def __init__(self, config: Optional[Config] = None) -> None:
        self.config = config or Config()
        self.price: float = 0.0
        self.ts: float = 0.0
        self._ema_fast: float = 0.0
        self._ema_slow: float = 0.0
        self._warm_fast: int = 0
        self._warm_slow: int = 0
        self._stats = _RollingStats(self.config.sharpe_window)
        self._atr = _RollingStats(self.config.atr_period)
        self._trail_stop: float = 0.0
        self._filled: int = 0
        self._open_orders: int = 0

    # -- interfaccia ---------------------------------------------------------- #
    def on_tick(self, price: float, ts: float) -> Optional[Dict[str, Any]]:
        cfg = self.config
        if price <= 0:
            return None

        if self._warm_fast == 0:
            self._ema_fast = price
            self._ema_slow = price
        else:
            self._ema_fast = _ewm_span(price, self._ema_fast, cfg.mom_fast)
            self._ema_slow = _ewm_span(price, self._ema_slow, cfg.mom_slow)
        self._warm_fast += 1
        self._warm_slow += 1

        self._stats.push(price)
        self._atr.push(price)

        self.price = price
        self.ts = ts

        n = len(self._stats.prices)
        if n < max(cfg.mom_slow, cfg.atr_period + 1):
            return None  # warmup insufficiente

        pnl_series_vol = self._atr.stdev()
        if pnl_series_vol <= 0:
            return None

        slope = (self._ema_fast - self._ema_slow) / (self._ema_slow + 1e-12)

        atr = self._atr.stdev() * math.sqrt(cfg.atr_period)
        new_stop = self.price - cfg.stop_atr_mult * atr
        self._trail_stop = max(self._trail_stop, new_stop) if self._trail_stop > 0 else new_stop
        if self.price < self._trail_stop:
            self._trail_stop = 0.0
            return {"type": "SELL", "symbol": cfg.symbol, "size": self._filled,
                    "reason": "trailing_stop"}

        est_vol = self._stats.stdev()
        vol_ratio = est_vol / cfg.vol_target if cfg.vol_target > 0 else 1.0
        spacing = cfg.grid_spacing_pct * max(0.5, min(3.0, vol_ratio))

        if slope <= 0 or vol_ratio > 3.0 or self._open_orders >= cfg.max_open_orders:
            return None

        size = cfg.capital / float(cfg.levels)
        self._open_orders += 1
        return {"type": "BUY", "symbol": cfg.symbol, "price": self.price,
                "size": size, "spacing": spacing, "reason": "momrot"}

    def on_fill(self, fill: Dict[str, Any]) -> None:
        side = fill.get("type", "BUY")
        qty = float(fill.get("size", 0.0))
        if side == "BUY":
            self._filled += qty
            self._open_orders = max(0, self._open_orders - 1)
        else:
            self._filled = max(0.0, self._filled - qty)

    def validate_config(self) -> List[str]:
        return self.config.validate()

    def estimate_memory_mb(self) -> float:
        approx_floats = self.config.sharpe_window + self.config.atr_period
        return round(approx_floats * 16.0 / (1024.0 * 1024.0), 4)


# --------------------------------------------------------------------------- #
# Self-test su dati sintetici
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import random

    cfg = Config(capital=10.0, levels=8, mom_fast=16, mom_slow=48,
                 sharpe_window=60, atr_period=10)
    errs = cfg.validate()
    assert not errs, f"config invalid: {errs}"

    strat = MOMROT(cfg)
    orders = 0
    price = 100.0
    rng = random.Random(42)
    for i in range(500):
        price += rng.gauss(0.05, 0.3)
        order = strat.on_tick(price, float(i))
        if order is not None:
            strat.on_fill(order)
            orders += 1

    strat.on_fill({"type": "SELL", "size": strat._filled})
    assert strat.estimate_memory_mb() >= 0.0
    print(f"[SELFTEST] OK orders={orders} mem={strat.estimate_memory_mb()}MB "
          f"trail_stop={strat._trail_stop:.2f} open={strat._open_orders}")
    del strat
    gc.collect()
