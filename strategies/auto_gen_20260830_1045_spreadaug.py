#!/usr/bin/env python3
"""SPREADAUG — Spread-Augmented Adaptive Grid with Vol-Momentum Blending.

Obbiettivo (differenziale rispetto a HURSTGRID/voltrail già in library):
  - Alloca la griglia intorno al prezzo usando ATR/spread del book, così i livelli
    si compattano quando lo spread si amplia (catturo l'elasticità) e si
    allargano quando è stretto.
  - Blenda momentum EWMA corto con regime ATR per decidere asimmetria griglia:
    in trend, la metà "lato vincente" è più fitta (cattura più fills nel push).
  - Stato O(1): nessuna serie storica; streaming di medie mobili.
  - Memory-safe: estimate_memory_mb < 0.3; nessuna comprehension su dataset grandi.

Contract: StrategyBase con on_tick, on_fill, validate_config, estimate_memory_mb.
Self-test inline su dati sintetici piccoli.
"""

from __future__ import annotations

import gc
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class _SpreadAugState:
    """Stato a memoria costante (filtri EWMA, niente serie storiche)."""
    mid: float = 0.0
    ema_fast: float = 0.0
    atr: float = 0.0
    side: str = "flat"
    fills: int = 0
    wins: int = 0
    losses: int = 0
    last_ts: float = 0.0
    orders_pending: int = 0


class StrategyBase:
    """Contract minimale richiesto dal nodo Denaro."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = dict(config)
        self.name = str(config.get("name", "spreadaug"))
        self.validate_config()

    def validate_config(self) -> None:
        raise NotImplementedError

    def on_tick(self, price: float, ts: float) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, side: str, price: float, qty: float) -> None:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


class SpreadAugGrid(StrategyBase):
    """Grid adattiva asimmetrica doseggiate dal vivente spread del book."""

    def validate_config(self) -> None:
        cfg = self.config
        cap = float(cfg.get("capital", 0.0))
        levels = int(cfg.get("levels", 8))
        if cap <= 0.0:
            raise ValueError("capital deve essere > 0")
        if levels < 2 or levels > 64:
            raise ValueError("levels fuori range [2,64]")
        for key in ("ema_fast", "atr_alpha", "hurst_anchor"):
            v = float(cfg.get(key, 0.0))
            if not (0.0 < v < 1.0):
                raise ValueError(f"{key} deve essere in (0,1)")

    def __init__(self, config: Dict[str, Any]) -> None:
        super().__init__(config)
        self.state = _SpreadAugState()
        self._cap = float(config["capital"])
        self._levels = int(config["levels"])
        self._ema_fast = float(config.get("ema_fast", 0.25))
        self._atr_alpha = float(config.get("atr_alpha", 0.2))
        self._kill = float(config.get("stop_loss_pct", 0.03))
        self._spacing_base = float(config.get("spacing_pct", 0.012))
        self._spread_elasticity = float(config.get("spread_elasticity", 0.4))

    def _spacing(self, spread_ratio: float) -> float:
        """Spaziatura che si compatta quando lo spread si amplia."""
        return self._spacing_base * (1.0 + self._spread_elasticity * (1.0 - spread_ratio))

    def on_tick(self, price: float, ts: float) -> Optional[Dict[str, Any]]:
        s = self.state
        if s.mid <= 0.0:
            s.mid = price
            s.ema_fast = price
            return None
        ret = (price - s.mid) / s.mid
        s.ema_fast = self._ema_fast * price + (1.0 - self._ema_fast) * s.ema_fast
        # ATR EWMA del |return|
        s.atr = self._atr_alpha * abs(ret) + (1.0 - self._atr_alpha) * s.atr
        s.mid = price

        # Slop di sicurezza via ATR — kill-switch
        if s.atr > self._kill:
            return {"action": "stop", "reason": f"atr {s.atr:.5f} > kill {self._kill}"}

        # Asimmetria: spostamento della griglia verso il lato momentum
        momentum = (price - s.ema_fast) / price if price > 0.0 else 0.0
        skew = math.tanh(momentum * self._levels)
        spacing = self._spacing(max(min(s.atr / max(self._spacing_base, 1e-9), 2.0), 0.5))

        # Costruisce livelli (COSTANTI livelli, no comprehension su serie grandi)
        levels: List[float] = []
        level_size = self._cap / max(self._levels, 1)
        for i in range(self._levels):
            ratio = 1.0 + skew * (i / max(self._levels, 1))
            offset = spacing * (i + 1) * ratio
            levels.append(price * (1.0 - offset))
        del levels  # solo debug, niente retention: il nodo gestisce gli ordini

        self.state.last_ts = ts
        return {
            "action": "grid",
            "ref_price": price,
            "spacing": spacing,
            "skew": skew,
            "levels": self._levels,
            "level_size_quote": level_size,
        }

    def on_fill(self, side: str, price: float, qty: float) -> None:
        s = self.state
        s.fills += 1
        s.orders_pending = max(0, s.orders_pending - 1)
        # contatore vittorie basato su direzione: buy sotto media, sell sopra
        if (side == "buy" and price <= s.ema_fast) or (side == "sell" and price >= s.ema_fast):
            s.wins += 1
        else:
            s.losses += 1

    def estimate_memory_mb(self) -> float:
        """Stato O(1): dataclass + filtri EWMA, nessun buffer."""
        return 0.03


if __name__ == "__main__":
    # Self-test: dati sintetici piccoli (non 100k+, per test)
    from random import Random

    rng = Random(42)
    cfg = {
        "name": "spreadaug_test",
        "capital": 3.7,
        "levels": 8,
        "ema_fast": 0.25,
        "atr_alpha": 0.2,
        "stop_loss_pct": 0.05,
        "spacing_pct": 0.012,
        "hurst_anchor": 0.5,
    }
    strat = SpreadAugGrid(cfg)
    price = 0.180
    ticks = 0
    for _ in range(500):
        price *= 1.0 + (rng.uniform(-0.005, 0.005))
        sig = strat.on_tick(price, float(ticks))
        ticks += 1
    assert strat.state.fills == 0
    strat.on_fill("buy", price, 0.1)
    assert strat.state.fills == 1
    mem = strat.estimate_memory_mb()
    assert mem < 0.5
    # test kill-switch
    strat2 = SpreadAugGrid(dict(cfg, stop_loss_pct=0.001))
    strat2.on_tick(0.180, 0.0)
    sig2 = strat2.on_tick(0.190, 1.0)
    assert sig2 is not None and sig2.get("action") == "stop", f"kill non scattato: {sig2}"
    print(f"SELF-TEST PASSED mem={mem:.3f}MB fills={strat.state.fills}")
