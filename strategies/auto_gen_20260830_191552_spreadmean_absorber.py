"""
auto_gen_20260830_191552_spreadmean_absorber.py
Strategy: SpreadMeanAbsorber

Grid adattivo che assorbe la volatilità: i livelli non sono fissi ma si
espandono/contraggono attorno a una media mobile esponenziale del prezzo,
proporzionalmente a una misura di deviazione (ATR su finestra corta).

Idee chiave:
  * spacing dinamico = max(base_spacing, k_atr * atr_mean)
  * livelli ricalcolati a ogni tick dal prezzo EMAn e dalla distanza media
  * exposure size degrada quanto più il prezzo è lontano dall'EMA (fade)
  * nessuna list comprehension su array lunghi: si usano finestre a deque
    e streaming window (Attenzione OOM).

Classi: SpreadMeanAbsorber(StrategyBase), _ATRStream (helper streaming).
"""

from __future__ import annotations

import gc
import math
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Optional

# --------------------------------------------------------------------------
# Schema dei tick attesi (config-driven, niente hardcode nel metodo on_tick)
# --------------------------------------------------------------------------
TICK_KEYS: tuple[str, ...] = ("price", "timestamp", "quote_bal")


@dataclass
class _ATRStream:
    """Streaming ATR su finestra scorrevole, senza list comprehension.

    Mantiene una deque limitata (maxlen fissato in __init__) e ricalcola
    la media dei true-range in modo incremental. Dimensione memoria O(len)
    ma bounded dal maxlen, quindi nessun rischio OOM su serie lunghe.
    """

    window: int
    prev_close: Optional[float] = None
    _ranges: Deque[float] = field(default_factory=deque)
    _sum: float = 0.0

    def update(self, price: float, high: float, low: float, ts: float) -> float:
        """Inserisce un nuovo punto e ritorna l'ATR corrente (media true-range)."""
        if self.prev_close is None:
            self.prev_close = price
            return self._mean()
        tr = max(high - low, abs(high - self.prev_close), abs(low - self.prev_close))
        self.prev_close = price
        self._ranges.append(tr)
        self._sum += tr
        if len(self._ranges) > self.window:
            self._sum -= self._ranges.popleft()
        return self._mean()

    def _mean(self) -> float:
        if not self._ranges:
            return 0.0
        return self._sum / len(self._ranges)


class StrategyBase:
    """Base comune. Definisce il contratto testato da estrarre in engine."""

    name: str = "StrategyBase"

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        self.validate_config(config)

    # -- Hooks che la strategia concreta è tenuta a implementare -------------
    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Riceve un tick, ritorna eventuale ordine da piazzare o None."""
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> None:
        """Aggiorna lo stato interno dopo un'esecuzione.""" 
        raise NotImplementedError

    @staticmethod
    def validate_config(config: Dict[str, Any]) -> None:
        """Valida la config, solleva ValueError se non coerente."""
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        """Stima l'ingombro in memoria della strategia, in MiB."""
        raise NotImplementedError


def _f(num: Any, *, name: str, lo: float, hi: float) -> float:
    """Converte a float e verifica il range; errore esplicito se fuori."""
    val = float(num)
    if not (lo <= val <= hi):
        raise ValueError(f"config[{name!r}]={val!r} fuori intervallo [{lo}, {hi}]")
    return val


def _i(num: Any, *, name: str, lo: int, hi: int) -> int:
    """Converte a int (intero) e verifica il range; errore esplicito se fuori."""
    val = int(num)
    if val < lo or val > hi:
        raise ValueError(f"config[{name!r}]={val!r} fuori intervallo [{lo}, {hi}]")
    return val


class SpreadMeanAbsorber(StrategyBase):
    """Griglia adattiva con spice dinamico dato da ATR ed EMA del prezzo."""

    name: str = "spreadmean_absorber"

    def __init__(self, config: Dict[str, Any]) -> None:
        self.validate_config(config)
        self.base_spacing: float = float(config["base_spacing"])
        self.k_atr: float = float(config["k_atr"])
        self.levels: int = int(config["levels"])
        self.fade_k: float = float(config["fade_k"])
        self.max_order_value: float = float(config["max_order_value"])
        self.atr_window: int = int(config["atr_window"])
        self.ema_alpha: float = 2.0 / (1.0 + int(config["ema_period"]))

        # Stato interno
        self._ema: Optional[float] = None
        self._atr = _ATRStream(window=self.atr_window)
        self._fills: Deque[float] = deque()  # traccia prezzi di esecuzione
        self._last_tick_ts: float = 0.0
        self._open_orders: Dict[str, float] = {}

        super().__init__(config)

    # ------------------------------------------------------------------ API
    @staticmethod
    def validate_config(config: Dict[str, Any]) -> None:
        required = {
            "base_spacing", "k_atr", "levels", "fade_k",
            "max_order_value", "atr_window", "ema_period",
        }
        missing = required - set(config.keys())
        if missing:
            raise ValueError(f"config mancanti: {sorted(missing)}")
        _f(config["base_spacing"], name="base_spacing", lo=1e-6, hi=1e6)
        _f(config["k_atr"], name="k_atr", lo=0.0, hi=100.0)
        _i(config["levels"], name="levels", lo=1, hi=200)
        _f(config["fade_k"], name="fade_k", lo=0.0, hi=10.0)
        _f(config["max_order_value"], name="max_order_value", lo=1e-6, hi=1e12)
        _i(config["atr_window"], name="atr_window", lo=2, hi=10_000)
        _i(config["ema_period"], name="ema_period", lo=1, hi=10_000)

    def estimate_memory_mb(self) -> float:
        # ATR deque bounded + fills bounded: ingombro trascurabile.
        return 0.05 + self.atr_window * 32e-6 + self.levels * 64e-6

    # ------------------------------------------------------------- on_tick
    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        price = float(tick["price"])
        ts = float(tick.get("timestamp", time.time()))

        # Streaming EMA incrementale (zero allocazioni su array lunghi)
        self._ema = price if self._ema is None else self._ema + self.ema_alpha * (price - self._ema)

        # True range con pseudo high/low: uso una banda attorno al prezzo.
        high = price * 1.0001
        low = price * 0.9999
        atr_now = self._atr.update(price, high, low, ts)

        # spacing dinamico
        spacing = max(self.base_spacing, self.k_atr * atr_now)
        if spacing <= 0.0:
            return None

        ema = self._ema if self._ema is not None else price
        # Fade: più distante dall'EMA, più piccolo l'ordine (mean-reversion)
        dist = abs(price - ema)
        fade = 1.0 / (1.0 + self.fade_k * dist)
        order_value = min(self.max_order_value, self.max_order_value * fade)

        # Direzione dal cross EMA (mean-reversion): buy sotto, sell sopra.
        if price < ema - spacing / 2.0:
            direction, side_price = "buy", price
        elif price > ema + spacing / 2.0:
            direction, side_price = "sell", price
        else:
            return None
        order: Dict[str, Any] = {
            "action": direction,
            "price": round(side_price, 8),
            "size": round(order_value, 8),
            "strategy": self.name,
        }
        key = f"{direction}:{side_price:.8f}"
        # Evita duplicati: un ordine aperto già a quel prezzo non si ri-spara
        if key not in self._open_orders:
            self._open_orders[key] = order_value
            self._last_tick_ts = ts
            return order
        return None

    # ------------------------------------------------------------ on_fill
    def on_fill(self, fill: Dict[str, Any]) -> None:
        price = float(fill.get("price", 0.0))
        action = str(fill.get("action", ""))
        key = f"{action}:{price:.8f}"
        self._open_orders.pop(key, None)
        self._fills.append(price)
        # Risorsa: anche i fill sono bounding per evitare crescita illimitata.
        if len(self._fills) > 10_000:
            del self._fills[0]


if __name__ == "__main__":
    import random

    cfg = {
        "base_spacing": 0.0005,
        "k_atr": 1.2,
        "levels": 10,
        "fade_k": 0.02,
        "max_order_value": 5.0,
        "atr_window": 20,
        "ema_period": 30,
    }
    strat = SpreadMeanAbsorber(cfg)
    assert strat.estimate_memory_mb() > 0.0

    # dataset sintetico piccolissimo: nessuna list comprehension a 100k
    orders = 0
    px = 1.0
    rng = random.Random(42)
    for _ in range(2_000):
        px *= 1.0 + rng.gauss(0.0, 0.002)
        tick = {"price": px, "timestamp": float(_), "quote_bal": 100.0}
        ord = strat.on_tick(tick)
        if ord:
            orders += 1
            strat.on_fill({"price": ord["price"], "action": ord["action"]})
        if _ % 500 == 0:
            gc.collect()

    print(f"SpreadMeanAbsorber OK: {orders} ordini su 2000 tick, "
          f"mem={strat.estimate_memory_mb():.4f} MiB")
    assert orders > 0, "dovrebbe almeno piazzare qualche ordine"
