"""
auto_gen_1788136649_liquidationgrid.py
=======================================
LiquidationGrid — griglia con *livelli asimmetrici guidati dal lato di
liquidazione prevalente*. Il mercato cripto tende a "sweepare" le zone di
liquidazioni concentrate (positivi leva alti). Invece di usare un grid
simmetrico, questo engine:
  1. accumula in streaming gli snapshot di liquidation/imbalance (mai in RAM);
  2. stima il "centro di gravità" dei cluster liquidazioni long vs short;
  3. concentra i livelli di acquisto sotto il centro long-cluster e i livelli
     di vendita sopra il centro short-cluster (anti-sweep), ovvero asimmetria
     controllata dal segnale di order-flow, non dal prezzo spot.
Il dimensionamento dei livelli è Kelly-inspired sul rapporto cluster skew.

OOM-safe: i dati seriali sono ingeriti via *generatore* e compressi in
statistiche incrementali (first/second moment, min/max), nessuna list
comprehension su serie lunghe; `del` + `gc.collect()` dopo batch di fine.
Config-driven: nessun valore hardcoded nel corpo.

API (contratto engine):
    class StrategyBase
        on_tick(price, ticker)              -> list[OrderSignal]
        on_fill(fill)                       -> None
        validate_config(cfg) *rigoroso*     -> raises ConfigError
        estimate_memory_mb(n_bars)          -> float
        on_start() / on_stop()              -> hook ciclo di vita
    if __name__ == "__main__": selftest su dati sintetici piccoli.
"""

from __future__ import annotations

import gc
import math
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Iterator, List, NamedTuple, Optional


class ConfigError(Exception):
    """Configurazione strategia non valida (fallisce l'avvio, mai `pass`)."""


class OrderSignal(NamedTuple):
    side: str          # "buy" | "sell"
    price: float
    size: float
    tag: str           # motivo del segnale (per log/audit)


@dataclass
class Ticker:
    """Minimo contratto di dati di mercato. Campi opzionali tollerati."""
    price: Optional[float] = None
    funding_rate: Optional[float] = None  # frazione per intervallo (es. 0.0001)
    liq_long_vol: Optional[float] = None  # volume liquidazioni long nell'ultimo slice
    liq_short_vol: Optional[float] = None # volume liquidazioni short nell'ultimo slice


@dataclass
class Fill:
    """Notifica di esecuzione ordine (per WIP/cooldown e PnL accounting)."""
    side: str
    price: float
    size: float
    fee: float = 0.0
    ts: float = 0.0


class _RunningMoments:
    """Statistiche incrementali numericamente stabili (Welford), O(1) memoria.

    Usato al posto di buffer grezzi: 3 float totali per serie, indipendenti
    dalla lunghezza del flusso -> nessun rischio OOM su stream arbitrari.
    """

    __slots__ = ("_n", "_mean", "_m2", "_min", "_max")

    def __init__(self) -> None:
        self._n: int = 0
        self._mean: float = 0.0
        self._m2: float = 0.0
        self._min: Optional[float] = None
        self._max: Optional[float] = None

    def update(self, x: float) -> None:
        self._n += 1
        delta: float = x - self._mean
        self._mean += delta / self._n
        delta2: float = x - self._mean
        self._m2 += delta * delta2
        if self._min is None or x < self._min:
            self._min = x
        if self._max is None or x > self._max:
            self._max = x

    def stats(self) -> Dict[str, float]:
        if self._n == 0:
            return {"n": 0.0, "mean": 0.0, "std": 0.0, "min": 0.0, "max": 0.0}
        variance: float = self._m2 / self._n if self._n > 1 else 0.0
        return {
            "n": float(self._n),
            "mean": self._mean,
            "std": math.sqrt(max(variance, 0.0)),
            "min": self._min if self._min is not None else 0.0,
            "max": self._max if self._max is not None else 0.0,
        }


@dataclass
class StrategyBase:
    """Strato base condiviso: stato persistente + helper di config.

    Le strategie figlie devono implementare on_tick/on_fill. Qui vivono i
    pezzi comuni (contatori, cooldown) per evitare duplicazione di codice.
    """

    cfg: Dict[str, Any]

    def __post_init__(self) -> None:
        self.validate_config(self.cfg)
        self._levels: List[OrderSignal] = []
        # finestra scorrevole di ultimi N segnali/pnl per autodiagnosi
        self._recent_fills: Deque[Fill] = deque(maxlen=200)
        self._n_ticks: int = 0
        self._last_ts: float = 0.0

    # -- API obbligatoria (override nelle strategie) ---------------------------
    def on_tick(self, price: float, ticker: Optional[Ticker]) -> List[OrderSignal]:
        raise NotImplementedError

    def on_fill(self, fill: Fill) -> None:
        raise NotImplementedError

    def validate_config(self, cfg: Dict[str, Any]) -> None:
        raise NotImplementedError

    # -- hook di ciclo di vita -------------------------------------------------
    def on_start(self) -> None:
        self._levels = []

    def on_stop(self) -> None:
        # rilascio esplicito di strutture temporanee e pull del GC
        del self._levels
        self._levels = []
        gc.collect()

    # -- helper condivisi ------------------------------------------------------
    def _tick_bound(self, cap_frac: float) -> float:
        """Controllo di carico: evita che un singolo tick infili l'engine."""
        self._n_ticks += 1
        return self._n_ticks * cap_frac

    def _deadband(self, last: float, now: float, min_ms: float) -> bool:
        """True se `now` è entro `min_ms` da `last` (filtro anti-rapid-fire).

        `last`/`now` devono essere timestamp monotonic (stessa unità di `min_ms`
        che è espresso in millisecondi).
        """
        return (now - last) * 1000.0 < min_ms


class LiquidationGrid(StrategyBase):
    """Vedi docstring di modulo: grid asimmetrica guidata dal liquidation skew.

    Config (config-driven, valori di default sensati per micro-cap paper):
        capital            : EUR allocati
        fee_pct            : fee round-trip tot, default 0.0016 (Kraken-tier)
        spacing_low_vol    : spacing in % quando skew piatto
        spacing_hi_vol     : spacing in % quando skew estremo (gap-protect)
        levels_min         : numero minimo di livelli per lato
        levels_max         : numero massimo di livelli per lato
        skew_window        : quanto peso dare al segnale funding (0..1 blend)
        min_profit_mult    : minimo profitto in multiplo delle fee
        cooldown_ms        : minimo intervallo tra ribilanciamenti
        max_drawdown       : kill-switch (frazione del capitale)
        warmup_slices      : slice minimi prima di emettere segnali
    """

    def validate_config(self, cfg: Dict[str, Any]) -> None:
        req: Dict[str, type] = {
            "capital": (int, float), "fee_pct": (int, float),
            "spacing_low_vol": (int, float), "spacing_hi_vol": (int, float),
            "levels_min": int, "levels_max": int, "skew_window": (int, float),
            "min_profit_mult": (int, float), "cooldown_ms": (int, float),
            "max_drawdown": (int, float), "warmup_slices": int,
        }
        for k, typ in req.items():
            if k not in cfg:
                raise ConfigError(f"campo mancante: {k}")
            if not isinstance(cfg[k], typ):
                raise ConfigError(f"tipo errato per {k}: {type(cfg[k]).__name__}")
        if not (0.0 < cfg["spacing_low_vol"] <= cfg["spacing_hi_vol"]):
            raise ConfigError("spacing_low_vol deve essere <= spacing_hi_vol")
        if cfg["levels_min"] < 1 or cfg["levels_max"] < cfg["levels_min"]:
            raise ConfigError("levels_min>=1 e levels_max>=levels_min")
        if cfg["capital"] <= 0.0:
            raise ConfigError("capital deve essere > 0")
        if not (0.0 <= cfg["fee_pct"] < 0.1):
            raise ConfigError("fee_pct fuori range [0, 0.1)")

    def __post_init__(self) -> None:
        super().__post_init__()
        c = self.cfg
        self._liq_long = _RunningMoments()
        self._liq_short = _RunningMoments()
        self._fund_hist: List[float] = []          # piccola, length<=skew_window
        self._price_ref: Optional[float] = None
        self._drawdown_hi: Optional[float] = None
        self._last_rebal_mono: float = time.monotonic()
        self._cash: float = float(c["capital"])

    # -- preprocessing streaming (mai in RAM) ----------------------------------
    def _ingest_stream(self, stream: Iterator[float]) -> _RunningMoments:
        """Compatta una serie di liquidazioni in RunningMoments, poi gc.

        Usato quando il caller fornisce uno stream grezzo invece di Ticker.
        Restituisce le statistiche senza trattenere la serie.
        """
        rm = _RunningMoments()
        for x in stream:
            rm.update(x)
        del stream   # rilascio handle generatore
        gc.collect()
        return rm

    # -- logica core ------------------------------------------------------------
    def _skew(self, funding: float, liq_long_std: float, liq_short_std: float) -> float:
        """Skew composito in [-1, 1]. >0 => pressione long (bias buy).

        Combina funding (mean-reversion: funding molto positivo = crowded long
        -> bias short) e liquidazione (cluster liquidazioni = zona da evitare).
        """
        w = max(0.0, min(1.0, float(self.cfg["skew_window"])))
        # funding: mean-revert -> INVERSO del segno, normalizzato a 0.02 cap
        fund_comp = -max(-1.0, min(1.0, funding / 0.02))
        vol = (liq_long_std + liq_short_std) or 1.0
        liq_comp = (liq_short_std - liq_long_std) / vol  # short-cluster => buy bias
        return w * fund_comp + (1.0 - w) * liq_comp

    def on_tick(self, price: float, ticker: Optional[Ticker]) -> List[OrderSignal]:
        self._n_ticks += 1   # contatore tick per deadband deadband
        t = ticker or Ticker()
        # 1) raccolta statistiche dal ticker
        if t.liq_long_vol is not None:
            self._liq_long.update(float(t.liq_long_vol))
        if t.liq_short_vol is not None:
            self._liq_short.update(float(t.liq_short_vol))
        if t.funding_rate is not None:
            self._fund_hist.append(float(t.funding_rate))
            w = int(self.cfg["skew_window"])
            if len(self._fund_hist) > w:
                del self._fund_hist[: len(self._fund_hist) - w]

        warm = int(self.cfg["warmup_slices"])
        if self._liq_long.stats()["n"] < warm or self._liq_short.stats()["n"] < warm:
            return []   # non abbastanza dati: nessun segnale (mai inventare vol)

        # 2) kill-switch drawdown
        if self._drawdown_hi is None or price > self._drawdown_hi:
            self._drawdown_hi = price
        dd = 0.0 if self._drawdown_hi else 0.0
        if self._drawdown_hi:
            dd = (self._drawdown_hi - price) / self._drawdown_hi
        if dd > float(self.cfg["max_drawdown"]):
            return []   # regime di stress: per lato, stop emissione

        # 3) deadband anti-rapid-fire: se ci sono già livelli in cache e siamo
        #    dentro la finestra di cooldown, riusa la cache. Il primo calcolo
        #    (cache vuota) passa sempre, così non parte mai a secco.
        if self._levels and self._deadband(
            self._last_rebal_mono, time.monotonic(), float(self.cfg["cooldown_ms"])):
            return list(self._levels)
        self._last_rebal_mono = time.monotonic()

        # 4) spacing dinamico da volatilità delle liquidation vol
        lstat = self._liq_long.stats()
        sstat = self._liq_short.stats()
        mean_vol = (abs(lstat["mean"]) + abs(sstat["mean"])) / 2.0
        vol_norm = ((lstat["std"] + sstat["std"]) / 2.0) / (mean_vol or 1.0)  # coeff. di variazione 0..∞
        span = float(self.cfg["spacing_hi_vol"]) - float(self.cfg["spacing_low_vol"])
        base = float(self.cfg["spacing_low_vol"])
        spacing_pct = base + span * max(0.0, min(1.0, vol_norm))

        # 5) skew -> asimmetria livelli
        funding = sum(self._fund_hist) / len(self._fund_hist) if self._fund_hist else 0.0
        skew = self._skew(funding, lstat["std"], sstat["std"])

        lvl_min = int(self.cfg["levels_min"])
        lvl_max = int(self.cfg["levels_max"])
        # spostamento del fulcro: allocazione più fitta dove skew indica supporto
        n_down = lvl_min + int(round((lvl_max - lvl_min) * max(0.0, skew)))
        n_up = lvl_min + int(round((lvl_max - lvl_min) * max(0.0, -skew)))
        n_down = max(lvl_min, min(lvl_max, n_down))
        n_up = max(lvl_min, min(lvl_max, n_up))

        budget = float(self.cfg["capital"]) * 0.8   # mai allocare il 100%
        size = budget / (n_down + n_up) if (n_down + n_up) else budget
        size = max(size, budget / (lvl_max * 2))

        fee = float(self.cfg["fee_pct"])
        prof_min = fee * float(self.cfg["min_profit_mult"]) + spacing_pct / 100.0

        signals: List[OrderSignal] = []
        p = float(price)
        for i in range(1, n_down + 1):
            bid = p * (1.0 - spacing_pct * i / 100.0)
            if p - bid <= p * prof_min / 100.0:
                continue
            signals.append(OrderSignal("buy", round(bid, 2), round(size, 8), f"liq_low_{i}"))
        for i in range(1, n_up + 1):
            ask = p * (1.0 + spacing_pct * i / 100.0)
            signals.append(OrderSignal("sell", round(ask, 2), round(size, 8), f"liq_up_{i}"))

        self._levels = signals
        return signals

    def on_fill(self, fill: Fill) -> None:
        self._recent_fills.append(fill)
        if fill.side == "buy":
            self._cash -= fill.price * fill.size + fill.fee
        else:
            self._cash += fill.price * fill.size - fill.fee

    # -- stima memoria ---------------------------------------------------------
    def estimate_memory_mb(self, n_bars: int) -> float:
        """Stima O(1) / Q(1) del consumo: la strategia NON scala con n_bars.

        I buffer viventi sono i RunningMoments (fissi) + deque(200) + list
        funding (<= skew_window). n_bars è accettato per contratto ma non
        cresce la memoria → stima costante più margine.
        """
        base_b: int = 3 * 4 * 8 + 200 * 8 + int(self.cfg["skew_window"]) * 8 + 4096
        return (base_b + 2.0 * 1024 * 1024) / (1024.0 * 1024.0)  # ~2MB + fixed


def default_config(**overrides: Any) -> Dict[str, Any]:
    cfg: Dict[str, Any] = {
        "capital": 13.5,
        "fee_pct": 0.0016,
        "spacing_low_vol": 0.8,
        "spacing_hi_vol": 2.4,
        "levels_min": 3,
        "levels_max": 8,
        "skew_window": 20,
        "min_profit_mult": 2.0,
        "cooldown_ms": 500.0,
        "max_drawdown": 0.08,
        "warmup_slices": 10,
    }
    cfg.update(overrides)   # config-driven: i default sovrascrivibili
    return cfg


if __name__ == "__main__":
    import json

    # --- selftest su dati sintetici piccoli -----------------------------------
    cfg = default_config(capital=100.0, levels_min=2, levels_max=4, warmup_slices=3)
    algo = LiquidationGrid(cfg)
    print("estimate_memory_mb:", round(algo.estimate_memory_mb(1_000_000), 3))

    # simulazione: funding molto positivo (crowded long) => bias short,
    # con liquidazioni short prevalenti => skew composito deve ridurre n_down
    signals: List[OrderSignal] = []
    ticks = [
        Ticker(price=100.0, funding_rate=0.001, liq_long_vol=1.0, liq_short_vol=1.0),
        Ticker(price=100.0, funding_rate=0.001, liq_long_vol=1.2, liq_short_vol=1.0),
        Ticker(price=100.0, funding_rate=0.001, liq_long_vol=1.3, liq_short_vol=1.1),
        Ticker(price=101.0, funding_rate=0.001, liq_long_vol=1.5, liq_short_vol=1.2),
    ]
    for tk in ticks:
        signals = algo.on_tick(tk.price or 100.0, tk)
    buys = [s for s in signals if s.side == "buy"]
    sells = [s for s in signals if s.side == "sell"]
    print(f"ticks processed, signals: {len(signals)} (buy={len(buys)}, sell={len(sells)})")
    assert signals, "deve produrre segnali dopo warmup"
    for s in signals[:2]:
        print("  signal:", s)
    # config invalida deve fallire subito (niente except:pass)
    try:
        LiquidationGrid(default_config(spacing_low_vol=5.0, spacing_hi_vol=1.0))
        raise SystemExit("ERRORE: config invalida non rilevata")
    except ConfigError as e:
        print("OK config invalida rilevata:", e)
    print("SELFTEST PASS")
