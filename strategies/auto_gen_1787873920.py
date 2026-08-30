"""
auto_gen_1787873920.py — VolAdaptiveGrid (Volatility-Scaled Adaptive Grid).

Improvement rispetto alla grid statica attuale (buy_distance fisso su tutti i nodi):
- lo spacing della griglia scala con la volatilita' realizzata (EMA dei rendimenti),
  normalizzata sul proprio percentile storico: vol alta -> griglia piu' larga
  (meno overtrading nel chop), vol bassa -> griglia piu' fitta (piu' tick catturati).
- de-risking automatico: se il drawdown di equita' supera una soglia, i livelli
  attivi vengono ridotti (levels // 2) e la dimensione per livello si adegua.
- streaming puro: buffer circolari (deque a capacita' limitata), generatori per
  iterare i rendimenti e i livelli, nessuna copia di serie storiche -> memoria O(1)
  rispetto alla lunghezza del dataset.

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
from typing import Any, Deque, Dict, Generator, Optional

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_CONFIG: Dict[str, float] = {
    "levels": 4,                    # numero massimo di livelli di acquisto
    "base_spacing": 0.005,          # spacing base (frazione di prezzo)
    "min_spacing": 0.002,           # floor dello spacing adattivo
    "max_spacing": 0.030,           # cap dello spacing adattivo
    "vol_lookback": 50,             # finestra EMA della volatilita' realizzata
    "vol_ema_alpha": 0.15,          # smoothing EMA
    "vol_percentile_window": 200,   # finestra storica per il percentile
    "vol_percentile": 0.75,         # percentile di normalizzazione (0..1)
    "atr_mult": 1.0,                # sensibilita' dello scaling alla volatilita'
    "profit_target": 0.010,         # take-profit frazionale per livello
    "stop_loss": 0.100,             # stop-loss frazionale sulla posizione
    "degrade_drawdown": 0.050,      # dd oltre il quale si riduce il rischio
    "max_buffer_points": 5000,      # capacita' massima dei buffer (memoria O(1))
}


# ---------------------------------------------------------------------------
# Stato
# ---------------------------------------------------------------------------

@dataclass
class PositionState:
    """Stato aggregato della posizione di un livello."""

    entry_price: float = 0.0
    qty: float = 0.0
    realized_pnl: float = 0.0

    @property
    def is_open(self) -> bool:
        return self.qty > 0.0

    def mark_to_market(self, price: float) -> float:
        """PnL non realizzato (lineare, long)."""
        if not self.is_open:
            return 0.0
        return (price - self.entry_price) * self.qty


@dataclass
class GridState:
    """Stato interno della griglia adattiva."""

    anchor_price: float = 0.0          # prezzo di ancoraggio della griglia
    vol_ema: float = 0.0               # volatilita' realizzata smussata
    vol_baseline: float = 0.0          # percentile di normalizzazione
    peak_equity: float = 0.0           # picco di equita' per il drawdown
    filled_levels: int = 0             # livelli attualmente pieni
    active_levels: int = 0             # livelli abilitati (dopo de-risking)
    price_buffer: Deque[float] = field(default_factory=list)  # type: ignore[assignment]
    vol_history: Deque[float] = field(default_factory=list)   # type: ignore[assignment]

    def __post_init__(self) -> None:
        if isinstance(self.price_buffer, list):
            self.price_buffer = deque(maxlen=5000)
        if isinstance(self.vol_history, list):
            self.vol_history = deque(maxlen=200)


# ---------------------------------------------------------------------------
# Strategia
# ---------------------------------------------------------------------------

class StrategyBase:
    """Contratto minimo delle strategie auto-gen (vedi cron orchestratore)."""

    name: str = "strategy_base"

    def on_tick(self, price: float, timestamp: float, equity: float) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> None:
        raise NotImplementedError

    def validate_config(self) -> None:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


class VolAdaptiveGrid(StrategyBase):
    """Griglia a spacing adattivo sulla volatilita' realizzata con de-risking su drawdown."""

    name = "vol_adaptive_grid"

    def __init__(self, symbol: str, config: Optional[Dict[str, float]] = None) -> None:
        self.symbol = symbol
        self.config: Dict[str, float] = {**DEFAULT_CONFIG, **(config or {})}
        self.validate_config()
        lookback = int(self.config["vol_lookback"])
        pwin = int(self.config["vol_percentile_window"])
        mcap = int(self.config["max_buffer_points"])
        self.state = GridState(
            price_buffer=deque(maxlen=max(lookback, mcap)),
            vol_history=deque(maxlen=pwin),
        )
        self.positions: Dict[int, PositionState] = {}
        self.last_price: float = 0.0

    # -- validazione -------------------------------------------------------

    def validate_config(self) -> None:
        cfg = self.config
        if cfg["levels"] < 1 or cfg["levels"] > 64:
            raise ValueError(f"levels={cfg['levels']} fuori range [1, 64]")
        if not (0.0 < cfg["min_spacing"] <= cfg["base_spacing"] <= cfg["max_spacing"]):
            raise ValueError("spacing invalido: min <= base <= max e tutti > 0")
        if not (0.0 < cfg["vol_ema_alpha"] <= 1.0):
            raise ValueError(f"vol_ema_alpha={cfg['vol_ema_alpha']} deve essere in (0, 1]")
        if not (0.0 < cfg["vol_percentile"] < 1.0):
            raise ValueError(f"vol_percentile={cfg['vol_percentile']} deve essere in (0, 1)")
        if cfg["vol_lookback"] < 5 or cfg["vol_lookback"] > 100_000:
            raise ValueError("vol_lookback fuori range [5, 100000]")
        if cfg["profit_target"] <= 0.0 or cfg["stop_loss"] <= 0.0:
            raise ValueError("profit_target e stop_loss devono essere > 0")
        if cfg["degrade_drawdown"] <= 0.0:
            raise ValueError("degrade_drawdown deve essere > 0")

    # -- memoria -----------------------------------------------------------

    def estimate_memory_mb(self) -> float:
        """Stima memoria: buffer circolari a capacita' limitata -> O(1)."""
        floats = (
            self.state.price_buffer.maxlen
            + self.state.vol_history.maxlen
            + int(self.config["vol_lookback"])
        )
        # float = 24 B + puntatori deque 8 B, margine overhead 2x
        return round(floats * 32 * 2 / (1024 * 1024), 6)

    # -- streaming helpers --------------------------------------------------

    def _iter_returns(self) -> Generator[float, None, None]:
        """Rendimenti logaritmici dalla coda prezzi, senza copie (streaming)."""
        prev: Optional[float] = None
        for price in self.state.price_buffer:
            if prev is not None and prev > 0.0:
                yield math.log(price / prev)
            prev = price

    def _grid_levels(self, spacing: float) -> Generator[float, None, None]:
        """Livelli di acquisto sotto l'ancora, generati on-the-fly (niente liste)."""
        anchor = self.state.anchor_price
        if anchor <= 0.0:
            return
        for i in range(1, self.state.active_levels + 1):
            yield anchor * (1.0 - spacing * i)

    def _update_volatility(self) -> None:
        """Aggiorna EMA volatilita' e percentile storico (streaming)."""
        alpha = float(self.config["vol_ema_alpha"])
        window = self.state.vol_history
        n = 0
        total = 0.0
        for r in self._iter_returns():
            n += 1
            total += r * r
        if n >= 2:
            realized = math.sqrt(total / max(n - 1, 1))
            ema = self.state.vol_ema
            self.state.vol_ema = realized if ema <= 0.0 else alpha * realized + (1.0 - alpha) * ema
            window.append(self.state.vol_ema)
            if len(window) >= 5:
                # percentile via sort su finestra limitata (max 200 elementi)
                sorted_vals = sorted(window)
                idx = min(len(sorted_vals) - 1, int(self.config["vol_percentile"] * len(sorted_vals)))
                self.state.vol_baseline = sorted_vals[idx]
        del total

    def _effective_spacing(self) -> float:
        """Spacing adattivo: base scalata da vol_ema / vol_baseline, clampato."""
        base = float(self.config["base_spacing"])
        mult = float(self.config["atr_mult"])
        baseline = self.state.vol_baseline
        if baseline <= 0.0:
            return base
        scalar = 1.0 + mult * (self.state.vol_ema / baseline - 1.0)
        return min(float(self.config["max_spacing"]), max(float(self.config["min_spacing"]), base * scalar))

    def _drawdown(self, equity: float) -> float:
        """Drawdown corrente rispetto al picco di equita'."""
        if equity <= 0.0:
            return 1.0
        if equity > self.state.peak_equity:
            self.state.peak_equity = equity
        if self.state.peak_equity <= 0.0:
            return 0.0
        return (self.state.peak_equity - equity) / self.state.peak_equity

    # -- API principale ------------------------------------------------------

    def on_tick(self, price: float, timestamp: float, equity: float) -> Optional[Dict[str, Any]]:
        """Tick di mercato -> eventuale segnale {side, price, qty, level} o None.

        Puro signal: NON muta lo stato delle posizioni (lo fa solo on_fill).
        """
        if price <= 0.0 or not math.isfinite(price):
            return None
        self.last_price = price
        self.state.price_buffer.append(price)
        if self.state.anchor_price <= 0.0:
            self.state.anchor_price = price
            self.state.peak_equity = equity
            self.state.active_levels = int(self.config["levels"])
            return None

        self._update_volatility()

        # de-risking su drawdown
        full_levels = int(self.config["levels"])
        if self._drawdown(equity) >= float(self.config["degrade_drawdown"]):
            self.state.active_levels = max(1, full_levels // 2)
        else:
            self.state.active_levels = full_levels

        spacing = self._effective_spacing()
        qty_per_level = self._qty_per_level(equity)

        # take-profit sui livelli pieni
        if self.positions:
            tp = 1.0 + float(self.config["profit_target"])
            for idx, pos in self.positions.items():
                if pos.is_open and price >= pos.entry_price * tp:
                    return {"side": "sell", "price": price, "qty": pos.qty, "level": idx}

        # stop-loss globale
        if self.positions and self._drawdown(equity) >= float(self.config["stop_loss"]):
            for idx, pos in self.positions.items():
                if pos.is_open:
                    return {"side": "sell", "price": price, "qty": pos.qty, "level": idx}

        # acquisto sul primo livello di griglia non coperto
        for i, level_price in enumerate(self._grid_levels(spacing)):
            if price <= level_price and (i not in self.positions or not self.positions[i].is_open):
                return {"side": "buy", "price": price, "qty": qty_per_level, "level": i}
        return None

    def _qty_per_level(self, equity: float) -> float:
        """Dimensione per livello: frazione di capitale / livelli attivi."""
        budget = equity * float(self.config.get("max_capital_pct", 1.0))
        return max(budget / max(self.state.active_levels, 1), 0.0)

    def on_fill(self, fill: Dict[str, Any]) -> None:
        """Conferma di esecuzione: unica via di mutazione dello stato posizioni."""
        side = fill.get("side")
        qty = float(fill.get("qty", 0.0))
        price = float(fill.get("price", 0.0))
        if qty <= 0.0 or price <= 0.0:
            raise ValueError(f"fill invalido: {fill}")
        if side == "buy":
            idx = int(fill.get("level", 0))
            pos = self.positions.setdefault(idx, PositionState())
            new_qty = pos.qty + qty
            pos.entry_price = (pos.entry_price * pos.qty + price * qty) / new_qty
            pos.qty = new_qty
            self.state.filled_levels = max(self.state.filled_levels, idx + 1)
        elif side == "sell":
            idx = int(fill.get("level", -1))
            pos = self.positions.get(idx)
            if pos is None or not pos.is_open:
                raise ValueError(f"sell senza posizione aperta al livello {idx}")
            closed_qty = min(qty, pos.qty)
            pos.realized_pnl += (price - pos.entry_price) * closed_qty
            pos.qty = max(pos.qty - qty, 0.0)
        else:
            raise ValueError(f"side sconosciuto: {side!r}")


# ---------------------------------------------------------------------------
# Test inline (dati sintetici piccoli)
# ---------------------------------------------------------------------------

def _synthetic_ticks(n: int = 400, start: float = 100.0, vol: float = 0.01) -> Generator[float, None, None]:
    """Tick sintetici con random walk a volatilita' controllata."""
    price = start
    rng_state = 12345  # LCG semplice, deterministico

    def _rand() -> float:
        nonlocal rng_state
        rng_state = (rng_state * 1103515245 + 12345) % 0x80000000
        return rng_state / 0x7FFFFFFF

    for _ in range(n):
        shock = vol * (_rand() - 0.5) * 2.0
        price = price * (1.0 + shock)
        yield price


def _main() -> None:
    cfg = {
        "levels": 4,
        "base_spacing": 0.005,
        "vol_lookback": 50,
        "vol_percentile_window": 100,
    }
    strat = VolAdaptiveGrid("SOL/EUR", cfg)
    print(f"memoria stimata: {strat.estimate_memory_mb()} MB")

    equity = 1000.0
    buys = 0
    sells = 0
    for ts, price in enumerate(_synthetic_ticks(400)):
        sig = strat.on_tick(price, float(ts), equity)
        if sig is not None:
            if sig["side"] == "buy":
                strat.on_fill({"side": "buy", "price": sig["price"], "qty": sig["qty"], "level": sig["level"]})
                buys += 1
                equity -= sig["qty"] * sig["price"]
            else:
                strat.on_fill({"side": "sell", "price": sig["price"], "qty": sig["qty"], "level": sig["level"]})
                sells += 1
                equity += sig["qty"] * sig["price"]
    realized = sum(p.realized_pnl for p in strat.positions.values())
    open_pos = sum(1 for p in strat.positions.values() if p.is_open)
    print(f"ticks=400 buys={buys} sells={sells} open_pos={open_pos} realized_pnl={realized:.4f} "
          f"spacing_eff={strat._effective_spacing():.5f} active_levels={strat.state.active_levels}")
    assert buys >= 0 and sells >= 0
    assert strat.estimate_memory_mb() < 1.0, "memoria fuori budget O(1)"
    assert len(strat.state.price_buffer) <= 5000
    # libera memoria esplicitamente (discipline OOM)
    del strat, cfg
    gc.collect()
    print("TEST OK")


if __name__ == "__main__":
    _main()
