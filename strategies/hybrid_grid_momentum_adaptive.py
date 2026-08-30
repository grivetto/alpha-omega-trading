#!/usr/bin/env python3
"""
Hybrid Grid-Momentum-Adaptive Strategy for Denaro Trading Infrastructure.

Combines:
- Grid trading for range-bound markets (spread capture)
- Momentum following for trending markets (directional bias)
- Adaptive regime switching (volatility/regime awareness)
- Asymmetric risk management (Kelly sizing, dynamic stops, EUR floor)

Architecture:
- StrategyBase: abstract interface (on_tick, on_fill, validate_config, estimate_memory_mb)
- Config-driven via dataclass (HMAConfig)
- OOM-safe: generators, chunked CSV ingestion, explicit del + gc.collect
- Inline self-test with synthetic data
"""

from __future__ import annotations

import csv
import gc
import json
import math
import os
import sys
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Generator, Iterator, Optional
from collections import deque


class Action(Enum):
    """Trading actions."""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    CANCEL_ALL = "CANCEL_ALL"


class Regime(Enum):
    """Market regime classification."""
    BULL_QUIET = "BULL_QUIET"
    BULL_VOLATILE = "BULL_VOLATILE"
    BEAR_QUIET = "BEAR_QUIET"
    BEAR_VOLATILE = "BEAR_VOLATILE"
    RANGING = "RANGING"
    UNKNOWN = "UNKNOWN"


class OrderSide(Enum):
    """Order side."""
    BUY = "buy"
    SELL = "sell"


@dataclass(frozen=True, slots=True)
class Tick:
    """Market tick data."""
    timestamp: float
    symbol: str
    bid: float
    ask: float
    mid: float
    volume: float
    high: float = 0.0
    low: float = 0.0

    def __post_init__(self):
        if self.high == 0.0:
            object.__setattr__(self, 'high', self.mid)
        if self.low == 0.0:
            object.__setattr__(self, 'low', self.mid)

    @property
    def spread(self) -> float:
        return self.ask - self.bid

    @property
    def spread_pct(self) -> float:
        return self.spread / self.mid if self.mid > 0 else 0.0


@dataclass(frozen=True, slots=True)
class Fill:
    """Order fill notification."""
    order_id: str
    symbol: str
    side: OrderSide
    price: float
    qty: float
    fee: float
    timestamp: float


@dataclass(frozen=True, slots=True)
class Order:
    """Order representation."""
    id: str
    symbol: str
    side: OrderSide
    price: float
    qty: float
    timestamp: float
    status: str = "open"


@dataclass(slots=True)
class Position:
    """Current position state."""
    symbol: str
    qty: float = 0.0
    avg_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0


@dataclass
class HMAConfig:
    """
    Hybrid Momentum-Adaptive Grid Configuration.

    All parameters are config-driven via JSON/env. No hardcoded magic numbers.
    """
    # Symbol & Exchange
    symbol: str = "SOL/EUR"
    exchange: str = "okx"

    # Capital & Risk
    total_capital_eur: float = 250.0
    eur_floor: float = 15.0
    max_drawdown_pct: float = 0.05
    max_position_pct: float = 0.5
    kelly_fraction: float = 0.25

    # Grid Parameters
    grid_levels: int = 6
    base_spread_pct: float = 0.02
    grid_range_pct: float = 0.03
    martingale_factor: float = 1.15
    min_order_eur: float = 10.0

    # Momentum Parameters
    ema_fast: int = 20
    ema_slow: int = 50
    ema_trend: int = 200
    rsi_period: int = 14
    rsi_oversold: float = 35.0
    rsi_overbought: float = 65.0
    momentum_threshold: float = 0.01

    # Adaptive/Regime Parameters
    atr_period: int = 14
    atr_multiplier: float = 2.0
    regime_lookback_hours: int = 200
    volatility_window: int = 50
    regime_update_interval_sec: int = 900

    # Asymmetric Risk Management
    stop_loss_pct: float = 0.02
    take_profit_pct: float = 0.04
    trailing_stop_pct: float = 0.015
    max_consecutive_losses: int = 3
    cooldown_after_loss_sec: int = 300

    # Execution
    maker_fee: float = 0.0016
    taker_fee: float = 0.0026
    slippage_pct: float = 0.0005
    tick_size: float = 0.01
    lot_size: float = 0.001

    # Memory / Performance
    max_tick_history: int = 5000
    csv_chunk_size: int = 10000
    gc_interval: int = 5
    max_memory_mb: float = 100.0

    def validate(self) -> None:
        """Validate configuration constraints."""
        if self.total_capital_eur <= 0:
            raise ConfigError("total_capital_eur must be > 0")
        if self.eur_floor < 0:
            raise ConfigError("eur_floor must be >= 0")
        if not 0 < self.max_drawdown_pct < 1:
            raise ConfigError("max_drawdown_pct must be in (0, 1)")
        if not 0 < self.max_position_pct <= 1:
            raise ConfigError("max_position_pct must be in (0, 1]")
        if not 0 < self.kelly_fraction <= 1:
            raise ConfigError("kelly_fraction must be in (0, 1]")
        if self.grid_levels < 2:
            raise ConfigError("grid_levels must be >= 2")
        if not 0 < self.base_spread_pct < 0.1:
            raise ConfigError("base_spread_pct must be in (0, 0.1)")
        if not 0 < self.grid_range_pct < 0.5:
            raise ConfigError("grid_range_pct must be in (0, 0.5)")
        if self.martingale_factor <= 1.0:
            raise ConfigError("martingale_factor must be > 1.0")
        if self.min_order_eur <= 0:
            raise ConfigError("min_order_eur must be > 0")
        if self.ema_fast >= self.ema_slow:
            raise ConfigError("ema_fast must be < ema_slow")
        if self.ema_slow >= self.ema_trend:
            raise ConfigError("ema_slow must be < ema_trend")
        if not 0 < self.rsi_oversold < self.rsi_overbought < 100:
            raise ConfigError("RSI thresholds invalid: oversold < overbought < 100")
        if self.atr_period < 2:
            raise ConfigError("atr_period must be >= 2")
        if self.maker_fee >= self.taker_fee:
            raise ConfigError("maker_fee must be < taker_fee")
        if self.base_spread_pct < 3 * (self.maker_fee + self.taker_fee):
            raise ConfigError(
                f"base_spread_pct ({self.base_spread_pct:.4f}) must be >= "
                f"3x round-trip fee ({3*(self.maker_fee+self.taker_fee):.4f})"
            )
        if self.max_memory_mb <= 0:
            raise ConfigError("max_memory_mb must be > 0")

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_json(cls, path: str | Path) -> HMAConfig:
        with open(path) as f:
            data = json.load(f)
        return cls(**data)

    @classmethod
    def from_env(cls, prefix: str = "HMA_") -> HMAConfig:
        """Load config from environment variables with HMA_ prefix."""
        import os
        kwargs = {}
        for key, value in os.environ.items():
            if key.startswith(prefix):
                field_name = key[len(prefix):].lower()
                if hasattr(cls, field_name):
                    field_type = cls.__annotations__.get(field_name, str)
                    if field_type == bool:
                        kwargs[field_name] = value.lower() in ("1", "true", "yes")
                    elif field_type == int:
                        kwargs[field_name] = int(value)
                    elif field_type == float:
                        kwargs[field_name] = float(value)
                    else:
                        kwargs[field_name] = value
        return cls(**kwargs)


class StrategyError(Exception):
    """Base strategy exception."""
    pass


class ConfigError(StrategyError):
    """Configuration validation error."""
    pass


class DataError(StrategyError):
    """Market data error."""
    pass


class ExecutionError(StrategyError):
    """Order execution error."""
    pass


class RiskError(StrategyError):
    """Risk management violation."""
    pass


class StrategyBase(ABC):
    """
    Abstract base class for all Denaro strategies.

    Interface:
    - on_tick(tick): process market tick, return Action + params
    - on_fill(fill): process order fill, update state
    - validate_config(): raise ConfigError if invalid
    - estimate_memory_mb(): return estimated memory footprint in MB
    """

    @abstractmethod
    def on_tick(self, tick: Tick) -> tuple[Action, dict[str, Any]]:
        """Process a market tick. Returns (action, parameters)."""
        ...

    @abstractmethod
    def on_fill(self, fill: Fill) -> None:
        """Process an order fill. Updates internal state."""
        ...

    @abstractmethod
    def validate_config(self) -> None:
        """Validate strategy configuration. Raises ConfigError if invalid."""
        ...

    @abstractmethod
    def estimate_memory_mb(self) -> float:
        """Estimate current memory usage in MB."""
        ...

    @abstractmethod
    def get_state(self) -> dict[str, Any]:
        """Return serializable state for persistence."""
        ...

    @abstractmethod
    def load_state(self, state: dict[str, Any]) -> None:
        """Load state from persistence."""
        ...


class HybridGridMomentumAdaptive(StrategyBase):
    """
    Hybrid Grid-Momentum-Adaptive Strategy.

    Three-layer architecture:
    1. REGIME LAYER: Classifies market (BULL/BEAR/RANGING, QUIET/VOLATILE)
    2. GRID LAYER: Places buy/sell orders around dynamic center (ATR-adjusted)
    3. MOMENTUM LAYER: Biases grid center + sizing based on trend/momentum
    4. RISK LAYER: Asymmetric Kelly sizing, dynamic stops, EUR floor guard
    """

    def __init__(self, config: HMAConfig):
        self.config = config
        self.config.validate()

        # State
        self._ticks: deque[Tick] = deque(maxlen=config.max_tick_history)
        self._positions: dict[str, Position] = {}
        self._open_orders: dict[str, Order] = {}
        self._grid_center: float = 0.0
        self._grid_levels_active: list[dict] = []
        self._current_regime: Regime = Regime.UNKNOWN
        self._regime_multiplier: float = 1.0
        self._last_regime_update: float = 0.0

        # Indicators (incremental)
        self._ema_fast: float = 0.0
        self._ema_slow: float = 0.0
        self._ema_trend: float = 0.0
        self._rsi_gain: float = 0.0
        self._rsi_loss: float = 0.0
        self._atr: float = 0.0
        self._prev_close: float = 0.0
        self._tick_count: int = 0

        # Risk tracking
        self._consecutive_losses: int = 0
        self._last_loss_time: float = 0.0
        self._daily_pnl: float = 0.0
        self._peak_equity: float = config.total_capital_eur
        self._total_fees: float = 0.0
        _ = 0

        # CSV backtest ingestion state
        self._csv_chunk_counter: int = 0

    # --------------------------------------------------------------------- #
    # StrategyBase Interface
    # --------------------------------------------------------------------- #

    def on_tick(self, tick: Tick) -> tuple[Action, dict[str, Any]]:
        """
        Main tick handler. Returns action and parameters.

        Flow:
        1. Update indicators incrementally
        2. Update regime if interval elapsed
        3. Compute grid center with momentum bias
        4. Check risk guards (EUR floor, drawdown, consecutive losses)
        5. Generate grid orders or momentum entries
        """
        self._update_indicators(tick)
        self._ticks.append(tick)
        self._tick_count += 1

        # Periodic regime update
        if tick.timestamp - self._last_regime_update >= self.config.regime_update_interval_sec:
            self._update_regime()

        # Risk guards
        if not self._check_risk_guards(tick):
            return Action.CANCEL_ALL, {"reason": "risk_guard_triggered"}

        # Generate actions based on regime
        if self._current_regime in (Regime.BULL_QUIET, Regime.BULL_VOLATILE):
            return self._bull_market_action(tick)
        elif self._current_regime in (Regime.BEAR_QUIET, Regime.BEAR_VOLATILE):
            return self._bear_market_action(tick)
        elif self._current_regime == Regime.RANGING:
            return self._ranging_market_action(tick)
        else:
            return Action.HOLD, {"reason": "unknown_regime"}

    def on_fill(self, fill: Fill) -> None:
        """Process fill: update position, PnL, risk metrics."""
        pos = self._positions.get(fill.symbol)
        if pos is None:
            pos = Position(symbol=fill.symbol, qty=0.0, avg_price=0.0)
            self._positions[fill.symbol] = pos

        if fill.side == OrderSide.BUY:
            new_qty = pos.qty + fill.qty
            if new_qty > 0:
                pos.avg_price = ((pos.qty * pos.avg_price) + (fill.qty * fill.price)) / new_qty
            pos.qty = new_qty
        else:
            realized = (fill.price - pos.avg_price) * fill.qty - fill.fee
            pos.realized_pnl += realized
            pos.qty -= fill.qty
            self._daily_pnl += realized
            self._total_fees += fill.fee

            # Track consecutive losses for asymmetric risk
            if realized < 0:
                self._consecutive_losses += 1
                self._last_loss_time = fill.timestamp
            else:
                self._consecutive_losses = 0

            # Update peak equity
            equity = self._calculate_equity(tick_mid=fill.price)
            if equity > self._peak_equity:
                self._peak_equity = equity

        # Remove filled order
        self._open_orders.pop(fill.order_id, None)

        # Recenter grid if position changed significantly
        if abs(pos.qty) > self.config.total_capital_eur * self.config.max_position_pct * 0.5 / max(fill.price, 1):
            self._recenter_grid(fill.price)

    def validate_config(self) -> None:
        """Validate configuration. Delegates to config.validate()."""
        self.config.validate()

    def estimate_memory_mb(self) -> float:
        """
        Estimate memory footprint in MB.

        Accounts for:
        - Tick history deque
        - Position/order dicts
        - Indicator buffers
        """
        tick_mem = len(self._ticks) * 200  # ~200 bytes per Tick
        pos_mem = len(self._positions) * 150
        order_mem = len(self._open_orders) * 150
        indicator_mem = 1024  # fixed overhead
        total_bytes = tick_mem + pos_mem + order_mem + indicator_mem
        return total_bytes / (1024 * 1024)

    def get_state(self) -> dict[str, Any]:
        """Serialize state for persistence."""
        return {
            "config": asdict(self.config),
            "grid_center": self._grid_center,
            "grid_levels_active": self._grid_levels_active,
            "current_regime": self._current_regime.value,
            "regime_multiplier": self._regime_multiplier,
            "last_regime_update": self._last_regime_update,
            "ema_fast": self._ema_fast,
            "ema_slow": self._ema_slow,
            "ema_trend": self._ema_trend,
            "rsi_gain": self._rsi_gain,
            "rsi_loss": self._rsi_loss,
            "atr": self._atr,
            "prev_close": self._prev_close,
            "consecutive_losses": self._consecutive_losses,
            "last_loss_time": self._last_loss_time,
            "daily_pnl": self._daily_pnl,
            "peak_equity": self._peak_equity,
            "total_fees": self._total_fees,
            "positions": {k: asdict(v) for k, v in self._positions.items()},
            "open_orders": {k: asdict(v) for k, v in self._open_orders.items()},
        }

    def load_state(self, state: dict[str, Any]) -> None:
        """Load state from persistence."""
        self._grid_center = state.get("grid_center", 0.0)
        self._grid_levels_active = state.get("grid_levels_active", [])
        self._current_regime = Regime(state.get("current_regime", "UNKNOWN"))
        self._regime_multiplier = state.get("regime_multiplier", 1.0)
        self._last_regime_update = state.get("last_regime_update", 0.0)
        self._ema_fast = state.get("ema_fast", 0.0)
        self._ema_slow = state.get("ema_slow", 0.0)
        self._ema_trend = state.get("ema_trend", 0.0)
        self._rsi_gain = state.get("rsi_gain", 0.0)
        self._rsi_loss = state.get("rsi_loss", 0.0)
        self._atr = state.get("atr", 0.0)
        self._prev_close = state.get("prev_close", 0.0)
        self._consecutive_losses = state.get("consecutive_losses", 0)
        self._last_loss_time = state.get("last_loss_time", 0.0)
        self._daily_pnl = state.get("daily_pnl", 0.0)
        self._peak_equity = state.get("peak_equity", self.config.total_capital_eur)
        self._total_fees = state.get("total_fees", 0.0)

        self._positions = {
            k: Position(**v) for k, v in state.get("positions", {}).items()
        }
        self._open_orders = {
            k: Order(**v) for k, v in state.get("open_orders", {}).items()
        }

    # --------------------------------------------------------------------- #
    # Indicator Updates (Incremental, O(1) memory)
    # --------------------------------------------------------------------- #

    def _update_indicators(self, tick: Tick) -> None:
        """Update all indicators incrementally with new tick."""
        price = tick.mid

        # EMA updates (Wilder smoothing)
        alpha_fast = 2.0 / (self.config.ema_fast + 1)
        alpha_slow = 2.0 / (self.config.ema_slow + 1)
        alpha_trend = 2.0 / (self.config.ema_trend + 1)

        if self._ema_fast == 0:
            self._ema_fast = self._ema_slow = self._ema_trend = price
        else:
            self._ema_fast = alpha_fast * price + (1 - alpha_fast) * self._ema_fast
            self._ema_slow = alpha_slow * price + (1 - alpha_slow) * self._ema_slow
            self._ema_trend = alpha_trend * price + (1 - alpha_trend) * self._ema_trend

        # RSI (Wilder)
        if self._prev_close > 0:
            delta = price - self._prev_close
            gain = max(delta, 0.0)
            loss = max(-delta, 0.0)
            alpha_rsi = 1.0 / self.config.rsi_period
            self._rsi_gain = alpha_rsi * gain + (1 - alpha_rsi) * self._rsi_gain
            self._rsi_loss = alpha_rsi * loss + (1 - alpha_rsi) * self._rsi_loss

        # ATR (True Range EMA)
        tr = max(
            tick.ask - tick.bid,
            abs(tick.ask - self._prev_close) if self._prev_close > 0 else 0,
            abs(tick.bid - self._prev_close) if self._prev_close > 0 else 0,
        )
        alpha_atr = 1.0 / self.config.atr_period
        if self._atr == 0:
            self._atr = tr
        else:
            self._atr = alpha_atr * tr + (1 - alpha_atr) * self._atr

        self._prev_close = price

    def _get_rsi(self) -> float:
        """Calculate current RSI value."""
        if self._rsi_loss == 0:
            return 50.0
        rs = self._rsi_gain / self._rsi_loss
        return 100.0 - (100.0 / (1.0 + rs))

    def _get_momentum_signal(self) -> float:
        """
        Returns momentum signal in [-1, 1]:
        - Positive: bullish momentum
        - Negative: bearish momentum
        - Near 0: neutral
        """
        if self._ema_trend == 0:
            return 0.0

        # Trend direction
        trend = 1.0 if self._ema_fast > self._ema_trend else -1.0

        # Momentum strength (EMA fast vs slow)
        momentum = (self._ema_fast - self._ema_slow) / max(self._ema_slow, 1e-8)

        # RSI component
        rsi = self._get_rsi()
        rsi_signal = (rsi - 50.0) / 50.0  # [-1, 1]

        # Combine with weights
        signal = 0.5 * trend + 0.3 * math.tanh(momentum * 100) + 0.2 * rsi_signal
        return max(-1.0, min(1.0, signal))

    # --------------------------------------------------------------------- #
    # Regime Classification
    # --------------------------------------------------------------------- #

    def _update_regime(self) -> None:
        """Classify market regime based on trend + volatility."""
        if len(self._ticks) < max(self.config.ema_trend, self.config.volatility_window):
            self._current_regime = Regime.UNKNOWN
            self._regime_multiplier = 1.0
            self._last_regime_update = time.time()
            return

        # Trend: price vs EMA200
        current_price = self._ticks[-1].mid
        trend_bull = current_price > self._ema_trend

        # Volatility: ATR as % of price
        vol_pct = self._atr / max(current_price, 1e-8)
        is_volatile = vol_pct > (self.config.atr_multiplier * 0.01)

        # Ranging detection: price within grid_range of center
        if self._grid_center > 0:
            ranging = abs(current_price - self._grid_center) / self._grid_center < self.config.grid_range_pct * 0.5
        else:
            ranging = False

        # Classify
        if ranging:
            self._current_regime = Regime.RANGING
            self._regime_multiplier = 1.0
        elif trend_bull and not is_volatile:
            self._current_regime = Regime.BULL_QUIET
            self._regime_multiplier = 1.5
        elif trend_bull and is_volatile:
            self._current_regime = Regime.BULL_VOLATILE
            self._regime_multiplier = 1.2
        elif not trend_bull and not is_volatile:
            self._current_regime = Regime.BEAR_QUIET
            self._regime_multiplier = 0.7
        else:
            self._current_regime = Regime.BEAR_VOLATILE
            self._regime_multiplier = 0.4

        self._last_regime_update = time.time()

    # --------------------------------------------------------------------- #
    # Risk Guards (Asymmetric)
    # --------------------------------------------------------------------- #

    def _check_risk_guards(self, tick: Tick) -> bool:
        """
        Asymmetric risk checks. Returns False if trading should halt.

        Checks:
        1. EUR floor (capital preservation)
        2. Max drawdown
        3. Consecutive losses cooldown
        4. Daily loss limit
        5. Position size limit
        """
        equity = self._calculate_equity(tick.mid)

        # 1. EUR Floor
        eur_free = self._estimate_eur_free(equity)
        if eur_free < self.config.eur_floor:
            return False

        # 2. Max Drawdown
        drawdown = (self._peak_equity - equity) / max(self._peak_equity, 1e-8)
        if drawdown >= self.config.max_drawdown_pct:
            return False

        # 3. Consecutive Losses Cooldown
        if self._consecutive_losses >= self.config.max_consecutive_losses:
            if tick.timestamp - self._last_loss_time < self.config.cooldown_after_loss_sec:
                return False
            # Reset after cooldown
            self._consecutive_losses = 0

        # 4. Daily Loss Limit (2x max_drawdown)
        if self._daily_pnl < -2 * self.config.max_drawdown_pct * self.config.total_capital_eur:
            return False

        # 5. Position Size
        pos = self._positions.get(self.config.symbol)
        if pos and abs(pos.qty * tick.mid) > self.config.total_capital_eur * self.config.max_position_pct:
            return False

        return True

    def _estimate_eur_free(self, equity: float) -> float:
        """Estimate free EUR (equity - position value)."""
        pos = self._positions.get(self.config.symbol)
        if pos:
            return equity - abs(pos.qty * pos.avg_price)
        return equity

    def _calculate_equity(self, tick_mid: float) -> float:
        """Calculate total equity in EUR."""
        equity = self.config.total_capital_eur + self._daily_pnl
        for pos in self._positions.values():
            equity += pos.qty * (tick_mid - pos.avg_price)
        return equity

    def _kelly_position_size(self, win_rate: float, win_loss_ratio: float) -> float:
        """
        Kelly Criterion position sizing with fractional Kelly.

        f* = (p * b - q) / b where p=win_rate, b=win_loss_ratio, q=1-p
        """
        if win_loss_ratio <= 0 or win_rate <= 0 or win_rate >= 1:
            return self.config.min_order_eur

        kelly = (win_rate * win_loss_ratio - (1 - win_rate)) / win_loss_ratio
        kelly = max(0.0, min(kelly, 1.0)) * self.config.kelly_fraction
        return self.config.total_capital_eur * kelly

    # --------------------------------------------------------------------- #
    # Regime-Specific Actions
    # --------------------------------------------------------------------- #

    def _bull_market_action(self, tick: Tick) -> tuple[Action, dict[str, Any]]:
        """Bull market: bias grid UP, larger buy sizes, trailing stops."""
        momentum = self._get_momentum_signal()
        bias = 0.5 * momentum * self._regime_multiplier  # [-0.75, 0.75]

        # Dynamic grid center with momentum bias
        atr_dist = self._atr * self.config.atr_multiplier
        self._grid_center = tick.mid * (1 + bias * self.config.grid_range_pct * 0.5)

        # Grid levels (asymmetric: more buys below, fewer sells above)
        n_buys = int(self.config.grid_levels * (0.6 + 0.2 * max(momentum, 0)))
        n_sells = self.config.grid_levels - n_buys

        orders = self._build_grid_orders(
            tick.mid,
            n_buys=n_buys,
            n_sells=n_sells,
            spread_pct=self.config.base_spread_pct * (1 + max(momentum, 0) * 0.5),
            bias=bias,
        )

        if orders:
            return Action.BUY, {"orders": orders, "regime": self._current_regime.value}
        return Action.HOLD, {"reason": "no_grid_levels"}

    def _bear_market_action(self, tick: Tick) -> tuple[Action, dict[str, Any]]:
        """Bear market: bias grid DOWN, reduce exposure, tight stops."""
        momentum = self._get_momentum_signal()
        bias = 0.5 * momentum * self._regime_multiplier  # Negative in bear

        # Reduce grid levels in bear
        effective_levels = max(2, int(self.config.grid_levels * self._regime_multiplier))
        n_sells = int(effective_levels * (0.6 - 0.2 * min(momentum, 0)))
        n_buys = effective_levels - n_sells

        atr_dist = self._atr * self.config.atr_multiplier
        self._grid_center = tick.mid * (1 + bias * self.config.grid_range_pct * 0.5)

        orders = self._build_grid_orders(
            tick.mid,
            n_buys=n_buys,
            n_sells=n_sells,
            spread_pct=self.config.base_spread_pct * (1.5 - 0.3 * self._regime_multiplier),
            bias=bias,
        )

        if orders:
            return Action.SELL, {"orders": orders, "regime": self._current_regime.value}
        return Action.HOLD, {"reason": "no_grid_levels"}

    def _ranging_market_action(self, tick: Tick) -> tuple[Action, dict[str, Any]]:
        """Ranging market: symmetric grid around center, mean reversion."""
        # Recenter on VWAP of recent ticks
        recent = list(self._ticks)[-self.config.volatility_window:]
        if recent:
            vwap = sum(t.mid * t.volume for t in recent) / sum(t.volume for t in recent)
            self._grid_center = 0.7 * self._grid_center + 0.3 * vwap

        n_buys = n_sells = self.config.grid_levels // 2
        orders = self._build_grid_orders(
            tick.mid,
            n_buys=n_buys,
            n_sells=n_sells,
            spread_pct=self.config.base_spread_pct,
            bias=0.0,
        )

        if orders:
            return Action.BUY, {"orders": orders, "regime": self._current_regime.value}
        return Action.HOLD, {"reason": "no_grid_levels"}

    def _build_grid_orders(
        self,
        mid: float,
        n_buys: int,
        n_sells: int,
        spread_pct: float,
        bias: float,
    ) -> list[dict[str, Any]]:
        """Build grid order levels with martingale sizing and tick rounding."""
        orders = []
        base_qty_eur = self.config.min_order_eur * self._regime_multiplier
        base_qty_eur = max(base_qty_eur, self.config.min_order_eur)

        # Buy levels (below mid)
        for i in range(1, n_buys + 1):
            level_pct = spread_pct * i * (1 + bias)
            price = mid * (1 - level_pct)
            price = self._round_to_tick(price)
            qty_eur = base_qty_eur * (self.config.martingale_factor ** (i - 1))
            qty = self._round_to_lot(qty_eur / price)
            notional = qty * price

            if notional >= self.config.min_order_eur:
                orders.append({
                    "side": "buy",
                    "price": price,
                    "qty": qty,
                    "notional_eur": notional,
                    "level": i,
                })

        # Sell levels (above mid)
        for i in range(1, n_sells + 1):
            level_pct = spread_pct * i * (1 - bias)
            price = mid * (1 + level_pct)
            price = self._round_to_tick(price)
            qty_eur = base_qty_eur * (self.config.martingale_factor ** (i - 1))
            qty = self._round_to_lot(qty_eur / price)
            notional = qty * price

            if notional >= self.config.min_order_eur:
                orders.append({
                    "side": "sell",
                    "price": price,
                    "qty": qty,
                    "notional_eur": notional,
                    "level": i,
                })

        self._grid_levels_active = orders
        return orders

    def _round_to_tick(self, price: float) -> float:
        """Round price to exchange tick size."""
        tick = self.config.tick_size
        return round(round(price / tick) * tick, len(str(tick).split('.')[-1]))

    def _round_to_lot(self, qty: float) -> float:
        """Round quantity to exchange lot size."""
        step = self.config.lot_size
        return round(round(qty / step) * step, len(str(step).split('.')[-1]))

    def _recenter_grid(self, new_center: float) -> None:
        """Recenter grid around new price level."""
        self._grid_center = new_center
        # Cancel all open orders (handled by executor)
        self._open_orders.clear()

    # --------------------------------------------------------------------- #
    # OOM-Safe CSV Ingestion for Backtesting
    # --------------------------------------------------------------------- #

    @classmethod
    def from_csv_chunked(
        cls,
        csv_path: str | Path,
        config: HMAConfig,
        chunk_size: int | None = None,
        gc_interval: int | None = None,
    ) -> Generator[Tick, None, None]:
        """
        Memory-safe CSV tick generator.

        Yields Tick objects chunk by chunk, running gc.collect() periodically.
        """
        chunk_size = chunk_size or config.csv_chunk_size
        gc_interval = gc_interval or config.gc_interval

        with open(csv_path, newline="") as f:
            reader = csv.DictReader(f)
            chunk = []
            chunk_idx = 0

            for row in reader:
                try:
                    tick = Tick(
                        timestamp=float(row["timestamp"]),
                        symbol=row["symbol"],
                        bid=float(row["bid"]),
                        ask=float(row["ask"]),
                        mid=float(row["mid"]),
                        volume=float(row["volume"]),
                    )
                    chunk.append(tick)

                    if len(chunk) >= chunk_size:
                        yield from chunk
                        chunk.clear()
                        chunk_idx += 1
                        if chunk_idx % gc_interval == 0:
                            gc.collect()

                except (KeyError, ValueError) as e:
                    raise DataError(f"Invalid CSV row: {row}") from e

            # Yield remaining
            if chunk:
                yield from chunk
                gc.collect()

    def run_backtest(
        self,
        csv_path: str | Path,
        initial_capital: float | None = None,
    ) -> dict[str, Any]:
        """
        Run backtest on CSV data. OOM-safe via chunked generator.

        Returns summary statistics.
        """
        if initial_capital:
            self.config.total_capital_eur = initial_capital
            self._peak_equity = initial_capital

        fills = 0
        total_pnl = 0.0
        max_dd = 0.0
        equity_curve = []

        for tick in self.from_csv_chunked(csv_path, self.config):
            action, params = self.on_tick(tick)

            # Simulate fills (simplified: fill if price crosses)
            for order_data in params.get("orders", []):
                if order_data["side"] == "buy" and tick.low <= order_data["price"]:
                    fill = Fill(
                        order_id=f"sim_{fills}",
                        symbol=self.config.symbol,
                        side=OrderSide.BUY,
                        price=order_data["price"],
                        qty=order_data["qty"],
                        fee=order_data["notional_eur"] * self.config.taker_fee,
                        timestamp=tick.timestamp,
                    )
                    self.on_fill(fill)
                    fills += 1
                elif order_data["side"] == "sell" and tick.high >= order_data["price"]:
                    fill = Fill(
                        order_id=f"sim_{fills}",
                        symbol=self.config.symbol,
                        side=OrderSide.SELL,
                        price=order_data["price"],
                        qty=order_data["qty"],
                        fee=order_data["notional_eur"] * self.config.taker_fee,
                        timestamp=tick.timestamp,
                    )
                    self.on_fill(fill)
                    fills += 1

            equity = self._calculate_equity(tick.mid)
            equity_curve.append(equity)
            dd = (max(equity_curve) - equity) / max(max(equity_curve), 1e-8)
            max_dd = max(max_dd, dd)

        final_equity = equity_curve[-1] if equity_curve else self.config.total_capital_eur
        total_pnl = final_equity - self.config.total_capital_eur

        return {
            "initial_capital": self.config.total_capital_eur,
            "final_equity": final_equity,
            "total_pnl": total_pnl,
            "total_return_pct": total_pnl / self.config.total_capital_eur * 100,
            "max_drawdown_pct": max_dd * 100,
            "total_fills": fills,
            "total_fees": self._total_fees,
            "consecutive_losses": self._consecutive_losses,
            "final_regime": self._current_regime.value,
            "memory_mb": self.estimate_memory_mb(),
        }


# -------------------------------------------------------------------------- #
# Synthetic Data Generation for Inline Testing
# -------------------------------------------------------------------------- #

def generate_synthetic_ticks(
    n: int = 1000,
    symbol: str = "SOL/EUR",
    start_price: float = 100.0,
    trend: float = 0.0001,
    volatility: float = 0.01,
    seed: int = 42,
) -> list[Tick]:
    """Generate synthetic OHLCV ticks for testing."""
    import random
    random.seed(seed)

    ticks = []
    price = start_price
    timestamp = time.time()

    for i in range(n):
        # Random walk with trend
        change = random.gauss(trend, volatility)
        price *= (1 + change)
        price = max(price, 0.01)

        spread = price * 0.001
        bid = price - spread / 2
        ask = price + spread / 2
        volume = random.uniform(10, 1000)

        ticks.append(Tick(
            timestamp=timestamp + i * 60,
            symbol=symbol,
            bid=bid,
            ask=ask,
            mid=price,
            volume=volume,
        ))

    return ticks


# -------------------------------------------------------------------------- #
# Inline Self-Test
# -------------------------------------------------------------------------- #

def _run_self_test() -> None:
    """Run inline self-test with synthetic data."""
    print("Running HybridGridMomentumAdaptive self-test...")

    # Config for testing
    config = HMAConfig(
        symbol="SOL/EUR",
        total_capital_eur=250.0,
        eur_floor=15.0,
        grid_levels=6,
        base_spread_pct=0.02,
        grid_range_pct=0.03,
        martingale_factor=1.15,
        min_order_eur=10.0,
        ema_fast=20,
        ema_slow=50,
        ema_trend=200,
        rsi_period=14,
        rsi_oversold=35.0,
        rsi_overbought=65.0,
        atr_period=14,
        atr_multiplier=2.0,
        stop_loss_pct=0.02,
        take_profit_pct=0.04,
        maker_fee=0.0016,
        taker_fee=0.0026,
        csv_chunk_size=100,
        gc_interval=2,
        max_memory_mb=50.0,
    )

    strategy = HybridGridMomentumAdaptive(config)

    # Generate synthetic data: ranging market with occasional trend
    ticks = generate_synthetic_ticks(
        n=500,
        symbol="SOL/EUR",
        start_price=100.0,
        trend=0.00005,
        volatility=0.008,
        seed=123,
    )

    # Add some trend regimes
    for i, tick in enumerate(ticks):
        if 150 <= i < 250:  # Bull trend
            new_mid = tick.mid * 1.02
            ticks[i] = Tick(
                timestamp=tick.timestamp,
                symbol=tick.symbol,
                bid=new_mid * 0.9995,
                ask=new_mid * 1.0005,
                mid=new_mid,
                volume=tick.volume,
            )
        elif 350 <= i < 450:  # Bear trend
            new_mid = tick.mid * 0.98
            ticks[i] = Tick(
                timestamp=tick.timestamp,
                symbol=tick.symbol,
                bid=new_mid * 0.9995,
                ask=new_mid * 1.0005,
                mid=new_mid,
                volume=tick.volume,
            )

    # Run ticks through strategy
    actions = {"BUY": 0, "SELL": 0, "HOLD": 0, "CANCEL_ALL": 0}
    fills = 0

    for tick in ticks:
        action, params = strategy.on_tick(tick)
        actions[action.value] += 1

        # Simulate some fills
        if action in (Action.BUY, Action.SELL) and params.get("orders"):
            for order in params["orders"][:1]:  # Fill first order only
                if order["side"] == "buy" and tick.bid <= order["price"]:
                    fill = Fill(
                        order_id=f"test_{fills}",
                        symbol=config.symbol,
                        side=OrderSide.BUY,
                        price=order["price"],
                        qty=order["qty"],
                        fee=order["notional_eur"] * config.taker_fee,
                        timestamp=tick.timestamp,
                    )
                    strategy.on_fill(fill)
                    fills += 1
                elif order["side"] == "sell" and tick.ask >= order["price"]:
                    fill = Fill(
                        order_id=f"test_{fills}",
                        symbol=config.symbol,
                        side=OrderSide.SELL,
                        price=order["price"],
                        qty=order["qty"],
                        fee=order["notional_eur"] * config.taker_fee,
                        timestamp=tick.timestamp,
                    )
                    strategy.on_fill(fill)
                    fills += 1

    # Assertions
    mem_mb = strategy.estimate_memory_mb()
    assert mem_mb > 0, "Memory estimate should be positive"
    assert mem_mb < config.max_memory_mb, f"Memory {mem_mb:.4f}MB exceeds limit {config.max_memory_mb}MB"

    assert actions[Action.BUY] + actions[Action.SELL] > 0, "Should have generated orders"
    assert fills > 0, "Should have simulated fills"

    pos = strategy._positions.get(config.symbol)
    assert pos is not None, "Should have position after fills"

    # Test config validation
    try:
        bad_config = HMAConfig(base_spread_pct=0.0001)  # Too small for fees
        bad_config.validate()
        assert False, "Should have raised ConfigError"
    except ConfigError:
        pass  # Expected

    # Test state serialization
    state = strategy.get_state()
    assert "config" in state
    assert "current_regime" in state
    assert "positions" in state

    new_strategy = HybridGridMomentumAdaptive(config)
    new_strategy.load_state(state)
    assert new_strategy._current_regime == strategy._current_regime
    assert abs(new_strategy._grid_center - strategy._grid_center) < 1e-8

    print(f"OK: {len(ticks)} ticks, {actions[Action.BUY]} BUY, {actions[Action.SELL]} SELL, "
          f"{actions[Action.HOLD]} HOLD, {fills} fills, inv={pos.qty:.4f}, "
          f"pnl={pos.realized_pnl:.4f}, mem={mem_mb:.6f} MB")


if __name__ == "__main__":
    _run_self_test()