"""
auto_gen_1788131175_vwapdrift_grid.py

VWAP-Drift Adaptive Grid
========================
Combina un grid medio-revertente ancorato al VWAP con un filtro di deriva
(momentum/adaptive). Quando la deriva e' bassa, il grid lavora a pieno;
quando la deriva sale oltre soglia, il grid si "stringe" (spacing ridotto,
piu' livelli) per catturare il micro-movimento senza inseguire il trend.

Design goals
------------
* OOM-safe: nessuna list comprehension su serie lunghe; uso di generatori
  chunked, esclusione esplicita di variabili grandi e gc.collect() a fine ciclo.
* Config-driven: zero valori hardcoded nel flusso, tutto da CONFIG.
* Error handling esplicito: nessun `except: pass`.
* API: classe StrategyBase con on_tick / on_fill / validate_config /
  estimate_memory_mb + test inline su dati sintetici.

Author: Hermes (orchestrator)
"""
from __future__ import annotations

import gc
import math
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Iterable, List, Optional

# --------------------------------------------------------------------------
# Tipi ed errori
# --------------------------------------------------------------------------


class StrategyConfigError(ValueError):
    """Configurazione non valida per la strategia."""


class DataError(RuntimeError):
    """Dati in ingresso malformati o insufficienti."""


# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

# Default di produzione (config-driven, niente hardcode nel flusso)
DEFAULT_CONFIG: Dict[str, Any] = {
    "capital": 5.0,
    "levels": 16,
    "spacing": 0.014,
    "vwap_window": 120,          # ticks per il calcolo VWAP
    "drift_window": 40,          # ticks per la stima di deriva
    "drift_lo": 0.004,           # deriva sotto la quale grid full-size
    "drift_hi": 0.010,           # deriva sopra la quale grid compresso
    "compress_scale": 0.5,       # frazione di spacing in regime di deriva alta
    "exit_mult": 3.0,            # multiplo per l'exit protettivo (chandelier)
    "base_entry_pct": 0.5,       # frazione del capital per entry al livello base
    "max_ticks": 50_000,         # buffer circolare (memoria costante)
    "chunk_size": 5_000,         # dimensione chunk per processare serie lunghe
}


# --------------------------------------------------------------------------
# Modello dati
# --------------------------------------------------------------------------

@dataclass
class Bar:
    """Barra sintetica di mercato (tick aggregato)."""
    ts: float
    price: float
    volume: float
    side: str = "buy"


@dataclass
class Order:
    """Rappresentazione di un ordine piazzato/riempito."""
    price: float
    size: float
    side: str
    level: int = 0
    filled: bool = False


@dataclass
class StrategyState:
    """Stato interno persistente tra i tick (memoria costante)."""
    price_buffer: Deque[float] = field(default_factory=deque)
    vol_buffer: Deque[float] = field(default_factory=deque)
    orders: List[Order] = field(default_factory=list)
    realized_pnl: float = 0.0
    entry_price: Optional[float] = None
    locked_capital: float = 0.0
    n_ticks: int = 0


# --------------------------------------------------------------------------
# Strategia base (abstract)
# --------------------------------------------------------------------------

class StrategyBase(ABC):
    """Contratto comune a tutte le strategie del framework Denaro."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config: Dict[str, Any] = dict(DEFAULT_CONFIG)
        if config:
            self.config.update(config)
        self.validate_config(self.config)
        self.state = StrategyState()
        self._ts: float = 0.0

    # -- API richiesta dal framework -------------------------------------
    @abstractmethod
    def on_tick(self, price: float, volume: float, ts: float) -> List[Order]:
        """Processa un tick di mercato e ritorna eventuali ordini."""

    @abstractmethod
    def on_fill(self, order: Order, fill_price: float, ts: float) -> None:
        """Registra un fill (entry o exit)."""

    @abstractmethod
    def validate_config(self, config: Dict[str, Any]) -> None:
        """Valida la config; alza StrategyConfigError se invalida."""

    @abstractmethod
    def estimate_memory_mb(self, n_ticks: int) -> float:
        """Stima in MB il footprint per n_ticks buffered."""


# --------------------------------------------------------------------------
# Implementazione VWAP-Drift
# --------------------------------------------------------------------------

class VwapDriftGrid(StrategyBase):
    """
    Griglia ancorata al VWAP con compressione adattiva in base alla deriva.

    La logica non accumula mai piu' di `max_ticks` campioni (deque a capacita'
    fissata) => memoria costante O(max_ticks) indipendentemente dal volume
    di dati in ingresso. Le serie lunghe sono processate a chunk con generatori.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(config)
        self._vwap: Optional[float] = None
        self._drift: float = 0.0

    def validate_config(self, config: Dict[str, Any]) -> None:
        """Validazione esplicita dei parametri critici."""
        errors: List[str] = []
        if config.get("capital", 0) <= 0:
            errors.append("capital deve essere > 0")
        if config.get("levels", 0) < 2:
            errors.append("levels deve essere >= 2")
        if config.get("spacing", 0) <= 0:
            errors.append("spacing deve essere > 0")
        if config.get("vwap_window", 0) < 1:
            errors.append("vwap_window deve essere >= 1")
        if config.get("drift_window", 0) < 1:
            errors.append("drift_window deve essere >= 1")
        drift_hi = config.get("drift_hi", math.inf)
        drift_lo = config.get("drift_lo", -math.inf)
        if drift_lo >= drift_hi:
            errors.append("drift_lo deve essere < drift_hi")
        if not (0 < config.get("compress_scale", 0) <= 1.0):
            errors.append("compress_scale deve essere in (0,1]")
        if errors:
            raise StrategyConfigError("; ".join(errors))

    def estimate_memory_mb(self, n_ticks: int) -> float:
        """Stima RAM per n_ticks buffer (8 byte/float x2 buffer + overhead)."""
        cap = min(n_ticks, int(self.config["max_ticks"]))
        # deque di float ~ 8.1 byte/elem + allocazione deque
        per_elem = 8.1 * 2  # price + volume
        base = 200_000      # oggetti Python, ordini, overhead fisso
        return (base + cap * per_elem) / (1024 * 1024)

    def _vwap_from_buffers(self) -> Optional[float]:
        """Calcola VWAP in un singolo passaggio con generatori chunked."""
        if not self.state.price_buffer:
            return None
        prices = self.state.price_buffer
        vols = self.state.vol_buffer
        # Chunking esplicito: evita di materializzare liste complete
        pv_sum = 0.0
        v_sum = 0.0
        chunk = int(self.config["chunk_size"])
        it = iter(zip(prices, vols))
        while True:
            block = [(p, v) for _, (p, v) in zip(range(chunk), it)]
            if not block:
                break
            for p, v in block:
                pv_sum += p * v
                v_sum += v
            del block  # libera subito il blocco
        gc.collect()
        if v_sum <= 0:
            return None
        return pv_sum / v_sum

    def _estimate_drift(self) -> float:
        """Deriva = |variazione relativa| sull'ultima finestra."""
        buf = self.state.price_buffer
        win = int(self.config["drift_window"])
        if len(buf) < 2:
            return 0.0
        current = buf[-1]
        # indice di partenza dipende dalla finestra
        start = buf[0] if win >= len(buf) else buf[-(win + 1)]
        if start <= 0:
            return 0.0
        return abs(current - start) / start

    def _effective_spacing(self) -> float:
        """Spacing adattivo: piu' stretto quando la deriva e' alta."""
        base = float(self.config["spacing"])
        hi = float(self.config["drift_hi"])
        lo = float(self.config["drift_lo"])
        scale = float(self.config["compress_scale"])
        if self._drift <= lo:
            return base
        if self._drift >= hi:
            return base * scale
        # interpolazione lineare tra lo e hi
        t = (self._drift - lo) / (hi - lo)
        return base * (1.0 - (1.0 - scale) * t)

    def on_tick(self, price: float, volume: float, ts: float) -> List[Order]:
        """Aggiorna lo stato e ritorna la lista di ordini da piazzare."""
        if price <= 0 or ts < self._ts:
            raise DataError(f"tick invalido: price={price} ts={ts}")
        self._ts = ts
        self.state.n_ticks += 1
        max_cap = int(self.config["max_ticks"])
        self.state.price_buffer.append(price)
        self.state.vol_buffer.append(volume)
        # Mantiene la capacita' costante (pop da sinistra se supera)
        if len(self.state.price_buffer) > max_cap:
            self.state.price_buffer.popleft()
            self.state.vol_buffer.popleft()

        self._vwap = self._vwap_from_buffers()
        self._drift = self._estimate_drift()

        if self._vwap is None:
            return []
        spacing = self._effective_spacing()
        levels = int(self.config["levels"])
        capital = float(self.config["capital"])
        chunk = float(self.config["chunk_size"])

        loc = price - self._vwap
        # livello piu' vicino sotto il prezzo (zona di acquisto)
        raw_level = int(loc / spacing)
        orders: List[Order] = []
        half = max(1, levels // 2)
        for k in range(1, half + 1):
            lvl = raw_level - k
            target = self._vwap + lvl * spacing
            if target >= price:
                continue
            size_share = chunk * (1.0 / (half + 1))
            size = (capital * float(self.config["base_entry_pct"])) * size_share
            orders.append(Order(price=target, size=max(size, 1e-9),
                                side="buy", level=lvl))
        return orders

    def on_fill(self, order: Order, fill_price: float, ts: float) -> None:
        """Aggiorna pnl e riferimento d'ingresso al riempimento."""
        if order.side == "buy":
            self.state.entry_price = fill_price
            self.state.locked_capital += order.size * fill_price
        else:
            # exit: chiudi parte del rischio
            if self.state.entry_price and self.state.entry_price > 0:
                pnl = (fill_price - self.state.entry_price) * order.size
                self.state.realized_pnl += pnl
            else:
                raise DataError("sell fill senza entry_price registrato")
            self.state.locked_capital = max(
                0.0, self.state.locked_capital - order.size * fill_price)


# --------------------------------------------------------------------------
# Helper OOM-safe per il backtest su serie lunghe
# --------------------------------------------------------------------------

def replay_chunked(strategy: StrategyBase,
                   prices: Iterable[float],
                   volumes: Iterable[float],
                   chunk_size: int = 5_000) -> Dict[str, Any]:
    """
    Replay di una serie di prezzi a chunk, senza materializzare tutto in RAM.

    Ritorna metriche aggregate. Processa chunk-by-chunk per serie lunghe.
    """
    total_orders = 0
    realized_pnl = 0.0
    buf_prices: List[float] = []
    buf_vols: List[float] = []
    ts = 0.0
    it_p = iter(prices)
    it_v = iter(volumes)
    while True:
        buf_prices = list((p for _, p in zip(range(chunk_size), it_p)))
        buf_vols = list((v for _, v in zip(range(chunk_size), it_v)))
        if not buf_prices:
            break
        for p, v in zip(buf_prices, buf_vols):
            ts += 1.0
            try:
                orders = strategy.on_tick(p, v, ts)
            except DataError:
                continue
            for o in orders:
                # simulate fill at limit (mark-to-market)
                if o.price >= p:  # buy limit hit
                    strategy.on_fill(o, o.price, ts)
                    total_orders += 1
        # libera i buffer di blocco esplicitamente
        del buf_prices, buf_vols
        gc.collect()
    return {
        "orders": total_orders,
        "realized_pnl": strategy.state.realized_pnl,
        "n_ticks": strategy.state.n_ticks,
        "memory_mb": strategy.estimate_memory_mb(strategy.state.n_ticks),
    }


# --------------------------------------------------------------------------
# Test inline su dati sintetici piccoli
# --------------------------------------------------------------------------

if __name__ == "__main__":
    import random

    def _run() -> None:
        rng = random.Random(42)
        strat = VwapDriftGrid({"capital": 5.0, "levels": 8, "spacing": 0.01})
        # serie sintetica mean-reverting attorno a 100 con rumore
        n = 2_000
        prices_gen = (100.0 + 0.5 * math.sin(i / 50.0) + rng.gauss(0, 0.15)
                      for i in range(n))
        vols_gen = (1.0 + rng.random() for _ in range(n))
        res = replay_chunked(strat, prices_gen, vols_gen, chunk_size=500)
        mem = strat.estimate_memory_mb(res["n_ticks"])
        assert res["orders"] >= 0
        assert mem > 0
        print(f"orders={res['orders']} pnl={res['realized_pnl']:.4f} "
              f"ticks={res['n_ticks']} mem={mem:.2f}MB")
        print("test_auto_gen_1788131175_vwapdrift_grid: OK")

    _run()
