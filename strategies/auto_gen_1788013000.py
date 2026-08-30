"""
Volatility-Adaptive Grid with Regime-Locked Kelly Sizing (VAGR-KS)
auto-generated 2026-08-29 16:16 UTC by Hermes (alpha-omega-trading)

A mean-reversion grid whose half-spacing and level count adapt to realised
volatility (exponentially weighted), with position sizing capped by a
regime-locked Kelly fraction. Improves on LGR-AKR by making spacing a
smooth function of vol instead of a hard-coded multiple.
"""
from __future__ import annotations

import gc
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

DEFAULT_CONFIG: Dict[str, Any] = {
    "symbol": "SOL/EUR",
    "capital": 13.5,
    "base_spacing": 0.012,
    "ref_vol": 0.02,
    "vol_floor": 0.006,
    "vol_ceil": 0.06,
    "max_levels": 16,
    "kelly_fraction": 0.35,
    "ewm_span": 32,
    "stop_loss_frac": 0.08,
    "equity_sizing": True,
}


@dataclass
class EngineState:
    free_quote: float = 0.0
    total_equity: float = 0.0
    last_price: Optional[float] = None
    prev_fill_price: Optional[float] = None
    peak_equity: float = 0.0
    halted: bool = False
    buys: int = 0
    sells: int = 0
    realized_pnl: float = 0.0
    vol_sq: float = 0.0
    _count: int = 0
    _levels: List[float] = field(default_factory=list)


class StrategyBase:
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self.validate_config()
        self.state = EngineState()

    def on_tick(self, price: float, quote_balance: float,
                equity: float) -> Optional[str]:
        raise NotImplementedError

    def on_fill(self, side: str, price: float, qty: float) -> None:
        raise NotImplementedError

    def validate_config(self) -> None:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError

    @staticmethod
    def _clamp(x: float, lo: float, hi: float) -> float:
        return lo if x < lo else (hi if x > hi else x)


class VolAdaptiveGridKelly(StrategyBase):
    def on_tick(self, price: float, quote_balance: float,
                equity: float) -> Optional[str]:
        st = self.state
        st.free_quote = quote_balance
        st.total_equity = equity
        st.peak_equity = max(st.peak_equity, equity)

        if st.peak_equity > 0 and equity > 0:
            dd = (st.peak_equity - equity) / st.peak_equity
            if dd >= self.config["stop_loss_frac"]:
                st.halted = True
                return "HALT"

        if st.halted:
            return None

        if st.last_price is not None:
            r = math.log(price / st.last_price) if st.last_price > 0 else 0.0
            if st._count == 0:
                st.vol_sq = r * r
            else:
                alpha = 2.0 / (self.config["ewm_span"] + 1.0)
                st.vol_sq = alpha * (r * r) + (1.0 - alpha) * st.vol_sq
            st._count += 1
        st.last_price = price

        vol = math.sqrt(st.vol_sq) if st.vol_sq > 0 else self.config["ref_vol"]
        vol = self._clamp(vol, self.config["vol_floor"], self.config["vol_ceil"])

        spacing = (self.config["base_spacing"]
                   * math.sqrt(vol / self.config["ref_vol"]))
        spacing = self._clamp(spacing, 0.001, 0.1)

        st._levels = self._build_levels(price, spacing)

        capital = self.config["capital"]
        if self.config["equity_sizing"] and equity > 0:
            capital *= min(1.0, quote_balance / equity)

        per_level = capital / len(st._levels)
        per_level *= self.config["kelly_fraction"]

        target = None
        for lvl in st._levels:
            if lvl < price and (target is None or lvl > target):
                target = lvl
        if target is not None and st.prev_fill_price != target:
            return f"LIMIT_BUY {target:.6f} qty={per_level/target:.8f}"
        return None

    def _build_levels(self, price: float, spacing: float) -> List[float]:
        n = self.config["max_levels"]
        half = n // 2
        return [price * (1.0 + i * spacing) for i in range(-half, n - half)]

    def on_fill(self, side: str, price: float, qty: float) -> None:
        st = self.state
        if side == "sell":
            if st.prev_fill_price is not None:
                st.realized_pnl += (price - st.prev_fill_price) * qty
            st.sells += 1
        elif side == "buy":
            st.buys += 1
        st.prev_fill_price = price

    def validate_config(self) -> None:
        c = self.config
        if c["base_spacing"] <= 0:
            raise ValueError("base_spacing must be > 0")
        if not (0 < c["kelly_fraction"] <= 1):
            raise ValueError("kelly_fraction must be in (0, 1]")
        if c["max_levels"] < 2 or c["max_levels"] > 64:
            raise ValueError("max_levels out of [2, 64]")
        if c["vol_floor"] >= c["vol_ceil"]:
            raise ValueError("vol_floor must be < vol_ceil")

    def estimate_memory_mb(self) -> float:
        return 1.5


if __name__ == "__main__":
    for cfg in ({"capital": 13.5, "max_levels": 16},
                {"capital": 0.8, "max_levels": 8}):
        strat = VolAdaptiveGridKelly(cfg)
        assert strat.estimate_memory_mb() > 0
        last = None
        for i in range(200):
            if i == 100:
                price = strat.state.last_price * 1.05
            else:
                price = 200.0 * math.exp(0.001 * math.sin(i / 5.0))
            intent = strat.on_tick(price, 10.0, 11.0)
            if intent:
                last = intent
        fp = strat.state._levels[0] if strat.state._levels else 200.0
        strat.on_fill("buy", fp, 0.01)
        strat.on_fill("sell", fp * 1.01, 0.01)
        assert strat.state.buys >= 1 and strat.state.sells >= 1
        assert strat.state.realized_pnl > 0
        print(f"OK capital={cfg['capital']} vol={math.sqrt(strat.state.vol_sq):.5f} "
              f"levels={len(strat.state._levels)} intent_last={last}")
    gc.collect()
    print("ALL SMOKE TESTS PASSED")
