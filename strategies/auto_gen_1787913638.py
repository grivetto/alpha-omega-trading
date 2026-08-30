"""
Regime-Aware Hybrid Strategy — auto-generated 2026-08-28 12:40 UTC.
Combines grid, momentum, and mean-reversion with automatic regime detection.
Optimized for low-capital accounts (5-50 EUR) with dynamic position sizing.
"""
from __future__ import annotations

import gc
import logging
from dataclasses import dataclass
from typing import Generator, Literal

import numpy as np

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RegimeHybridConfig:
    """Configuration for RegimeAwareHybrid strategy."""
    symbol: str
    capital: float
    # Grid parameters
    base_spacing_pct: float = 0.006
    max_levels: int = 8
    min_spacing_pct: float = 0.002
    max_spacing_pct: float = 0.03
    # Momentum parameters
    momentum_window: int = 15
    momentum_threshold: float = 0.0015
    momentum_strong_threshold: float = 0.005
    # Mean reversion parameters
    mr_window: int = 30
    mr_entry_zscore: float = 1.5
    mr_exit_zscore: float = 0.3
    # Regime detection
    regime_window: int = 100
    adx_threshold: float = 25.0
    # Risk management
    stop_loss_pct: float = 0.04
    take_profit_pct: float = 0.025
    max_drawdown_pct: float = 0.15
    fee_rate: float = 0.0016
    rebalance_interval_sec: int = 180

    def validate_config(self) -> None:
        if self.capital <= 0:
            raise ValueError("capital must be positive")
        if not 0 < self.base_spacing_pct < 1:
            raise ValueError("base_spacing_pct must be in (0, 1)")
        if self.max_levels < 2:
            raise ValueError("max_levels must be >= 2")
        if not 0 < self.min_spacing_pct <= self.max_spacing_pct < 1:
            raise ValueError("invalid spacing bounds")
        if self.momentum_window < 5:
            raise ValueError("momentum_window must be >= 5")
        if self.mr_window < 10:
            raise ValueError("mr_window must be >= 10")
        if self.regime_window < 20:
            raise ValueError("regime_window must be >= 20")
        if self.rebalance_interval_sec < 30:
            raise ValueError("rebalance_interval_sec must be >= 30")


@dataclass(slots=True)
class GridLevel:
    """Single grid level with order tracking."""
    price: float
    qty: float
    side: str  # "buy" or "sell"
    order_id: str | None = None
    filled: bool = False


class RegimeType:
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    VOLATILE = "volatile"


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


class RegimeAwareHybrid(StrategyBase):
    """
    Regime-aware hybrid strategy:
    - TRENDING: Momentum-following grid (wider spacing, directional bias)
    - RANGING: Tight mean-reversion grid (tight spacing, both sides)
    - VOLATILE: Reduced size, wider stops, skip trading if too chaotic
    - Dynamic position sizing based on capital and regime confidence
    """
    def __init__(self, config: RegimeHybridConfig) -> None:
        self.config = config
        self.config.validate_config()
        self._price_buffer: list[float] = []
        self._volume_buffer: list[float] = []
        self._levels: list[GridLevel] = []
        self._last_rebalance_ts: float = 0.0
        self._position_qty: float = 0.0
        self._avg_entry_price: float = 0.0
        self._realized_pnl: float = 0.0
        self._current_regime: str = RegimeType.RANGING
        self._regime_confidence: float = 0.5
        self._peak_equity: float = config.capital
        self._drawdown_hit: bool = False

    def estimate_memory_mb(self) -> float:
        """Estimate memory usage in MB."""
        buffer_bytes = (self.config.momentum_window + self.config.mr_window + self.config.regime_window) * 8 * 2
        levels_bytes = self.config.max_levels * 64
        overhead = 1024 * 1024
        return (buffer_bytes + levels_bytes + overhead) / (1024 * 1024)

    def _update_buffers(self, price: float, volume: float) -> None:
        """Update price and volume buffers."""
        self._price_buffer.append(price)
        self._volume_buffer.append(volume)
        max_window = max(self.config.momentum_window, self.config.mr_window, self.config.regime_window)
        if len(self._price_buffer) > max_window:
            self._price_buffer.pop(0)
            self._volume_buffer.pop(0)

    def _calc_momentum(self) -> float:
        """Calculate momentum as ROC over window."""
        if len(self._price_buffer) < self.config.momentum_window:
            return 0.0
        return (self._price_buffer[-1] - self._price_buffer[-self.config.momentum_window]) / self._price_buffer[-self.config.momentum_window]

    def _calc_mr_zscore(self) -> float:
        """Calculate mean reversion z-score."""
        if len(self._price_buffer) < self.config.mr_window:
            return 0.0
        window_data = np.array(self._price_buffer[-self.config.mr_window:])
        mean = np.mean(window_data)
        std = np.std(window_data)
        if std == 0:
            return 0.0
        return (window_data[-1] - mean) / std

    def _calc_adx(self) -> float:
        """Simplified ADX calculation for trend strength."""
        if len(self._price_buffer) < self.config.regime_window:
            return 0.0
        prices = np.array(self._price_buffer[-self.config.regime_window:])
        highs = np.maximum.accumulate(prices)
        lows = np.minimum.accumulate(prices)
        tr = highs - lows
        dm_plus = np.diff(highs, prepend=highs[0])
        dm_minus = np.diff(lows, prepend=lows[0])
        dm_plus = np.where((dm_plus > dm_minus) & (dm_plus > 0), dm_plus, 0)
        dm_minus = np.where((dm_minus > dm_plus) & (dm_minus > 0), dm_minus, 0)
        atr = np.mean(tr[-14:]) if len(tr) >= 14 else np.mean(tr)
        if atr == 0:
            return 0.0
        di_plus = 100 * np.mean(dm_plus[-14:]) / atr if len(dm_plus) >= 14 else 0
        di_minus = 100 * np.mean(dm_minus[-14:]) / atr if len(dm_minus) >= 14 else 0
        dx = 100 * abs(di_plus - di_minus) / (di_plus + di_minus) if (di_plus + di_minus) > 0 else 0
        return float(dx)

    def _detect_regime(self) -> tuple[str, float]:
        """Detect market regime and confidence."""
        if len(self._price_buffer) < self.config.regime_window:
            return RegimeType.RANGING, 0.5

        momentum = self._calc_momentum()
        adx = self._calc_adx()
        zscore = self._calc_mr_zscore()

        if adx > self.config.adx_threshold:
            if momentum > 0:
                return RegimeType.TRENDING_UP, min(adx / 50.0, 1.0)
            else:
                return RegimeType.TRENDING_DOWN, min(adx / 50.0, 1.0)
        elif abs(zscore) > 2.0:
            return RegimeType.VOLATILE, min(abs(zscore) / 4.0, 1.0)
        else:
            return RegimeType.RANGING, 1.0 - min(adx / self.config.adx_threshold, 1.0)

    def _calc_dynamic_spacing(self, regime: str, confidence: float) -> float:
        """Adjust spacing based on regime."""
        base = self.config.base_spacing_pct
        if regime == RegimeType.TRENDING_UP or regime == RegimeType.TRENDING_DOWN:
            return min(self.config.max_spacing_pct, base * (1.5 + confidence))
        elif regime == RegimeType.VOLATILE:
            return min(self.config.max_spacing_pct, base * 2.0)
        else:  # RANGING
            return max(self.config.min_spacing_pct, base * 0.5)

    def _calc_position_size(self, regime: str, confidence: float) -> float:
        """Dynamic position sizing based on regime and drawdown."""
        if self._drawdown_hit:
            return self.config.capital * 0.25
        base_size = self.config.capital
        if regime == RegimeType.TRENDING_UP or regime == RegimeType.TRENDING_DOWN:
            return base_size * (0.8 + confidence * 0.4)
        elif regime == RegimeType.VOLATILE:
            return base_size * 0.4
        else:  # RANGING
            return base_size * (0.6 + confidence * 0.4)

    def _build_grid(self, mid_price: float, spacing_pct: float, regime: str, position_size: float) -> list[GridLevel]:
        """Generate grid levels adapted to regime."""
        levels = []
        per_level_capital = position_size / self.config.max_levels

        if regime == RegimeType.TRENDING_UP:
            # Bias toward buys, fewer sells
            buy_levels = self.config.max_levels // 2 + 1
            sell_levels = self.config.max_levels - buy_levels
            for i in range(-buy_levels, 0):
                level_price = mid_price * (1 + i * spacing_pct)
                levels.append(GridLevel(price=level_price, qty=per_level_capital / level_price, side="buy"))
            for i in range(1, sell_levels + 1):
                level_price = mid_price * (1 + i * spacing_pct * 1.5)
                levels.append(GridLevel(price=level_price, qty=per_level_capital / level_price, side="sell"))
        elif regime == RegimeType.TRENDING_DOWN:
            # Bias toward sells, fewer buys
            sell_levels = self.config.max_levels // 2 + 1
            buy_levels = self.config.max_levels - sell_levels
            for i in range(1, sell_levels + 1):
                level_price = mid_price * (1 + i * spacing_pct)
                levels.append(GridLevel(price=level_price, qty=per_level_capital / level_price, side="sell"))
            for i in range(-buy_levels, 0):
                level_price = mid_price * (1 + i * spacing_pct * 1.5)
                levels.append(GridLevel(price=level_price, qty=per_level_capital / level_price, side="buy"))
        else:
            # RANGING or VOLATILE: symmetric grid
            half = self.config.max_levels // 2
            for i in range(-half, half + 1):
                if i == 0:
                    continue
                level_price = mid_price * (1 + i * spacing_pct)
                levels.append(GridLevel(price=level_price, qty=per_level_capital / level_price, side="buy" if i < 0 else "sell"))
        return levels

    def _should_rebalance(self, timestamp: float) -> bool:
        return timestamp - self._last_rebalance_ts >= self.config.rebalance_interval_sec

    def _update_drawdown(self, current_price: float) -> None:
        """Track equity and drawdown."""
        unrealized = 0.0
        if self._position_qty > 0 and self._avg_entry_price > 0:
            unrealized = (current_price - self._avg_entry_price) * self._position_qty
        elif self._position_qty < 0 and self._avg_entry_price > 0:
            unrealized = (self._avg_entry_price - current_price) * -self._position_qty
        equity = self.config.capital + self._realized_pnl + unrealized
        if equity > self._peak_equity:
            self._peak_equity = equity
        dd = (self._peak_equity - equity) / self._peak_equity if self._peak_equity > 0 else 0
        if dd >= self.config.max_drawdown_pct:
            self._drawdown_hit = True
            logger.warning(f"Max drawdown hit: {dd:.2%}, reducing size")

    def on_tick(self, timestamp: float, price: float, volume: float) -> list[dict]:
        """Process market tick. Returns list of order dicts to place."""
        orders = []
        self._update_buffers(price, volume)
        self._update_drawdown(price)

        regime, confidence = self._detect_regime()
        if regime != self._current_regime:
            logger.info(f"Regime change: {self._current_regime} -> {regime} (confidence: {confidence:.2f})")
            self._current_regime = regime
            self._regime_confidence = confidence

        spacing = self._calc_dynamic_spacing(regime, confidence)
        position_size = self._calc_position_size(regime, confidence)

        if self._should_rebalance(timestamp) or not self._levels:
            self._levels = self._build_grid(price, spacing, regime, position_size)
            self._last_rebalance_ts = timestamp
            logger.info(f"Rebalanced: regime={regime}, spacing={spacing:.4f}, size={position_size:.2f}")

        momentum = self._calc_momentum()
        zscore = self._calc_mr_zscore()

        # Determine which sides to allow based on regime
        allow_buy = True
        allow_sell = True
        if regime == RegimeType.TRENDING_UP:
            allow_sell = self._position_qty > 0  # Only sell to reduce position
        elif regime == RegimeType.TRENDING_DOWN:
            allow_buy = self._position_qty < 0  # Only buy to reduce position
        elif regime == RegimeType.VOLATILE:
            # In volatile, only trade mean reversion extremes
            allow_buy = zscore < -self.config.mr_entry_zscore
            allow_sell = zscore > self.config.mr_entry_zscore

        for level in self._levels:
            if level.filled or level.order_id is not None:
                continue
            if level.side == "buy" and not allow_buy:
                continue
            if level.side == "sell" and not allow_sell:
                continue

            orders.append({
                "symbol": self.config.symbol,
                "side": level.side,
                "type": "limit",
                "price": round(level.price, 5),
                "amount": round(level.qty, 6),
                "client_order_id": f"rah_{level.side}_{level.price:.5f}_{timestamp}",
                "strategy": "regime_aware_hybrid",
            })
            level.order_id = orders[-1]["client_order_id"]

        # Stop loss / take profit
        if self._position_qty != 0 and self._avg_entry_price > 0:
            pnl_pct = (price - self._avg_entry_price) / self._avg_entry_price if self._position_qty > 0 else (self._avg_entry_price - price) / self._avg_entry_price
            if pnl_pct <= -self.config.stop_loss_pct or pnl_pct >= self.config.take_profit_pct:
                orders.append({
                    "symbol": self.config.symbol,
                    "side": "sell" if self._position_qty > 0 else "buy",
                    "type": "market",
                    "amount": round(abs(self._position_qty), 6),
                    "client_order_id": f"rah_sl_tp_{timestamp}",
                    "strategy": "regime_aware_hybrid",
                    "reduce_only": True,
                })

        return orders

    def on_fill(self, order_id: str, side: str, price: float, qty: float, fee: float) -> list[dict]:
        """Process fill. Returns list of new orders."""
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
                        "client_order_id": f"rah_{level.side}_{level.price:.5f}_{order_id}",
                        "strategy": "regime_aware_hybrid",
                    })
                    level.order_id = orders[-1]["client_order_id"]
                    break

        if filled_count > self.config.max_levels * 0.8:
            self._levels = [l for l in self._levels if not l.filled or l.order_id is not None]
            gc.collect()

        return orders


def _synthetic_data_gen(n: int = 500) -> Generator[tuple[float, float, float], None, None]:
    """Generate synthetic price/volume data for testing with regime changes."""
    price = 100.0
    ts = 1_700_000_000.0
    regime = 0  # 0=ranging, 1=trend_up, 2=trend_down, 3=volatile
    for i in range(n):
        if i % 125 == 0:
            regime = (regime + 1) % 4
        if regime == 0:
            ret = np.random.normal(0.0, 0.008)
        elif regime == 1:
            ret = np.random.normal(0.0015, 0.006)
        elif regime == 2:
            ret = np.random.normal(-0.0015, 0.006)
        else:
            ret = np.random.normal(0.0, 0.025)
        price *= (1 + ret)
        price = max(price, 1.0)
        volume = np.random.lognormal(10, 0.5)
        yield ts + i * 60, price, volume


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    config = RegimeHybridConfig(
        symbol="DOGE/EUR",
        capital=10.0,
        base_spacing_pct=0.006,
        max_levels=8,
        min_spacing_pct=0.002,
        max_spacing_pct=0.03,
        momentum_window=15,
        momentum_threshold=0.0015,
        momentum_strong_threshold=0.005,
        mr_window=30,
        mr_entry_zscore=1.5,
        mr_exit_zscore=0.3,
        regime_window=100,
        adx_threshold=25.0,
        stop_loss_pct=0.04,
        take_profit_pct=0.025,
        max_drawdown_pct=0.15,
        fee_rate=0.0016,
        rebalance_interval_sec=180,
    )

    strat = RegimeAwareHybrid(config)
    print(f"Estimated memory: {strat.estimate_memory_mb():.2f} MB")

    total_orders = 0
    total_fills = 0
    for ts, price, vol in _synthetic_data_gen(300):
        orders = strat.on_tick(ts, price, vol)
        total_orders += len(orders)
        if orders:
            o = orders[0]
            fills = strat.on_fill(o["client_order_id"], o["side"], o["price"], o["amount"], o["amount"] * o["price"] * config.fee_rate)
            total_fills += len(fills)

    print(f"Test complete: {total_orders} orders placed, {total_fills} fills processed")
    print(f"Final position: {strat._position_qty:.6f}, Realized PnL: {strat._realized_pnl:.6f}")
    print(f"Final regime: {strat._current_regime}, Drawdown hit: {strat._drawdown_hit}")
    print("OK")
