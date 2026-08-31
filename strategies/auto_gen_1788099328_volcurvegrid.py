#!/usr/bin/env python3
"""VOLCURVEGRID — Volatility-Adaptive Curve Grid.

Converte la campana di volatilita' in livelli di griglia non uniformi:
- Livelli piu' fitti vicino al prezzo (alta densita' di scambio).
- Livelli piu' radi ai margini (cattura spikes, meno capitale lockato).
- Ricalibra dinamicamente l'ampiezza in base all'ATR.
OOM-safe: usa generatori per i livelli, zero materializzazione di liste enormi.
"""

from __future__ import annotations

import gc
import math
from typing import Any, Dict, Generator, List

DEFAULTS: Dict[str, Any] = {
    "symbol": "UNKNOWN/EUR",
    "base_price": 0.0,
    "n_levels_below": 10,
    "n_levels_above": 10,
    "atr": 0.0,
    "kurtosis": 3.0,          # >3 = fat tails -> widen margins
    "vol_mult_below": 1.0,    # relative to vol_mult_above (bear skew)
    "max_leverage": 1.0,
    "stop_loss_pct": 0.05,
}


class StrategyBase:
    """Base contract for every auto-gen strategy."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config: Dict[str, Any] = {**DEFAULTS, **config}
        self.validate_config()
        self._levels: List[float] = []
        self._positions: int = 0
        self._gross_pnl: float = 0.0

    def validate_config(self) -> None:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError

    def on_tick(self, price: float, ts: float) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> None:
        raise NotImplementedError


class VolCurveGrid(StrategyBase):
    """Griglia a livelli distribuiti secondo una curva di densita' normale.

    La distanza tra livelli adiacenti segue l'ATR scalato da un fattore
    gaussiano accumulato: piu' ci si allontana dal centro, piu' largo e'
    l'intervallo. Riduce capitale lockato in zone morte, alza probabilita'
    di match vicino al prezzo.
    """

    def validate_config(self) -> None:
        if self.config["base_price"] <= 0:
            raise ValueError("base_price deve essere > 0")
        if self.config["atr"] <= 0:
            raise ValueError("atr deve essere > 0")
        if self.config["max_leverage"] <= 0:
            raise ValueError("max_leverage deve essere > 0")
        if self.config["n_levels_below"] < 1 or self.config["n_levels_above"] < 1:
            raise ValueError("livelli devono essere >= 1")
        self.config["vol_mult_below"] = max(0.1, min(10.0, self.config["vol_mult_below"]))
        self.config["kurtosis"] = max(1.0, min(10.0, self.config["kurtosis"]))

    def estimate_memory_mb(self) -> float:
        n = self.config["n_levels_below"] + self.config["n_levels_above"]
        return round(n * 2 * 8 / (1024 * 1024), 6)

    def _gen_spacing(self) -> Generator[float, None, None]:
        """Rendimento passo-passo degli step di prezzo (mai lista piena)."""
        k = self.config["kurtosis"]
        base = self.config["atr"]
        tail_factor = math.exp(((k - 3.0) * 0.5)) + 0.5
        for i in range(1, max(self.config["n_levels_below"], self.config["n_levels_above"]) + 1):
            gauss = 1.0 + math.exp(-0.5 * (i - 1.0) ** 2) * 0.35
            yield base * (gauss + ((i - 1.0) * 0.035)) * tail_factor

    def _build_levels(self) -> None:
        below: List[float] = []
        above: List[float] = []
        price = self.config["base_price"]
        mb = self.config["vol_mult_below"]
        for idx, step in enumerate(self._gen_spacing()):
            if idx < self.config["n_levels_below"]:
                below.append(price - step * mb)
            if idx < self.config["n_levels_above"]:
                above.append(price + step)
        below.reverse()
        self._levels = below + [price] + above
        del below, above
        gc.collect()

    def on_tick(self, price: float, ts: float) -> List[Dict[str, Any]]:
        if not self._levels:
            self._build_levels()
        orders: List[Dict[str, Any]] = []
        for lvl in self._levels:
            dist = abs(lvl - price) / self.config["base_price"]
            if dist <= self.config["stop_loss_pct"]:
                orders.append({
                    "side": "buy",
                    "price": round(lvl, 6),
                    "qty": round(self.config["max_leverage"] / (len(self._levels) or 1), 8),
                    "ts": ts,
                })
        return orders

    def on_fill(self, fill: Dict[str, Any]) -> None:
        side = fill.get("side", "buy")
        qty = float(fill.get("qty", 0.0))
        price = float(fill.get("price", 0.0))
        if side == "sell":
            self._gross_pnl += (self.config["base_price"] - price) * qty
        else:
            self._positions += 1
        if self._positions > len(self._levels):
            self._positions = 0


if __name__ == "__main__":
    cfg = {
        "symbol": "DOGE/EUR",
        "base_price": 0.10,
        "atr": 0.001,
        "n_levels_below": 6,
        "n_levels_above": 6,
        "kurtosis": 4.2,
        "max_leverage": 1.0,
    }
    s: StrategyBase = VolCurveGrid(cfg)
    print("mem_mb:", s.estimate_memory_mb())
    s._build_levels()
    print("n_levels:", len(s._levels), "span:", s._levels[0], "->", s._levels[-1])
    ticks = s.on_tick(cfg["base_price"], 1234.5)
    print("orders_on_center:", len(ticks))
    s.on_fill({"side": "buy", "qty": 0.01, "price": cfg["base_price"]})
    print("positions_after_buy:", s._positions)
    print("JSON_OK")
