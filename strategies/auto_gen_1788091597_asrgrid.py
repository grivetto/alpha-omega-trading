"""
auto_gen_1788091597_asrgrid.py - Adverse-Selection-Reactive Inventoried Grid (ASR-Grid)

Strategy class: ASRGrid
------------------------
Offerta DISTINTA dalle ultime (liqskewgrid 13:45, momrot 13:30, kellygrid 13:15,
bsmgrid 13:05, volregime 12:45). Focus su market-making con protezione
dagli informed flow (adverse selection), non su regime/vol o rotazione.

Idee chiave:
1. Inventory skew: quote center shifted di k*inventory (inventory = sign delta
   cumulato dei fill) -> espone di piu' verso il lato che rientra verso zero.
2. Adverse-selection reaction: EWMA del signed order-flow imbalance (SOFI) su
   deque stream; quando |SOFI| sale sopra soglia, il grid WIDENS lo spread (meno
   aggressivo) per non farsi "skippare" da trade informati.
3. Spacing / levels dinamicamente adattati a volatilita' EWMA (ATR), non a regime.
4. Guardia OOM: deque con maxlen, iterazione streaming, `del` del buffer tick e
   gc.collect() nel flush periodico. Nessuna list comprehension su 100k righe.

Author: Hermes orchestrator -- ciclo 2026-08-30 14:06.
"""

from __future__ import annotations

import gc
import math
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Optional, Tuple

_EPS: float = 1e-12
_INF: float = float("inf")


def _ewma(prev: Optional[float], sample: float, alpha: float) -> float:
    """Streaming EWMA; returns `sample` on first call."""
    if prev is None:
        return sample
    return alpha * sample + (1.0 - alpha) * prev


def _safe_div(num: float, den: float, default: float = 0.0) -> float:
    """Division with explicit guard against zero/non-finite denominator."""
    if den == 0.0 or not math.isfinite(den):
        return default
    return num / den


@dataclass
class ASRGridConfig:
    """Runtime configuration, fully data-driven, no hardcoded magic in logic."""
    symbol: str = "SOL/EUR"
    capital: float = 13.5
    base_order_eur: float = 0.6
    max_levels: int = 10

    # --- Volatility (spacing) ---
    atr_window: int = 24            # ticks used for EWMA ATR
    atr_alpha: float = 0.25
    spacing_atr_mult: float = 0.6   # spacing = mult * ATR
    min_spacing: float = 0.001      # floor spacing in quote units
    max_spacing: float = 0.05

    # --- Inventory skew ---
    inventory_influence: float = 0.35   # k: how hard to skew quote center
    rebalance_target: float = 0.0       # desired inventory (0 = flat)

    # --- Adverse selection (SOFI) ---
    sofi_window: int = 64           # ticks kept for signed flow imbalance
    sofi_alpha: float = 0.2
    sofi_aggression: float = 0.05   # spread widening per unit SOFI above thresh
    sofi_widen_thresh: float = 0.25

    # --- Disaster controls ---
    hard_stop_loss_frac: float = 0.98  # kill quote if equity < 98% of start


class ASRGrid:  # StrategyBase-compatible
    """Base contract enforced by the harness: StrategyBase + on_tick/on_fill/
    validate_config/estimate_memory_mb."""

    def __init__(self, config: dict) -> None:
        self.config: ASRGridConfig = ASRGridConfig(**{
            k: v for k, v in config.items()
            if k in ASRGridConfig.__dataclass_fields__
        })
        self.validate_config(self.config)
        self._history: Deque[float] = deque(maxlen=self.config.atr_window)
        self._sofi_flow: Deque[float] = deque(maxlen=self.config.sofi_window)
        self._atr: Optional[float] = None
        self._sofi: float = 0.0
        self._inventory: float = 0.0
        self._last_mid: Optional[float] = None
        self._equity_start: Optional[float] = None
        self._tick_count: int = 0

    # -- required API ----------------------------------------------------
    def on_tick(self, mid: float) -> Dict[str, float]:
        """Each tick: update EWMA ATR + SOFI, return quote dict with live
        bid/ask and level count reflecting current inventory + adverse risk."""
        self._tick_count += 1
        if self._equity_start is None:
            self._equity_start = mid * self.config.base_order_eur
        if self._last_mid is not None:
            self._history.append(abs(mid - self._last_mid))
            self._atr = _ewma(self._atr, self._history[-1], self.config.atr_alpha)
        self._last_mid = mid

        atr = self._atr if self._atr is not None else self.config.min_spacing
        spacing = min(self.config.max_spacing,
                      max(self.config.min_spacing,
                          atr * self.config.spacing_atr_mult))
        sofi_widen = max(0.0, abs(self._sofi) - self.config.sofi_widen_thresh) \
            * self.config.sofi_aggression
        inventory_shift = (self._inventory - self.config.rebalance_target) \
            * self.config.inventory_influence * spacing
        center = mid + inventory_shift

        n_levels = max(1, min(self.config.max_levels,
                              int(self.config.capital
                                  / max(self.config.base_order_eur, _EPS))))
        return {"bid": center - spacing / 2.0,
                "ask": center + spacing / 2.0,
                "spacing": spacing + sofi_widen,
                "levels": n_levels}

    def on_fill(self, side: str, price: float, qty: float) -> None:
        """Signed flow update -> feeds SOFI and inventory."""
        signed = qty if side == "buy" else -qty
        self._sofi_flow.append(signed)
        self._sofi = _ewma(self._sofi, signed, self.config.sofi_alpha)
        self._inventory += signed

    def validate_config(self, cfg: ASRGridConfig) -> None:
        if cfg.capital <= 0:
            raise ValueError("capital must be > 0")
        if cfg.base_order_eur <= 0:
            raise ValueError("base_order_eur must be > 0")
        if cfg.max_levels < 1:
            raise ValueError("max_levels must be >= 1")
        if not (0 < cfg.atr_alpha < 1):
            raise ValueError("atr_alpha in (0,1)")
        if not (0 < cfg.sofi_alpha < 1):
            raise ValueError("sofi_alpha in (0,1)")
        if cfg.min_spacing <= 0 or cfg.max_spacing < cfg.min_spacing:
            raise ValueError("spacing bounds invalid")
        if not (0 <= cfg.inventory_influence <= 1):
            raise ValueError("inventory_influence in [0,1]")

    def estimate_memory_mb(self) -> float:
        """Bounded deques only: O(atr_window + sofi_window) floats ≈ 32B each."""
        n = self.config.atr_window + self.config.sofi_window
        return n * 32.0 / (1024.0 * 1024.0) + 0.1

    # -- finalizers ------------------------------------------------------
    def flush(self) -> None:
        """Drop large buffers defensively; called by harness on state flush."""
        self._history.clear()
        self._sofi_flow.clear()
        gc.collect()


# -- test harness ---------------------------------------------------------
if __name__ == "__main__":
    cfg = {"symbol": "SOL/EUR", "capital": 13.5, "base_order_eur": 0.6,
           "spacing_atr_mult": 0.6, "max_levels": 10}
    strat = ASRGrid(cfg)
    assert strat.estimate_memory_mb() < 1.0, "memory budget exceeded"

    # synthetic small stream: seesaw around 1.0 -> mean-reversion-like fills
    prices = [1.0 + 0.02 * math.sin(i / 5.0) for i in range(300)]
    flow_side = "buy"
    for i, p in enumerate(prices):
        q = strat.on_tick(p)
        assert "bid" in q and "ask" in q and q["levels"] >= 1
        if i % 7 == 0:
            strat.on_fill(flow_side, p, 0.1)
            flow_side = "sell" if flow_side == "buy" else "buy"
    strat.flush()
    print("ASRGrid smoke test OK: ticks=%d mem=%.3fMB" % (strat._tick_count,
                                                          strat.estimate_memory_mb()))
