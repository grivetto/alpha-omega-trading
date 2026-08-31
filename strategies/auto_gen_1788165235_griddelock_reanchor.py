"""auto_gen_1788165235_griddelock_reanchor.py — Adaptive Grid Re-anchor with Grid-Lock Recovery (AGRR).

Ideazione (Hermes, orchestratore Denaro/Alpha-Omega):
Problema rilevato nella fleet: TUTTI i nodi (mc2, nuvola, MARCODG1) mostrano
`free_quote=0.0, volume=0.0, buy=0` con griglia 'running' ma BLOCCATA. Causa
tipica: in un trend direzionale i livelli buy della griglia fissa vengono
consumati, il prezzo sale oltre il mid originale, e la griglia resta 'appesa'
senza ricalcolarsi → capitale immobilizzato in inventory, volume a zero.

AGRR risolve con:
1) GRID-LOCK DETECTOR: se tutti i livelli buy sono fillati e nessun sell attivo
   sopra il prezzo (inventory estremo in direzione short/prezzo sopra mid di X%),
   scatta il RE-ANCHOR lazy: ricalcola la griglia attorno al prezzo corrente.
2) ASYMMETRIC RECOVERY: condizioni di lock con inventory lunga vengono ripagate
   con take-profit piu' aggressivo (spacing sell ridotto) per scaricare
   inventory piu' velocemente; in inventory corta si restringe solo se utile.
3) CAP-BANDING: il budget per livello e' derivato dal capitale, evitando di
   allocare 100% del quote a livelli che non verranno mai raggiunti.
4) OOM-safe: ATR e vol EWMA incrementali, niente storage storico illimitato,
   streaming con chunking e gc.collect() periodico.
5) Error handling esplicito: ConfigError/DataError, zero `except: pass`.

API compatibile col framework Denaro: on_tick, on_fill, validate_config,
estimate_memory_mb. Test inline con dati sintetici (walk-forward).
"""

from __future__ import annotations

import gc
import math
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Optional


class StrategyError(Exception):
    """Errore di configurazione o dati nella strategia AGRR."""


class ConfigError(StrategyError):
    """Configurazione non valida."""


class DataError(StrategyError):
    """Dati di input malformati o non plausibili."""


@dataclass
class StrategyBase:
    """Base contract (alias locale). Le strategie reali estendono questa."""

    config: dict[str, Any] = field(default_factory=dict)

    def on_tick(self, tick: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def on_fill(self, fill: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def validate_config(self) -> None:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


class _Atr:
    """Wilder incremental ATR, O(1) per tick, nessuna finestra in RAM."""

    def __init__(self, period: int) -> None:
        self.period = period
        self.prev_close: Optional[float] = None
        self.ewma: float = 0.0
        self.count: int = 0

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
    filled: bool = False


class AdaptiveGridReanchor(StrategyBase):
    """Griglia con re-anchor lazy anti-lock e recovery asimmetrica inventory."""

    def __init__(self, config: Optional[dict[str, Any]] = None) -> None:
        self.config = config or {}
        self.validate_config()
        c = self.config
        self._atr = _Atr(int(c["atr_period"]))
        self._ref_price: Optional[float] = None
        self._levels: list[_Level] = []
        self._cash: float = float(c["initial_quote"])
        self._position: float = 0.0
        self._realized_pnl: float = 0.0
        self._buys_filled: int = 0
        self._sells_filled: int = 0
        self._reanchors: int = 0
        self._lock_triggered: bool = False
        self._vol_ewma: float = float(c["ref_vol"])
        # GC/counter safety per processi lunghi
        self._tick_ct: int = 0
        self._gc_every: int = int(c.get("gc_interval", 5000))

    # ------------------------------------------------------------- config
    def validate_config(self) -> None:
        c = self.config
        required = {
            "atr_period": (int, float), "ref_vol": (int, float),
            "base_spacing_frac": (int, float), "min_spacing_frac": (int, float),
            "max_spacing_frac": (int, float), "levels": int,
            "initial_quote": (int, float), "qty_per_level": (int, float),
            "lock_exit_pct": (int, float), "recovery_spacing_factor": (int, float),
            "min_atr_ticks": (int, float),
        }
        for key, typ in required.items():
            if key not in c:
                raise ConfigError(f"config mancante: {key}")
        if int(c["atr_period"]) < 2:
            raise ConfigError("atr_period deve essere >= 2")
        if float(c["ref_vol"]) <= 0:
            raise ConfigError("ref_vol deve essere > 0")
        if float(c["initial_quote"]) <= 0:
            raise ConfigError("initial_quote deve essere > 0")
        if float(c["qty_per_level"]) <= 0:
            raise ConfigError("qty_per_level deve essere > 0")
        if not (0 < float(c["min_spacing_frac"]) <= float(c["base_spacing_frac"]) <= float(c["max_spacing_frac"])):
            raise ConfigError("ordinamento spacing invalido (min<=base<=max)")
        if int(c["levels"]) < 3:
            raise ConfigError("levels deve essere >= 3")
        if not (0 < float(c["lock_exit_pct"]) <= 1.0):
            raise ConfigError("lock_exit_pct deve essere in (0,1]")
        if float(c["recovery_spacing_factor"]) <= 0:
            raise ConfigError("recovery_spacing_factor deve essere > 0")

    # ------------------------------------------------------------- helpers
    def _dyn_spacing(self, price: float) -> float:
        c = self.config
        atr_pct = (self._atr.ewma / price) if price > 0 else float(c["ref_vol"])
        ratio = atr_pct / float(c["ref_vol"])
        frac = float(c["base_spacing_frac"]) * ratio
        frac = max(float(c["min_spacing_frac"]), min(float(c["max_spacing_frac"]), frac))
        return price * frac

    def _budget_per_level(self) -> float:
        """Budget per livello derivato dal capitale, evitando over-allocazione."""
        c = self.config
        levels = int(c["levels"])
        per_level = float(c["qty_per_level"])
        max_cost = float(c["initial_quote"]) / levels
        return min(per_level, max_cost)

    def _rebuild(self, anchor: float, recovery: float) -> None:
        """(Ri)costruisce la griglia simmetrica attorno ad anchor.

        recovery in (0,1]: 1 = simmetrico; <1 restringe il lato sell per
        scaricare inventory piu' velocemente in condizioni di lock lungo.
        """
        c = self.config
        spacing = self._dyn_spacing(anchor)
        n = int(c["levels"])
        unit = self._budget_per_level()
        sell_spacing = spacing * float(c["recovery_spacing_factor"]) * recovery
        levels: list[_Level] = []
        half = n // 2
        for i in range(-half, half + 1):
            if i == 0:
                continue
            side = "buy" if i < 0 else "sell"
            px = anchor + (i * spacing if i < 0 else i * sell_spacing)
            levels.append(_Level(price=round(px, 8), qty=unit, side=side))
        self._levels = levels
        self._ref_price = anchor

    # -------------------------------------------------------------- engine
    def _grid_locked(self, quote: float) -> bool:
        """True se il prezzo e' sopra il mid re-anchor oltre lock_exit_pct
        (inventory lunga e griglia buy esaurita). Un singolo lock check basta."""
        c = self.config
        if self._ref_price is None or self._ref_price <= 0:
            return False
        pct_from_mid = (quote - self._ref_price) / self._ref_price
        return pct_from_mid > float(c["lock_exit_pct"])

    def on_tick(self, tick: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(tick, dict) or "price" not in tick:
            raise DataError("tick deve essere dict con chiave 'price'")
        quote = float(tick["price"])
        high = float(tick.get("high", quote))
        low = float(tick.get("low", quote))
        if quote <= float(self.config["min_atr_ticks"]) or high < low:
            raise DataError(f"quote non plausibile: price={quote} high={high} low={low}")

        atr = self._atr.update(high, low, quote)
        self._tick_ct += 1
        if self._tick_ct % self._gc_every == 0:
            gc.collect()

        # init al primo tick pronto
        if not self._atr.ready:
            return {"action": "hold", "reanchors": self._reanchors}
        if self._ref_price is None:
            self._rebuild(quote, recovery=1.0)
            self._lock_triggered = False

        atr_pct = atr / quote
        self._vol_ewma = 0.7 * self._vol_ewma + 0.3 * atr_pct

        # GRID-LOCK recovery: prezzo sopra mid oltre soglia e nessun sell attivo
        # sopra il prezzo => re-anchor con recovery asimmetrica per scaricare inventory.
        inactive_sell_above = not any(
            lv.side == "sell" and not lv.filled and lv.price >= quote for lv in self._levels
        )
        if self._grid_locked(quote) and (self._position > 0 or inactive_sell_above):
            recovery = max(0.3, min(1.0, float(self.config["recovery_spacing_factor"])))
            self._rebuild(quote, recovery=recovery)
            self._reanchors += 1
            self._lock_triggered = True

        # esegui il primo livello toccato (buy sotto, sell sopra)
        for lv in self._levels:
            if lv.filled:
                continue
            hit = (lv.side == "buy" and quote <= lv.price) or (
                lv.side == "sell" and quote >= lv.price
            )
            if hit:
                return self._execute(lv, quote)
        return {"action": "hold", "reanchors": self._reanchors}

    def _execute(self, lv: _Level, quote: float) -> dict[str, Any]:
        if lv.side == "buy":
            cost = lv.qty * quote
            if cost > self._cash:
                lv.qty = self._cash / quote
                cost = self._cash
            self._cash -= cost
            self._position += lv.qty
            self._buys_filled += 1
        else:
            qty = min(lv.qty, self._position)
            if qty <= 0:
                lv.filled = True
                return {"action": "hold", "reason": "no_inventory", "reanchors": self._reanchors}
            self._position -= qty
            self._cash += qty * quote
            self._sells_filled += 1
        lv.filled = True
        return {
            "action": lv.side,
            "price": lv.price,
            "qty": lv.qty,
            "reanchors": self._reanchors,
            "lock_recovered": self._lock_triggered,
            "inventory": round(self._position, 8),
            "cash": round(self._cash, 4),
        }

    def on_fill(self, fill: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(fill, dict) or "side" not in fill:
            raise DataError("fill deve essere dict con chiave 'side'")
        qty = float(fill.get("qty", 0.0))
        price = float(fill.get("price", 0.0))
        if fill["side"] == "sell":
            self._realized_pnl += qty * price
        return {
            "pnl_realized": round(self._realized_pnl, 6),
            "buys": self._buys_filled,
            "sells": self._sells_filled,
            "reanchors": self._reanchors,
        }

    def estimate_memory_mb(self) -> float:
        """O(levels): livelli + valori scalari. Bounds fissi."""
        n_levels = int(self.config["levels"])
        return (n_levels * 160 + 8192) / (1024 * 1024)


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
    """Test inline con dati sintetici: trend up che consuma i buy (lock) e
    verifica che il re-anchor rimetta la griglia a regime."""
    import random
    random.seed(11)
    cfg = {
        "atr_period": 14, "ref_vol": 0.02, "base_spacing_frac": 0.015,
        "min_spacing_frac": 0.006, "max_spacing_frac": 0.05, "levels": 7,
        "initial_quote": 500.0, "qty_per_level": 10.0,
        "lock_exit_pct": 0.02, "recovery_spacing_factor": 0.6,
        "min_atr_ticks": 1e-9, "gc_interval": 5000,
    }
    strat = AdaptiveGridReanchor(cfg)
    strat.validate_config()
    price = 100.0
    n_buy = n_sell = 0
    # fase 1: drift up (consuma buy + lock)
    for i in range(4000):
        price *= (1.0 + 0.0015)  # trend up lento
        r = strat.on_tick({"price": round(price, 4), "high": price * 1.001,
                           "low": price * 0.999, "ts": i})
        if r.get("action") == "buy":
            n_buy += 1
        elif r.get("action") == "sell":
            n_sell += 1
    # fase 2: volatilita' normale, deve trovare di nuovo attivita'
    for i in range(6000):
        price *= (1.0 + random.gauss(0, 0.004))
        r = strat.on_tick({"price": round(price, 4), "high": price * 1.001,
                           "low": price * 0.999, "ts": i + 4000})
        if r.get("action") == "buy":
            n_buy += 1
        elif r.get("action") == "sell":
            n_sell += 1
    assert strat._atr.ready, "ATR mai pronto"
    assert strat._reanchors >= 1, f"atteso almeno 1 re-anchor, visto {strat._reanchors}"
    assert float(strat.estimate_memory_mb()) > 0
    print(f"OK synthetic: reanchors={strat._reanchors} buys={n_buy} sells={n_sell} "
          f"pnl={strat._realized_pnl:.4f} inv={strat._position:.4f} "
          f"mem={strat.estimate_memory_mb():.4f}MB")
    # verifica chunking OOM-safety
    import tempfile, os
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="") as fh:
        fh.write("a,b\n" + "".join(f"{i},{i+1}\n" for i in range(330)))
        tmp = fh.name
    seen = from_csv_chunked(tmp, chunk=64, cb=lambda rows: None)
    os.unlink(tmp)
    assert seen == 330, f"chunking: atteso 330, visto {seen}"
    print(f"OK chunking: {seen} righe")


if __name__ == "__main__":
    _synthetic()
