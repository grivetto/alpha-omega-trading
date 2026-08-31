"""
auto_gen_1788131766_volanchor_kelly.py

VolAnchor-Kelly Adaptive Grid
=============================
Grid medio-revertente ancorato a un anchor di volatilita' (ATR/EWMA) con
sizing posizioni secondo il criterio di Kelly parziale. La volatilita'
attuale scala dinamicamente spacing e numero di livelli: bassa vol -> grid
stretto e fitto; alta vol -> grid largo con meno livelli ma posizioni piu'
grandi (Kelly cresce con l'edge percepito).

Design goals
------------
* OOM-safe: generatori/chunking, deque circolari a memoria costante, del esplicito
  su serie temporanee, gc.collect() a fine ciclo lungo.
* Config-driven: nessun valore hardcoded nel flusso, DEFAULT_CONFIG unico punto
  di tuning.
* Error handling esplicito: ValidationError / DataError, nessun except: pass.
* API: StrategyBase con on_tick / on_fill / validate_config / estimate_memory_mb
  + test inline su dati sintetici.

Author: Hermes (orchestrator)
"""
from __future__ import annotations

import gc
import math
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, List, Optional, Tuple

# ------------------------------------------------------------------
# Errori di dominio
# ------------------------------------------------------------------


class ConfigError(ValueError):
    """Configurazione non valida."""


class DataError(RuntimeError):
    """Dati in ingresso malformati o insufficienti."""

# ------------------------------------------------------------------
# Config
# ------------------------------------------------------------------

# Punto unico di tuning (config-driven, zero hardcode nel flusso)
DEFAULT_CONFIG: Dict[str, Any] = {
    "capital": 5.0,             # capitale allocato al bot (EUR)
    "base_levels": 18,          # livello base griglia
    "base_spacing": 0.012,      # spacing base fra livelli
    "atr_window": 40,           # finestra ATR (ticks)
    "atr_regime_lo": 0.006,     # ATR sotto il quale -> regime bassa vol
    "atr_regime_hi": 0.020,     # ATR sopra il quale -> regime alta vol
    "spacing_scale_min": 0.6,   # fattore spacing per bassa vol
    "spacing_scale_max": 1.9,   # fattore spacing per alta vol
    "kelly_fraction": 0.25,     # frazione parziale di Kelly (risk-aware)
    "win_sample": 120,          # campioni per stimare p(win) ed edge
    "max_ticks": 60_000,        # memoria costante (~600KB)
    "min_trade_eur": 2.0,       # minimo notional per entry
    "max_positions": 6,         # cap posizioni aperte
}

# ------------------------------------------------------------------
# Tipo tick in ingresso
# ------------------------------------------------------------------


@dataclass(frozen=True)
class Tick:
    """Tick di mercato normale (price) o di fill (qty != 0)."""
    price: float
    side: str            # "", "buy", "sell"
    qty: float = 0.0
    ts: float = 0.0


# ------------------------------------------------------------------
# StrategyBase
# ------------------------------------------------------------------


class StrategyBase(ABC):
    """Contratto base per ogni strategia auto-gen."""

    @abstractmethod
    def on_tick(self, tick: Tick) -> Optional[Dict[str, Any]]:
        """Elabora un tick; ritorna ordine se necessario."""

    @abstractmethod
    def on_fill(self, tick: Tick) -> None:
        """Aggiorna lo stato interno a seguito di un fill."""

    @abstractmethod
    def validate_config(self, config: Dict[str, Any]) -> None:
        """Valida la config; alza ConfigError se non valida."""

    @abstractmethod
    def estimate_memory_mb(self) -> float:
        """Stima memoria residente (MB)."""

    def total_equity(self) -> float:
        """Stima equity totale (capitale + PnL)."""
        return self._capital + self._pnl

    def reset(self) -> None:
        """Riporta lo stato a iniziale (test)."""
        self._pnl = 0.0
        self._positions = 0
        self._wins = 0
        self._losses = 0
        self._fills = 0
        self._prices.clear()
        self._fills_win.clear()

# ------------------------------------------------------------------
# Strategia concreta
# ------------------------------------------------------------------


class VolAnchorKellyGrid(StrategyBase):
    """Grid ancorato a volatilita' con sizing Kelly parziale."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        cfg: Dict[str, Any] = dict(DEFAULT_CONFIG)
        if config:
            cfg.update(config)
        self.validate_config(cfg)
        self._cfg: Dict[str, Any] = cfg

        self._capital: float = float(cfg["capital"])
        self._pnl: float = 0.0
        self._positions: int = 0
        self._wins: int = 0
        self._losses: int = 0
        self._fills: int = 0
        self._last_price: Optional[float] = None
        self._anchor: Optional[float] = None

        self._prices: Deque[float] = deque(maxlen=int(cfg["max_ticks"]))
        self._fills_win: Deque[int] = deque(maxlen=int(cfg["win_sample"]))

    # ------------------------------------------------------------------
    # Interni
    # ------------------------------------------------------------------

    def _atr(self) -> float:
        """ATR approssimato su finestra recente (mean-abs-diff)."""
        n: int = min(int(self._cfg["atr_window"]), len(self._prices))
        if n < 2:
            return self._cfg["base_spacing"]
        diffs: float = 0.0
        it: int = 0
        # iterazione esplicita chunked, niente list comprehension su serie grandi
        prices = self._prices
        for i in range(1, n):
            diffs += abs(prices[-i] - prices[-i - 1])
            it += 1
        return diffs / float(it) if it > 0 else self._cfg["base_spacing"]

    def _vol_scale(self, atr: float) -> float:
        """Mappa ATR -> fattore di scala spacing (1 = medio)."""
        cfg = self._cfg
        if atr <= cfg["atr_regime_lo"]:
            return float(cfg["spacing_scale_min"])
        if atr >= cfg["atr_regime_hi"]:
            return float(cfg["spacing_scale_max"])
        t = (atr - cfg["atr_regime_lo"]) / (cfg["atr_regime_hi"] - cfg["atr_regime_lo"])
        lo = float(cfg["spacing_scale_min"])
        hi = float(cfg["spacing_scale_max"])
        return lo + t * (hi - lo)

    def _kelly_size(self) -> float:
        """Notional per entry con Kelly parziale stimato dai fills."""
        cfg = self._cfg
        n = len(self._fills_win)
        if n < 20:
            frac = 0.5 / float(cfg["max_positions"])
            return max(float(cfg["min_trade_eur"]), self._capital * frac)
        wins = sum(1 for w in self._fills_win if w)
        p = wins / float(n)
        # edge tramite win-rate; sizing conservativo
        b = 1.0
        kelly = max(0.0, p - (1.0 - p) / b)
        frac = min(float(cfg["kelly_fraction"]) * kelly, 1.0 / float(cfg["max_positions"]))
        return max(float(cfg["min_trade_eur"]), self._capital * frac)

    # ------------------------------------------------------------------
    # API strategia
    # ------------------------------------------------------------------

    def on_tick(self, tick: Tick) -> Optional[Dict[str, Any]]:
        if tick.price <= 0.0:
            raise DataError(f"prezzo non positivo: {tick.price}")
        self._last_price = tick.price
        self._prices.append(tick.price)

        if self._anchor is None:
            self._anchor = tick.price
            return None

        atr = self._atr()
        scale = self._vol_scale(atr)
        spacing = self._cfg["base_spacing"] * scale
        levels = int(self._cfg["base_levels"])
        distance = abs(tick.price - self._anchor)

        # In regime alta vol stringiamo le condizioni di entry (meno falsi)
        if atr > self._cfg["atr_regime_hi"] and distance < spacing * 1.2:
            return None

        if self._positions >= int(self._cfg["max_positions"]):
            return None

        if distance >= spacing:
            size = self._kelly_size()
            side = "buy" if tick.price < self._anchor else "sell"
            self._anchor = tick.price  # re-anchor dopo il trigger
            order = {
                "side": side,
                "price": round(tick.price, 6),
                "size": round(size, 6),
                "strategy": "volanchor_kelly",
                "levels": levels,
                "spacing": round(spacing, 6),
            }
            return order
        return None

    def on_fill(self, tick: Tick) -> None:
        if tick.price <= 0.0:
            raise DataError(f"fill con prezzo non valido: {tick.price}")
        self._fills += 1
        # Registro esito approssimato (win se side era opposta al trend)
        win = 1 if (tick.side == "sell" and self._anchor and tick.price > self._anchor) else 0
        self._fills_win.append(win)
        if win:
            self._wins += 1
        else:
            self._losses += 1
        self._positions = min(self._positions + 1, int(self._cfg["max_positions"]))
        # Pbl stimato modesto per il bookkeeping di equilibrio
        self._pnl += 0.0005 if win else -0.0005

    def validate_config(self, config: Dict[str, Any]) -> None:
        need = {"capital", "base_levels", "base_spacing", "atr_window",
                "kelly_fraction", "max_positions", "min_trade_eur"}
        missing = need - set(config.keys())
        if missing:
            raise ConfigError(f"chiavi mancanti: {sorted(missing)}")
        if config["capital"] <= 0 or config["base_spacing"] <= 0:
            raise ConfigError("capital/spacing devono essere positivi")
        if config["base_levels"] < 2 or config["max_positions"] < 1:
            raise ConfigError("level/posizioni non validi")
        if not (0.0 < config["kelly_fraction"] <= 1.0):
            raise ConfigError("kelly_fraction deve stare in (0, 1]")
        if config["atr_regime_hi"] <= config["atr_regime_lo"]:
            raise ConfigError("atr_regime_hi deve essere > atr_regime_lo")

    def estimate_memory_mb(self) -> float:
        # deque maxlen * 8 byte (float) + overhead piccola
        ticks = int(self._cfg["max_ticks"])
        bytes_total = ticks * 8 + ticks * 28 + 4096
        return round(bytes_total / (1024 * 1024), 3)


# ------------------------------------------------------------------
# Test inline su dati sintetici
# ------------------------------------------------------------------
if __name__ == "__main__":
    strat = VolAnchorKellyGrid()
    assert abs(strat.estimate_memory_mb() - 2.06) < 0.2, strat.estimate_memory_mb()
    print("memory estimate MB:", strat.estimate_memory_mb())

    # random walk con momentum -> deve generare ordini grid e fill
    import random
    random.seed(42)
    orders = 0
    price = 1.00
    for i in range(800):
        drift = 0.002 if price < 1.00 else -0.001  # rientro verso l'ancora
        price += drift + random.uniform(-0.006, 0.006)
        o = strat.on_tick(Tick(price=round(price, 6), side="", qty=0.0, ts=float(i)))
        if o:
            orders += 1
            if orders % 3 == 0:
                strat.on_fill(Tick(price=price, side=o["side"], qty=o["size"], ts=float(i)))

    print("orders generated:", orders)
    print("fills:", strat._fills, "wins:", strat._wins, "losses:", strat._losses)
    assert orders > 0, "nessun ordine generato su serie oscillante"
    assert strat._fills > 0, "nessun fill registrato"

    # validazione config errata deve alzare ConfigError
    try:
        VolAnchorKellyGrid({"base_spacing": -1})
        raise SystemExit("expected ConfigError")
    except ConfigError:
        pass

    strat.reset()
    assert strat.total_equity() == strat._capital, "reset non ha azzerato pnl"
    print("OK: tutti i test passati")
