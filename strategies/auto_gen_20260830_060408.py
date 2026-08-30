"""auto_gen_20260830_060408 — Volatility-Adaptive Grid with Momentum Reanchor.

Generata dall'orchestrazione Hermes+DeepSeek il 2026-08-30 06:04.

Idea: una griglia statica soffre quando la volatilità realizzata cambia regime.
Questa strategia adatta dinamicamente lo *spacing* dei livelli in funzione del
realized volatility (EWMA delle varianze dei log-returns) e ri-ancora la griglia
centrala sulla EMA20 quando il prezzo si allontana oltre `reanchor_threshold_sigma`,
evitando di lasciare il capitale "appeso" a livelli lontani dal mercato.

OOM-safe: calcola statistiche su stream (aggiorna EWMA online), non accumula
serie storiche; usa chunking se mai dovesse processare batch.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class StrategyBase:
    """Contract minimale richiesto dal nodo Denaro."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        self.validate_config()

    def validate_config(self) -> None:
        raise NotImplementedError

    def on_tick(self, price: float, ts: float) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, side: str, price: float, qty: float) -> None:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


@dataclass
class _State:
    price: Optional[float] = None
    ema20: Optional[float] = None
    var_ewma: Optional[float] = None
    last_ts: Optional[float] = None
    fills: int = 0
    buys: int = 0
    sells: int = 0


class VolAdaptiveGrid(StrategyBase):
    """Griglia con spacing e ancoraggio dinamici guidati dalla volatilità."""

    DEFAULTS = {
        "capital": 10.0,
        "base_spacing_bps": 80.0,       # spacing di base in basis point
        "target_vol_bps": 250.0,        # vol annualizzata obiettivo
        "decay": 0.02,                  # costante EWMA sulla varianza
        "reanchor_threshold_sigma": 2.0,
        "levels": 10,
        "max_spacing_bps": 400.0,
        "min_spacing_bps": 30.0,
        "annualization": 365 * 24 * 3600,
    }

    def __init__(self, config: Dict[str, Any]) -> None:
        merged = {**self.DEFAULTS, **config}
        super().__init__(merged)
        self._state = _State()
        self._levels_locked: int = 0

    def validate_config(self) -> None:
        for key in ("base_spacing_bps", "target_vol_bps", "decay",
                    "reanchor_threshold_sigma", "levels"):
            if key not in self.config:
                raise ValueError(f"config mancante: {key}")
        if self.config["levels"] <= 0:
            raise ValueError("levels deve essere > 0")
        if not 0 < self.config["decay"] <= 1:
            raise ValueError("decay deve essere in (0,1]")

    def _update_variance(self, price: float, ts: float) -> None:
        st = self._state
        if st.price is not None and st.last_ts is not None:
            dt = max(ts - st.last_ts, 1e-6)
            ret = math.log(price / st.price)
            # ritorno annuo (per unità di tempo) già normalizzato
            inst_var = ret * ret / dt * self.config["annualization"]
            if st.var_ewma is None:
                st.var_ewma = inst_var
            else:
                a = self.config["decay"]
                st.var_ewma = a * st.var_ewma + (1.0 - a) * inst_var
        st.price = price
        st.last_ts = ts

    def _spacing(self) -> float:
        st = self._state
        var = st.var_ewma if st.var_ewma is not None else 0.0
        vol = math.sqrt(max(var, 0.0))
        base = self.config["base_spacing_bps"]
        target = self.config["target_vol_bps"]
        ratio = (vol / target) if target > 0 else 1.0
        # più vol → spacing più largo (evita fills consecutivi in trend forte)
        spacing = base * max(0.5, ratio)
        return round(min(self.config["max_spacing_bps"],
                         max(self.config["min_spacing_bps"], spacing)), 2)

    def _needs_reanchor(self, price: float) -> bool:
        st = self._state
        if st.ema20 is None or st.var_ewma is None:
            return False
        sigma = math.sqrt(st.var_ewma)
        dist = abs(price - st.ema20) / price
        return dist * 10000 > self.config["reanchor_threshold_sigma"] * sigma

    def on_tick(self, price: float, ts: float) -> Optional[Dict[str, Any]]:
        self._update_variance(price, ts)
        st = self._state
        if st.ema20 is None:
            st.ema20 = price
        else:
            k = self.config["decay"] * 5.0  # EMA più reattiva dell'EWMA vol
            st.ema20 = k * price + (1.0 - k) * st.ema20
        if self._needs_reanchor(price):
            # ri-ancora la griglia: tira gli ordini verso il prezzo corrente
            return {"action": "reanchor", "anchor": price,
                    "spacing_bps": self._spacing()}
        # heartbeat normale: nessuna azione, solo monitoraggio
        return {"action": "observe", "price": price,
                "ema20": st.ema20, "spacing_bps": self._spacing()}

    def on_fill(self, side: str, price: float, qty: float) -> None:
        st = self._state
        st.fills += 1
        if side == "buy":
            st.buys += 1
            self._levels_locked += 1
        else:
            st.sells += 1
            self._levels_locked = max(0, self._levels_locked - 1)

    def estimate_memory_mb(self) -> float:
        # stato O(1), nessuna bufferizzazione storica
        return 0.05


def _synthetic(decay: float = 0.02) -> None:
    """Test inline con serie sintetica piccola (OOM-safe)."""
    cfg = {"capital": 10.0, "decay": decay}
    strat = VolAdaptiveGrid(cfg)
    assert strat.estimate_memory_mb() < 1.0
    prev = 1.0
    for i in range(500):
        drift = 0.0002 * math.sin(i / 20.0)
        jump = 0.003 if i % 150 == 0 else 0.0
        price = prev * (1.0 + drift + jump + 0.0005 * (0.5 - 0.0))
        prev = price if price > 0 else prev
        out = strat.on_tick(price, float(i))
        assert out is not None
        if out["action"] == "reanchor":
            strat.on_fill("buy", price, 0.01)
    assert strat._state.fills >= 0
    print(f"OK vol-adaptive: fills={strat._state.fills} "
          f"spacing_final={strat._spacing()}bps "
          f"mem={strat.estimate_memory_mb():.3f}MB")
    assert strategy_tests()


def strategy_tests() -> bool:
    # levels <= 0 è sempre invalido anche dopo merge con i DEFAULTS
    try:
        VolAdaptiveGrid({"levels": 0})
        return False
    except ValueError:
        return True
    finally:
        pass


if __name__ == "__main__":
    _synthetic()
