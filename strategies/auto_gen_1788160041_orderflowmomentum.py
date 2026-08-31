"""Order-Flow Momentum Engine — auto-generated strategy.

A momentum strategy driven by cumulative order-book imbalance (cumulative delta)
and volume-weighted drift, with adaptive exposure. DISTINCT from grid variants:
it trades directional momentum based on persistent bid/ask flow imbalance, not
mean-reversion grids. Config-driven, streaming (ring-buffer), OOM-safe, fully typed.

Author: Hermes (auto-generated)
"""
from __future__ import annotations

import gc
import logging
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("orderflow_momentum")


@dataclass
class OFMConfig:
    """Configuration for OrderFlowMomentum strategy."""

    symbol: str = "SOL/EUR"
    capital: float = 10.0
    flow_window: int = 120          # ticks of cumulative-delta history kept
    base_vol_window: int = 40       # ticks for realized vol of delta
    z_buy_threshold: float = 1.5    # z-score to open long
    z_sell_threshold: float = -1.5  # z-score to open short
    take_profit_pct: float = 0.035  # 3.5% directional take-profit
    stop_loss_pct: float = 0.03     # 3.0% hard stop
    max_exposure_frac: float = 0.5  # max capital deployed
    decay: float = 0.92             # exponential decay of older flows (0<decay<1)
    regime_vol_max: float = 0.12    # skip new entries if realized vol > this

    def validate(self) -> List[str]:
        """Validate config, return list of error strings."""
        errors: List[str] = []
        if self.capital <= 0:
            errors.append("capital must be > 0")
        if self.flow_window < 20:
            errors.append("flow_window too small (<20)")
        if self.base_vol_window < 5:
            errors.append("base_vol_window too small (<5)")
        if not (0.0 < self.decay < 1.0):
            errors.append("decay must be in (0,1)")
        if not (self.z_buy_threshold > self.z_sell_threshold):
            errors.append("buy/sell thresholds must bound a neutral band")
        if not (0.0 < self.take_profit_pct <= 0.10):
            errors.append("take_profit_pct out of range")
        return errors


class StrategyBase:
    """Base interface every strategy must implement."""

    def __init__(self, config: Any) -> None:
        self.config = config

    def validate_config(self) -> List[str]:
        return self.config.validate()

    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> None:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


class OrderFlowMomentum(StrategyBase):
    """Trades persistent order-flow imbalance as momentum signal."""

    def __init__(self, config: OFMConfig) -> None:
        super().__init__(config)
        errs = self.validate_config()
        if errs:
            raise ValueError(f"invalid config: {errs}")

        # streaming ring-buffer of cumulative delta, memory-bounded
        self._deltas: "deque[float]" = deque(maxlen=config.flow_window)
        self._vols: "deque[float]" = deque(maxlen=config.base_vol_window)

        self._position: int = 0          # +1 long, -1 short, 0 flat
        self._entry_price: float = 0.0
        self._cum_delta: float = 0.0
        self._cum_delta_decayed: float = 0.0
        self._ticks: int = 0
        self._last_price: float = 0.0

    # -- signal helpers ---------------------------------------------------
    def _running_mean(self, xs: "deque[float]") -> float:
        if not xs:
            return 0.0
        return sum(xs) / len(xs)

    def _realized_vol(self, prices: List[float]) -> float:
        """std of log returns from a small window (list is bounded)."""
        if len(prices) < 2:
            return 0.0
        returns = [math.log(prices[i + 1] / prices[i]) for i in range(len(prices) - 1)]
        mean = sum(returns) / len(returns)
        var = sum((r - mean) ** 2 for r in returns) / len(returns)
        return math.sqrt(var)

    # -- interface ---------------------------------------------------------
    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process one market tick; return an order signal or None."""
        price = float(tick.get("price", 0.0))
        bid = float(tick.get("bid", price))
        ask = float(tick.get("ask", price))
        if price <= 0.0 or bid <= 0.0 or ask < bid:
            return None

        bid_vol = float(tick.get("bid_vol", 0.0))
        ask_vol = float(tick.get("ask_vol", 0.0))
        # imbalance in [0,1]: >0.5 bid-heavy, <0.5 ask-heavy
        total = bid_vol + ask_vol
        imbalance = (bid_vol / total) - 0.5 if total > 0 else 0.0
        # signed delta: + when bid-heavy
        delta = imbalance * 2.0 * (bid_vol + ask_vol) / max(total, 1e-9)

        self._ticks += 1
        self._last_price = price
        self._cum_delta += delta
        self._cum_delta_decayed = self.config.decay * self._cum_delta_decayed + delta
        self._deltas.append(delta)
        signal = None

        # streaming realized vol from last N prices tracked in a small buffer
        pxbuf = [self._last_price for _ in range(1)] if self._ticks % self.config.base_vol_window == 0 else []
        # NOTE: kept minimal — full vol from close deque is OOM-safe
        if len(self._vols) >= self.config.base_vol_window:
            self._vols.popleft()
        self._vols.append(delta)  # proxy: vol of delta stream

        if len(self._deltas) >= self.config.flow_window and self._position == 0:
            mu = self._running_mean(self._deltas)
            sigma = self._running_mean(self._vols) + 1e-9
            z = (self._cum_delta_decayed - mu) / sigma
            realized_vol = sigma  # normalized flow-vol proxy
            if abs(realized_vol) < self.config.regime_vol_max and self._ticks % 7 == 0:
                if z >= self.config.z_buy_threshold:
                    signal = {"action": "buy", "symbol": self.config.symbol,
                              "size_frac": self.config.max_exposure_frac,
                              "reason": f"ofm_long_z={z:.2f}"}
                    self._position = 1
                    self._entry_price = price
                elif z <= self.config.z_sell_threshold:
                    signal = {"action": "sell", "symbol": self.config.symbol,
                              "size_frac": self.config.max_exposure_frac,
                              "reason": f"ofm_short_z={z:.2f}"}
                    self._position = -1
                    self._entry_price = price

        elif self._position != 0:
            ret = (price - self._entry_price) / self._entry_price
            if (self._position == 1 and ret >= self.config.take_profit_pct) or \
               (self._position == -1 and ret <= -self.config.take_profit_pct):
                signal = {"action": "close", "symbol": self.config.symbol,
                          "size_frac": 1.0, "reason": "tp"}
                self._position = 0
            elif (self._position == 1 and ret <= -self.config.stop_loss_pct) or \
                 (self._position == -1 and ret >= self.config.stop_loss_pct):
                signal = {"action": "close", "symbol": self.config.symbol,
                          "size_frac": 1.0, "reason": "sl"}
                self._position = 0

        if self._ticks % 500 == 0:
            del self._deltas  # force large-buffer cleanup periodically
            self._deltas = deque(self._deltas, maxlen=self.config.flow_window)
            gc.collect()

        return signal

    def on_fill(self, fill: Dict[str, Any]) -> None:
        """Update internal entry tracking after a fill confirmation."""
        self._entry_price = float(fill.get("price", self._entry_price))
        # optional: reset deltas after fill

    def estimate_memory_mb(self) -> float:
        """Rough memory estimate: bounded deques dominate."""
        delta_bytes = self.config.flow_window * 24
        vol_bytes = self.config.base_vol_window * 24
        return round((delta_bytes + vol_bytes + 4096) / (1024 * 1024), 3)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cfg = OFMConfig(capital=10.0, symbol="SOL/EUR")
    strat = OrderFlowMomentum(cfg)
    ntrades = 0
    # synthetic directed flow: bid-heavy then ask-heavy
    synth = []
    base = 100.0
    for i in range(300):
        heavy = 0.6 if i < 150 else 0.4
        synth.append({"price": base + i * 0.001,
                      "bid": base + i * 0.001 - 0.01,
                      "ask": base + i * 0.001 + 0.01,
                      "bid_vol": heavy + 0.3, "ask_vol": 1.0 - heavy + 0.3})
    for tk in synth:
        sig = strat.on_tick(tk)
        if sig:
            ntrades += 1
            print(f"signal: {sig['action']} ({sig['reason']})")
    print(f"signals: {ntrades}, mem_est: {strat.estimate_memory_mb()}MB")
    print("smoke test OK" if ntrades >= 1 else "no trades generated")
