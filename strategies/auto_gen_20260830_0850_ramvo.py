"""auto_gen_20260830_0850_ramvo.py — RAMVO (Regime-Adaptive Momentum with Volatility-Scaled Positioning).

Obbiettivo: catturare trend persistenti su SOL/DOGE filtrando il chop con un
filtro di regime e dimensionando la posizione in modo inversamente proporzionale
alla volatilità realizzata (rallentare la rotazione in regime rumoroso).

Differenziali rispetto alla library corrente:
  - Doppio EWMA (fast/slow) per il segnale di tendenza -> meno falsi cross.
  - Filtro di regime ATR% : sopra soglia -> widens stop e riduce leva.
  - Streak counter per evitare rientri multipli nella stessa direzione.
  - Stato O(1): nessuna serie storica conservata (memory-safe).

Memory: O(1) -> estimate_memory_mb ~ 0.2.
"""
from __future__ import annotations

import gc
import math
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class _RamvoState:
    """Stato interno a memoria costante (nessuna lista storica)."""
    price: Optional[float] = None
    fast_ema: Optional[float] = None
    slow_ema: Optional[float] = None
    atr: Optional[float] = None
    side: str = "flat"
    streak: int = 0
    fills: int = 0
    wins: int = 0
    losses: int = 0
    last_ts: float = 0.0


class StrategyBase:
    """Contract minimale richiesto dal nodo Denaro."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = dict(config)
        self.validate_config()

    def validate_config(self) -> None:
        raise NotImplementedError

    def on_tick(self, price: float, ts: float) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, side: str, price: float, qty: float) -> None:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


class RAMVO(StrategyBase):
    """Regime-Adaptive Momentum with Volatility-Scaled sizing."""

    def __init__(self, config: Dict[str, Any]) -> None:
        super().__init__(config)
        self.state = _RamvoState()
        self._e = 1e-9  # epsilon anti-zerodivision

    # ------------------------------------------------------------------ API
    def validate_config(self) -> None:
        c = self.config
        required = ("capital", "fast_span", "slow_span", "atr_period",
                    "atr_thresh", "base_stop_pct", "max_leverage")
        missing = [k for k in required if k not in c]
        if missing:
            raise ValueError(f"RAMVO config mancanti: {missing}")
        if c["fast_span"] >= c["slow_span"]:
            raise ValueError("fast_span deve essere < slow_span")
        if c["atr_thresh"] <= 0 or c["base_stop_pct"] <= 0:
            raise ValueError("soglie devono essere positive")
        if not (0 < c["max_leverage"] <= 20):
            raise ValueError("max_leverage fuori range (1..20)")

    def on_tick(self, price: float, ts: float) -> Optional[Dict[str, Any]]:
        cfg = self.config
        st = self.state

        # --- aggiornamento EWMA + ATR (streaming, O(1)) ------------------
        if st.price is not None:
            a_fast = 2.0 / (cfg["fast_span"] + 1.0)
            a_slow = 2.0 / (cfg["slow_span"] + 1.0)
            st.fast_ema = (price * a_fast) + st.fast_ema * (1.0 - a_fast)
            st.slow_ema = (price * a_slow) + st.slow_ema * (1.0 - a_slow)
            rng = abs(price - st.price)
            a_atr = 2.0 / (cfg["atr_period"] + 1.0)
            st.atr = (rng * a_atr + st.atr * (1.0 - a_atr)) if st.atr is not None else rng
        else:
            st.fast_ema = price
            st.slow_ema = price
            st.atr = 0.0

        st.price = price
        st.last_ts = ts

        if st.fast_ema is None or st.slow_ema is None or st.atr is None:
            return None

        # --- regime & vol-scaled sizing ---------------------------------
        atr_pct = st.atr / (price + self._e)
        high_vol = atr_pct > cfg["atr_thresh"]
        vol_scale = 1.0 / (1.0 + atr_pct / (cfg["atr_thresh"] + self._e)) if high_vol else 1.0

        pos_size = cfg["capital"] * cfg["max_leverage"] * vol_scale
        stop_pct = cfg["base_stop_pct"] * (2.0 if high_vol else 1.0)

        delta = st.fast_ema - st.slow_ema
        span = max(st.slow_ema * 1e-4, self._e)
        mom = delta / span  # momentum normalizzato

        signal: Optional[Dict[str, Any]] = None
        target = "flat"
        if mom > 0.05 and st.streak < 4:
            target = "long"
        elif mom < -0.05 and st.streak > -4:
            target = "short"

        if target != st.side:
            st.side = target
            st.streak = st.streak + 1 if (target == "long") else st.streak - 1
            qty = pos_size / (price + self._e)
            signal = {
                "action": "enter" if target != "flat" else "exit",
                "side": target,
                "qty": qty,
                "stop_pct": stop_pct,
                "reason": f"mom={mom:.3f} atr%={atr_pct:.4f} vol_scale={vol_scale:.2f}",
            }

        del mom, span
        if gc.isenabled():
            gc.collect()
        return signal

    def on_fill(self, side: str, price: float, qty: float) -> None:
        self.state.fills += 1
        # bookkeeping win/loss semplificato lato orchestratore

    def estimate_memory_mb(self) -> float:
        return 0.2  # stato O(1), nessun buffer


# ------------------------------------------------------------------ TEST
if __name__ == "__main__":
    cfg = {
        "capital": 13.5,
        "fast_span": 12,
        "slow_span": 48,
        "atr_period": 14,
        "atr_thresh": 0.04,
        "base_stop_pct": 0.02,
        "max_leverage": 2.0,
    }
    strat = RAMVO(cfg)
    assert strat.estimate_memory_mb() < 1.0

    px, ts = 100.0, 0.0
    signals = 0
    for i in range(300):
        px = px * (1.0 + (0.002 if i < 150 else -0.0003))
        ts += 1.0
        sig = strat.on_tick(px, ts)
        if sig is not None:
            signals += 1
            if i < 150 and sig["side"] != "long":
                raise AssertionError(f"atteso long a i={i}, got {sig['side']}")

    print(f"RAMVO self-test OK: {signals} transizioni, fills={strat.state.fills}")
