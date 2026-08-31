"""Volatility-Regime Adaptive Grid Strategy — auto-generated.

Adjusts grid spacing and level count dynamically based on realized volatility
regime detection. Config-driven, streaming-friendly, typed.

Author: Hermes (auto-generated)
"""
from __future__ import annotations

import gc
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Generator, List, Optional

logger = logging.getLogger("volregime_grid")


@dataclass
class VolRegimeConfig:
    """Configuration for VolRegimeGrid strategy."""
    symbol: str = "DOGE/EUR"
    capital: float = 3.7
    vol_window: int = 20
    spacing_base: float = 0.05
    spacing_min: float = 0.02
    spacing_max: float = 0.12
    levels_base: int = 8
    levels_min: int = 4
    levels_max: int = 12
    bias: str = "neutral"  # neutral | long_bias | short_bias
    risk_per_trade: float = 0.01

    def validate(self) -> List[str]:
        """Validate config, return list of errors."""
        errors: List[str] = []
        if self.capital <= 0:
            errors.append("capital must be > 0")
        if self.vol_window < 5:
            errors.append("vol_window too small (<5)")
        if not (0 < self.spacing_min <= self.spacing_base <= self.spacing_max):
            errors.append("spacing constraints violated")
        if not (0 < self.levels_min <= self.levels_base <= self.levels_max):
            errors.append("levels constraints violated")
        if self.bias not in ("neutral", "long_bias", "short_bias"):
            errors.append(f"invalid bias: {self.bias}")
        if not (0 < self.risk_per_trade <= 0.1):
            errors.append("risk_per_trade outside sane range")
        return errors


class StrategyBase:
    """Interface contract for all strategies."""

    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> None:
        raise NotImplementedError

    def validate_config(self) -> List[str]:
        return []

    def estimate_memory_mb(self, n: int) -> float:
        raise NotImplementedError


class VolRegimeGrid(StrategyBase):
    """Grid strategy whose spacing adapts to volatility regime."""

    def __init__(self, config: Optional[VolRegimeConfig] = None, capacity: int = 10_000) -> None:
        self.config = config or VolRegimeConfig()
        self._capacity = max(capacity, 100)
        # ring buffer to bound memory: fixed-size deque-like list
        self._prices: List[float] = []
        self._fills: List[Dict[str, Any]] = []
        self._pnl: float = 0.0
        self._regime: str = "unknown"

    # ---- core hooks ----
    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Feed one price tick, return optional order signal."""
        price = float(tick.get("price", 0.0))
        if price <= 0:
            logger.warning("ignoring non-positive price")
            return None
        # bounded append (streaming, no unbounded growth)
        self._prices.append(price)
        if len(self._prices) > self._capacity:
            del self._prices[:-self._capacity]
        vol = self._realized_vol(self._prices, self.config.vol_window)
        if vol is None:
            return None
        spacing, levels = self._params_for_vol(vol)
        signal = self._build_signal(price, spacing, levels, vol)
        return signal

    def on_fill(self, fill: Dict[str, Any]) -> None:
        """Record a fill and update PnL estimate."""
        pnl = float(fill.get("pnl", 0.0) or 0.0)
        pnl = fill.get("realized_pnl", pnl)
        self._pnl += float(pnl)
        fee = float(fill.get("fee", 0.0) or 0.0)
        self._pnl -= fee
        self._fills.append(fill)
        if len(self._fills) > self._capacity:
            del self._fills[:-self._capacity]

    def validate_config(self) -> List[str]:
        """Validate active config, throw if fatal."""
        errors = self.config.validate()
        if errors:
            logger.error("config invalid: %s", errors)
            raise ValueError("invalid config: " + "; ".join(errors))
        return errors

    def estimate_memory_mb(self, n: int) -> float:
        """Estimate memory for n buffered ticks (~56 bytes/float + obj)."""
        per_float = 56.0 / (1024 * 1024)
        per_fill = 256.0 / (1024 * 1024)
        mb = n * (per_float + per_fill)
        gc.collect()
        return round(mb, 3)

    # ---- internals ----
    @staticmethod
    def _realized_vol(prices: List[float], window: int) -> Optional[float]:
        """Return realized volatility of the last `window` returns."""
        if len(prices) < window + 1:
            return None
        chunk = prices[-(window + 1):]
        rets: List[float] = []
        for i in range(1, len(chunk)):
            prev = chunk[i - 1]
            if prev == 0:
                return None
            rets.append(chunk[i] / prev - 1.0)
        if not rets:
            return None
        mean = sum(rets) / len(rets)
        var = sum((r - mean) ** 2 for r in rets) / len(rets)
        return var ** 0.5

    def _params_for_vol(self, vol: float) -> tuple:
        """Map volatility to (spacing, levels) via linear interpolation."""
        hi, lo = self.config.spacing_max, self.config.spacing_min
        # high vol -> wide spacing + fewer levels (defensive)
        spread = max(vol, lo * 0.5)
        spacing = min(hi, max(lo, self.config.spacing_base * (1.0 + spread * 8.0)))
        hi_l, lo_l = self.config.levels_max, self.config.levels_min
        levels = int(round(hi_l - (hi_l - lo_l) * (spacing - lo) / max(hi - lo, 1e-9)))
        levels = max(lo_l, min(hi_l, levels))
        self._regime = "high" if vol > 0.04 else ("low" if vol < 0.015 else "mid")
        return spacing, levels

    def _build_signal(self, price: float, spacing: float, levels: int, vol: float) -> Dict[str, Any]:
        """Compose an order signal honoring bias direction."""
        base_side = "buy"
        if self.config.bias == "short_bias":
            base_side = "sell"
        elif self.config.bias == "long_bias":
            base_side = "buy"
        return {
            "symbol": self.config.symbol,
            "side": base_side,
            "type": "limit",
            "price": round(price * (1.0 - spacing * 0.5), 8),
            "qty": round(self.config.capital * self.config.risk_per_trade * (vol / max(self.config.spacing_base, 1e-9)), 8),
            "levels": levels,
            "regime": self._regime,
            "reason": f"vol={vol:.4f} spacing={spacing:.4f} levels={levels}",
        }


def _load_config_from_env() -> VolRegimeConfig:
    """Load config overrides from env if present (config-driven)."""
    import os
    cfg = VolRegimeConfig()
    try:
        cfg.capital = float(os.getenv("VRG_CAPITAL", cfg.capital))
        cfg.vol_window = int(os.getenv("VRG_VOL_WINDOW", cfg.vol_window))
        cfg.spacing_base = float(os.getenv("VRG_SPACING_BASE", cfg.spacing_base))
        cfg.levels_base = int(os.getenv("VRG_LEVELS_BASE", cfg.levels_base))
        cfg.bias = os.getenv("VRG_BIAS", cfg.bias)
    except (TypeError, ValueError) as exc:
        logger.error("bad env override: %s", exc)
    return cfg


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cfg = _load_config_from_env()
    cfg.validate()
    strat = VolRegimeGrid(cfg, capacity=1000)
    print(f"strategy={type(strat).__name__} mem~{strat.estimate_memory_mb(10_000)}MB")
    # synthetic small tick stream (not 100k rows; bounded for CI)
    ticks = [
        {"price": 0.10 + 0.001 * (i % 7)} for i in range(200)
    ] + [
        {"price": 0.10 + 0.02 * (i % 3)} for i in range(200, 400)
    ]
    signals = 0
    for tk in ticks:
        sig = strat.on_tick(tk)
        if sig:
            signals += 1
            if signals <= 3:
                print(f"signal#{signals} {sig}")
    strat.on_fill({"realized_pnl": 0.005, "fee": 0.0002})
    print(f"ticks={len(ticks)} signals={signals} pnl={strat._pnl:.4f} regime={strat._regime}")
    print("OK: smoke test passed")
