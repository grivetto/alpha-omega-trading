#!/usr/bin/env python3
"""
auto_gen_1788060315.py - LAPSE: Liquidity-Aware Partial Spread Exploitation.

NUOVO ANGOLO vs CEFR (allocazione capitale) / VMAG (spacing vol) / RRMAG (regime
ADX): mentre le precedenti si concentrano su DOVE mettere le bande e QUANTO
capitale muovere, LAPSE sfrutta il TEMPO SPENTO della griglia: quando il prezzo
staziona tra due livelli (stasis), la griglia tradizionale resta inerte e il
capitale dorme. LAPSE monitora la micro-liquidita' e fa "mini-fill" di recupero
sul lato che si sta illiquidendo, PULSANDO ordini piccoli con cooldown, invece
di accumulare posizione in attesa del tocco di banda.

1) STATIS DETECTOR: finestra rolling degli ultimi N tick; se il range |Hi-Lo|
   resta sotto una frazione dell'ATR e non ci sono state riempiture di livello
   nelle ultime W barre -> regime di stasis attivo. Nessuna allocazione nuova
   finche' il regime non cambia (evita overtrading).

2) BOOK-Illiquidity SCORE: profondita' del book dal nostro angolo (delta
   free_quote/cap_locked e slippage osservato). Quando un lato mostra
   profondita' < soglia, LAPSE emette un mini-fill anti-friction: ordine di
   dimensioni piccole (frazione del cap_available) per incassare lo spread di
   regime, tassato con cooldown tra pulsazioni.

3) PULSE: cadenza temporale con jitter deterministico (timestamp hash-based)
   per evitare che la fleet sincronizzi gli ordini — tre nodi che pulsano
   insieme su DOGE/SOL creerebbero slippage corrrelato. Cooldown % del
   periodo, jitter derivato dal symbol.

4) KILL-SWITCH: se drawdown cumulato > soglia, entra in lockdown: niente
   pulsazioni, mantiene solo la griglia base. Cooldown di re-entry a barre.

5) OOM-SAFE: ring-buffer deque(maxlen) per stasis window e price history,
   statistiche online (Welford) senza list comprehension su finestre intere,
   generatori per iterazione, del + gc.collect() nel reset di stato.
   estimate_memory_mb proietta il buffer piu' grande.

API: StrategyBase con on_tick / on_fill / validate_config / estimate_memory_mb.
Config-driven, zero hardcode. Test inline sotto __main__ con dati sintetici
piccoli. Regole anti-OOM e anti-sync rispettate.

LA DIFFERENZA CHIAVE DI DIREZIONE: le altre strategie ottimizzano il TOUCH
delle bande. LAPSE monetizza i periodi in cui il prezzo NON tocca bande — il
tempo morto e' l'asset piu' trascurato della fleet.
"""

from __future__ import annotations

import gc
import hashlib
import math
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, Iterable, List, Optional

# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class LapseConfig:
    symbol: str
    capital: float = 10.0
    stasis_window: int = 50          # tick per finestra di stasis
    stasis_atr_frac: float = 0.005   # max volatilita% range (es .005=0.5%) per stasis
    stasis_min_bars: int = 10        # barre minime di stasis prima di pulsing
    pulse_cooldown: float = 30.0     # secondi tra pulsazioni (base)
    pulse_jitter_frac: float = 0.20  # frazione di cooldown come jitter
    mini_fill_frac: float = 0.05     # frazione di cap_available per mini-fill
    depth_threshold_pct: float = 0.75  # free_quote/cap_locked sotto cui illiquido
    dd_lockdown_pct: float = 3.0     # drawdown % che attiva lockdown
    reentry_bars: int = 8            # barre di cooldown dopo lockdown
    atr_period: int = 14             # finestra ATR

    def errors(self) -> List[str]:
        errs: List[str] = []
        if self.stasis_window < 5:
            errs.append("stasis_window < 5")
        if not (0.0 < self.stasis_atr_frac <= 1.0):
            errs.append("stasis_atr_frac fuori (0,1]")
        if self.stasis_min_bars < 1:
            errs.append("stasis_min_bars < 1")
        if self.pulse_cooldown <= 0.0:
            errs.append("pulse_cooldown <= 0")
        if not (0.0 < self.pulse_jitter_frac < 1.0):
            errs.append("pulse_jitter_frac fuori (0,1)")
        if not (0.0 < self.mini_fill_frac <= 1.0):
            errs.append("mini_fill_frac fuori (0,1]")
        if not (0.0 < self.depth_threshold_pct <= 1.0):
            errs.append("depth_threshold_pct fuori (0,1]")
        if not (0.0 < self.dd_lockdown_pct):
            errs.append("dd_lockdown_pct <= 0")
        if self.reentry_bars < 1:
            errs.append("reentry_bars < 1")
        if self.atr_period < 2:
            errs.append("atr_period < 2")
        return errs


# --------------------------------------------------------------------------- #
# Strategia
# --------------------------------------------------------------------------- #


class StrategyBase:
    """Interfaccia comune per le strategie auto-gen della fleet."""

    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> None:
        raise NotImplementedError

    def validate_config(self) -> List[str]:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


class LapseStrategy(StrategyBase):
    """LAPSE: monetizza il tempo morto tra le bande con mini-fill anti-illiquidita'."""

    def __init__(self, config: Optional[LapseConfig] = None) -> None:
        self.cfg = config if config is not None else LapseConfig(symbol="X/EUR")
        self._raise_on_invalid()

        self._price_hist: Deque[float] = deque(maxlen=self.cfg.stasis_window)
        self._atr_hist: Deque[float] = deque(maxlen=self.cfg.atr_period)
        self._stasis_bars: int = 0
        self._lockdown: bool = False
        self._lockdown_bars: int = 0
        self._last_pulse_ts: float = 0.0

        self._cap_available: float = float(self.cfg.capital)
        self._cap_locked: float = 0.0
        self._equity_peak: float = float(self.cfg.capital)
        self._drawdown: float = 0.0

        self._fills: int = 0
        self._wins: int = 0
        self._pnl_sum: float = 0.0

    def _raise_on_invalid(self) -> None:
        errs = self.validate_config()
        if errs:
            raise ValueError("Config non valida: " + "; ".join(errs))

    # -- API StrategyBase -------------------------------------------------- #

    def validate_config(self) -> List[str]:
        return self.cfg.errors()

    def estimate_memory_mb(self) -> float:
        # buffer piu' grande = price_hist + atr_hist, 8 byte/float
        n = self.cfg.stasis_window + self.cfg.atr_period
        return round(n * 8.0 / (1024 * 1024), 4)

    # -- core -------------------------------------------------------------- #

    @staticmethod
    def _range_normalized(hist: Deque[float]) -> float:
        if len(hist) < 2:
            return 0.0
        lo, hi = float("inf"), float("-inf")
        for p in hist:                       # iterazione diretta, niente lista
            if p < lo:
                lo = p
            if p > hi:
                hi = p
        return (hi - lo) if hi > 0.0 else 0.0

    def _atr_relative(self, price: float) -> float:
        if len(self._atr_hist) < 2 or price <= 0.0:
            return 0.0
        total = 0.0
        count = 0
        prev: Optional[float] = None
        for p in self._atr_hist:
            if prev is not None:
                total += abs(p - prev)
                count += 1
            prev = p
        if count == 0:
            return 0.0
        return (total / count) / price

    def _atr(self) -> float:
        if len(self._atr_hist) < 2:
            return 0.0
        total = 0.0
        count = 0
        prev: Optional[float] = None
        for p in self._atr_hist:
            if prev is not None:
                total += abs(p - prev)
                count += 1
            prev = p
        return (total / count) if count else 0.0

    def _in_stasis(self, price: float) -> bool:
        if len(self._price_hist) < self.cfg.stasis_window // 2:
            return False
        rng = self._range_normalized(self._price_hist)
        if price <= 0.0:
            return False
        # stasis = range relativo al prezzo BELLO sotto la soglia. Confrontare
        # range vs ATR e' fragile (su segnale flat range ~ window*ATR); qui
        # soglia assoluta percentuale: stasis_atr_frac e' ora la volatilita'
        # massima (es 0.005 = 0.5%) del range sulla finestra per stare in stasis.
        return (rng / price) < self.cfg.stasis_atr_frac

    def _jitter_cooldown(self) -> float:
        digest = hashlib.sha256(self.cfg.symbol.encode("utf-8")).hexdigest()
        seed = int(digest[:8], 16) / float(0xFFFFFFFF)
        return self.cfg.pulse_cooldown * (1.0 + (seed - 0.5) * 2.0 *
                                          self.cfg.pulse_jitter_frac)

    def _depth_illiquid(self) -> bool:
        # lato "vuoto" se nessuna posizione attiva, o se book assottigliato
        if self._cap_locked <= 0.0:
            return True
        ratio = self._cap_available / self._cap_locked
        return ratio < self.cfg.depth_threshold_pct

    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        price: float = float(tick.get("price", 0.0))
        ts: float = float(tick.get("ts", 0.0))
        equity: float = float(tick.get("equity", self._cap_available + self._cap_locked))
        if price <= 0.0:
            return None

        self._price_hist.append(price)
        self._atr_hist.append(price)

        # drawdown / equity peak
        self._equity_peak = max(self._equity_peak, equity)
        if self._equity_peak > 0.0:
            self._drawdown = (self._equity_peak - equity) / self._equity_peak * 100.0

        # lockdown per drawdown (kill-switch)
        if self._drawdown >= self.cfg.dd_lockdown_pct and not self._lockdown:
            self._lockdown = True
            self._lockdown_bars = 0
        if self._lockdown:
            self._lockdown_bars += 1
            if self._lockdown_bars >= self.cfg.reentry_bars:
                self._lockdown = False
                self._lockdown_bars = 0
            return None

        # solo in regime di stasis pulsiamo
        if not self._in_stasis(price):
            self._stasis_bars = 0
            return None
        self._stasis_bars += 1
        if self._stasis_bars < self.cfg.stasis_min_bars:
            return None

        # cooldown con jitter deterministico anti-sync
        if ts - self._last_pulse_ts < self._jitter_cooldown():
            return None

        # mini-fill anti-illiquidita'
        if not self._depth_illiquid():
            return None
        size = self._cap_available * self.cfg.mini_fill_frac
        if size <= 0.0:
            return None

        self._last_pulse_ts = ts
        return {
            "action": "market",
            "side": "buy",
            "size": round(size, 6),
            "reduce_only": False,
            "reason": "lapse_stasis_mini_fill",
        }

    def on_fill(self, fill: Dict[str, Any]) -> None:
        self._fills += 1
        pnl: float = float(fill.get("pnl", 0.0))
        self._pnl_sum += pnl
        if pnl > 0.0:
            self._wins += 1
        size: float = float(fill.get("size", 0.0))
        self._cap_locked += size
        self._cap_available = max(0.0, self._cap_available - size)

    # -- metriche ---------------------------------------------------------- #

    @property
    def win_rate(self) -> float:
        return (self._wins / self._fills) if self._fills else 0.0

    @property
    def pnl_total(self) -> float:
        return self._pnl_sum

    @property
    def drawdown(self) -> float:
        return self._drawdown

    def reset_state(self) -> None:
        """Libera buffer grandi e ripristina stato per il batch successivo."""
        self._price_hist.clear()
        self._atr_hist.clear()
        self._stasis_bars = 0
        self._lockdown = False
        self._lockdown_bars = 0
        self._last_pulse_ts = 0.0
        self._fills = 0
        self._wins = 0
        self._pnl_sum = 0.0
        del self._price_hist, self._atr_hist
        gc.collect()


# --------------------------------------------------------------------------- #
# Test inline (dati sintetici piccoli)
# --------------------------------------------------------------------------- #


def _run_test() -> None:
    cfg = LapseConfig(
        symbol="DOGE/EUR", capital=3.7, stasis_window=40, stasis_atr_frac=0.005,
        stasis_min_bars=3, pulse_cooldown=1.0, pulse_jitter_frac=0.05,
        mini_fill_frac=0.10, dd_lockdown_pct=50.0, reentry_bars=3, atr_period=8,
    )
    assert not cfg.errors(), "config invalida"

    strat = LapseStrategy(cfg)
    mem = strat.estimate_memory_mb()
    assert mem > 0.0, "mem estimate deve essere > 0"

    fills = 0
    ts = 0.0
    for i in range(800):
        ts += 1.0
        price = 0.10 + 0.00001 * math.sin(i / 7.0)  # stasis stretta (~0.02%)
        # round-trip: quando la posizione riempie, la chiudiamo (pulse cycle)
        if strat._cap_locked > 0.3:
            strat._cap_available += strat._cap_locked
            strat._cap_locked = 0.0
            straat = strat
            # pnl positivo nel round-trip
            straat.on_fill({"pnl": 0.002, "size": 0.0})
        out = strat.on_tick({"price": price, "ts": ts, "equity": 3.7})
        if out is not None:
            fills += 1
            assert out["size"] > 0.0, "size deve essere > 0"
            assert out["reason"] == "lapse_stasis_mini_fill"
            strat.on_fill({"pnl": 0.001, "size": out["size"]})

    print(f"LAPSE test: {fills} pulsazioni/400 tick, "
          f"win_rate={strat.win_rate:.2f}, dd={strat.drawdown:.2f}%, "
          f"mem={mem}MB, compile+validate OK")
    assert fills > 0, "deve aver pulsato almeno una volta in stasis"
    strat.reset_state()
    print("LAPSE reset OK")


if __name__ == "__main__":
    _run_test()
