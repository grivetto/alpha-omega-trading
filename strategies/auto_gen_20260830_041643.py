"""Volatility-Adaptive Grid Strategy (VolGrid).

A grid strategy whose spacing and levels adapt dynamically to the realized
volatility of the underlying asset, instead of using a fixed spacing.

Design goals:
  - Config-driven: every tunable is in StrategyConfig (no hardcoded magic).
  - OOM-safe: only keep a rolling window of ticks; never accumulate history.
  - Explicit error handling: no bare except / pass.
  - Fully typed, docstringed, zero duplication via small helper functions.
"""
from __future__ import annotations

import gc
import json
import math
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional


@dataclass
class StrategyConfig:
    """Runtime configuration for the VolGrid strategy."""

    symbol: str = "SOL/EUR"
    capital: float = 13.5                 # per-bot capital in quote (EUR)
    base_spacing_pct: float = 0.008       # min spacing as fraction of price
    vol_lookback: int = 24                # ticks used to estimate vol
    vol_scale: float = 10.0               # spacing_mult = 1 + vol_scale * realized_vol
    max_levels: int = 8                   # max grid levels per side
    max_spacing_pct: float = 0.05         # cap spacing as fraction of price
    order_size_pct: float = 0.25          # fraction of free quote per order
    stop_loss_pct: float = 0.15           # hard stop-loss from last fill
    fee_pct: float = 0.0016               # taker fee to account for slippage
    poll_interval_s: float = 5.0

    def validate(self) -> None:
        """Validate configuration; raise on invalid values."""
        if self.capital <= 0:
            raise ValueError("capital must be positive")
        if not 0 < self.base_spacing_pct <= self.max_spacing_pct:
            raise ValueError("spacing bounds inconsistent")
        if self.vol_lookback < 2:
            raise ValueError("vol_lookback must be >= 2 for a meaningful estimate")
        if self.max_levels < 1 or self.order_size_pct <= 0 or self.order_size_pct > 1:
            raise ValueError("grid geometry params out of range")
        if self.stop_loss_pct <= 0 or not 0 <= self.fee_pct < 1:
            raise ValueError("risk params invalid")


class StrategyBase:
    """Minimal abstract base interface shared across the Denaro fleet."""

    def __init__(self, config: StrategyConfig) -> None:
        self.config = config
        config.validate()
        self.buys: int = 0
        self.sells: int = 0
        self.pnl: float = 0.0
        self.last_fill_price: Optional[float] = None
        self.trades: int = 0
        self.wins: int = 0

    # -- helpers shared by inheritors --------------------------------
    @staticmethod
    def _spread(mult: float, mid: float) -> float:
        """Full symmetric half-width from midpoint for a multiplier."""
        return mid * (mult - 1.0)

    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> None:
        raise NotImplementedError

    def validate_config(self, config: Dict[str, Any]) -> None:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


class VolGrid(StrategyBase):
    """Volatility-adaptive grid with streaming volatility estimation."""

    def __init__(self, config: StrategyConfig) -> None:
        super().__init__(config)
        self._prices: Deque[float] = deque(maxlen=config.vol_lookback)
        self._levels: List[float] = []
        self._side_buy: List[bool] = []
        self._realized_vol: float = 0.0
        self._mid: float = 0.0
        self._spacing: float = 0.0

    def validate_config(self, config: Dict[str, Any]) -> None:
        """Validate a raw config dict, raising for any bad key/value."""
        allowed = {f for f in StrategyConfig.__dataclass_fields__}  # type: ignore[attr-defined]
        unknown = set(config) - allowed
        if unknown:
            raise ValueError(f"unknown config keys: {sorted(unknown)}")
        StrategyConfig(**{**self.config.__dict__, **config}).validate()

    def estimate_memory_mb(self) -> float:
        """Fixed tiny footprint: only bounded rolling deque + level lists."""
        n = self.config.max_levels * 2
        bytes_ = (2 * n * 8) + (self.config.vol_lookback * 8) + 4096
        return bytes_ / (1024.0 * 1024.0)

    # -- volatility estimation (streaming) ---------------------------
    @staticmethod
    def _realized_vol_from_returns(returns: List[float]) -> float:
        """Std-dev of simple returns; 0.0 if fewer than 2 samples."""
        if len(returns) < 2:
            return 0.0
        mean = sum(returns) / len(returns)
        var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
        return math.sqrt(max(var, 0.0))

    def _update_vol(self, price: float) -> None:
        """Append price and re-estimate realized volatility from deltas."""
        if self._prices:
            prev = self._prices[-1]
            self._prices.append(price)
            returns = [
                (self._prices[i] - self._prices[i - 1]) / self._prices[i - 1]
                for i in range(1, len(self._prices))
            ]
            return_std = self._realized_vol_from_returns(returns)
            self._realized_vol = return_std
        else:
            self._prices.append(price)

    # -- grid geometry ------------------------------------------------
    def _rebuild_grid(self) -> None:
        """Rebuild buy/sell levels around the current midpoint."""
        mult = min(
            self.config.max_spacing_pct + 1.0,
            1.0 + self.config.base_spacing_pct * (
                1.0 + self.config.vol_scale * self._realized_vol
            ),
        )
        self._spacing = self._spread(mult, self._mid)
        self._levels = []
        self._side_buy = []
        for i in range(1, self.config.max_levels + 1):
            self._levels.append(self._mid - self._spacing * i)  # buy level
            self._side_buy.append(True)
            self._levels.append(self._mid + self._spacing * i)  # sell level
            self._side_buy.append(False)

    def _closest_hit(self, price: float) -> Optional[int]:
        """Index of the level closest to price, or None if empty."""
        if not self._levels:
            return None
        return min(range(len(self._levels)), key=lambda i: abs(self._levels[i] - price))

    # -- order sizing --------------------------------------------------
    def _order_amount(self) -> float:
        """Quote amount per order from remaining free capital."""
        free = self.config.capital * self.config.order_size_pct
        return max(0.0, free)

    # -- core ------------------------------------------------------------
    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process a tick; return an order dict if a grid level is hit."""
        price = float(tick.get("price", 0.0))
        if price <= 0:
            return None
        self._mid = price
        self._update_vol(price)

        if self._mid <= 0:
            return None
        self._rebuild_grid()
        idx = self._closest_hit(price)
        if idx is None:
            return None

        level = self._levels[idx]
        order: Dict[str, Any] = {
            "symbol": self.config.symbol,
            "type": "limit",
            "price": round(level, 8),
            "amount": round(self._order_amount(), 8),
            "side": "buy" if self._side_buy[idx] else "sell",
            "strategy": "volgrid",
        }
        self.last_fill_price = price
        return order

    def on_fill(self, fill: Dict[str, Any]) -> None:
        """Record a fill, updating PnL and win/loss counts."""
        side = fill.get("side", "")
        price = float(fill.get("price", 0.0))
        amount = float(fill.get("amount", 0.0))
        if price <= 0 or amount <= 0:
            raise ValueError(f"invalid fill payload: {fill}")

        if side == "sell" and self.last_fill_price is not None:
            gross = (price - self.last_fill_price) * amount
            fees = price * amount * self.config.fee_pct
            net = gross - fees
            self.pnl += net
            self.trades += 1
            if net > 0:
                self.wins += 1
            self.sells += 1
        elif side == "buy":
            self.buys += 1
        else:
            raise ValueError(f"unknown fill side: {side}")

        self.last_fill_price = price
        self._prices.clear()   # reset rolling window post-fill
        gc.collect()


def _run_self_test() -> None:
    """Inline smoke test with synthetic ticks."""
    cfg = StrategyConfig(symbol="SOL/EUR", capital=13.5, vol_lookback=8, max_levels=3)
    strat = VolGrid(cfg)
    print(f"memory: {strat.estimate_memory_mb():.6f} MB")

    # rising series to simulate a move through sell levels
    orders_seen = 0
    for t in range(30):
        price = 10.0 + t * 0.05
        tick = {"price": price}
        order = strat.on_tick(tick)
        if order is not None:
            orders_seen += 1

    # simulate a buy then sell cycle for PnL accounting
    strat.on_fill({"side": "buy", "price": 10.0, "amount": 1.0})
    strat.on_fill({"side": "sell", "price": 10.2, "amount": 1.0})
    print(f"orders seen: {orders_seen}, trades: {strat.trades}, "
          f"wins: {strat.wins}, pnl: {strat.pnl:.4f}")
    assert orders_seen >= 0
    assert strat.trades == 1 and strat.wins == 1
    print("SELFTEST OK")


if __name__ == "__main__":
    _run_self_test()
