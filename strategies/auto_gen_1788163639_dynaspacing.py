"""DynamicSpacingAdaptiveGrid — griglia adattiva con spacing proporzionale alla volatilità.

Miglioramento diretto delle grid fisse attuali della fleet (DOGE, SOL): una grid
statica soffre quando la volatilità cambia regime — spacing troppo largo in
mercato calmo (poche eseguzioni) o troppo stretto in mercato vivo (riempimenti
subito sotto/oltre, inventory drift). Questa strategia rende lo spacing e il
numero di livelli funzione della volatilità realizzata (ewma su ATR%) così da
mantenere un rapporto costante tra levels coperti e range atteso.

Design:
- Volatilità ATR Wilder incrementale (O(1) per tick, nessuna finestra in RAM).
- EWMA su ATR% per smussare il regime: `dyn_spacing = base_spacing * atr_pct / ref_vol`.
- Livelli: `levels` derivato da `range_mult * atr / dyn_spacing`, clampato.
- OOM-safe: niente storage storico illimitato; streaming con chunking esplicito
  e `gc.collect()` periodico.
- Error handling esplicito: ConfigError / DataError. Zero `except: pass`.

API compatibile col framework Denaro: on_tick, on_fill, validate_config,
estimate_memory_mb. Test inline con dati sintetici.
"""

from __future__ import annotations

import gc
import logging
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Optional

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Configurazione non valida."""


class DataError(Exception):
    """Dati di input malformati."""


@dataclass
class StrategyBase:
    """Base contract (alias locale). Le strategie reali estendono questa."""

    config: dict[str, Any] = field(default_factory=dict)

    def on_tick(self, quote: float, ts: int, **ctx: Any) -> dict[str, Any]:  # pragma: no cover
        raise NotImplementedError

    def on_fill(self, fill_price: float, qty: float, side: str, **ctx: Any) -> dict[str, Any]:  # pragma: no cover
        raise NotImplementedError

    def validate_config(self) -> None:  # pragma: no cover
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:  # pragma: no cover
        raise NotImplementedError


@dataclass
class _Atr:
    """Wilder incremental ATR, O(1) per aggiornamento."""

    period: int
    prev_close: Optional[float] = None
    ewma: float = 0.0
    count: int = 0

    def update(self, high: float, low: float, close: float) -> float:
        if self.prev_close is None:
            tr = high - low
        else:
            tr = max(high - low, abs(high - self.prev_close), abs(low - self.prev_close))
        self.prev_close = close
        if self.count < self.period:
            self.count += 1
            self.ewma += (tr - self.ewma) / self.count
        else:
            alpha = 1.0 / self.period
            self.ewma += alpha * (tr - self.ewma)
        return self.ewma

    @property
    def ready(self) -> bool:
        return self.count >= self.period


@dataclass
class _Level:
    price: float
    qty: float
    side: str  # buy | sell


class DynamicSpacingAdaptiveGrid(StrategyBase):
    """Griglia compra/vendi con spacing adattivo al regime di volatilità.

    I livelli vengono (ri)calcolati attorno al mid reference ogni volta che il
    regime EWMA di volatilità cambia oltre una soglia (re-anchor lazy), oppure
    quando il prezzo tocca un bordo estremo. La quantità per livello segue il
    budget configurato, evitando di concentrare tutto il capitale su pochi livelli.
    """

    def __init__(self, config: Optional[dict[str, Any]] = None) -> None:
        self.config = config or {}
        self.validate_config()
        c = self.config
        self._atr = _Atr(int(c["atr_period"]))
        self._ref_price: Optional[float] = None
        self._levels: list[_Level] = []
        self._active_levels: int = 0
        self._vol_ewma: float = c["ref_vol"]
        self._last_anchor_vol: float = c["ref_vol"]
        self._reanchor_frac: float = float(c["reanchor_vol_frac"])
        self._filled_px: deque = deque(maxlen=1000)
        self._fills: int = 0
        self._realized_pnl: float = 0.0
        self._position: float = 0.0
        self._budget_unit: float = 0.0
        self._cash: float = float(c["initial_quote"])

    # ---------------------------------------------------------------- config
    def validate_config(self) -> None:
        c = self.config
        required = {
            "atr_period": (int, float), "ref_vol": (int, float),
            "base_spacing_frac": (int, float), "min_spacing_frac": (int, float),
            "max_spacing_frac": (int, float), "range_mult": (int, float),
            "min_levels": int, "max_levels": int, "initial_quote": (int, float),
            "qty_per_level": (int, float), "reanchor_vol_frac": (int, float),
            "min_atr_ticks": (int, float),
        }
        for k, typ in required.items():
            if k not in c:
                raise ConfigError(f"config mancante: {k}")
        try:
            atr_p = int(c["atr_period"])
        except (TypeError, ValueError) as e:
            raise ConfigError("atr_period deve essere int") from e
        if atr_p < 2:
            raise ConfigError("atr_period deve essere >= 2")
        if float(c["ref_vol"]) <= 0:
            raise ConfigError("ref_vol deve essere > 0")
        if float(c["initial_quote"]) <= 0:
            raise ConfigError("initial_quote deve essere > 0")
        if not (0 < float(c["min_spacing_frac"]) <= float(c["base_spacing_frac"]) <= float(c["max_spacing_frac"])):
            raise ConfigError("ordinamento spacing invalido (min<=base<=max)")
        if int(c["min_levels"]) > int(c["max_levels"]):
            raise ConfigError("min_levels non puo' eccedere max_levels")
        if float(c["reanchor_vol_frac"]) <= 0:
            raise ConfigError("reanchor_vol_frac deve essere > 0")

    # ------------------------------------------------------------- utilities
    def _dyn_spacing(self, price: float) -> float:
        c = self.config
        atr_pct = (self._atr.ewma / price) if price > 0 else float(c["ref_vol"])
        ratio = atr_pct / float(c["ref_vol"])
        frac = float(c["base_spacing_frac"]) * ratio
        frac = max(float(c["min_spacing_frac"]), min(float(c["max_spacing_frac"]), frac))
        return price * frac

    def _rebuild_levels(self, anchor: float) -> None:
        c = self.config
        spacing = self._dyn_spacing(anchor)
        range_span = float(c["range_mult"]) * self._atr.ewma
        n_raw = int((range_span / spacing) // 2) * 2 + 1  # simmetrico dispari
        n = max(int(c["min_levels"]), min(int(c["max_levels"]), n_raw))
        unit = self._budget_unit if self._budget_unit > 0 else float(c["qty_per_level"])
        levels: list[_Level] = []
        half = n // 2
        for i in range(-half, half + 1):
            if i == 0:
                continue
            px = anchor + i * spacing
            side = "buy" if i < 0 else "sell"
            levels.append(_Level(price=px, qty=unit, side=side))
        self._levels = levels
        self._active_levels = len(levels)

    # ---------------------------------------------------------------- engine
    def on_tick(self, quote: float, ts: int, **ctx: Any) -> dict[str, Any]:
        # FIX 4: check quote all'inizio, prima di ogni uso
        if quote <= 0 or quote <= float(self.config["min_atr_ticks"]):
            raise DataError(f"quote non plausibile: {quote}")
        high = float(ctx.get("high", quote))
        low = float(ctx.get("low", quote))
        atr = self._atr.update(high, low, quote)
        if not self._atr.ready:
            return {"action": "hold", "levels": 0}

        if self._ref_price is None:
            # FIX 2: rebuild livelli PRIMA di allocare il budget
            self._ref_price = quote
            self._rebuild_levels(quote)
            n_levels = max(1, self._active_levels)
            self._budget_unit = float(self.config["initial_quote"]) / n_levels

        # FIX 1: protezione divisione per zero
        atr_pct = atr / quote if quote > 0 else self._vol_ewma
        self._vol_ewma = 0.7 * self._vol_ewma + 0.3 * atr_pct
        drift = abs(self._vol_ewma - self._last_anchor_vol) / max(self._last_anchor_vol, 1e-10)
        if drift > self._reanchor_frac or self._active_levels == 0:
            self._rebuild_levels(quote)
            self._last_anchor_vol = self._vol_ewma
            self._ref_price = quote

        order: Optional[_Level] = None
        for lv in self._levels:
            if lv.side == "buy" and quote <= lv.price:
                order = lv
                break
            if lv.side == "sell" and quote >= lv.price:
                order = lv
                break
        if order is None:
            return {"action": "hold", "levels": self._active_levels}

        self._execute(order, quote)
        return {"action": order.side, "price": order.price, "qty": order.qty,
                "levels": self._active_levels, "spacing": self._dyn_spacing(quote)}

    def _execute(self, order: _Level, quote: float) -> None:
        if order.side == "buy":
            cost = order.qty * quote
            if cost > self._cash:
                order.qty = self._cash / quote
                cost = self._cash
            self._cash -= cost
            self._position += order.qty
        else:
            if self._position >= order.qty:
                self._position -= order.qty
                self._cash += order.qty * quote
            else:
                qty = self._position
                self._position = 0.0
                self._cash += qty * quote
        self._fills += 1
        self._filled_px.append(quote)
        # FIX 3: rimuovi il livello eseguito (niente doppia esecuzione)
        if order in self._levels:
            self._levels.remove(order)
        self._active_levels = len(self._levels)

    def on_fill(self, fill_price: float, qty: float, side: str, **ctx: Any) -> dict[str, Any]:
        if side == "sell":
            # valorizza realized PnL rispetto al costo medio implicito
            self._realized_pnl += qty * fill_price
        self._fills += 1
        return {"pnl_realized": self._realized_pnl, "fills": self._fills}

    def estimate_memory_mb(self) -> float:
        # livelli + lista fills; bounds fissi -> memoria O(levels)
        n_levels = int(self.config["max_levels"])
        return (n_levels * 96 + 4096) / (1024 * 1024)


def from_csv_chunked(path: str, chunk: int, cb: Callable[[list[dict[str, Any]]], None],
                     gc_interval: int = 50) -> int:
    """Streaming CSV reader OOM-safe: processa `chunk` righe alla volta."""
    import csv
    total = 0
    buf: list[dict[str, Any]] = []
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            buf.append(row)
            total += 1
            if len(buf) >= chunk:
                cb(buf)
                buf.clear()
            if total % (chunk * gc_interval) == 0:
                gc.collect()
    if buf:
        cb(buf)
    return total


def _synthetic() -> None:
    """Test inline con dati sintetici piccoli (walk-forward su sequenza)."""
    import random
    random.seed(7)
    cfg = {
        "atr_period": 14, "ref_vol": 0.02, "base_spacing_frac": 0.02,
        "min_spacing_frac": 0.008, "max_spacing_frac": 0.06, "range_mult": 2.0,
        "min_levels": 5, "max_levels": 21, "initial_quote": 1000.0,
        "qty_per_level": 10.0, "reanchor_vol_frac": 0.25, "min_atr_ticks": 1e-9,
    }
    strat = DynamicSpacingAdaptiveGrid(cfg)
    strat.validate_config()
    price = 100.0
    buys = sells = 0
    for _ in range(2000):
        price *= (1.0 + random.gauss(0, 0.004))
        r = strat.on_tick(round(price, 4), _,
                          high=price * 1.001, low=price * 0.999)
        if r.get("action") == "buy":
            buys += 1
        elif r.get("action") == "sell":
            sells += 1
    assert strat._atr.ready, "ATR mai pronto"
    assert float(strat.estimate_memory_mb()) > 0
    print(f"OK synthetic: fills={strat._fills} buys={buys} sells={sells} "
          f"eq={strat._cash + strat._position * price:.2f} "
          f"levels={strat._active_levels} mem={strat.estimate_memory_mb():.4f}MB")
    # verifica chunking
    import tempfile, os
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="") as fh:
        fh.write("a,b\n" + "".join(f"{i},{i+1}\n" for i in range(250)))
        tmp = fh.name
    seen = from_csv_chunked(tmp, chunk=64, cb=lambda rows: None)
    os.unlink(tmp)
    assert seen == 250, f"chunking: atteso 250, visto {seen}"
    print(f"OK chunking: {seen} righe")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _synthetic()
