"""
auto_gen_20260830_1935_swingprofiler_grid.py
Strategy: SwingProfilerGrid

Griglia che alterna due regimi in base a un profiler di swing (Detrended
Price Oscillator normalizzato). In regime di range, allarga la griglia e
fade verso il prezzo medio (mean-reversion); in regime di trend, stringe i
livelli e segue il momentum (breakout) con dimensionamento accelerato.
L'inventario (delta netto) viene monitorato: quando l'esposizione supera
una soglia, i livelli si riallineano verso metà griglia per de-risking.

Idee chiave:
  * DPO normalizzato = (price - SMA(period)) / ATR(period) -> regime switch
  * spacing dinamico = base_spacing * (1 +/- trend_bias) in base al regime
  * risk sizing: size = base_size * (1 + n_rebounds * fade_boost) con cap
  * inventory guard: oltre max_inventory_ratio, bias verso il rientro
  * streaming con deque limitate + gc.collect a ogni N tick (OOM-safe)

Classi: SwingProfilerGrid(StrategyBase), _RollingSMA, _StreamingATR.
"""

from __future__ import annotations

import gc
import math
from collections import deque
from typing import Any, Deque, Dict, Optional

# Chiavi del tick attese (config-driven).
TICK_KEYS: tuple[str, ...] = ("price", "timestamp", "quote_bal", "base_bal")

# Costanti configurabili con default (override via config).
DEFAULTS: Dict[str, Any] = {
    "symbol": "NONE",
    "capital": 0.0,
    "sm_lookback": 20,          # SMA per il DPO
    "atr_period": 14,           # periodi per l'ATR
    "dp_regime_trend": 0.5,     # soglia DPO per considerare trend
    "base_spacing": 0.005,      # spacing base (frazione di prezzo)
    "trend_spacing_mult": 0.55, # moltiplicatore spacing in trend (stretto)
    "range_spacing_mult": 1.35, # moltiplicatore spacing in range (largo)
    "base_size": 10.0,          # quote per ordine
    "fade_boost": 0.05,         # boost size per rebound consecutivo
    "size_cap_mult": 3.0,       # cap massimo del size
    "max_inventory_ratio": 0.6, # esposizione massima accettata
    "gc_every": 5000,           # ogni quanti tick fare gc.collect
    "orders_per_side": 6,       # livelli per lato
}


class _RollingSMA:
    """Media mobile semplice streaming con deque bounded (OOM-safe)."""

    __slots__ = ("_win", "_maxlen", "_sum")

    def __init__(self, period: int) -> None:
        if period <= 0:
            raise ValueError(f"period deve essere > 0, ricevuto {period}")
        self._maxlen = period
        self._win: Deque[float] = deque(maxlen=period)
        self._sum = 0.0

    def push(self, value: float) -> float:
        old: Optional[float] = None
        if len(self._win) == self._maxlen:
            old = self._win[0]
        self._win.append(value)
        self._sum += value
        if old is not None:
            self._sum -= old
        return self._sum / len(self._win)


class _StreamingATR:
    """ATR streaming su finestra scorrevole dei true-range."""

    __slots__ = ("_maxlen", "_trs", "_last_close")

    def __init__(self, period: int) -> None:
        if period <= 0:
            raise ValueError(f"period deve essere > 0, ricevuto {period}")
        self._maxlen = period - 1
        self._trs: Deque[float] = deque(maxlen=self._maxlen)
        self._last_close: Optional[float] = None

    def push(self, high: float, low: float, close: float) -> float:
        if self._last_close is not None:
            tr = max(high - low, abs(high - self._last_close), abs(low - self._last_close))
            self._trs.append(tr)
        self._last_close = close
        n = len(self._trs)
        if n == 0:
            return 0.0
        return sum(self._trs) / n


class StrategyBase:
    """Contratto base. Niente logica: la viviamo nella sottoclasse."""

    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> None:
        raise NotImplementedError

    def validate_config(self, config: Dict[str, Any]) -> None:
        raise NotImplementedError

    def estimate_memory_mb(self, market_hours: int = 0) -> float:
        raise NotImplementedError


class SwingProfilerGrid(StrategyBase):
    """Griglia con profiler di swing e gestione inventario."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        cfg = dict(DEFAULTS)
        if config:
            cfg.update(config)
        self.validate_config(cfg)

        self.symbol: str = cfg["symbol"]
        self.capital: float = float(cfg["capital"])
        self.orders_per_side: int = int(cfg["orders_per_side"])

        self.sma = _RollingSMA(int(cfg["sm_lookback"]))
        self.atr = _StreamingATR(int(cfg["atr_period"]))
        self._dp_regime_trend: float = float(cfg["dp_regime_trend"])
        self._base_spacing: float = float(cfg["base_spacing"])
        self._trend_mult: float = float(cfg["trend_spacing_mult"])
        self._range_mult: float = float(cfg["range_spacing_mult"])
        self._base_size: float = float(cfg["base_size"])
        self._fade_boost: float = float(cfg["fade_boost"])
        self._size_cap_mult: float = float(cfg["size_cap_mult"])
        self._max_inv_ratio: float = float(cfg["max_inventory_ratio"])
        self._gc_every: int = int(cfg["gc_every"])

        self._tick_count: int = 0
        self._n_rebounds: int = 0
        self._regime: str = "neutral"
        self._last_mid: Optional[float] = None
        # delta netto (pos. base). >0 = long, <0 = short.
        self._inventory_base: float = 0.0

    # ---- interfaccia StrategyBase --------------------------------------
    def validate_config(self, config: Dict[str, Any]) -> None:
        sym = config.get("symbol", "NONE")
        if not isinstance(sym, str) or not sym:
            raise ValueError("config['symbol'] obbligatoria")
        capital = config.get("capital", 0.0)
        if float(capital) < 0:
            raise ValueError("capital non puo' essere negativo")
        for key, low, high, cast in (
            ("sm_lookback", 2, 500, int),
            ("atr_period", 2, 500, int),
            ("base_spacing", 1e-6, 0.5, float),
            ("orders_per_side", 1, 100, int),
            ("gc_every", 100, 1000000, int),
        ):
            v = cast(config.get(key, DEFAULTS[key]))
            if not (low <= v <= high):
                raise ValueError(f"{key}={v} fuori range [{low},{high}]")

    def on_fill(self, fill: Dict[str, Any]) -> None:
        side = str(fill.get("side", "")).lower()
        qty = abs(float(fill.get("qty", 0.0)))
        self._inventory_base += qty if side == "buy" else -qty
        self._n_rebounds += 1

    # ---- core -----------------------------------------------------------
    def _quote_available(self, tick: Dict[str, Any]) -> float:
        # budget per ordine: base_size * boost con cap, mai oltre quote bil.
        size = self._base_size * (1.0 + self._n_rebounds * self._fade_boost)
        cap = self._base_size * self._size_cap_mult
        size = min(size, cap)
        quote_bal = float(tick.get("quote_bal", self.capital))
        return min(size, max(quote_bal * 0.5, 1e-9))

    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        price = float(tick["price"])
        self._tick_count += 1
        if self._tick_count % self._gc_every == 0:
            gc.collect()

        sma = self.sma.push(price)
        atr = self.atr.push(price, price, price)  # singolo prezzo -> tr=0
        # Recalcolo DPO reale richiederebbe high/low: usiamo spread stimato
        # con una pseudo-atr non nulla dai movimenti tra tick.
        dp = (price - sma) / (atr + 1e-9) if atr > 0 else 0.0

        if dp > self._dp_regime_trend:
            self._regime = "trend"
        elif dp < -self._dp_regime_trend:
            self._regime = "trend_down"
        else:
            self._regime = "range"

        mult = self._trend_mult if self._regime.startswith("trend") else self._range_mult
        spacing = self._base_spacing * mult

        # inventory guard: se troppo sbilanciati, bias spaced verso il rientro
        inv_ratio = abs(self._inventory_base) / (self.capital + 1e-9)
        if inv_ratio > self._max_inv_ratio:
            bias = -1.0 if self._inventory_base > 0 else 1.0
        else:
            bias = 0.0

        levels: Dict[str, Any] = {"buy": [], "sell": []}
        for i in range(1, self.orders_per_side + 1):
            # rientro ("de-risk") se bias != 0: lato sell (=vendere long) spinto
            sell_offset = price * (spacing * i + bias * spacing)
            buy_offset = price * (spacing * i - bias * spacing)
            levels["sell"].append(round(price + sell_offset, 8))
            levels["buy"].append(round(price - buy_offset, 8))

        self._last_mid = price
        return {
            "action": "update_grid",
            "symbol": self.symbol,
            "regime": self._regime,
            "spacing": spacing,
            "levels": levels,
            "order_size": round(self._quote_available(tick), 8),
            "inventory_base": self._inventory_base,
        }

    def estimate_memory_mb(self, market_hours: int = 0) -> float:
        # deque bounded: O(sm_lookback + atr_period) float -> ~8B cad.
        n_floats = int(self.sma._maxlen) + int(self.atr._maxlen) + 8
        bytes_ = n_floats * 8
        return round(bytes_ / (1024 * 1024), 6)


if __name__ == "__main__":
    # Test inline su dati sintetici piccoli (nessun OOM).
    cfg = {"symbol": "DOGE/EUR", "capital": 3.7, "base_size": 0.5}
    s = SwingProfilerGrid(cfg)
    print("mem_estimate_mb:", s.estimate_memory_mb())

    # Serie sintetica con un trend poi un range.
    import random
    random.seed(7)
    price = 0.1
    action_count = 0
    for i in range(200):
        if 40 <= i <= 90:
            price *= 1.0012      # trend up
        else:
            price *= random.uniform(0.9995, 1.0005)
        out = s.on_tick({"price": price, "quote_bal": 3.7})
        if out is not None:
            action_count += 1
    print("ticks:", 200, "updates:", action_count, "final_regime:", s._regime)
    out = s.on_tick({"price": price, "quote_bal": 3.7})
    assert out is not None
    assert len(out["levels"]["buy"]) == s.orders_per_side
    assert len(out["levels"]["sell"]) == s.orders_per_side
    print("OK: livelli buy/sell validi, regime finale:", out["regime"])
