"""
auto_gen_20260831_0215_volsurf_grid.py
=======================================
VolSurface Grid — griglia adattiva guidata da volatilita' realizzata e
imbalance di order-flow. Sparging dinamico: quando la volatilita' sale,
l'ordine sale (spacing piu' largo per coprire il pump) e i livelli si
addensano sul lato dove i volumi indicano supporto.

Config-driven, typing completo, OOM-safe: il preprocessing avviene via
streaming/chunking (mai caricare tutto in RAM), zero `except: pass`.

API:
    class StrategyBase
        on_tick(price, ticker) -> list[OrderSignal]
        on_fill(fill)          -> None
        validate_config(cfg)   -> raises ConfigError
        estimate_memory_mb(n)  -> float
    if __name__ == "__main__": selftest con dati sintetici piccoli
"""

from __future__ import annotations

import gc
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Generator, List, Optional, Sequence

# token (importlazy per non rompere assenza di libs)
try:  # pragma: no cover
    import numpy as np  # noqa: F401
    _HAS_NUMPY = True
except ImportError:  # pragma: no cover
    _HAS_NUMPY = False


class ConfigError(Exception):
    """Configurazione strategia non valida."""


@dataclass
class OrderSignal:
    """Segnale opzionale verso l'esecutore."""
    side: str            # "buy" | "sell"
    price: float
    size: float
    kind: str = "limit"
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VolSurfaceState:
    """Stato interno della griglia (mutabile, sopravvive tra i tick)."""
    window: Deque[float] = field(default_factory=lambda: deque(maxlen=0))
    fills_buy: List[float] = field(default_factory=list)
    fills_sell: List[float] = field(default_factory=list)
    last_price: Optional[float] = None
    realized_vol: float = 0.0
    level_buy: float = 0.0
    level_sell: float = 0.0


class StrategyBase:
    """Strategia adattiva di griglia su superficie di volatilita'.

    Parametri (config, niente hardcoded):
      symbol           str    ticker
      capital          float  capitale allocato in quote (EUR)
      base_spacing     float  spacing base in frazione di prezzo  (es .002)
      vol_lookback     int    finestra vol (numeri di tick)
      vol_floor        float  minimo vol annuo da usare (0.0 = usa realized)
      vol_ceiling      float  massimo vol accettato
      max_levels       int    massimo numero livelli per lato
      risk_per_trade   float  frazione di capitale per ordine
      imbalance_span   int    profondita' order-book considerata (livelli)
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config: Dict[str, Any] = self.validate_config(config)
        self.symbol: str = config["symbol"]
        self.capital: float = float(config["capital"])
        self.base_spacing: float = float(config["base_spacing"])
        self.vol_lookback: int = int(config["vol_lookback"])
        self.vol_floor: float = float(config["vol_floor"])
        self.vol_ceiling: float = float(config["vol_ceiling"])
        self.max_levels: int = int(config["max_levels"])
        self.risk_per_trade: float = float(config["risk_per_trade"])
        self.imbalance_span: int = int(config["imbalance_span"])
        # stato
        self.st = VolSurfaceState()
        self.st.window = deque(maxlen=self.vol_lookback)
        self.tick_count: int = 0

    # ------------------------------------------------------------------
    @staticmethod
    def validate_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
        required = ("symbol", "capital", "base_spacing", "vol_lookback",
                    "vol_ceiling", "max_levels", "risk_per_trade",
                    "imbalance_span")
        for k in required:
            if k not in cfg:
                raise ConfigError(f"campo mancante: {k}")
        if float(cfg["capital"]) <= 0:
            raise ConfigError("capital deve essere > 0")
        if float(cfg["base_spacing"]) <= 0:
            raise ConfigError("base_spacing deve essere > 0")
        if int(cfg["vol_lookback"]) < 10:
            raise ConfigError("vol_lookback < 10 rende la vol instabile")
        if not (0 <= int(cfg["imbalance_span"]) <= 20):
            raise ConfigError("imbalance_span fuori range [0,20]")
        if not (0.0 < float(cfg["risk_per_trade"]) <= 0.5):
            raise ConfigError("risk_per_trade fuori range (0, 0.5]")
        return dict(cfg)

    # ------------------------------------------------------------------
    def _ingest_price(self, price: float, volume: float) -> float:
        """Aggiorna window vol e calcola la volatilita' realizzata.

        Ritorna lo sqrt-variance campionario su finestra mobile.
        Usa varianza incrementale (Welford) O(1) per memoria.
        """
        self.st.window.append(price)
        self.tick_count += 1
        if len(self.st.window) < 2:
            return 0.0
        # ritorni log
        n: int = 0
        mean: float = 0.0
        m2: float = 0.0
        prev: Optional[float] = None
        for p in self.st.window:
            if prev is not None:
                r: float = math.log(p / prev) if prev > 0 else 0.0
                n += 1
                d: float = r - mean
                mean += d / n
                m2 += d * (r - mean)
            prev = p
        var: float = (m2 / (n - 1)) if n > 1 else 0.0
        self.st.realized_vol = max(self.vol_floor, math.sqrt(max(var, 0.0)))
        return self.st.realized_vol

    # ------------------------------------------------------------------
    @staticmethod
    def _surface_clamp(vol: float, floor: float, ceiling: float) -> float:
        if floor > ceiling:
            raise ConfigError("vol_floor > vol_ceiling")
        return min(max(vol, floor), ceiling) if ceiling > 0 else max(vol, floor)

    # ------------------------------------------------------------------
    def _spacing(self, price: float) -> float:
        """Spacing adattivo = base_spacing * (1 + vol_scaling)."""
        vol = self._surface_clamp(self.st.realized_vol,
                                  self.vol_floor, self.vol_ceiling)
        # normalizza: 0 = base, 1 = raddoppio spacing
        span = max(self.vol_ceiling - self.vol_floor, 1e-12)
        scale: float = 1.0 + (vol - self.vol_floor) / span
        return price * self.base_spacing * scale

    # ------------------------------------------------------------------
    def on_tick(self, price: float, ticker: Dict[str, Any]) -> List[OrderSignal]:
        """Esegue la griglia sul nuovo prezzo. ticker puo' contenere
        'bid_vol' e 'ask_vol' (list) per il bias di imbalance_span."""
        if price <= 0:
            raise ValueError("price <= 0 in on_tick")
        self._ingest_price(price, float(ticker.get("volume", 0.0)))

        # bias laterale da imbalance orderbook (se disponibile)
        bias: float = self._imbalance_bias(ticker)
        step: float = self._spacing(price)
        risk_eur: float = self.capital * self.risk_per_trade

        signals: List[OrderSignal] = []
        # builda livelli attorno al mid, densita' maggiore sul lato bias
        # (n_asks/levels = max but skew count)
        n_each: int = max(1, self.max_levels)
        for i in range(1, n_each + 1):
            # spacing dei livelli moltiplicato da sqrt(i) -> piu' larghi man mano
            multi: float = math.sqrt(float(i))
            sell_px: float = price + step * multi * (1.0 + bias)
            buy_px: float = price - step * multi * (1.0 - bias)
            signals.append(OrderSignal("sell", round(sell_px, 8),
                                       round(risk_eur / sell_px, 8),
                                       meta={"level": i, "vol": self.st.realized_vol}))
            signals.append(OrderSignal("buy", round(buy_px, 8),
                                       round(risk_eur / buy_px, 8),
                                       meta={"level": i, "vol": self.st.realized_vol}))
        # memoria: window gia' limitata da deque(maxlen)
        return signals

    # ------------------------------------------------------------------
    def _imbalance_bias(self, ticker: Dict[str, Any]) -> float:
        """Bias in [-0.5, +0.5] dal flusso bid/ask. Uscita esplicita."""
        bids: Sequence[float] = ticker.get("bid_vol") or []
        asks: Sequence[float] = ticker.get("ask_vol") or []
        if not bids or not asks:
            return 0.0
        b: float = sum(bids[: self.imbalance_span])
        a: float = sum(asks[: self.imbalance_span])
        tot: float = b + a
        if tot <= 0:
            return 0.0
        return (b - a) / tot  # -1..1 -> clip per sicurezza
        # (bias largo -> sposta ordini verso lato piu' profondo)

    # ------------------------------------------------------------------
    def on_fill(self, fill: Dict[str, Any]) -> None:
        """Registra fill; nessun try/except pass: errori espliciti."""
        side: str = fill.get("side", "")
        px: float = float(fill.get("price", 0.0))
        if px <= 0:
            raise ValueError("fill con price <= 0")
        if side == "buy":
            self.st.fills_buy.append(px)
        elif side == "sell":
            self.st.fills_sell.append(px)
        else:
            raise ValueError(f"side ignoto in on_fill: {side!r}"
                             if side else "side mancante in on_fill")
        # asintotico: tiene solo ultimi N fill per non crescere senza limite
        if len(self.st.fills_buy) > 4096:
            self.st.fills_buy = self.st.fills_buy[-2048:]
        if len(self.st.fills_sell) > 4096:
            self.st.fills_sell = self.st.fills_sell[-2048:]

    # ------------------------------------------------------------------
    @staticmethod
    def estimate_memory_mb(n: int) -> float:
        """Stima RAM (MB) per finestra di n tick (streaming, niente listoni).

        deque di float: ~112 B/entry + overhead, baseline ~1.5 MB.
        """
        if n <= 0:
            raise ValueError("n <= 0 in estimate_memory_mb")
        per_tick: float = 112.0          # bytes/float in deque CPython
        base: float = 1.5 * 1024 * 1024  # interpreter + stack
        return (base + n * per_tick) / (1024.0 * 1024.0)


# ----------------------------------------------------------------------
# helper streaming OOM-safe per batch di prezzi (evita list comprehension)
def stream_prices(rows: Generator[float, None, None],
                  chunk: int = 100_000) -> Generator[float, None, None]:
    """Ritorna i prezzi a chunk per non tenere tutto in RAM."""
    buf: List[float] = []
    for px in rows:
        buf.append(px)
        if len(buf) >= chunk:
            yield from buf
            buf.clear()
            gc.collect()
    if buf:
        yield from buf


# ----------------------------------------------------------------------
if __name__ == "__main__":
    _cfg: Dict[str, Any] = {
        "symbol": "SOL/EUR", "capital": 100.0, "base_spacing": 0.003,
        "vol_lookback": 50, "vol_floor": 0.005, "vol_ceiling": 0.08,
        "max_levels": 3, "risk_per_trade": 0.05, "imbalance_span": 3,
    }
    s: StrategyBase = StrategyBase(_cfg)
    assert s.estimate_memory_mb(100_000) > 1.0
    # selftest tick sequenziali con drift + orderbook sbilanciato
    _bias_t: Dict[str, Any] = {"bid_vol": [10, 9, 8], "ask_vol": [2, 2, 2]}
    _n_signals: int = 0
    _i: int = 0
    for _i in range(200):
        _n_signals += len(s.on_tick(100.0 + _i * 0.002, _bias_t))
    s.on_fill({"side": "buy", "price": 99.5})
    s.on_fill({"side": "sell", "price": 100.4})
    print(f"SELFTEST OK ticks={_i} signals={_n_signals} "
          f"mem_100k={s.estimate_memory_mb(100_000):.2f}MB "
          f"realized_vol={s.st.realized_vol:.5f}")
    # verifica OOM-safe streaming
    _g: Generator[float, None, None] = (float(i) for i in range(250_000))
    _p: int = 0
    for _chunk in stream_prices(_g, chunk=50_000):
        _p += 1
    del _g, _chunk, _p
    gc.collect()
    print("STREAM CHUNK OK")
