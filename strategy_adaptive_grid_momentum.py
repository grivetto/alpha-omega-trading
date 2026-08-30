#!/usr/bin/env python3
"""
Adaptive Grid-Momentum Trading Strategy for Denaro.
Config-driven, OOM-safe, asymmetric risk management.
Python 3.10+ | Full typing | No hardcoded values.
"""

from __future__ import annotations

import gc
import json
import logging
import math
import os
import sys
import time
import uuid
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Generator, List, Optional, Tuple, Union

import yaml

try:
    import ccxt
except ImportError:
    ccxt = None

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    LIMIT = "limit"
    MARKET = "market"


class OrderStatus(str, Enum):
    OPEN = "open"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class SignalType(str, Enum):
    GRID_BUY = "grid_buy"
    GRID_SELL = "grid_sell"
    MOMENTUM_LONG = "momentum_long"
    MOMENTUM_SHORT = "momentum_short"
    ADAPTIVE_REBALANCE = "adaptive_rebalance"
    RISK_REDUCE = "risk_reduce"


@dataclass(slots=True)
class MarketTick:
    symbol: str
    timestamp: int
    bid: float
    ask: float
    last: float
    volume: float
    bid_volume: float = 0.0
    ask_volume: float = 0.0

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2.0

    @property
    def spread_pct(self) -> float:
        return (self.ask - self.bid) / self.mid if self.mid > 0 else 0.0


@dataclass(slots=True)
class Order:
    id: str
    symbol: str
    side: OrderSide
    type: OrderType
    price: float
    amount: float
    filled: float = 0.0
    status: OrderStatus = OrderStatus.OPEN
    timestamp: int = field(default_factory=lambda: int(time.time() * 1000))
    client_order_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def remaining(self) -> float:
        return max(0.0, self.amount - self.filled)

    @property
    def is_buy(self) -> bool:
        return self.side == OrderSide.BUY

    @property
    def notional(self) -> float:
        return self.price * self.amount


@dataclass(slots=True)
class Fill:
    order_id: str
    symbol: str
    side: OrderSide
    price: float
    amount: float
    fee: float
    fee_currency: str
    timestamp: int = field(default_factory=lambda: int(time.time() * 1000))
    trade_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Position:
    symbol: str
    size: float = 0.0
    entry_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    max_favorable: float = 0.0
    max_adverse: float = 0.0
    last_update: int = field(default_factory=lambda: int(time.time() * 1000))

    def update(self, price: float, side: OrderSide, amount: float, fee: float) -> None:
        if side == OrderSide.BUY:
            new_size = self.size + amount
            if new_size != 0:
                self.entry_price = ((self.size * self.entry_price) + (amount * price) + fee) / new_size
            self.size = new_size
        else:
            realized = (price - self.entry_price) * amount - fee
            self.realized_pnl += realized
            self.size -= amount
            if self.size == 0:
                self.entry_price = 0.0
        self.last_update = int(time.time() * 1000)

    def mark_to_market(self, price: float) -> None:
        if self.size != 0:
            self.unrealized_pnl = (price - self.entry_price) * self.size
            self.max_favorable = max(self.max_favorable, self.unrealized_pnl)
            self.max_adverse = min(self.max_adverse, self.unrealized_pnl)


@dataclass
class RiskParameters:
    max_position_pct: float = 0.10
    max_drawdown_pct: float = 0.15
    daily_loss_limit_pct: float = 0.05
    max_consecutive_losses: int = 5
    stop_loss_pct: float = 0.02
    take_profit_pct: float = 0.04
    trailing_stop_pct: float = 0.015
    trailing_activation_pct: float = 0.01
    max_leverage: float = 1.0
    min_order_notional: float = 10.0
    max_open_orders: int = 50
    kill_switch_dd_pct: float = 0.20
    eur_floor: float = 0.0
    asymmetric_risk: bool = True
    risk_reward_ratio: float = 2.0


@dataclass
class GridConfig:
    levels: int = 5
    range_pct: float = 0.02
    spacing_factor: float = 1.0
    base_order_size: float = 20.0
    max_total_invested: float = 100.0
    profit_per_grid: float = 0.0035
    martingale_factor: float = 1.0
    atr_spacing_factor: float = 1.0
    rebalance_interval_sec: int = 120
    force_recenter: bool = True


@dataclass
class MomentumConfig:
    ema_fast: int = 8
    ema_slow: int = 21
    rsi_period: int = 14
    rsi_overbought: float = 70.0
    rsi_oversold: float = 30.0
    volume_threshold: float = 1.5
    trend_ema_period: int = 200
    entry_buffer_pct: float = 0.0001
    soft_entry_mult: float = 0.5
    mean_reversion_mult: float = 0.25
    profit_target_pct: float = 0.01
    stop_loss_pct: float = 0.005
    check_interval_sec: int = 15


@dataclass
class AdaptiveConfig:
    volatility_window: int = 100
    regime_threshold: float = 0.02
    correlation_threshold: float = 0.85
    capital_allocation_pct: float = 0.3
    min_confidence: float = 0.6
    max_regime_duration: int = 3600
    shadow_grid_enabled: bool = True
    shadow_levels: List[float] = field(default_factory=lambda: [0.08, 0.12, 0.18])
    shadow_recovery_target: float = 0.04
    shadow_capital_pct: float = 0.15


@dataclass
class StrategyConfig:
    symbol: str
    exchange: str
    quote_currency: str = "EUR"
    risk: RiskParameters = field(default_factory=RiskParameters)
    grid: GridConfig = field(default_factory=GridConfig)
    momentum: MomentumConfig = field(default_factory=MomentumConfig)
    adaptive: AdaptiveConfig = field(default_factory=AdaptiveConfig)
    dry_run: bool = True
    log_level: str = "INFO"
    state_file: str = "./strategy_state.json"
    config_reload_sec: int = 300


class ExchangeClient(ABC):
    @abstractmethod
    def fetch_ticker(self, symbol: str) -> MarketTick: ...

    @abstractmethod
    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int) -> List[List[float]]: ...

    @abstractmethod
    def fetch_balance(self) -> Dict[str, Dict[str, float]]: ...

    @abstractmethod
    def create_order(self, order: Order) -> Order: ...

    @abstractmethod
    def cancel_order(self, order_id: str, symbol: str) -> bool: ...

    @abstractmethod
    def fetch_open_orders(self, symbol: str) -> List[Order]: ...


class CCXTExchangeClient(ExchangeClient):
    def __init__(self, config: StrategyConfig):
        if ccxt is None:
            raise RuntimeError("ccxt not installed")
        self.config = config
        self.exchange = getattr(ccxt, config.exchange.lower())({
            "apiKey": os.getenv(f"{config.exchange.upper()}_API_KEY"),
            "secret": os.getenv(f"{config.exchange.upper()}_API_SECRET"),
            "enableRateLimit": True,
            "options": {"defaultType": "spot"},
        })
        if config.dry_run:
            self.exchange.set_sandbox_mode(True)
        self.markets = self.exchange.load_markets()

    def fetch_ticker(self, symbol: str) -> MarketTick:
        t = self.exchange.fetch_ticker(symbol)
        return MarketTick(
            symbol=symbol,
            timestamp=t["timestamp"],
            bid=t["bid"] or 0.0,
            ask=t["ask"] or 0.0,
            last=t["last"] or t["close"] or 0.0,
            volume=t["baseVolume"] or 0.0,
            bid_volume=t.get("bidVolume", 0.0) or 0.0,
            ask_volume=t.get("askVolume", 0.0) or 0.0,
        )

    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int) -> List[List[float]]:
        return self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)

    def fetch_balance(self) -> Dict[str, Dict[str, float]]:
        bal = self.exchange.fetch_balance()
        return {k: {"free": v.get("free", 0.0), "used": v.get("used", 0.0), "total": v.get("total", 0.0)} for k, v in bal.items() if isinstance(v, dict)}

    def create_order(self, order: Order) -> Order:
        side = "buy" if order.side == OrderSide.BUY else "sell"
        params = {"clientOrderId": order.client_order_id} if order.client_order_id else {}
        if order.type == OrderType.LIMIT:
            res = self.exchange.create_limit_order(order.symbol, side, order.amount, order.price, params)
        else:
            res = self.exchange.create_market_order(order.symbol, side, order.amount, params)
        order.id = res["id"]
        order.status = OrderStatus.OPEN if res["status"] == "open" else OrderStatus.FILLED
        order.filled = res.get("filled", 0.0)
        return order

    def cancel_order(self, order_id: str, symbol: str) -> bool:
        try:
            self.exchange.cancel_order(order_id, symbol)
            return True
        except Exception:
            return False

    def fetch_open_orders(self, symbol: str) -> List[Order]:
        orders = self.exchange.fetch_open_orders(symbol)
        result = []
        for o in orders:
            result.append(Order(
                id=o["id"],
                symbol=o["symbol"],
                side=OrderSide(o["side"]),
                type=OrderType(o["type"]),
                price=o["price"],
                amount=o["amount"],
                filled=o.get("filled", 0.0),
                status=OrderStatus(o["status"]),
                timestamp=o["timestamp"],
                client_order_id=o.get("clientOrderId", ""),
            ))
        return result


class TechnicalIndicators:
    @staticmethod
    def ema(values: List[float], period: int) -> Generator[float, None, None]:
        if not values or period <= 0:
            return
        k = 2.0 / (period + 1)
        ema_val = values[0]
        yield ema_val
        for v in values[1:]:
            ema_val = v * k + ema_val * (1 - k)
            yield ema_val

    @staticmethod
    def rsi(values: List[float], period: int = 14) -> Generator[float, None, None]:
        if len(values) < period + 1:
            return
        gains = []
        losses = []
        for i in range(1, len(values)):
            diff = values[i] - values[i - 1]
            gains.append(max(diff, 0.0))
            losses.append(max(-diff, 0.0))
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        if avg_loss == 0:
            yield 100.0
        else:
            rs = avg_gain / avg_loss
            yield 100.0 - (100.0 / (1.0 + rs))
        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            if avg_loss == 0:
                yield 100.0
            else:
                rs = avg_gain / avg_loss
                yield 100.0 - (100.0 / (1.0 + rs))

    @staticmethod
    def atr(high: List[float], low: List[float], close: List[float], period: int = 14) -> Generator[float, None, None]:
        if len(high) < period + 1:
            return
        trs = []
        for i in range(1, len(high)):
            tr = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))
            trs.append(tr)
        atr_val = sum(trs[:period]) / period
        yield atr_val
        for i in range(period, len(trs)):
            atr_val = (atr_val * (period - 1) + trs[i]) / period
            yield atr_val

    @staticmethod
    def std_dev(values: List[float], period: int) -> Generator[float, None, None]:
        if len(values) < period:
            return
        for i in range(period - 1, len(values)):
            window = values[i - period + 1:i + 1]
            mean = sum(window) / period
            variance = sum((x - mean) ** 2 for x in window) / period
            yield math.sqrt(variance)


class StateManager:
    def __init__(self, state_file: str):
        self.state_file = Path(state_file)
        self._state: Dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if self.state_file.exists():
            try:
                with open(self.state_file, "r") as f:
                    self._state = json.load(f)
            except Exception as e:
                logger.warning("Failed to load state: %s", e)
                self._state = {}

    def save(self) -> None:
        tmp = self.state_file.with_suffix(".tmp")
        try:
            with open(tmp, "w") as f:
                json.dump(self._state, f, separators=(",", ":"))
            tmp.replace(self.state_file)
        except Exception as e:
            logger.error("Failed to save state: %s", e)

    def get(self, key: str, default: Any = None) -> Any:
        return self._state.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._state[key] = value

    def update(self, data: Dict[str, Any]) -> None:
        self._state.update(data)

    def clear(self) -> None:
        self._state.clear()


class StrategyBase(ABC):
    def __init__(self, config: StrategyConfig, exchange: ExchangeClient, state: StateManager):
        self.config = config
        self.exchange = exchange
        self.state = state
        self.position = Position(symbol=config.symbol)
        self.open_orders: Dict[str, Order] = {}
        self.fills_history: deque[Fill] = deque(maxlen=1000)
        self.equity_curve: deque[float] = deque(maxlen=10000)
        self.daily_pnl: float = 0.0
        self.consecutive_losses: int = 0
        self.peak_equity: float = 0.0
        self.current_regime: str = "UNKNOWN"
        self.regime_start_time: int = int(time.time())
        self.grid_levels_buy: List[float] = []
        self.grid_levels_sell: List[float] = []
        self.last_rebalance: int = 0
        self.shadow_active: bool = False
        self.shadow_orders: List[str] = []
        self._price_history: deque[float] = deque(maxlen=500)
        self._volume_history: deque[float] = deque(maxlen=500)
        self._high_history: deque[float] = deque(maxlen=500)
        self._low_history: deque[float] = deque(maxlen=500)
        self._close_history: deque[float] = deque(maxlen=500)

    @abstractmethod
    def on_tick(self, tick: MarketTick) -> List[Order]: ...

    @abstractmethod
    def on_fill(self, fill: Fill) -> List[Order]: ...

    @abstractmethod
    def validate_config(self) -> Tuple[bool, List[str]]: ...

    @abstractmethod
    def estimate_memory_mb(self) -> float: ...

    def _update_price_history(self, tick: MarketTick) -> None:
        self._price_history.append(tick.mid)
        self._volume_history.append(tick.volume)
        self._high_history.append(tick.ask)
        self._low_history.append(tick.bid)
        self._close_history.append(tick.last)

    def _calculate_atr(self) -> Optional[float]:
        if len(self._high_history) < self.config.momentum.ema_slow + 1:
            return None
        atr_gen = TechnicalIndicators.atr(
            list(self._high_history), list(self._low_history), list(self._close_history), 14
        )
        return list(atr_gen)[-1] if atr_gen else None

    def _calculate_ema(self, period: int) -> Optional[float]:
        if len(self._close_history) < period:
            return None
        ema_gen = TechnicalIndicators.ema(list(self._close_history), period)
        ema_list = list(ema_gen)
        return ema_list[-1] if ema_list else None

    def _calculate_rsi(self) -> Optional[float]:
        if len(self._close_history) < self.config.momentum.rsi_period + 1:
            return None
        rsi_gen = TechnicalIndicators.rsi(list(self._close_history), self.config.momentum.rsi_period)
        rsi_list = list(rsi_gen)
        return rsi_list[-1] if rsi_list else None

    def _calculate_std_dev(self, period: int) -> Optional[float]:
        if len(self._close_history) < period:
            return None
        std_gen = TechnicalIndicators.std_dev(list(self._close_history), period)
        std_list = list(std_gen)
        return std_list[-1] if std_list else None

    def _get_quote_balance(self) -> float:
        bal = self.exchange.fetch_balance()
        return bal.get(self.config.quote_currency, {}).get("free", 0.0)

    def _get_base_balance(self) -> float:
        base = self.config.symbol.split("/")[0]
        bal = self.exchange.fetch_balance()
        return bal.get(base, {}).get("free", 0.0)

    def _check_risk_limits(self, tick: MarketTick) -> bool:
        total_equity = self._calculate_total_equity(tick)
        if self.peak_equity == 0 or total_equity > self.peak_equity:
            self.peak_equity = total_equity

        if self.config.risk.eur_floor > 0 and total_equity < self.config.risk.eur_floor:
            logger.warning("EUR floor breached: %.2f < %.2f", total_equity, self.config.risk.eur_floor)
            return False

        dd_pct = (self.peak_equity - total_equity) / self.peak_equity if self.peak_equity > 0 else 0
        if dd_pct >= self.config.risk.kill_switch_dd_pct:
            logger.critical("Kill switch: drawdown %.2f%% >= %.2f%%", dd_pct * 100, self.config.risk.kill_switch_dd_pct * 100)
            return False

        if dd_pct >= self.config.risk.max_drawdown_pct:
            logger.warning("Max drawdown reached: %.2f%%", dd_pct * 100)
            return False

        if self.daily_pnl <= -abs(self.peak_equity * self.config.risk.daily_loss_limit_pct):
            logger.warning("Daily loss limit reached: %.2f", self.daily_pnl)
            return False

        if self.consecutive_losses >= self.config.risk.max_consecutive_losses:
            logger.warning("Max consecutive losses: %d", self.consecutive_losses)
            return False

        if len(self.open_orders) >= self.config.risk.max_open_orders:
            logger.warning("Max open orders reached: %d", len(self.open_orders))
            return False

        return True

    def _calculate_total_equity(self, tick: MarketTick) -> float:
        quote_free = self._get_quote_balance()
        base_free = self._get_base_balance()
        return quote_free + base_free * tick.mid

    def _apply_asymmetric_risk(self, entry_price: float, side: OrderSide) -> Tuple[float, float]:
        if not self.config.risk.asymmetric_risk:
            sl = entry_price * (1 - self.config.risk.stop_loss_pct) if side == OrderSide.BUY else entry_price * (1 + self.config.risk.stop_loss_pct)
            tp = entry_price * (1 + self.config.risk.take_profit_pct) if side == OrderSide.BUY else entry_price * (1 - self.config.risk.take_profit_pct)
            return sl, tp

        rr = self.config.risk.risk_reward_ratio
        if side == OrderSide.BUY:
            sl = entry_price * (1 - self.config.risk.stop_loss_pct)
            tp = entry_price * (1 + self.config.risk.stop_loss_pct * rr)
        else:
            sl = entry_price * (1 + self.config.risk.stop_loss_pct)
            tp = entry_price * (1 - self.config.risk.stop_loss_pct * rr)
        return sl, tp

    def _check_trailing_stop(self, tick: MarketTick) -> Optional[OrderSide]:
        if self.position.size == 0:
            return None
        if self.position.max_favorable <= 0:
            return None
        activation = self.position.entry_price * (1 + self.config.risk.trailing_activation_pct) if self.position.size > 0 else self.position.entry_price * (1 - self.config.risk.trailing_activation_pct)
        if (self.position.size > 0 and tick.mid < activation) or (self.position.size < 0 and tick.mid > activation):
            return None
        trail_price = self.position.max_favorable * (1 - self.config.risk.trailing_stop_pct) if self.position.size > 0 else self.position.max_favorable * (1 + self.config.risk.trailing_stop_pct)
        if (self.position.size > 0 and tick.mid < trail_price) or (self.position.size < 0 and tick.mid > trail_price):
            return OrderSide.SELL if self.position.size > 0 else OrderSide.BUY
        return None

    def _cleanup_memory(self) -> None:
        gc.collect()


class AdaptiveGridMomentumStrategy(StrategyBase):
    def __init__(self, config: StrategyConfig, exchange: ExchangeClient, state: StateManager):
        super().__init__(config, exchange, state)
        self._restore_state()

    def _restore_state(self) -> None:
        self.grid_levels_buy = self.state.get("grid_levels_buy", [])
        self.grid_levels_sell = self.state.get("grid_levels_sell", [])
        self.position.size = self.state.get("position_size", 0.0)
        self.position.entry_price = self.state.get("position_entry", 0.0)
        self.position.realized_pnl = self.state.get("realized_pnl", 0.0)
        self.daily_pnl = self.state.get("daily_pnl", 0.0)
        self.consecutive_losses = self.state.get("consecutive_losses", 0)
        self.peak_equity = self.state.get("peak_equity", 0.0)
        self.current_regime = self.state.get("regime", "UNKNOWN")
        self.regime_start_time = self.state.get("regime_start", int(time.time()))
        self.shadow_active = self.state.get("shadow_active", False)
        self.shadow_orders = self.state.get("shadow_orders", [])
        self.last_rebalance = self.state.get("last_rebalance", 0)

    def _persist_state(self) -> None:
        self.state.update({
            "grid_levels_buy": self.grid_levels_buy,
            "grid_levels_sell": self.grid_levels_sell,
            "position_size": self.position.size,
            "position_entry": self.position.entry_price,
            "realized_pnl": self.position.realized_pnl,
            "daily_pnl": self.daily_pnl,
            "consecutive_losses": self.consecutive_losses,
            "peak_equity": self.peak_equity,
            "regime": self.current_regime,
            "regime_start": self.regime_start_time,
            "shadow_active": self.shadow_active,
            "shadow_orders": self.shadow_orders,
            "last_rebalance": self.last_rebalance,
            "timestamp": int(time.time()),
        })
        self.state.save()

    def validate_config(self) -> Tuple[bool, List[str]]:
        errors = []
        if not self.config.symbol:
            errors.append("symbol required")
        if not self.config.exchange:
            errors.append("exchange required")
        if self.config.grid.levels <= 0:
            errors.append("grid.levels must be > 0")
        if self.config.grid.range_pct <= 0:
            errors.append("grid.range_pct must be > 0")
        if self.config.grid.base_order_size < self.config.risk.min_order_notional:
            errors.append(f"grid.base_order_size must be >= risk.min_order_notional ({self.config.risk.min_order_notional})")
        if self.config.risk.stop_loss_pct <= 0:
            errors.append("risk.stop_loss_pct must be > 0")
        if self.config.risk.take_profit_pct <= 0:
            errors.append("risk.take_profit_pct must be > 0")
        if self.config.momentum.ema_fast >= self.config.momentum.ema_slow:
            errors.append("momentum.ema_fast must be < ema_slow")
        if self.config.adaptive.capital_allocation_pct <= 0 or self.config.adaptive.capital_allocation_pct > 1:
            errors.append("adaptive.capital_allocation_pct must be in (0, 1]")
        return len(errors) == 0, errors

    def estimate_memory_mb(self) -> float:
        history_size = (
            len(self._price_history) * 8 +
            len(self._volume_history) * 8 +
            len(self._high_history) * 8 +
            len(self._low_history) * 8 +
            len(self._close_history) * 8
        )
        fills_size = len(self.fills_history) * 200
        equity_size = len(self.equity_curve) * 8
        orders_size = len(self.open_orders) * 500
        base_overhead = 5.0
        total_bytes = history_size + fills_size + equity_size + orders_size + base_overhead * 1_000_000
        return total_bytes / (1024 * 1024)

    def _detect_regime(self, tick: MarketTick) -> str:
        ema_fast = self._calculate_ema(self.config.momentum.ema_fast)
        ema_slow = self._calculate_ema(self.config.momentum.ema_slow)
        atr = self._calculate_atr()
        std_dev = self._calculate_std_dev(self.config.adaptive.volatility_window)

        if ema_fast is None or ema_slow is None:
            return "UNKNOWN"

        trend_up = ema_fast > ema_slow
        volatility = (atr / tick.mid) if atr and tick.mid > 0 else (std_dev / tick.mid if std_dev and tick.mid > 0 else 0)
        is_volatile = volatility > self.config.adaptive.regime_threshold

        if trend_up and not is_volatile:
            return "BULL_QUIET"
        elif trend_up and is_volatile:
            return "BULL_VOLATILE"
        elif not trend_up and not is_volatile:
            return "BEAR_QUIET"
        else:
            return "BEAR_VOLATILE"

    def _initialize_grid(self, tick: MarketTick) -> List[Order]:
        orders = []
        atr = self._calculate_atr()
        spacing_pct = self.config.grid.range_pct / self.config.grid.levels
        if atr and self.config.grid.atr_spacing_factor > 0:
            atr_pct = atr / tick.mid
            spacing_pct = max(spacing_pct, atr_pct * self.config.grid.atr_spacing_factor / self.config.grid.levels)

        self.grid_levels_buy = []
        self.grid_levels_sell = []

        for i in range(self.config.grid.levels):
            buy_price = tick.mid * (1 - spacing_pct * (i + 1))
            sell_price = tick.mid * (1 + spacing_pct * (i + 1))
            self.grid_levels_buy.append(round(buy_price, 2))
            self.grid_levels_sell.append(round(sell_price, 2))

        quote_free = self._get_quote_balance()
        max_invest = min(self.config.grid.max_total_invested, quote_free * self.config.adaptive.capital_allocation_pct)
        available_levels = int(max_invest / self.config.grid.base_order_size)
        levels_to_place = min(self.config.grid.levels, max(1, available_levels))

        for i in range(levels_to_place):
            buy_price = self.grid_levels_buy[i]
            order_size = self.config.grid.base_order_size * (self.config.grid.martingale_factor ** i)
            amount = order_size / buy_price
            if order_size >= self.config.risk.min_order_notional:
                order = Order(
                    id="",
                    symbol=self.config.symbol,
                    side=OrderSide.BUY,
                    type=OrderType.LIMIT,
                    price=buy_price,
                    amount=round(amount, 5),
                    metadata={"grid_level": i, "strategy": "grid"},
                )
                orders.append(order)

        self.last_rebalance = int(time.time())
        return orders

    def _check_grid_fills(self, tick: MarketTick, fills: List[Fill]) -> List[Order]:
        orders = []
        for fill in fills:
            if fill.metadata.get("strategy") != "grid":
                continue
            level = fill.metadata.get("grid_level", 0)
            if fill.side == OrderSide.BUY:
                if level < len(self.grid_levels_sell):
                    sell_price = self.grid_levels_sell[level]
                    amount = fill.amount
                    order = Order(
                        id="",
                        symbol=self.config.symbol,
                        side=OrderSide.SELL,
                        type=OrderType.LIMIT,
                        price=sell_price,
                        amount=amount,
                        metadata={"grid_level": level, "strategy": "grid", "parent_fill": fill.trade_id},
                    )
                    orders.append(order)
            else:
                if self.config.grid.force_recenter and level < len(self.grid_levels_buy):
                    buy_price = self.grid_levels_buy[level]
                    order_size = self.config.grid.base_order_size * (self.config.grid.martingale_factor ** level)
                    amount = order_size / buy_price
                    if order_size >= self.config.risk.min_order_notional:
                        order = Order(
                            id="",
                            symbol=self.config.symbol,
                            side=OrderSide.BUY,
                            type=OrderType.LIMIT,
                            price=buy_price,
                            amount=round(amount, 5),
                            metadata={"grid_level": level, "strategy": "grid", "recenter": True},
                        )
                        orders.append(order)
        return orders

    def _momentum_signal(self, tick: MarketTick) -> Optional[Tuple[OrderSide, float]]:
        ema_fast = self._calculate_ema(self.config.momentum.ema_fast)
        ema_slow = self._calculate_ema(self.config.momentum.ema_slow)
        rsi = self._calculate_rsi()
        atr = self._calculate_atr()

        if ema_fast is None or ema_slow is None or rsi is None:
            return None

        volume_avg = sum(self._volume_history) / len(self._volume_history) if self._volume_history else 0
        vol_ok = tick.volume >= volume_avg * self.config.momentum.volume_threshold if volume_avg > 0 else True
        price = tick.mid
        buffer = price * self.config.momentum.entry_buffer_pct
        trend_up = price > self._calculate_ema(self.config.momentum.trend_ema_period) if len(self._close_history) >= self.config.momentum.trend_ema_period else True

        if price > ema_slow + buffer and vol_ok:
            if rsi < self.config.momentum.rsi_overbought:
                return OrderSide.BUY, 1.0
            elif price > ema_fast:
                return OrderSide.BUY, self.config.momentum.soft_entry_mult
        elif price < ema_slow - buffer and vol_ok:
            if rsi > self.config.momentum.rsi_oversold:
                return OrderSide.SELL, 1.0
            elif price < ema_fast:
                return OrderSide.SELL, self.config.momentum.soft_entry_mult
        elif trend_up and price < ema_slow and price > ema_fast:
            return OrderSide.BUY, self.config.momentum.mean_reversion_mult
        elif not trend_up and price > ema_slow and price < ema_fast:
            return OrderSide.SELL, self.config.momentum.mean_reversion_mult

        return None

    def _check_shadow_grid(self, tick: MarketTick) -> List[Order]:
        if not self.config.adaptive.shadow_grid_enabled or self.shadow_active:
            return []

        if len(self._close_history) < 2:
            return []

        prev_close = self._close_history[-2]
        drop_pct = (prev_close - tick.mid) / prev_close
        if drop_pct < 0.07:
            return []

        quote_free = self._get_quote_balance()
        shadow_capital = quote_free * self.config.adaptive.shadow_capital_pct
        if shadow_capital < self.config.risk.min_order_notional * 3:
            return []

        self.shadow_active = True
        orders = []
        per_level = shadow_capital / len(self.config.adaptive.shadow_levels)
        for i, level_pct in enumerate(self.config.adaptive.shadow_levels):
            buy_price = tick.mid * (1 - level_pct)
            amount = per_level / buy_price
            if per_level >= self.config.risk.min_order_notional:
                order = Order(
                    id="",
                    symbol=self.config.symbol,
                    side=OrderSide.BUY,
                    type=OrderType.LIMIT,
                    price=round(buy_price, 2),
                    amount=round(amount, 5),
                    metadata={"strategy": "shadow_grid", "level": i, "recovery_target": self.config.adaptive.shadow_recovery_target},
                )
                orders.append(order)
                self.shadow_orders.append(order.client_order_id)

        logger.warning("SHADOW GRID ACTIVATED: drop %.2f%%, placing %d orders", drop_pct * 100, len(orders))
        return orders

    def _check_shadow_recovery(self, tick: MarketTick, fills: List[Fill]) -> List[Order]:
        orders = []
        for fill in fills:
            if fill.metadata.get("strategy") != "shadow_grid":
                continue
            recovery_price = fill.price * (1 + self.config.adaptive.shadow_recovery_target)
            order = Order(
                id="",
                symbol=self.config.symbol,
                side=OrderSide.SELL,
                type=OrderType.LIMIT,
                price=round(recovery_price, 2),
                amount=fill.amount,
                metadata={"strategy": "shadow_recovery", "parent_fill": fill.trade_id},
            )
            orders.append(order)

        if all(o.status == OrderStatus.FILLED for o in self.open_orders.values() if o.metadata.get("strategy") == "shadow_recovery"):
            self.shadow_active = False
            self.shadow_orders = []
            logger.info("Shadow grid cycle complete, deactivated")

        return orders

    def on_tick(self, tick: MarketTick) -> List[Order]:
        self._update_price_history(tick)
        self._cleanup_memory()

        if not self._check_risk_limits(tick):
            return []

        self.current_regime = self._detect_regime(tick)
        now = int(time.time())

        orders: List[Order] = []

        shadow_orders = self._check_shadow_grid(tick)
        orders.extend(shadow_orders)

        if not self.shadow_active:
            if not self.grid_levels_buy or now - self.last_rebalance > self.config.grid.rebalance_interval_sec:
                orders.extend(self._initialize_grid(tick))

            momentum_sig = self._momentum_signal(tick)
            if momentum_sig:
                side, size_mult = momentum_sig
                quote_free = self._get_quote_balance()
                base_free = self._get_base_balance()
                if side == OrderSide.BUY:
                    invest = max(self.config.grid.base_order_size * size_mult, self.config.risk.min_order_notional)
                    if quote_free >= invest:
                        amount = invest / tick.mid
                        sl, tp = self._apply_asymmetric_risk(tick.mid, OrderSide.BUY)
                        order = Order(
                            id="",
                            symbol=self.config.symbol,
                            side=OrderSide.BUY,
                            type=OrderType.LIMIT,
                            price=round(tick.mid * 0.999, 2),
                            amount=round(amount, 5),
                            metadata={"strategy": "momentum", "sl": sl, "tp": tp, "size_mult": size_mult},
                        )
                        orders.append(order)
                else:
                    max_sell = base_free * 0.5
                    if max_sell > 0:
                        amount = min(max_sell, self.config.grid.base_order_size * size_mult / tick.mid)
                        sl, tp = self._apply_asymmetric_risk(tick.mid, OrderSide.SELL)
                        order = Order(
                            id="",
                            symbol=self.config.symbol,
                            side=OrderSide.SELL,
                            type=OrderType.LIMIT,
                            price=round(tick.mid * 1.001, 2),
                            amount=round(amount, 5),
                            metadata={"strategy": "momentum", "sl": sl, "tp": tp, "size_mult": size_mult},
                        )
                        orders.append(order)

            trail_side = self._check_trailing_stop(tick)
            if trail_side and self.position.size != 0:
                amount = abs(self.position.size)
                order = Order(
                    id="",
                    symbol=self.config.symbol,
                    side=trail_side,
                    type=OrderType.MARKET,
                    price=tick.mid,
                    amount=amount,
                    metadata={"strategy": "trailing_stop"},
                )
                orders.append(order)

        self.position.mark_to_market(tick.mid)
        equity = self._calculate_total_equity(tick)
        self.equity_curve.append(equity)
        self._persist_state()

        return orders

    def on_fill(self, fill: Fill) -> List[Order]:
        self.fills_history.append(fill)
        self.position.update(fill.price, fill.side, fill.amount, fill.fee)

        if fill.side == OrderSide.SELL and self.position.size <= 0:
            pnl = (fill.price - self.position.entry_price) * fill.amount - fill.fee if self.position.entry_price > 0 else 0
            self.daily_pnl += pnl
            if pnl < 0:
                self.consecutive_losses += 1
            else:
                self.consecutive_losses = 0

        orders = self._check_grid_fills(MarketTick(
            symbol=fill.symbol,
            timestamp=fill.timestamp,
            bid=fill.price,
            ask=fill.price,
            last=fill.price,
            volume=0,
        ), [fill])

        orders.extend(self._check_shadow_recovery(MarketTick(
            symbol=fill.symbol,
            timestamp=fill.timestamp,
            bid=fill.price,
            ask=fill.price,
            last=fill.price,
            volume=0,
        ), [fill]))

        if fill.metadata.get("strategy") == "momentum":
            sl = fill.metadata.get("sl")
            tp = fill.metadata.get("tp")
            if sl and tp:
                side = OrderSide.SELL if fill.side == OrderSide.BUY else OrderSide.BUY
                for price, label in [(sl, "stop_loss"), (tp, "take_profit")]:
                    o = Order(
                        id="",
                        symbol=self.config.symbol,
                        side=side,
                        type=OrderType.LIMIT,
                        price=round(price, 2),
                        amount=fill.amount,
                        metadata={"strategy": "momentum_protect", "type": label, "parent_fill": fill.trade_id},
                    )
                    orders.append(o)

        self._persist_state()
        return orders


def load_config(path: str) -> StrategyConfig:
    with open(path, "r") as f:
        if path.endswith(".yaml") or path.endswith(".yml"):
            data = yaml.safe_load(f)
        else:
            data = json.load(f)

    risk = RiskParameters(**data.get("risk", {}))
    grid = GridConfig(**data.get("grid", {}))
    momentum = MomentumConfig(**data.get("momentum", {}))
    adaptive = AdaptiveConfig(**data.get("adaptive", {}))

    return StrategyConfig(
        symbol=data["symbol"],
        exchange=data["exchange"],
        quote_currency=data.get("quote_currency", "EUR"),
        risk=risk,
        grid=grid,
        momentum=momentum,
        adaptive=adaptive,
        dry_run=data.get("dry_run", True),
        log_level=data.get("log_level", "INFO"),
        state_file=data.get("state_file", "./strategy_state.json"),
        config_reload_sec=data.get("config_reload_sec", 300),
    )


def generate_synthetic_ticks(symbol: str, count: int = 1000, start_price: float = 100.0, volatility: float = 0.02) -> Generator[MarketTick, None, None]:
    price = start_price
    base_time = int(time.time() * 1000) - count * 60_000
    for i in range(count):
        change = (hash(f"{i}{symbol}") % 1000 - 500) / 50000 * volatility
        price *= (1 + change)
        spread = price * 0.001
        yield MarketTick(
            symbol=symbol,
            timestamp=base_time + i * 60_000,
            bid=price - spread / 2,
            ask=price + spread / 2,
            last=price,
            volume=1000 + (hash(str(i)) % 5000),
        )


def generate_synthetic_fills(symbol: str, count: int = 50) -> Generator[Fill, None, None]:
    base_time = int(time.time() * 1000) - count * 60_000
    price = 100.0
    for i in range(count):
        side = OrderSide.BUY if i % 2 == 0 else OrderSide.SELL
        price *= 1.001 if side == OrderSide.BUY else 0.999
        yield Fill(
            order_id=str(uuid.uuid4()),
            symbol=symbol,
            side=side,
            price=round(price, 2),
            amount=0.1,
            fee=0.01,
            fee_currency="EUR",
            timestamp=base_time + i * 60_000,
        )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Adaptive Grid-Momentum Strategy Test")
    parser.add_argument("--config", type=str, help="Path to config file")
    parser.add_argument("--ticks", type=int, default=500, help="Number of synthetic ticks")
    parser.add_argument("--fills", type=int, default=30, help="Number of synthetic fills")
    parser.add_argument("--symbol", type=str, default="SOL/EUR", help="Trading symbol")
    args = parser.parse_args()

    if args.config:
        config = load_config(args.config)
    else:
        config = StrategyConfig(
            symbol=args.symbol,
            exchange="binance",
            quote_currency="EUR",
            risk=RiskParameters(
                max_position_pct=0.10,
                max_drawdown_pct=0.15,
                daily_loss_limit_pct=0.05,
                stop_loss_pct=0.02,
                take_profit_pct=0.04,
                trailing_stop_pct=0.015,
                trailing_activation_pct=0.01,
                min_order_notional=10.0,
                max_open_orders=50,
                kill_switch_dd_pct=0.20,
                eur_floor=50.0,
                asymmetric_risk=True,
                risk_reward_ratio=2.0,
            ),
            grid=GridConfig(
                levels=5,
                range_pct=0.02,
                spacing_factor=1.0,
                base_order_size=20.0,
                max_total_invested=100.0,
                profit_per_grid=0.0035,
                martingale_factor=1.15,
                atr_spacing_factor=1.0,
                rebalance_interval_sec=120,
                force_recenter=True,
            ),
            momentum=MomentumConfig(
                ema_fast=8,
                ema_slow=21,
                rsi_period=14,
                rsi_overbought=70.0,
                rsi_oversold=30.0,
                volume_threshold=1.5,
                trend_ema_period=200,
                entry_buffer_pct=0.0001,
                soft_entry_mult=0.5,
                mean_reversion_mult=0.25,
                profit_target_pct=0.01,
                stop_loss_pct=0.005,
                check_interval_sec=15,
            ),
            adaptive=AdaptiveConfig(
                volatility_window=100,
                regime_threshold=0.02,
                correlation_threshold=0.85,
                capital_allocation_pct=0.3,
                min_confidence=0.6,
                max_regime_duration=3600,
                shadow_grid_enabled=True,
                shadow_levels=[0.08, 0.12, 0.18],
                shadow_recovery_target=0.04,
                shadow_capital_pct=0.15,
            ),
            dry_run=True,
            state_file="./test_strategy_state.json",
        )

    exchange = MockExchange(config)
    state = StateManager(config.state_file)
    strategy = AdaptiveGridMomentumStrategy(config, exchange, state)

    valid, errors = strategy.validate_config()
    if not valid:
        logger.error("Config validation failed: %s", errors)
        sys.exit(1)

    logger.info("Strategy initialized. Memory estimate: %.2f MB", strategy.estimate_memory_mb())

    ticks = list(generate_synthetic_ticks(config.symbol, args.ticks))
    fills = list(generate_synthetic_fills(config.symbol, args.fills))

    fill_idx = 0
    for i, tick in enumerate(ticks):
        orders = strategy.on_tick(tick)
        if orders:
            logger.info("Tick %d: Generated %d orders", i, len(orders))
            for o in orders:
                exchange.create_order(o)

        if fill_idx < len(fills) and i % 15 == 0:
            fill = fills[fill_idx]
            fill_idx += 1
            fill_orders = strategy.on_fill(fill)
            if fill_orders:
                logger.info("Fill %d: Generated %d protective orders", fill_idx, len(fill_orders))
                for o in fill_orders:
                    exchange.create_order(o)

    logger.info("Test complete. Final equity: %.2f", strategy._calculate_total_equity(ticks[-1]))
    logger.info("Position: size=%.4f, entry=%.2f, unrealized=%.2f, realized=%.2f",
                strategy.position.size, strategy.position.entry_price,
                strategy.position.unrealized_pnl, strategy.position.realized_pnl)
    logger.info("Regime: %s", strategy.current_regime)
    logger.info("Grid levels: buy=%d, sell=%d", len(strategy.grid_levels_buy), len(strategy.grid_levels_sell))
    logger.info("Memory estimate: %.2f MB", strategy.estimate_memory_mb())

    if Path(config.state_file).exists():
        Path(config.state_file).unlink()