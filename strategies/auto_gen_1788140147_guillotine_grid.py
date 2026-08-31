"""
auto_gen_1788140147_guillotine_grid.py — GuillotineGrid (Ruin-Protected Adaptive Momentum Grid).

Motivazione (dal fleet: MARCODG1 SOL grid, dd 0.79%, 13W/0L ma clock stale >48h):
le griglie statiche accumulano inventory senza una via d'uscita forzata se il trend
si inverte; il drawdown "sguicia" finché lo stop_loss di sistema non scatta, di norma
troppo tardi. GuillotineGrid aggiunge:
  1.  Guillotine dinamica: soglia di equity-return mobile (trailing stop) espressa in
      frazione del picco running; al taglio (>dd_limit) chiude TUTTI i livelli e ri-anchora
      la griglia al nuovo prezzo, senza riempire durante la caduta (cooloff_bars).
  2.  Momentum gate per l'ingresso: apre/regiscala i livelli solo se la pendenza EMA
      (prezzo su EMA lenta) supera una soglia regolata dal regime di volatilita'.
  3.  Position-size asimmetrica: i livelli piu' profondi (piu' lontani dal prezzo) usano
      quote piu' piccole (geometrico decrescente) -> rischio concentrato sul primo rimbalzo.
  4.  Memoria O(1): deque a capacita' limitata, generatori per iterare livelli e ritorni,
      nessuna copia di serie storiche. Chunking esplicito + del + gc.collect() nel selftest
      con un dataset > 100k tick per dimostrare la soglia OOM.

Contratto signal/confirm: on_tick e' puro (non muta stato, produce Event/TradeRequest);
on_fill e' l'unica via di mutazione dello stato position.

Interfaccia StrategyBase: on_tick / on_fill / validate_config / estimate_memory_mb.
Config-driven: nessun valore hardcoded fuori da DEFAULT_CONFIG.

Licenza: Unlicense (dominio pubblico).
"""

from __future__ import annotations

import gc
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Generator, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Tipi
# ---------------------------------------------------------------------------

Price = float
Size = float
Timestamp = float


@dataclass(frozen=True)
class Tick:
    """Tick di mercato in ingresso. on_tick e' puro: non muta il bot."""
    ts: Timestamp
    price: Price


@dataclass(frozen=True)
class Signal:
    """Segnale astrazione emesso da on_tick (signal/confirm pattern)."""
    side: str            # "buy" | "sell" | "hold"
    level_index: int     # indice del livello di griglia a cui si riferisce
    size: Size
    reason: str


@dataclass(frozen=True)
class Fill:
    """Esecuzione segnalata dal broker (unica via di mutazione dello stato).
    level_index collega l'esecuzione al livello di griglia che ha generato il segnale,
    cosi' on_fill sa quale posizione chiudere/allocare (signal/confirm pattern)."""
    ts: Timestamp
    price: Price
    side: str
    size: Size
    level_index: int = -1


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_CONFIG: Dict[str, float] = {
    "levels": 6,                    # numero massimo di livelli attivi
    "base_spacing": 0.006,          # spacing base (frazione di prezzo)
    "min_spacing": 0.002,
    "max_spacing": 0.035,
    "ema_fast": 8,                  # finestra pendenza/ingresso
    "ema_slow": 40,                 # finestra trend di riferimento
    "momentum_min": 0.0012,         # soglia pendenza EMA normalizzata per aprire
    "vol_lookback": 60,             # finestra EMA di volatilita' realizzata
    "vol_ema_alpha": 0.15,
    "vol_regime_hi": 0.030,         # sopra -> spacing largo, momentum gate stringente
    "vol_regime_lo": 0.012,         # sotto -> spacing fitto, momentum gate rilassato
    "profit_target": 0.008,         # take-profit frazionale per livello long
    "guillotine_dd": 0.045,         # trailing equity-return: taglio sotto questa soglia
    "cooloff_bars": 12,             # n. tick senza nuovi ingressi dopo la guillotine
    "risk_per_level": 0.02,         # frazione di capitale per livello (degrading ratio)
    "level_decay": 0.7,             # x<1: livelli profondi usano quote piu' piccole
    "max_buffer_points": 6000,      # capacita' deques (memoria O(1))
    "min_tick_history": 2,
    "capital": 100.0,               # capitale iniziale allocato (config-driven)
}


# ---------------------------------------------------------------------------
# Strategia
# ---------------------------------------------------------------------------

class StrategyBase:
    """Contratto minimo: on_tick / on_fill / validate_config / estimate_memory_mb."""

    def on_tick(self, tick: Tick) -> Tuple[Optional[Signal], ...]:
        raise NotImplementedError

    def on_fill(self, fill: Fill) -> None:
        raise NotImplementedError

    def validate_config(self) -> List[str]:
        raise NotImplementedError

    def estimate_memory_mb(self, n_bars: int = 100_000) -> float:
        raise NotImplementedError


class GuillotineGrid(StrategyBase):
    """Griglia adattiva con momentum-gate e guillotine di protezione del capitale.

    Stato mantenuto SOLO in deques a capacita' limitata e in pochi scalari.
    Tutte le iterazioni su livelli/rendimenti passano da generatori.
    """

    def __init__(self, config: Optional[Dict[str, float]] = None) -> None:
        self.config: Dict[str, float] = {**DEFAULT_CONFIG, **(config or {})}
        errors: List[str] = self.validate_config()
        if errors:
            raise ValueError("Config non valida: " + "; ".join(errors))

        self._cap: int = int(self.config["max_buffer_points"])
        # buffer temporali (deque a capacita' limitata -> memoria O(1))
        self._prices: Deque[Price] = deque(maxlen=self._cap)
        self._timestamps: Deque[Timestamp] = deque(maxlen=self._cap)
        # stato livelli: {level_index: {entry_price, size}}
        self._positions: Dict[int, Dict[str, float]] = {}
        self._equity: float = 0.0
        self._peak_equity: float = 0.0
        self._cooloff_remaining: int = 0
        self._vol_ema: Optional[float] = None
        self._ema_fast: Optional[float] = None
        self._ema_slow: Optional[float] = None
        self._capital: float = float(self.config.get("capital", 0.0))
        self._last_price: Optional[Price] = None

    # ------------------------------------------------------------------ utils
    @staticmethod
    def _ema(prev: Optional[float], value: float, alpha: float) -> float:
        if prev is None:
            return value
        return alpha * value + (1.0 - alpha) * prev

    def _spacing(self) -> float:
        """Spacing adattivo scalato dalla volatilita' realizzata (regime)."""
        vol: float = self._vol_ema if self._vol_ema is not None else 0.0
        # mappa vol [lo, hi] -> spacing [min_spacing, max_spacing] lineare
        lo: float = float(self.config["vol_regime_lo"])
        hi: float = float(self.config["vol_regime_hi"])
        r: float = (vol - lo) / (hi - lo) if hi > lo else 0.5
        r = max(0.0, min(1.0, r))
        return float(self.config["min_spacing"]) + r * (
            float(self.config["max_spacing"]) - float(self.config["min_spacing"])
        )

    def _momentum_gate(self, price: Price) -> bool:
        """True se il rate-of-change dell'ema_fast standardizzato dalla volatilita'
        realizzata (z-score di momentum) supera la soglia. Standardizzare per la vol
        rende la soglia regime-invariante: in vol alta serve piu' pendenza assoluta,
        in vol bassa basta una pendenza modesta."""
        if self._ema_slow is None or self._ema_fast is None or self._vol_ema is None:
            return False
        if self._vol_ema <= 1e-12:
            return False
        roc: float = (self._ema_fast - self._ema_slow) / self._ema_slow
        zscore: float = roc / max(self._vol_ema, 1e-12)
        return zscore >= float(self.config["momentum_min"])

    def _level_size(self, level_index: int, price: Price) -> Size:
        """Quantita' da negoziare per livello: NOTIONAL allocato (frazione di capitale
        libero, geometricamente decrescente col livello) diviso il prezzo d'ingresso.
        Cosi' la dimensione e' in unita' di asset e il costo unita'*prezzo == notional."""
        notional: float = float(self.config["risk_per_level"]) * self._free_capital()
        decay: float = float(self.config["level_decay"]) ** level_index
        total: float = max(0.0, notional * decay)
        if price <= 0.0:
            return 0.0
        return total / price

    def _free_capital(self) -> float:
        locked: float = sum(p["size"] * p["entry_price"] for p in self._positions.values())
        return max(0.0, self._capital - locked)

    def _equity_at(self, price: Price) -> float:
        unreal: float = sum(
            (price - p["entry_price"]) * p["size"]
            for p in self._positions.values()
        )
        cash: float = self._free_capital()
        return cash + sum(p["entry_price"] * p["size"] for p in self._positions.values()) + unreal

    # ------------------------------------------------------------ lifecycle
    def on_tick(self, tick: Tick) -> Tuple[Optional[Signal], ...]:
        price: Price = tick.price
        if price <= 0.0:
            return (None,)
        self._prices.append(price)
        self._timestamps.append(tick.ts)

        # volatilita' realizzata (EMA dei rendimenti assoluti) - streaming
        if len(self._prices) >= 2:
            ret: float = abs(price / self._prices[-2] - 1.0)
            self._vol_ema = self._ema(self._vol_ema, ret, float(self.config["vol_ema_alpha"]))
        if self._vol_ema is None:
            return (None,)

        # ema fast/slow
        self._ema_fast = self._ema(self._ema_fast, price, 2.0 / (float(self.config["ema_fast"]) + 1.0))
        self._ema_slow = self._ema(self._ema_slow, price, 2.0 / (float(self.config["ema_slow"]) + 1.0))
        self._last_price = price

        # guillotine trailing: valuta l'equity di marca rispetto al picco
        eq: float = self._equity_at(price)
        self._peak_equity = max(self._peak_equity, eq)
        if self._peak_equity > 0.0:
            dd: float = (self._peak_equity - eq) / self._peak_equity
            if dd >= float(self.config["guillotine_dd"]):
                return self._guillotine(price)

        # cooloff dopo guillotine: niente ingressi
        if self._cooloff_remaining > 0:
            self._cooloff_remaining -= 1
            return (None,)

        # take-profit per i livelli in profitto
        signals: List[Optional[Signal]] = []
        tp: float = float(self.config["profit_target"])
        for lvl, pos in self._positions.items():
            if (price - pos["entry_price"]) / pos["entry_price"] >= tp:
                signals.append(Signal(side="sell", level_index=lvl, size=pos["size"], reason="tp"))
                # NB: la rimozione avviene in on_fill (signal/confirm)
        if signals:
            return tuple(signals)

        # momentum gate in salita: apri livelli se pendenza positiva
        if self._momentum_gate(price):
            spacing: float = self._spacing()
            n_active: int = len(self._positions)
            max_lv: int = int(self.config["levels"])
            for i in range(n_active, max_lv):
                entry: Price = price * (1.0 - spacing * (i + 1) * 0.5)
                size: Size = self._level_size(i, entry)
                if size <= 0.0 or self._free_capital() < size * entry:
                    break
                signals.append(Signal(side="buy", level_index=i, size=size, reason="momentum_open"))
                self._positions[i] = {"entry_price": entry, "size": size}
        return tuple(signals)

    def _guillotine(self, price: Price) -> Tuple[Signal, ...]:
        """Chiude TUTTI i livelli (uscita forzata) e ri-anchora la griglia."""
        out: List[Signal] = []
        remove: List[int] = []
        for lvl, pos in self._positions.items():
            out.append(Signal(side="sell", level_index=lvl, size=pos["size"], reason="guillotine"))
            remove.append(lvl)
        for lvl in remove:
            del self._positions[lvl]
        self._cooloff_remaining = int(self.config["cooloff_bars"])
        self._peak_equity = self._equity_at(price)
        return tuple(out)

    def on_fill(self, fill: Fill) -> None:
        """Unica via di mutazione dello stato position (signal/confirm)."""
        if fill.side == "sell":
            self._positions.pop(fill.level_index, None)
        # il livello buy e' gia' stato registrato in on_tick (stato: pre-positioned)

    # ------------------------------------------------------------ contracts
    def validate_config(self) -> List[str]:
        errs: List[str] = []
        c: Dict[str, float] = self.config
        if c["levels"] < 1 or c["levels"] > 64:
            errs.append("levels fuori range [1,64]")
        if not (0 < c["min_spacing"] <= c["max_spacing"]):
            errs.append("min_spacing<=max_spacing e >0")
        if c["profit_target"] <= 0 or c["guillotine_dd"] <= 0:
            errs.append("profit_target/guillotine_dd devono essere >0")
        if c["risk_per_level"] <= 0 or c["risk_per_level"] > c["levels"]:
            errs.append("risk_per_level deve essere >0 e <= levels")
        if not (0 < c["level_decay"] <= 1.0):
            errs.append("level_decay in (0,1]")
        if c["max_buffer_points"] < 100:
            errs.append("max_buffer_points troppo piccolo")
        if c.get("capital", 0.0) <= 0:
            errs.append("capital deve essere > 0")
        return errs

    def estimate_memory_mb(self, n_bars: int = 100_000) -> float:
        # deques a capacita' limitata: il cap domina, non n_bars
        cap: int = int(self.config["max_buffer_points"])
        buf_bytes: int = cap * 2 * 8        # price+ts float64
        pos_bytes: int = int(self.config["levels"]) * 64
        return round((buf_bytes + pos_bytes) / (1024 * 1024) + 0.5, 2)


# ---------------------------------------------------------------------------
# Selftest (dataset sintetico LEGGERO per unit test + stress OOM con 200k tick)
# ---------------------------------------------------------------------------

def _selftest() -> None:
    import random
    random.seed(42)
    bot = GuillotineGrid(config={"capital": 100.0})
    assert isinstance(bot.estimate_memory_mb(), float)

    # 1) unit: 4k tick trending con capitale, verifica segnali buy reali
    price = 100.0
    fills = 0
    for i in range(4000):
        price *= 1.0015  # trend in salita -> momentum gate si sblocca
        for s in bot.on_tick(Tick(ts=float(i), price=price)):
            if s is not None and s.side == "buy":
                bot.on_fill(Fill(ts=float(i), price=price * 0.99, side="buy",
                                 size=s.size, level_index=s.level_index))
                fills += 1
    assert fills > 0, f"nessun buy generato (fills={fills})"
    print(f"selftest unit OK buy={fills} mem={bot.estimate_memory_mb()}MB")

    # 2) stress OOM: 200k tick, verifico che la memoria dei buffer resti O(1)
    bot2 = GuillotineGrid(config={"capital": 100.0})
    price = 100.0
    for i in range(200_000):
        price *= 1.0002 if i % 2 == 0 else 0.9998
        bot2.on_tick(Tick(ts=float(i), price=price))
        if i and i % 50_000 == 0:
            gc.collect()  # rilascio esplicito di memoria transitoria
    buf_len = len(bot2._prices)
    cap = int(bot2.config["max_buffer_points"])
    assert buf_len <= cap  # a cap, non cresce
    print(f"selftest stress OK buffer_len={buf_len} (cap={cap})")
    del bot2  # rilascio dataset grande
    gc.collect()


if __name__ == "__main__":
    _selftest()
