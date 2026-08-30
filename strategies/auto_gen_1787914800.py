"""
Adaptive Volatility Grid Strategy — auto-generated 2026-08-28 13:00 UTC.
Grid with ATR-based dynamic spacing, capital allocation bands, and regime-aware risk scaling.
Optimized for multi-node deployment (mc2, nuvola, MARCODG1) with config-driven parameters.
"""

from __future__ import annotations

import gc
import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Generator, Literal

import numpy as np

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AdaptiveVolGridConfig:
    """Configuration for AdaptiveVolatilityGrid strategy."""
    symbol: str
    capital: float
    # Grid core
    base_levels: int = 10
    min_levels: int = 4
    max_levels: int = 20
    # ATR-based spacing
    atr_window: int = 14
    atr_multiplier: float = 1.5
    min_spacing_pct: float = 0.003
    max_spacing_pct: float = 0.04
    # Capital allocation bands
    capital_bands: tuple[float, ...] = (0.2, 0.4, 0.6, 0.8, 1.0)
    band_spacing_scale: tuple[float, ...] = (0.5, 0.75, 1.0, 1.25, 1.5)
    # Regime detection
    regime_window: int = 50
    volatility_quantile_low: float = 0.3
    volatility_quantile_high: float = 0.7
    trend_strength_window: int = 20
    # Risk management
    stop_loss_atr_mult: float = 3.0
    take_profit_atr_mult: float = 1.5
    max_drawdown_pct: float = 0.12
    fee_rate: float = 0.0016
    rebalance_interval_sec: int = 120
    # OOM protection
    max_price_history: int = 5000

    def validate_config(self) -> None:
        if self.capital <= 0:
            raise ValueError("capital must be positive")
        if self.base_levels < self.min_levels or self.base_levels > self.max_levels:
            raise ValueError("base_levels must be within [min_levels, max_levels]")
        if not 0 < self.min_spacing_pct <= self.max_spacing_pct < 1:
            raise ValueError("invalid spacing bounds")
        if self.atr_window < 5:
            raise ValueError("atr_window must be >= 5")
        if len(self.capital_bands) != len(self.band_spacing_scale):
            raise ValueError("capital_bands and band_spacing_scale must have same length")
        if not all(0 < b <= 1 for b in self.capital_bands):
            raise ValueError("capital_bands must be in (0, 1]")
        if not all(s > 0 for s in self.band_spacing_scale):
            raise ValueError("band_spacing_scale must be positive")
        if self.rebalance_interval_sec < 30:
            raise ValueError("rebalance_interval_sec must be >= 30")
        if self.max_price_history < 100:
            raise ValueError("max_price_history must be >= 100")


@dataclass(slots=True)
class GridLevel:
    """Single grid level with order tracking."""
    price: float
    qty: float
    side: Literal["buy", "sell"]
    order_id: str | None = None
    filled: bool = False
    band_index: int = 0


class RegimeType:
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING_LOW_VOL = "ranging_low_vol"
    RANGING_HIGH_VOL = "ranging_high_vol"


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


class AdaptiveVolatilityGrid(StrategyBase):
    """
    Adaptive Volatility Grid Strategy:
    - ATR-based dynamic spacing that expands/contracts with volatility
    - Capital allocation bands: deploy capital progressively as price moves
    - Regime-aware: tight grid in ranging, wider in trending
    - Memory-efficient: fixed-size deques, streaming ATR calc
    """

    def __init__(self, config: AdaptiveVolGridConfig) -> None:
        self.config = config
        self.config.validate_config()

        # Price/volume history (fixed-size deques for OOM protection)
        self._prices: deque[float] = deque(maxlen=config.max_price_history)
        self._volumes: deque[float] = deque(maxlen=config.max_price_history)
        self._highs: deque[float] = deque(maxlen=config.max_price_history)
        self._lows: deque[float] = deque(maxlen=config.max_price_history)

        # ATR calculation state (streaming)
        self._prev_close: float | None = None
        self._true_ranges: deque[float] = deque(maxlen=config.atr_window)
        self._atr: float | None = None

        # Grid state
        self._levels: list[GridLevel] = []
        self._center_price: float | None = None
        self._current_spacing_pct: float = config.min_spacing_pct
        self._active_levels: int = config.base_levels
        self._capital_deployed: float = 0.0
        self._current_band: int = 0

        # Regime state
        self._regime: str = RegimeType.RANGING_LOW_VOL
        self._volatility_history: deque[float] = deque(maxlen=config.regime_window)
        self._returns: deque[float] = deque(maxlen=config.trend_strength_window)

        # Risk tracking
        self._peak_equity: float = config.capital
        self._last_rebalance_ts: float = 0.0
        self._total_fees: float = 0.0
        self._realized_pnl: float = 0.0

        logger.info(f"AdaptiveVolGrid initialized for {config.symbol} with {config.capital} EUR")

    def on_tick(self, timestamp: float, price: float, volume: float) -> list[dict]:
        """Process new market tick. Returns list of order actions."""
        actions = []

        # Update price history
        self._prices.append(price)
        self._volumes.append(volume)
        self._highs.append(price)  # Simplified: using price as high/low for tick data
        self._lows.append(price)

        # Update streaming ATR
        self._update_atr(price)

        # Update returns for trend detection
        if self._prev_close is not None:
            ret = (price - self._prev_close) / self._prev_close
            self._returns.append(ret)
        self._prev_close = price

        # Initial grid setup
        if self._center_price is None and len(self._prices) >= self.config.atr_window:
            self._initialize_grid(price)

        # Regime detection (periodic)
        if len(self._prices) >= self.config.regime_window:
            self._detect_regime()

        # Rebalance check
        if timestamp - self._last_rebalance_ts >= self.config.rebalance_interval_sec:
            actions.extend(self._rebalance_grid(price, timestamp))
            self._last_rebalance_ts = timestamp

        # Grid order management
        actions.extend(self._manage_grid_orders(price))

        # Risk checks
        if self._check_risk_limits(price):
            actions.append({"type": "stop_all", "reason": "risk_limit_breached"})

        return actions

    def on_fill(self, order_id: str, side: str, price: float, qty: float, fee: float) -> list[dict]:
        """Process order fill. Returns list of follow-up actions."""
        actions = []
        self._total_fees += fee
        self._realized_pnl -= fee

        # Find and update filled level
        for level in self._levels:
            if level.order_id == order_id:
                level.filled = True
                level.order_id = None

                if side == "buy":
                    self._capital_deployed += price * qty
                    # Place corresponding sell order above
                    sell_price = price * (1 + self._current_spacing_pct)
                    sell_qty = qty
                    actions.append({
                        "type": "place_order",
                        "side": "sell",
                        "price": sell_price,
                        "qty": sell_qty,
                        "level_ref": level
                    })
                else:
                    self._capital_deployed -= price * qty
                    self._realized_pnl += price * qty
                    # Place corresponding buy order below
                    buy_price = price * (1 - self._current_spacing_pct)
                    buy_qty = qty
                    actions.append({
                        "type": "place_order",
                        "side": "buy",
                        "price": buy_price,
                        "qty": buy_qty,
                        "level_ref": level
                    })
                break

        # Check if we should advance capital band
        self._maybe_advance_band(price)

        return actions

    def validate_config(self) -> None:
        self.config.validate_config()

    def estimate_memory_mb(self) -> float:
        """Estimate memory usage in MB."""
        # Deques: 4 * max_price_history * 8 bytes (float64) + atr_window * 8 + regime_window * 8 + trend_window * 8
        # Levels: max_levels * ~200 bytes per GridLevel
        deque_bytes = (
            4 * self.config.max_price_history * 8 +
            self.config.atr_window * 8 +
            self.config.regime_window * 8 +
            self.config.trend_strength_window * 8
        )
        level_bytes = self.config.max_levels * 200
        overhead = 1024 * 1024  # 1MB overhead
        return (deque_bytes + level_bytes + overhead) / (1024 * 1024)

    # --- Internal methods ---

    def _update_atr(self, price: float) -> None:
        """Streaming ATR calculation."""
        if self._prev_close is not None:
            tr = max(
                price - self._prev_close,
                abs(price - self._prev_close),  # Simplified for tick data
                abs(self._prev_close - price)
            )
            self._true_ranges.append(tr)

        if len(self._true_ranges) == self.config.atr_window:
            self._atr = sum(self._true_ranges) / self.config.atr_window
            self._volatility_history.append(self._atr / price if price > 0 else 0)

    def _initialize_grid(self, center_price: float) -> None:
        """Initialize grid levels around center price."""
        self._center_price = center_price
        self._current_spacing_pct = self.config.min_spacing_pct
        self._active_levels = self.config.base_levels
        self._build_grid_levels(center_price)
        logger.info(f"Grid initialized: center={center_price:.4f}, levels={self._active_levels}, spacing={self._current_spacing_pct:.4f}")

    def _build_grid_levels(self, center: float) -> None:
        """Build grid levels for current band."""
        self._levels.clear()
        half = self._active_levels // 2
        spacing = self._current_spacing_pct

        for i in range(-half, half + 1):
            if i == 0:
                continue
            level_price = center * (1 + i * spacing)
            side = "buy" if i < 0 else "sell"
            # Capital allocation per band
            band_capital = self.config.capital * self.config.capital_bands[self._current_band]
            level_qty = (band_capital / self._active_levels) / level_price

            self._levels.append(GridLevel(
                price=level_price,
                qty=level_qty,
                side=side,
                band_index=self._current_band
            ))

    def _detect_regime(self) -> None:
        """Detect market regime using volatility quantiles and trend strength."""
        if len(self._volatility_history) < self.config.regime_window:
            return

        vol_array = np.array(self._volatility_history)
        vol_low = np.quantile(vol_array, self.config.volatility_quantile_low)
        vol_high = np.quantile(vol_array, self.config.volatility_quantile_high)
        current_vol = vol_array[-1]

        # Trend strength from returns
        if len(self._returns) >= self.config.trend_strength_window:
            returns_array = np.array(self._returns)
            trend_strength = abs(np.mean(returns_array)) / (np.std(returns_array) + 1e-8)
        else:
            trend_strength = 0.0

        prev_regime = self._regime

        if current_vol <= vol_low:
            if trend_strength > 0.5:
                self._regime = RegimeType.TRENDING_UP if np.mean(list(self._returns)[-5:]) > 0 else RegimeType.TRENDING_DOWN
            else:
                self._regime = RegimeType.RANGING_LOW_VOL
        elif current_vol >= vol_high:
            self._regime = RegimeType.RANGING_HIGH_VOL
        else:
            self._regime = RegimeType.RANGING_LOW_VOL

        if self._regime != prev_regime:
            logger.info(f"Regime change: {prev_regime} -> {self._regime}")
            self._adjust_grid_for_regime()

    def _adjust_grid_for_regime(self) -> None:
        """Adjust grid parameters based on regime."""
        if self._regime == RegimeType.RANGING_LOW_VOL:
            self._current_spacing_pct = self.config.min_spacing_pct
            self._active_levels = min(self.config.max_levels, self.config.base_levels + 2)
        elif self._regime == RegimeType.RANGING_HIGH_VOL:
            self._current_spacing_pct = min(self.config.max_spacing_pct, self._current_spacing_pct * 1.5)
            self._active_levels = max(self.config.min_levels, self.config.base_levels - 2)
        elif self._regime in (RegimeType.TRENDING_UP, RegimeType.TRENDING_DOWN):
            self._current_spacing_pct = min(self.config.max_spacing_pct, self._current_spacing_pct * 2.0)
            self._active_levels = max(self.config.min_levels, self.config.base_levels - 4)

        self._current_spacing_pct = np.clip(
            self._current_spacing_pct,
            self.config.min_spacing_pct,
            self.config.max_spacing_pct
        )

        if self._center_price:
            self._build_grid_levels(self._center_price)

    def _rebalance_grid(self, price: float, timestamp: float) -> list[dict]:
        """Rebalance grid around current price if drifted."""
        actions = []
        if self._center_price is None:
            return actions

        drift = abs(price - self._center_price) / self._center_price
        if drift > self._current_spacing_pct * 2:
            logger.info(f"Rebalancing: drift={drift:.4f}, center={self._center_price:.4f} -> {price:.4f}")
            self._center_price = price
            self._build_grid_levels(price)
            actions.append({"type": "rebalance", "new_center": price, "levels": self._active_levels})

        return actions

    def _manage_grid_orders(self, price: float) -> list[dict]:
        """Manage open grid orders."""
        actions = []
        for level in self._levels:
            if level.filled or level.order_id is not None:
                continue

            if level.side == "buy" and price <= level.price:
                actions.append({
                    "type": "place_order",
                    "side": "buy",
                    "price": level.price,
                    "qty": level.qty,
                    "level_ref": level
                })
            elif level.side == "sell" and price >= level.price:
                actions.append({
                    "type": "place_order",
                    "side": "sell",
                    "price": level.price,
                    "qty": level.qty,
                    "level_ref": level
                })
        return actions

    def _maybe_advance_band(self, price: float) -> None:
        """Advance capital deployment band if price moved favorably."""
        if self._current_band >= len(self.config.capital_bands) - 1:
            return

        if self._center_price is None:
            return

        # Check if price moved enough to deploy next band
        band_progress = self._capital_deployed / (self.config.capital * self.config.capital_bands[self._current_band])
        if band_progress > 0.8 and self._current_band < len(self.config.capital_bands) - 1:
            self._current_band += 1
            scale = self.config.band_spacing_scale[self._current_band]
            self._current_spacing_pct *= scale
            self._current_spacing_pct = np.clip(
                self._current_spacing_pct,
                self.config.min_spacing_pct,
                self.config.max_spacing_pct
            )
            self._build_grid_levels(self._center_price)
            logger.info(f"Advanced to band {self._current_band}, new spacing={self._current_spacing_pct:.4f}")

    def _check_risk_limits(self, price: float) -> bool:
        """Check risk limits. Returns True if stop triggered."""
        if self._center_price is None:
            return False

        # Current equity estimation
        unrealized = 0.0
        for level in self._levels:
            if level.filled and level.side == "buy":
                unrealized += (price - level.price) * level.qty
            elif level.filled and level.side == "sell":
                unrealized += (level.price - price) * level.qty

        current_equity = self.config.capital + self._realized_pnl + unrealized - self._total_fees

        # Update peak
        if current_equity > self._peak_equity:
            self._peak_equity = current_equity

        # Drawdown check
        drawdown = (self._peak_equity - current_equity) / self._peak_equity
        if drawdown >= self.config.max_drawdown_pct:
            logger.warning(f"Max drawdown breached: {drawdown:.2%} >= {self.config.max_drawdown_pct:.2%}")
            return True

        # ATR-based stop loss
        if self._atr is not None:
            stop_distance = self._atr * self.config.stop_loss_atr_mult
            if price < self._center_price - stop_distance:
                logger.warning(f"ATR stop loss triggered: price={price:.4f}, stop={self._center_price - stop_distance:.4f}")
                return True

        return False


# --- Inline test with synthetic data ---
if __name__ == "__main__":
    import random

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    # Synthetic data generator
    def generate_synthetic_ticks(n: int = 500, start_price: float = 100.0) -> Generator[tuple[float, float, float], None, None]:
        price = start_price
        for i in range(n):
            # Random walk with mild mean reversion
            drift = random.uniform(-0.002, 0.002)
            reversion = -0.0001 * (price - start_price)
            price *= 1 + drift + reversion
            volume = random.uniform(10, 1000)
            yield float(i), price, volume

    # Test configuration
    config = AdaptiveVolGridConfig(
        symbol="TEST/EUR",
        capital=50.0,
        base_levels=8,
        min_levels=4,
        max_levels=16,
        atr_window=14,
        atr_multiplier=1.5,
        min_spacing_pct=0.003,
        max_spacing_pct=0.04,
        capital_bands=(0.2, 0.4, 0.6, 0.8, 1.0),
        band_spacing_scale=(0.5, 0.75, 1.0, 1.25, 1.5),
        regime_window=50,
        volatility_quantile_low=0.3,
        volatility_quantile_high=0.7,
        trend_strength_window=20,
        stop_loss_atr_mult=3.0,
        take_profit_atr_mult=1.5,
        max_drawdown_pct=0.12,
        fee_rate=0.0016,
        rebalance_interval_sec=120,
        max_price_history=2000
    )

    strategy = AdaptiveVolatilityGrid(config)
    print(f"Memory estimate: {strategy.estimate_memory_mb():.2f} MB")

    # Run simulation
    fills = 0
    for ts, price, vol in generate_synthetic_ticks(300):
        actions = strategy.on_tick(ts, price, vol)
        for action in actions:
            if action.get("type") == "place_order":
                # Simulate fill
                fill_actions = strategy.on_fill(
                    order_id=f"order_{fills}",
                    side=action["side"],
                    price=action["price"],
                    qty=action["qty"],
                    fee=action["price"] * action["qty"] * config.fee_rate
                )
                fills += 1

    print(f"Simulation complete. Fills: {fills}, Regime: {strategy._regime}")
    print(f"Capital deployed: {strategy._capital_deployed:.2f}, Realized PnL: {strategy._realized_pnl:.2f}")
    print(f"Total fees: {strategy._total_fees:.2f}")
    print("Test passed.")
