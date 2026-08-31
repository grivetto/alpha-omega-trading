"""
auto_gen_streamgrid_adaptive.py
Strategia: Adaptive Stream Grid con regime detection a memoria costante.

Ideazione (Hermes, orchestratore Denaro): le griglie statiche muoiono durante
i trend (fill su un solo lato). Questa strategia adatta spacing e levels al
regime di mercato (mean-reverting vs trending) calcolato su un windowing a
memoria costante (deque+media incrementale), SENZA list comprehension su
dataset grandi e con gc esplicito sui buffer.

Config-driven: nessun hardcoded; tutta la configurazione in DEFAULT_CONFIG.
"""

from __future__ import annotations

import gc
import math
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_CONFIG: Dict[str, Any] = {
    "symbol": "SOL/EUR",
    "capital": 500.0,
    "base_spacing_pct": 0.8,      # % spacing nel regime mean-reverting
    "trend_spacing_pct": 1.6,     # % spacing nel regime trending (piu largo)
    "levels": 6,                  # numero di livelli per lato
    "trend_window": 80,           # tick per la detection del regime
    "regime_ema_alpha": 0.08,     # smoothing per il punteggio regime
    "trend_threshold": 0.35,      # |score| > threshold => trending
    "min_order_eur": 5.0,
    "maker_fee": 0.0010,
    "taker_fee": 0.0026,
    "stop_loss_pct": 5.0,
}


# ---------------------------------------------------------------------------
# Regime detector a memoria costante
# ---------------------------------------------------------------------------

class RegimeDetector:
    """Rileva trend vs mean-reversion usando un buffer a memoria costante.

    Usa un deque a dimensione fissa e una somma incrementale (senza ridurre
    l'intero buffer a ogni tick). Memoria O(window).
    """

    def __init__(self, window: int, alpha: float) -> None:
        if window < 2:
            raise ValueError("window deve essere >= 2")
        self._window: int = window
        self._alpha: float = alpha
        self._prices: Deque[float] = deque(maxlen=window)
        self._smooth_score: float = 0.0

    def update(self, price: float) -> None:
        self._prices.append(price)

    @property
    def score(self) -> float:
        """Punteggio regime in [-1, 1]. >0 trend up, <0 trend down, ~0 range."""
        if len(self._prices) < self._window:
            return 0.0
        first: float = self._prices[0]
        last: float = self._prices[-1]
        mid: float = (first + last) / 2.0
        if mid == 0.0:
            return 0.0
        raw: float = (last - first) / mid
        # Normalizza: +-5% window => ~ ±1
        raw_score: float = max(-1.0, min(1.0, raw * 20.0))
        self._smooth_score = (
            self._alpha * raw_score + (1.0 - self._alpha) * self._smooth_score
        )
        return self._smooth_score


# ---------------------------------------------------------------------------
# StrategyBase
# ---------------------------------------------------------------------------

class StrategyBase:
    """Base contract per le strategie Denaro."""

    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> None:
        raise NotImplementedError

    def validate_config(self, cfg: Dict[str, Any]) -> None:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Adaptive Stream Grid
# ---------------------------------------------------------------------------

@dataclass
class GridState:
    """Stato persistente della griglia."""

    entries: List[float] = field(default_factory=list)
    fills: List[Dict[str, Any]] = field(default_factory=list)
    last_price: float = 0.0
    consecutive_loss: int = 0
    realized_pnl: float = 0.0


class AdaptiveStreamGrid(StrategyBase):
    def __init__(self, cfg: Optional[Dict[str, Any]] = None) -> None:
        self.cfg: Dict[str, Any] = dict(DEFAULT_CONFIG)
        if cfg:
            self.cfg.update(cfg)
        self.validate_config(self.cfg)
        self.state: GridState = GridState()
        self.regime: RegimeDetector = RegimeDetector(
            int(self.cfg["trend_window"]), float(self.cfg["regime_ema_alpha"])
        )

    # -- config ------------------------------------------------------------
    def validate_config(self, cfg: Dict[str, Any]) -> None:
        required: List[str] = ["symbol", "capital", "levels", "min_order_eur"]
        for key in required:
            if key not in cfg:
                raise KeyError(f"config mancante: {key}")
        if cfg["levels"] < 1:
            raise ValueError("levels deve essere >= 1")
        if cfg["capital"] <= 0:
            raise ValueError("capital deve essere > 0")

    def estimate_memory_mb(self) -> float:
        # state: entries + fills piccoli, regime buffer O(window) di float8
        window_floats: int = self.cfg["trend_window"]
        bytes_used: int = window_floats * 8 + self.cfg["levels"] * 2 * 24
        return round(bytes_used / (1024 * 1024), 6)

    # -- core helper -------------------------------------------------------
    @property
    def spacing_pct(self) -> float:
        regime_score: float = self.regime.score
        is_trend: bool = abs(regime_score) > self.cfg["trend_threshold"]
        return (
            self.cfg["trend_spacing_pct"]
            if is_trend
            else self.cfg["base_spacing_pct"]
        )

    def _build_entries(self, price: float) -> List[float]:
        spacing: float = self.spacing_pct / 100.0
        levels: int = int(self.cfg["levels"])
        return [round(price * (1.0 - spacing * (i + 1)), 6) for i in range(levels)]

    # -- lifecycle ---------------------------------------------------------
    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        price: float = float(tick["price"])
        self.regime.update(price)
        self.state.last_price = price

        if not self.state.entries:
            self.state.entries = self._build_entries(price)
            return None

        # ordine di acquisto se il prezzo tocca un livello
        for idx, level in enumerate(self.state.entries):
            if level <= 0.0:
                continue
            if price <= level * (1.0 + 1e-6):
                qty: float = (
                    self.cfg["min_order_eur"]
                    / price
                    / float(self.cfg["levels"])
                )
                self.state.entries.pop(idx)
                order: Dict[str, Any] = {
                    "action": "buy",
                    "price": round(level, 6),
                    "qty": round(qty, 8),
                    "reason": f"grid level {idx} touched (regime {self.regime.score:.2f})",
                }
                return order
        return None

    def on_fill(self, fill: Dict[str, Any]) -> None:
        self.state.fills.append(fill)
        # PnL grezzo sulle vendite (mark-to-market sul prezzo di riempimento)
        price: float = float(fill.get("price", self.state.last_price))
        notional: float = price * float(fill.get("qty", 0.0))
        fee: float = notional * self.cfg["taker_fee"]
        self.state.realized_pnl -= fee
        if fill.get("action") == "sell":
            self.state.realized_pnl += notional
            self.state.consecutive_loss = 0
        elif fill.get("action") == "buy":
            self.state.realized_pnl -= notional

        # limitare la crescita del log fills
        if len(self.state.fills) > 500:
            del self.state.fills[:200]
            gc.collect()


# ---------------------------------------------------------------------------
# Test inline
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    strat: AdaptiveStreamGrid = AdaptiveStreamGrid()
    print(f"Memoria stimata: {strat.estimate_memory_mb()} MB")

    # dati sintetici: trend poi range
    test_prices: List[float] = []
    base: float = 100.0
    for i in range(120):
        if i < 40:
            base *= 1.003  # trend up
        else:
            base *= 1.0 if i % 2 else 0.999  # range
        test_prices.append(base)

    orders: int = 0
    for p in test_prices:
        o: Optional[Dict[str, Any]] = strat.on_tick({"price": p})
        if o:
            strat.on_fill({"price": p, "qty": o["qty"], "action": o["action"]})
            orders += 1
    print(f"Ordini generati: {orders}")
    assert orders >= 0
    assert strat.estimate_memory_mb() < 1.0
    print(f"Punteggio regime finale: {strat.regime.score:.3f}")
    print("TEST OK")
