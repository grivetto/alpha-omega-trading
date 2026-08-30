"""
Adaptive Grid-Momentum Strategy — auto-generated 2026-08-28 12:20 UTC.
Combines grid trading with momentum filtering and dynamic spacing.
"""
from __future__ import annotations

import gc
import logging
from dataclasses import dataclass
from typing import Generator

import numpy as np

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AdaptiveGridConfig:
    """Configuration for AdaptiveGridMomentum strategy."""
    symbol: str
    capital: float
    base_spacing_pct: float = 0.008
    max_levels: int = 10
    momentum_window: int = 20
    momentum_threshold: float = 0.002
    volatility_window: int = 50
    min_spacing_pct: float = 0.003
    max_spacing_pct: float = 0.025
    rebalance_interval_sec: int = 300
    stop_loss_pct: float = 0.05
    take_profit_pct: float = 0.03
    fee_rate: float = 0.0016

    def validate_config(self) -> None:
        if self.capital <= 0:
            raise ValueError("capital must be positive")
        if not 0 < self.base_spacing_pct < 1:
            raise ValueError("base_spacing_pct must be in (0, 1)")
        if self.max_levels < 2:
            raise ValueError("max_levels must be >= 2")
        if self.momentum_window < 5:
            raise ValueError("momentum_window must be >= 5")
        if self.volatility_window < 10:
            raise ValueError("volatility_window must be >= 10")
        if not 0 < self.min_spacing_pct <= self.max_spacing_pct < 1:
            raise ValueError("invalid spacing bounds")
        if self.rebalance_interval_sec < 60:
            raise ValueError("rebalance_interval_sec must be >= 60")


@dataclass(slots=True)
class GridLevel:
    """Single grid level with order tracking."""
    price: float
    qty: float
    side: str  # "buy" or "sell"
    order_id: str | None = None
    filled: bool = False


class StrategyBase:
    """Base class for all strategies."""
    def on_tick(self, timestamp: float, price: float, volume: float) -> list[dict]:
        raise NotImplementedError

    def on_fill(self, order_id: str, side: str, price: float, qty: float, fee: float) -> list[dict]:
        raise NotImplementedError

    def validate_config(self) -> None:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


class AdaptiveGridMomentum(StrategyBase):
    """
    Adaptive grid with momentum filter and dynamic spacing.
    - Expands grid spacing in high volatility
    - Contracts spacing in low volatility
    - Only places orders aligned with momentum direction
    - Rebalances grid periodically
    """
    def __init__(self, config: AdaptiveGridConfig) -> None:
        self.config = config
        self.config.validate_config()
        self._price_buffer: list[float] = []
        self._levels: list[GridLevel] = []
        self._last_rebalance_ts: float = 0.0
        self._position_qty: float = 0.0
        self._avg_entry_price: float = 0.0
        self._realized_pnl: float = 0.0

    def estimate_memory_mb(self) -> float:
        """Estimate memory usage in MB."""
        buffer_bytes = (self.config.momentum_window + self.config.volatility_window) * 8
        levels_bytes = self.config.max_levels * 64
        overhead = 1024 * 1024
        return (buffer_bytes + levels_bytes + overhead) / (1024 * 1024)

    def _update_buffers(self, price: float) -> None:
        """Update price buffer for both momentum and volatility."""
        self._price_buffer.append(price)
        max_window = max(self.config.momentum_window, self.config.volatility_window)
        if len(self._price_buffer) > max_window:
            self._price_buffer.pop(0)

    def _calc_momentum(self) -> float:
        """Calculate momentum as ROC over window."""
        if len(self._price_buffer) < self.config.momentum_window:
            return 0.0
        return (self._price_buffer[-1] - self._price_buffer[-self.config.momentum_window]) / self._price_buffer[-self.config.momentum_window]

    def _calc_volatility(self) -> float:
        """Calculate rolling volatility (std of returns)."""
        if len(self._price_buffer) < self.config.volatility_window:
            return 0.0
        window_data = self._price_buffer[-self.config.volatility_window:]
        returns = np.diff(window_data) / window_data[:-1]
        return float(np.std(returns) * np.sqrt(252 * 24 * 60))

    def _calc_dynamic_spacing(self, volatility: float) -> float:
        """Adjust spacing based on volatility regime."""
        if volatility == 0:
            return self.config.base_spacing_pct
        scaled = self.config.base_spacing_pct * (1 + volatility * 10)
        return max(self.config.min_spacing_pct, min(self.config.max_spacing_pct, scaled))

    def _build_grid(self, mid_price: float, spacing_pct: float) -> list[GridLevel]:
        """Generate grid levels around mid_price."""
        levels = []
        half = self.config.max_levels // 2
        per_level_capital = self.config.capital / self.config.max_levels
        for i in range(-half, half + 1):
            if i == 0:
                continue
            level_price = mid_price * (1 + i * spacing_pct)
            qty = per_level_capital / level_price
            side = "buy" if i < 0 else "sell"
            levels.append(GridLevel(price=level_price, qty=qty, side=side))
        return levels

    def _should_rebalance(self, timestamp: float) -> bool:
        return timestamp - self._last_rebalance_ts >= self.config.rebalance_interval_sec

    def on_tick(self, timestamp: float, price: float, volume: float) -> list[dict]:
        """Process market tick. Returns list of order dicts to place."""
        orders = []
        self._update_buffers(price)
        momentum = self._calc_momentum()
        volatility = self._calc_volatility()
        spacing = self._calc_dynamic_spacing(volatility)

        if self._should_rebalance(timestamp) or not self._levels:
            self._levels = self._build_grid(price, spacing)
            self._last_rebalance_ts = timestamp
            logger.info(f"Rebalanced grid: spacing={spacing:.4f}, momentum={momentum:.4f}, vol={volatility:.4f}")

        momentum_long = momentum > self.config.momentum_threshold
        momentum_short = momentum < -self.config.momentum_threshold

        for level in self._levels:
            if level.filled or level.order_id is not None:
                continue
            if level.side == "buy" and not momentum_long:
                continue
            if level.side == "sell" and not momentum_short and self._position_qty <= 0:
                continue

            orders.append({
                "symbol": self.config.symbol,
                "side": level.side,
                "type": "limit",
                "price": round(level.price, 5),
                "amount": round(level.qty, 6),
                "client_order_id": f"agm_{level.side}_{level.price:.5f}_{timestamp}",
                "strategy": "adaptive_grid_momentum",
            })
            level.order_id = orders[-1]["client_order_id"]

        if self._position_qty > 0 and self._avg_entry_price > 0:
            pnl_pct = (price - self._avg_entry_price) / self._avg_entry_price
            if pnl_pct <= -self.config.stop_loss_pct or pnl_pct >= self.config.take_profit_pct:
                orders.append({
                    "symbol": self.config.symbol,
                    "side": "sell",
                    "type": "market",
                    "amount": round(self._position_qty, 6),
                    "client_order_id": f"agm_sl_tp_{timestamp}",
                    "strategy": "adaptive_grid_momentum",
                    "reduce_only": True,
                })

        return orders

    def on_fill(self, order_id: str, side: str, price: float, qty: float, fee: float) -> list[dict]:
        """Process fill. Returns list of new orders (e.g., replacement grid orders)."""
        orders = []
        for level in self._levels:
            if level.order_id == order_id:
                level.filled = True
                level.order_id = None
                break

        if side == "buy":
            if self._position_qty >= 0:
                new_qty = self._position_qty + qty
                self._avg_entry_price = (
                    (self._avg_entry_price * self._position_qty + price * qty) / new_qty
                    if new_qty > 0 else price
                )
                self._position_qty = new_qty
            else:
                closed_qty = min(qty, -self._position_qty)
                self._realized_pnl += (self._avg_entry_price - price) * closed_qty - fee
                self._position_qty += qty
                if self._position_qty >= 0:
                    self._avg_entry_price = 0.0
        else:
            if self._position_qty <= 0:
                new_qty = self._position_qty - qty
                self._avg_entry_price = (
                    (self._avg_entry_price * -self._position_qty + price * qty) / -new_qty
                    if new_qty < 0 else price
                )
                self._position_qty = new_qty
            else:
                closed_qty = min(qty, self._position_qty)
                self._realized_pnl += (price - self._avg_entry_price) * closed_qty - fee
                self._position_qty -= qty
                if self._position_qty <= 0:
                    self._avg_entry_price = 0.0

        filled_count = sum(1 for l in self._levels if l.filled)
        if filled_count < self.config.max_levels:
            for level in self._levels:
                if not level.filled and level.order_id is None and level.side != side:
                    orders.append({
                        "symbol": self.config.symbol,
                        "side": level.side,
                        "type": "limit",
                        "price": round(level.price, 5),
                        "amount": round(level.qty, 6),
                        "client_order_id": f"agm_{level.side}_{level.price:.5f}_{order_id}",
                        "strategy": "adaptive_grid_momentum",
                    })
                    level.order_id = orders[-1]["client_order_id"]
                    break

        if filled_count > self.config.max_levels * 0.8:
            self._levels = [l for l in self._levels if not l.filled or l.order_id is not None]
            gc.collect()

        return orders


def _synthetic_data_gen(n: int = 500) -> Generator[tuple[float, float, float], None, None]:
    """Generate synthetic price/volume data for testing."""
    price = 100.0
    ts = 1_700_000_000.0
    for i in range(n):
        ret = np.random.normal(0.0001, 0.01)
        if i > 0 and abs(ret) > 0.015:
            ret *= 1.5
        price *= (1 + ret)
        price = max(price, 1.0)
        volume = np.random.lognormal(10, 0.5)
        yield ts + i * 60, price, volume


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    config = AdaptiveGridConfig(
        symbol="DOGE/EUR",
        capital=10.0,
        base_spacing_pct=0.008,
        max_levels=10,
        momentum_window=20,
        momentum_threshold=0.002,
        volatility_window=50,
        min_spacing_pct=0.003,
        max_spacing_pct=0.025,
        rebalance_interval_sec=300,
        stop_loss_pct=0.05,
        take_profit_pct=0.03,
        fee_rate=0.0016,
    )

    strat = AdaptiveGridMomentum(config)
    print(f"Estimated memory: {strat.estimate_memory_mb():.2f} MB")

    total_orders = 0
    total_fills = 0
    for ts, price, vol in _synthetic_data_gen(200):
        orders = strat.on_tick(ts, price, vol)
        total_orders += len(orders)
        if orders:
            o = orders[0]
            fills = strat.on_fill(o["client_order_id"], o["side"], o["price"], o["amount"], o["amount"] * o["price"] * config.fee_rate)
            total_fills += len(fills)

    print(f"Test complete: {total_orders} orders placed, {total_fills} fills processed")
    print(f"Final position: {strat._position_qty:.6f}, Realized PnL: {strat._realized_pnl:.6f}")
    print("OK")
