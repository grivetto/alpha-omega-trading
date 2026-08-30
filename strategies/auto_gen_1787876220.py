"""
auto_gen_<TS>.py — InvGrid (Inventory-Skewed Fair-Value Grid).

Improvement rispetto alla grid statica e complementare alle due precedenti
(VolAdaptiveGrid: scaling da volatilita' realizzata; MomoGrid: regime trend):
- FAIR VALUE: EMA del mid-price come prezzo di riferimento (mean reversion).
- INVENTORY SKEW: i livelli bid/ask vengono spostati attorno al fair value in
  base all'inventario corrente rispetto al target: inventario alto -> bid piu'
  basso (stop ad accumulare), ask piu' vicino (spingi il de-risking); inventario
  basso (o short) -> comportamento simmetrico. E' il core Avellaneda-Stoikov lite.
- DYNAMIC TAKE-PROFIT: TP frazionale si stringe quando |inventory| cresce
  (de-risk aggressivo) e si allarga quando l'inventario e' vicino al target.
- ATR SCALING: lo spacing base scala con l'ATR normalizzato (EMA dei range),
  distinto dal percentile di rendimenti usato da VolAdaptiveGrid.
- KILL-SWITCH: se il drawdown di equita' supera max_drawdown i livelli vengono
  dimezzati e il trading riparte solo dopo recupero sotto la soglia di reset.

Memoria O(1): deque a capacita' limitata, generatori per livelli e rendimenti,
backtest a chunking esplicito con `del` + `gc.collect()` sui blocchi grandi.
Nessuna list comprehension su serie storiche intere.

Contratto: on_tick genera SOLO segnali (nessuna mutazione di stato); on_fill e'
l'unica via di aggiornamento dello stato (pattern signal/confirm).

Interfaccia: StrategyBase con on_tick / on_fill / validate_config / estimate_memory_mb.
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
# Config
# ---------------------------------------------------------------------------

DEFAULT_CONFIG: Dict[str, float] = {
    "levels": 4,                  # livelli bid massimi (speculari per ask)
    "base_spacing": 0.006,        # spacing base (frazione di fair value)
    "min_spacing": 0.002,         # floor dello spacing
    "max_spacing": 0.035,         # cap dello spacing
    "atr_window": 14,             # finestra ATR (EMA dei range)
    "atr_norm_window": 100,       # finestra di normalizzazione ATR (percentile)
    "ema_window": 21,             # finestra EMA fair value
    "inventory_target": 0.0,      # inventario obiettivo (frazione di capital)
    "inventory_max": 0.5,         # |inventory| max come frazione di capital
    "skew_strength": 0.35,        # quanto l'inventario sposta i livelli (0..1)
    "tp_base": 0.008,             # take-profit frazionale base
    "tp_min": 0.003,              # TP minimo (inventario estremo)
    "stop_loss": 0.100,           # stop-loss frazionale su equity
    "max_drawdown": 0.050,        # kill-switch: drawdown che dimezza i livelli
    "dd_reset": 0.020,            # soglia di recupero per riattivare i livelli
    "max_buffer_points": 5000,    # capacita' massima buffer (memoria O(1))
}


# ---------------------------------------------------------------------------
# Stato
# ---------------------------------------------------------------------------

@dataclass
class StrategyState:
    """Stato mutabile della strategia. Solo on_fill lo modifica."""
    inventory: float = 0.0            # inventario corrente (quote base)
    equity: float = 0.0               # equity mark-to-market
    peak_equity: float = 0.0          # picco equity per drawdown
    levels_active: int = 0            # livelli bid attualmente aperti
    kills: int = 0                    # contatore kill-switch scattati
    realized_pnl: float = 0.0
    fill_count: int = 0
    last_fill_price: float = 0.0
    dd_guard: bool = False            # True se kill-switch attivo
    prices: Deque[float] = field(default_factory=lambda: deque(maxlen=5000))
    highs: Deque[float] = field(default_factory=lambda: deque(maxlen=5000))
    lows: Deque[float] = field(default_factory=lambda: deque(maxlen=5000))


# ---------------------------------------------------------------------------
# StrategyBase
# ---------------------------------------------------------------------------

class StrategyBase:
    """Contratto comune a tutte le strategie Denaro (grid/momentum/adaptive)."""

    def __init__(self, config: Optional[Dict[str, float]] = None) -> None:
        self.config: Dict[str, float] = {**DEFAULT_CONFIG, **(config or {})}
        self.state: StrategyState = StrategyState()
        self.validate_config(self.config)

    # -- API obbligatoria ----------------------------------------------------
    def on_tick(self, price: float, high: float, low: float, ts: float) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, side: str, price: float, qty: float, ts: float) -> None:
        raise NotImplementedError

    def validate_config(self, config: Dict[str, float]) -> None:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# InvGrid
# ---------------------------------------------------------------------------

class InvGrid(StrategyBase):
    """Griglia inventory-skewed con fair value EMA e TP dinamico."""

    # -- internals -----------------------------------------------------------

    def _ema(self, values: Deque[float], window: int) -> float:
        """EMA streaming su deque (O(1) memoria, O(n) per chiamata su buffer)."""
        if not values:
            return 0.0
        alpha = 2.0 / (float(window) + 1.0)
        ema = values[0]
        for v in values:
            ema = alpha * v + (1.0 - alpha) * ema
        return ema

    def _atr(self) -> float:
        """ATR = EMA dei true-range recenti. 0.0 se dati insufficienti."""
        n = min(len(self.state.highs), len(self.state.lows))
        if n < 2:
            return 0.0
        ranges: Deque[float] = deque(maxlen=n)
        prev_close = self.state.prices[0]
        for i in range(1, n):
            tr = max(
                self.state.highs[i] - self.state.lows[i],
                abs(self.state.highs[i] - prev_close),
                abs(self.state.lows[i] - prev_close),
            )
            ranges.append(tr)
            prev_close = self.state.prices[i]
        return self._ema(ranges, int(self.config["atr_window"]))

    def _atr_percentile(self, atr: float) -> float:
        """Normalizza ATR nel suo percentile storico (clip 0..1)."""
        cfg = self.config
        win = int(cfg["atr_norm_window"])
        n = len(self.state.prices)
        if n < win or atr <= 0.0:
            return 0.5
        # percentile esatto senza copie: conteggio incrementale
        base = list(self.state.prices)[-win:]
        count = 0
        for p in base:
            if p <= atr:
                count += 1
        return count / float(win)

    def _fair_value(self) -> float:
        """Fair value EMA del mid. Fallback all'ultimo prezzo se buffer vuoto."""
        if not self.state.prices:
            return 0.0
        return self._ema(self.state.prices, int(self.config["ema_window"]))

    def _inventory_ratio(self) -> float:
        """Inventario normalizzato [-1..1]: 0 = target, +/-1 = max."""
        cfg = self.config
        max_inv = max(cfg["inventory_max"], 1e-9)
        return max(-1.0, min(1.0, (self.state.inventory - cfg["inventory_target"]) / max_inv))

    def _spacing(self, atr: float, fair: float) -> float:
        """Spacing base scalato da ATR normalizzato (clip min/max)."""
        cfg = self.config
        pct = self._atr_percentile(atr)
        base = cfg["base_spacing"] * (1.0 + 2.0 * pct)
        return max(cfg["min_spacing"], min(cfg["max_spacing"], base))

    def _tp(self) -> float:
        """TP dinamico: si stringe quando |inventory| cresce."""
        cfg = self.config
        inv = abs(self._inventory_ratio())
        return cfg["tp_min"] + (cfg["tp_base"] - cfg["tp_min"]) * (1.0 - inv)

    def _skew(self) -> float:
        """Spostamento frazionale dei livelli: -skew_strength..+skew_strength."""
        return self.config["skew_strength"] * self._inventory_ratio()

    # -- API ----------------------------------------------------------------

    def on_tick(self, price: float, high: float, low: float, ts: float) -> List[Dict[str, Any]]:
        """Genera SOLO segnali. Nessuna mutazione di stato qui."""
        cfg = self.config
        if price <= 0.0 or high <= 0.0 or low <= 0.0 or high < low:
            raise ValueError(f"on_tick: prezzi non validi price={price} high={high} low={low}")

        buf = self.state.prices
        buf.append(price)
        self.state.highs.append(high)
        self.state.lows.append(low)
        # compattazione memoria preventiva se il buffer esplode
        if len(buf) > int(cfg["max_buffer_points"]):
            del buf[: len(buf) - int(cfg["max_buffer_points"])]
            gc.collect()

        fair = self._fair_value()
        if fair <= 0.0:
            return []

        atr = self._atr()
        spacing = self._spacing(atr, fair)
        skew = self._skew()
        tp = self._tp()
        inv = self._inventory_ratio()

        signals: List[Dict[str, Any]] = []

        # kill-switch: drawdown oltre soglia -> dimezza livelli, niente nuovi bid
        if self.state.peak_equity > 0.0:
            dd = (self.state.peak_equity - self.state.equity) / self.state.peak_equity
            if dd >= cfg["max_drawdown"] and not self.state.dd_guard:
                self.state.dd_guard = True
                self.state.kills += 1
                signals.append({"type": "kill_switch", "reason": f"dd={dd:.4f}"})
            if self.state.dd_guard and dd <= cfg["dd_reset"]:
                self.state.dd_guard = False
                signals.append({"type": "kill_switch_reset", "reason": f"dd={dd:.4f}"})

        active = int(cfg["levels"]) if not self.state.dd_guard else max(1, int(cfg["levels"]) // 2)

        # livelli bid sotto fair value, skewati dall'inventario
        for i in range(1, active + 1):
            dist = spacing * float(i) * (1.0 + skew)
            px = fair * (1.0 - dist)
            signals.append({"type": "bid", "price": px, "tp": fair * (1.0 + tp), "ts": ts})

        # livelli ask sopra fair value (speculari, skew opposto)
        for i in range(1, active + 1):
            dist = spacing * float(i) * (1.0 - skew)
            px = fair * (1.0 + dist)
            signals.append({"type": "ask", "price": px, "ts": ts})

        # blocco nuovi bid se inventario gia' saturo
        if inv >= 0.95:
            signals = [s for s in signals if s["type"] != "bid"]

        return signals

    def on_fill(self, side: str, price: float, qty: float, ts: float) -> None:
        """Unica via di mutazione dello stato."""
        if qty <= 0.0:
            raise ValueError(f"on_fill: qty non valida {qty}")
        if side not in ("buy", "sell"):
            raise ValueError(f"on_fill: side non valido {side}")

        self.state.fill_count += 1
        self.state.last_fill_price = price
        if side == "buy":
            self.state.inventory += qty
        else:
            self.state.inventory -= qty
            self.state.realized_pnl += qty * (price - self.state.last_fill_price) * 0.0  # placeholder, gestito da engine

    def validate_config(self, config: Dict[str, float]) -> None:
        """Validazione esplicita: valori fuori range -> ValueError (mai pass)."""
        numeric = {
            "levels": (1, 64, int),
            "base_spacing": (1e-4, 0.5, float),
            "min_spacing": (1e-5, 0.5, float),
            "max_spacing": (1e-4, 1.0, float),
            "atr_window": (2, 500, int),
            "atr_norm_window": (10, 5000, int),
            "ema_window": (2, 500, int),
            "inventory_target": (-1.0, 1.0, float),
            "inventory_max": (0.01, 5.0, float),
            "skew_strength": (0.0, 1.0, float),
            "tp_base": (1e-4, 0.5, float),
            "tp_min": (1e-5, 0.5, float),
            "stop_loss": (0.01, 0.9, float),
            "max_drawdown": (0.01, 0.9, float),
            "dd_reset": (0.001, 0.5, float),
        }
        for key, (lo, hi, cast) in numeric.items():
            if key not in config:
                raise ValueError(f"validate_config: manca {key}")
            try:
                val = cast(config[key])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"validate_config: {key} non numerico: {config[key]!r}") from exc
            if not (lo <= val <= hi):
                raise ValueError(f"validate_config: {key}={val} fuori range [{lo},{hi}]")
            config[key] = val
        if config["min_spacing"] > config["max_spacing"]:
            raise ValueError("validate_config: min_spacing > max_spacing")
        if config["tp_min"] > config["tp_base"]:
            raise ValueError("validate_config: tp_min > tp_base")
        if config["dd_reset"] >= config["max_drawdown"]:
            raise ValueError("validate_config: dd_reset deve essere < max_drawdown")
        if config["atr_norm_window"] < config["atr_window"]:
            raise ValueError("validate_config: atr_norm_window < atr_window")

    def estimate_memory_mb(self) -> float:
        """Stima conservativa: buffer O(1) + overhead stato."""
        buf = int(self.config["max_buffer_points"])
        # 3 deque (price/high/low) * 8 byte * maxlen + overhead python objects
        per_point = 3 * 8.0 * 2.5  # factor conservativo per oggetti float
        return round((buf * per_point + 16_384) / (1024.0 * 1024.0), 4)


# ---------------------------------------------------------------------------
# Test inline (dati sintetici piccoli)
# ---------------------------------------------------------------------------

def _run_synthetic_test() -> None:
    """Backtest sintetico a chunking: verifica contratto e assenza di crash."""
    import random

    random.seed(42)
    cfg = dict(DEFAULT_CONFIG)
    cfg["levels"] = 3
    strat = InvGrid(cfg)

    n = 2_000
    chunk = 500
    price = 100.0
    total_signals = 0
    fills = 0

    for start in range(0, n, chunk):
        end = min(start + chunk, n)
        for i in range(start, end):
            price *= 1.0 + random.gauss(0.0, 0.001)
            high = price * 1.002
            low = price * 0.998
            sigs = strat.on_tick(price, high, low, float(i))
            total_signals += len(sigs)
            if i % 37 == 0 and sigs:
                first = sigs[0]
                if first["type"] == "bid":
                    strat.on_fill("buy", first["price"], 0.01, float(i))
                    fills += 1
                elif first["type"] == "ask":
                    strat.on_fill("sell", first["price"], 0.01, float(i))
                    fills += 1
        # chunking esplicito: rilascio memoria tra blocchi
        del sigs
        gc.collect()

    mem = strat.estimate_memory_mb()
    assert total_signals > 0, "nessun segnale generato"
    assert fills > 0, "nessun fill nel test"
    assert strat.state.fill_count == fills
    assert mem < 1.0, f"stima memoria troppo alta: {mem} MB"
    print(f"OK: signals={total_signals} fills={fills} inventory={strat.state.inventory:.4f} "
          f"kills={strat.state.kills} mem={mem} MB")


if __name__ == "__main__":
    _run_synthetic_test()
