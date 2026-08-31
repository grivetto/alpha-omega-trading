"""auto_gen_${TS}: RegimePosition Grid with Adaptive Capitulation
=============================================================
Strategy: per-regime grid spacing/levels with flow-based capitulation
guard. Dynamically narrows grid around price, scales levels to
available equity, and halts re-entry during adverse flow regimes.

OOM-safe: all series processed via generators, no list() materialization
of large streams, explicit del + gc after config estimation.
"""
from __future__ import annotations

import gc
import math
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional


@dataclass
class RegimeConfig:
    """Per-regime tuning parameters (config-driven, no hardcoded)."""
    name: str
    spacing_pct: float    # grid spacing as fraction of mid
    levels: int           # number of grid levels each side
    vol_band: float       # tolerated volatility band
    reentry_flow: float   # max adverse flow signal to allow re-entry


@dataclass
class StrategyBase:
    """Base contract every auto-gen strategy implements."""
    symbol: str
    config: Dict[str, Any] = field(default_factory=dict)

    def validate_config(self) -> List[str]:
        """Return list of config errors (empty if valid)."""
        errors: List[str] = []
        for req in ("base_capital", "risk_pct", "regimes"):
            if req not in self.config:
                errors.append(f"missing config key: {req}")
        return errors

    def estimate_memory_mb(self, series_len: int) -> float:
        """Rough memory footprint for a dataset of `series_len` closes."""
        per_row = 48.0  # float64 close + metadata overhead
        return (series_len * per_row) / (1024 * 1024)

    def on_tick(self, price: float) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, fill_price: float, qty: float) -> Optional[Dict[str, Any]]:
        raise NotImplementedError


def _iter_chunks(closes: Iterator[float], chunk: int) -> Iterator[List[float]]:
    """Yield fixed-size chunks from a lazy stream (OOM-safe)."""
    bucket: List[float] = []
    for value in closes:
        bucket.append(value)
        if len(bucket) >= chunk:
            yield bucket
            bucket = []
    if bucket:
        yield bucket


class RegimePositionGrid(StrategyBase):
    """Grid strategy that re-anchors spacing/levels to detected regime."""

    def __init__(self, symbol: str, config: Dict[str, Any]) -> None:
        super().__init__(symbol, config)
        self.regimes: Dict[str, RegimeConfig] = {
            rcfg["name"]: RegimeConfig(**rcfg)
            for rcfg in self.config.get("regimes", [])
        }
        self.mid: Optional[float] = None
        self.active_levels: int = 0
        self.locked_capital: float = 0.0
        self.flow_signal: float = 0.0
        self._last_regime: Optional[str] = None

    def _pick_regime(self, vol: float) -> RegimeConfig:
        """Choose regime by matching volatility to band; fallback to wide."""
        for rcfg in self.regimes.values():
            if vol <= rcfg.vol_band:
                return rcfg
        return self.regimes["wide"]

    def reanchor(self, price: float, vol: float) -> Dict[str, Any]:
        """Re-anchor grid mid and regenerate level counts."""
        regime = self._pick_regime(vol)
        cap_per_level = self.config["base_capital"] * self.config["risk_pct"]
        max_levels = max(1, int(self.config["base_capital"] / cap_per_level))
        self.active_levels = min(regime.levels, max_levels)
        self.mid = price
        return {
            "mid": self.mid,
            "regime": regime.name,
            "spacing_pct": regime.spacing_pct,
            "levels": self.active_levels,
            "notional_level": cap_per_level,
        }

    def on_tick(self, price: float, vol: float) -> Dict[str, Any]:
        """Main grid decision on each price/vol tick."""
        # Capitulation guard: block new entries under adverse flow.
        if self.flow_signal > self.regimes["wide"].reentry_flow:
            return {"action": "hold", "reason": "adverse_flow"}
        # Re-anchor ONLY on regime change to keep a stable grid mid;
        # anchoring every tick would let the grid chase price and never fire.
        if self._pick_regime(vol).name != (self._last_regime or ""):
            anchor = self.reanchor(price, vol)
            self._last_regime = anchor["regime"]
        else:
            anchor = {
                "mid": self.mid or price,
                "regime": self._last_regime or "wide",
                "spacing_pct": self._pick_regime(vol).spacing_pct,
                "levels": self.active_levels,
                "notional_level": self.config["base_capital"] * self.config["risk_pct"],
            }
        dist = (price - anchor["mid"]) / anchor["mid"]
        level = int(abs(dist) / anchor["spacing_pct"]) if anchor["spacing_pct"] else 0
        if level <= 0:
            return {"action": "hold", "reason": "at_mid", **anchor}
        return {"action": "order", "side": "buy" if dist < 0 else "sell", **anchor}

    def on_fill(self, fill_price: float, qty: float) -> Dict[str, Any]:
        """Track locked capital after each fill."""
        notional = fill_price * qty
        self.locked_capital += notional
        budget = self.config["base_capital"] * self.config["risk_pct"]
        if self.locked_capital >= budget:
            return {"action": "cap_reached", "locked": self.locked_capital}
        return {"action": "continue", "locked": self.locked_capital}


if __name__ == "__main__":
    cfg: Dict[str, Any] = {
        "base_capital": 100.0,
        "risk_pct": 0.1,
        "regimes": [
            {"name": "tight", "spacing_pct": 0.004, "levels": 6, "vol_band": 0.05, "reentry_flow": 0.3},
            {"name": "wide", "spacing_pct": 0.01, "levels": 3, "vol_band": 1.0, "reentry_flow": 0.3},
        ],
    }
    strat = RegimePositionGrid("SOL/EUR", cfg)
    assert strat.validate_config() == [], strat.validate_config()
    ev = strat.reanchor(100.0, 0.03)
    assert ev["regime"] == "tight" and ev["levels"] == 6
    t0 = strat.on_tick(100.0, 0.03)   # anchors at 100.0
    tick = strat.on_tick(100.5, 0.03)  # 0.5% away -> triggers
    assert tick["action"] == "order" and tick["side"] == "sell", tick
    fill = strat.on_fill(100.5, 0.5)
    assert fill["action"] == "cap_reached"
    # OOM check: streaming chunking must not crash on 200k synthetic rows.
    noisy: Iterator[float] = (100.0 + 0.1 * math.sin(i) for i in range(200_000))
    rows = sum(len(chunk) for chunk in _iter_chunks(noisy, 4096))
    assert rows == 200_000
    mem = strat.estimate_memory_mb(200_000)
    assert 8.0 < mem < 10.0, mem
    del noisy, rows
    gc.collect()
    print("OK: RegimePositionGrid all tests passed")
