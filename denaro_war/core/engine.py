import asyncio
import logging
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, List, Any, Callable
from collections import deque
import statistics
import inspect

import aiofiles
import aiohttp

from config import load_config
from utils.metrics import MetricsRecorder
from utils.logger import setup_logging
from utils.exceptions import CircuitBreakerOpen, TradingError


class TradeDirection(Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    NONE = "NONE"


@dataclass
class Position:
    id: str
    symbol: str
    direction: TradeDirection
    entry_time: float
    entry_price: float
    quantity: float
    initial_capital: float
    exit_price: Optional[float] = None
    exit_time: Optional[float] = None
    pnl_usdc: float = 0.0
    pnl_pct: float = 0.0
    strategy: str = "unknown"
    exit_reason: str = "unknown"
    closed: bool = False

    def record_exit(self, price: float, reason: str = "normal_exit"):
        self.exit_price = price
        self.exit_time = time.time()
        self.exit_reason = reason
        if self.direction == TradeDirection.LONG:
            self.pnl_pct = (price - self.entry_price) / self.entry_price * 100
        else:
            self.pnl_pct = (self.entry_price - price) / self.entry_price * 100
        self.pnl_usdc = self.initial_capital * self.pnl_pct / 100
        self.closed = True


@dataclass
class MarketSnapshot:
    symbol: str
    timestamp: float
    price: float
    volume_24h: float
    current_price: float
    bid: float = 0.0
    ask: float = 0.0
    bid_ask_spread: float = 0.0


@dataclass
class ExecutionSignal:
    symbol: str
    direction: TradeDirection
    capital: float
    reason: str
    strategy: str
    timestamp: float = field(default_factory=time.time)
    priority: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not hasattr(self, 'priority'):
            self.priority = 0


class EventQueue:
    def __init__(self, max_size: int = 10000):
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=max_size)
        self.events: deque = deque(maxlen=max_size)
        self.lock = asyncio.Lock()

    async def put(self, event: Dict[str, Any]):
        async with self.lock:
            self.events.append(event)
            if len(self.events) > 10000:
                self.events.popleft()
        try:
            self.queue.put_nowait(event)
        except asyncio.QueueFull:
            logging.warning(f"Event queue full, dropping oldest event: {event.get('type', 'unknown')}")

    async def get(self, timeout: Optional[float] = None) -> Dict[str, Any]:
        try:
            return await asyncio.wait_for(self.queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    def size(self) -> int:
        return self.queue.qsize()


class CircuitBreaker:
    def __init__(self, threshold: int = 5, cooldown: float = 120):
        self.threshold = threshold
        self.cooldown = cooldown
        self.failures: deque = deque()
        self.lock = asyncio.Lock()
        self.enabled = True
        self.last_circuit_time: float = 0

    async def record_success(self):
        async with self.lock:
            if len(self.failures) > 0 and time.time() - self.failures[-1] < self.cooldown:
                self.failures.clear()

    async def record_failure(self) -> bool:
        async with self.lock:
            cutoff = time.time() - self.cooldown
            self.failures = deque([f for f in self.failures if f > cutoff])
            self.failures.append(time.time())
            if len(self.failures) >= self.threshold:
                self.last_circuit_time = time.time()
                return True
            return False

    def is_open(self) -> bool:
        if not self.enabled:
            return False
        return len(self.failures) >= self.threshold

    async def reset(self):
        async with self.lock:
            self.failures.clear()


class CapitalManager:
    def __init__(self, initial: float, max_risk_per_trade: float = 0.05):
        self.initial = initial
        self.total_capital = initial
        self.available_capital = initial
        self.bound_capital = 0.0
        self.max_risk = max_risk_per_trade
        self.daily_start_capital = initial
        self.daily_loss_limit = 0.15
        self.max_drawdown = 0.25
        self.daily_loss_pct = 0.0
        self.drawdown = 0.0
        self.lock = asyncio.Lock()

    async def allocate(self, amount: float) -> bool:
        async with self.lock:
            if amount <= 0:
                return False
            if self.available_capital >= amount:
                self.available_capital -= amount
                self.bound_capital += amount
                return True
            return False

    async def release(self, amount: float):
        async with self.lock:
            if self.bound_capital >= amount:
                self.bound_capital -= amount
                self.available_capital += amount

    async def update_pnl(self, pnl: float):
        async with self.lock:
            self.total_capital += pnl
            if pnl < 0:
                self.daily_loss_pct += abs(pnl) / self.daily_start_capital * 100
            self.drawdown = (self.daily_start_capital - self.total_capital) / self.daily_start_capital * 100

    async def reset_daily(self):
        async with self.lock:
            self.daily_start_capital = self.total_capital
            self.daily_loss_pct = 0.0

    def is_loss_limit_breach(self) -> bool:
        return self.daily_loss_pct >= self.daily_loss_limit * 100

    def is_drawdown_limit_breach(self) -> bool:
        return self.drawdown >= self.max_drawdown * 100

    def available_for_risk(self) -> float:
        return self.available_capital * self.max_risk

    def get_allocation_pct(self, symbol: str, positions: List[Position]) -> float:
        total = sum(p.initial_capital for p in positions if p.symbol == symbol and not p.closed)
        return total / self.total_capital if self.total_capital > 0 else 0.0


class HealthMonitor:
    def __init__(self):
        self.health_check_interval = 30
        self.heartbeat_interval = 10
        self.components: Dict[str, float] = {}
        self.lock = asyncio.Lock()
        self.health_status = "healthy"

    async def heartbeat(self, component: str):
        async with self.lock:
            self.components[component] = time.time()

    async def check_health(self) -> bool:
        async with self.lock:
            cutoff = time.time() - 60
            unhealthy = [c for c, t in self.components.items() if t < cutoff]
            if unhealthy:
                self.health_status = "degraded"
                logging.warning(f"Unhealthy components: {unhealthy}")
                return False
            self.health_status = "healthy"
            return True

    async def get_status(self) -> Dict[str, Any]:
        async with self.lock:
            return {
                "status": self.health_status,
                "components": {c: "alive" if t > time.time() - 60 else "dead" for c, t in self.components.items()},
                "uptime": time.time() - start_time
            }


class ExecutionEngine:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.position_size_pct = config.get("scalper", {}).get("position_size_pct", 0.10)
        self.slippage_bps = config.get("scalper", {}).get("slippage_bps", 3)
        self.order_type = config.get("scalper", {}).get("order_type", "MARKET")
        self.lock = asyncio.Lock()
        self.order_timeout_ms = 5000
        self.pending_orders: Dict[str, Dict[str, Any]] = {}
        self.max_retries = 3

    async def execute_order(self, signal: ExecutionSignal) -> Optional[Position]:
        async with self.lock:
            try:
                symbol = signal.symbol
                quantity = self._calc_quantity(signal)
                if quantity <= 0:
                    return None

                price = signal.metadata.get("price", 0.0)
                if price <= 0:
                    price = signal.metadata.get("current_price", 0.0)
                    if price <= 0:
                        logging.error(f"Cannot execute order for {symbol}: no price")
                        return None

                position = Position(
                    id=str(uuid.uuid4())[:8],
                    symbol=symbol,
                    direction=signal.direction,
                    entry_time=time.time(),
                    entry_price=price,
                    quantity=quantity,
                    initial_capital=signal.capital,
                    strategy=signal.strategy,
                    exit_reason=signal.reason
                )

                self.pending_orders[position.id] = {
                    "symbol": symbol,
                    "direction": signal.direction.value,
                    "quantity": quantity,
                    "price": price,
                    "strategy": signal.strategy
                }

                return position

            except Exception as e:
                logging.error(f"Execution error for {signal.symbol}: {e}")
                return None

    def _calc_quantity(self, signal: ExecutionSignal) -> float:
        symbol = signal.symbol
        entry_price = signal.metadata.get("price", 0.0) or signal.metadata.get("current_price", 0.0)
        if entry_price <= 0:
            return 0.0
        return signal.capital / entry_price

    def on_fill(self, order_id: str, fill_price: float, fill_qty: float):
        if order_id in self.pending_orders:
            del self.pending_orders[order_id]

    def on_reject(self, order_id: str, reason: str):
        if order_id in self.pending_orders:
            del self.pending_orders[order_id]
            logging.error(f"Order {order_id} rejected: {reason}")

    def on_timeout(self, order_id: str):
        if order_id in self.pending_orders:
            del self.pending_orders[order_id]
            logging.warning(f"Order {order_id} timed out")

    async def get_position(self, order_id: str) -> Optional[Dict[str, Any]]:
        if order_id in self.pending_orders:
            return self.pending_orders[order_id]
        return None


class PriceCache:
    def __init__(self, max_history: int = 10000):
        self.prices: Dict[str, deque] = {}
        self.lock = asyncio.Lock()
        self.max_history = max_history

    async def update(self, symbol: str, price: float, timestamp: float = None):
        async with self.lock:
            if symbol not in self.prices:
                self.prices[symbol] = deque(maxlen=self.max_history)
            self.prices[symbol].append((timestamp or time.time(), price))

    async def get_latest(self, symbol: str) -> Optional[float]:
        async with self.lock:
            if symbol in self.prices and len(self.prices[symbol]) > 0:
                return self.prices[symbol][-1][1]
            return None

    async def get_range(self, symbol: str, seconds: float) -> List[float]:
        async with self.lock:
            if symbol not in self.prices:
                return []
            cutoff = time.time() - seconds
            return [p for t, p in self.prices[symbol] if t >= cutoff]

    async def get_atr(self, symbol: str, period: int = 14) -> float:
        async with self.lock:
            if symbol not in self.prices or len(self.prices[symbol]) < period + 1:
                return 0.0
            prices = [p for t, p in self.prices[symbol][-period-1:]]
            atr_sum = 0.0
            for i in range(1, len(prices)):
                high = max(prices[i], prices[i-1])
                low = min(prices[i], prices[i-1])
                atr_sum += high - low
            return atr_sum / period


class DenaroEngine:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.start_time = time.time()
        self.running = False
        self.loop = None
        self.shutdown_event = asyncio.Event()

        self.event_queue = EventQueue()
        self.circuit_breaker = CircuitBreaker(
            threshold=config.get("orchestrator", {}).get("circuit_breaker_threshold", 5),
            cooldown=config.get("orchestrator", {}).get("circuit_breaker_cooldown_s", 120)
        )
        self.capital_manager = CapitalManager(
            initial=config.get("total_capital", 70.0),
            max_risk_per_trade=config.get("max_risk_per_trade", 0.05)
        )
        self.health_monitor = HealthMonitor()
        self.execution_engine = ExecutionEngine(config)
        self.price_cache = PriceCache()
        self.metrics = MetricsRecorder("logs/metrics.csv")

        self.positions: List[Position] = []
        self.last_rebal_time = 0
        self.strategy_allocations: Dict[str, float] = {}

        self.strategies: Dict[str, Any] = {}
        self.tasks: List[asyncio.Task] = []

        self._setup_logging()

    def _setup_logging(self):
        log_level = self.config.get("logging", {}).get("level", "DEBUG")
        setup_logging(log_level)

    def _load_strategies(self):
        from strategies.scalper import ScalperStrategy
        from strategies.whale_tracker import WhaleTrackerStrategy
        from strategies.news_reactor import NewsReactorStrategy

        self.strategies = {
            "scalper": ScalperStrategy(self.config, self),
            "whale_tracker": WhaleTrackerStrategy(self.config, self),
            "news_reactor": NewsReactorStrategy(self.config, self)
        }

        self.strategy_allocations = {
            "scalper": 0.33,
            "whale_tracker": 0.33,
            "news_reactor": 0.34
        }

    async def _allocate_capital(self, strategy_name: str) -> float:
        if strategy_name not in self.strategy_allocations:
            return 0.0
        allocation_pct = self.strategy_allocations[strategy_name]
        return self.capital_manager.total_capital * allocation_pct

    async def _rebalance_allocations(self):
        now = time.time()
        rebal_interval = self.config.get("capital_allocator", {}).get("rebalance_interval_s", 300)
        if now - self.last_rebal_time < rebal_interval:
            return

        logging.info("Rebalancing capital allocations...")

        performance = await self.metrics.get_strategy_performance(60)

        symbols = self.config.get("symbols", [])
        for symbol in symbols:
            for strategy_name in ["scalper", "whale_tracker", "news_reactor"]:
                positions = [p for p in self.positions if p.strategy == strategy_name and p.symbol == symbol and not p.closed]
                if len(positions) > 0:
                    pnl_pct_sum = sum(p.pnl_pct for p in positions)
                    if pnl_pct_sum > 0:
                        self.strategy_allocations[strategy_name] = min(
                            0.60,
                            self.strategy_allocations.get(strategy_name, 0.33) * 1.1
                        )
                    else:
                        self.strategy_allocations[strategy_name] = max(
                            0.05,
                            self.strategy_allocations.get(strategy_name, 0.33) * 0.8
                        )

        total_alloc = sum(self.strategy_allocations.values())
        if total_alloc > 0:
            for k in self.strategy_allocations:
                self.strategy_allocations[k] /= total_alloc

        self.last_rebal_time = now
        logging.info(f"Strategy allocations: {self.strategy_allocations}")

    async def _process_signals(self):
        while not self.shutdown_event.is_set():
            try:
                signal: ExecutionSignal = await asyncio.wait_for(
                    self.event_queue.get(timeout=1.0),
                    timeout=1.0
                )
                if signal:
                    current_capital = await self._allocate_capital(signal.strategy)
                    signal.capital = current_capital * signal.metadata.get("position_size_pct", 0.30) if signal.strategy != "scalper" else current_capital * 0.20

                    position = await self.execution_engine.execute_order(signal)
                    if position:
                        self.positions.append(position)
                        await self._track_position(position)
                        logging.info(f"Opened position {position.id}: {position.symbol} {position.direction.value} @ {position.entry_price:.4f}")

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logging.error(f"Error processing signal: {e}")

    async def _track_position(self, position: Position):
        try:
            while not position.closed and not self.shutdown_event.is_set():
                await asyncio.sleep(0.5)
                price = await self.price_cache.get_latest(position.symbol)
                if price:
                    if position.direction == TradeDirection.LONG:
                        position.pnl_pct = (price - position.entry_price) / position.entry_price * 100
                    else:
                        position.pnl_pct = (position.entry_price - price) / position.entry_price * 100
                    position.pnl_usdc = position.initial_capital * position.pnl_pct / 100

                    exit_time = position.exit_time or time.time()
                    if position.direction == TradeDirection.LONG:
                        exit_time = position.exit_time or time.time()
                        if position.entry_time > 0:
                            duration = exit_time - position.entry_time
                            strategy_config = self.config.get(position.strategy, {})
                            max_hold = strategy_config.get("max_hold_seconds", 120)
                            min_hold = strategy_config.get("min_hold_seconds", 10)
                            tp_mult = strategy_config.get("take_profit_atr_multiple", 1.5) if hasattr(self, "price_cache") else 1.5
                            sl_mult = strategy_config.get("stop_loss_atr_multiple", 1.0) if hasattr(self, "price_cache") else 1.0

                            if position.pnl_pct >= tp_mult * 100 or position.pnl_pct <= -sl_mult * 100 or duration >= max_hold or duration < min_hold:
                                self.positions.remove(position)
                                logging.info(f"Position {position.id}: closed with PnL ${position.pnl_usdc:.2f}")

        except Exception as e:
            logging.error(f"Error tracking position {position.id}: {e}")

    async def _collect_metrics(self):
        while not self.shutdown_event.is_set():
            try:
                await asyncio.sleep(60)
                await self.metrics.record("capital", self.capital_manager.total_capital, {})
                await self.metrics.record("available_capital", self.capital_manager.available_capital, {})
                await self.metrics.record("bound_capital", self.capital_manager.bound_capital, {})
                await self.metrics.record("open_positions", len([p for p in self.positions if not p.closed]), {})

                await self.health_monitor.heartbeat("core_metrics")

            except Exception as e:
                logging.error(f"Error collecting metrics: {e}")

    async def _health_check(self):
        while not self.shutdown_event.is_set():
            try:
                await asyncio.sleep(30)
                await self.health_monitor.check_health()
                await self.health_monitor.heartbeat("health_check")
            except Exception as e:
                logging.error(f"Health check error: {e}")

    async def _shutdown_handler(self):
        try:
            while not self.shutdown_event.is_set():
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            logging.info("Initiating graceful shutdown...")
            self.running = False

            for task in self.tasks:
                task.cancel()

            logging.info(f"Final position count: {len(self.positions)}")
            logging.info(f"Final capital: ${self.capital_manager.total_capital:.2f}")

            await self.metrics.close()

    async def run(self):
        self.running = True
        self._load_strategies()

        global start_time
        start_time = time.time()

        tasks = [
            asyncio.create_task(self._process_signals()),
            asyncio.create_task(self._collect_metrics()),
            asyncio.create_task(self._health_check())
        ]

        for strategy in self.strategies.values():
            strategy_task = asyncio.create_task(strategy.run())
            tasks.append(strategy_task)
            self.tasks.append(strategy_task)

        shutdown_task = asyncio.create_task(self._shutdown_handler())
        self.tasks.append(shutdown_task)

        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except asyncio.CancelledError:
            pass
        finally:
            logging.info("Engine shutdown complete")

    async def notify(self, signal: ExecutionSignal):
        await self.event_queue.put(signal)

    async def update_price(self, symbol: str, price: float):
        await self.price_cache.update(symbol, price)
        await self.health_monitor.heartbeat(f"price_{symbol}")


async def main():
    config = load_config("war_config.json")
    engine = DenaroEngine(config)

    try:
        await engine.run()
    except KeyboardInterrupt:
        logging.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logging.error(f"Fatal error: {e}", exc_info=True)
    finally:
        logging.info("Engine stopped")


if __name__ == "__main__":
    asyncio.run(main())