"""ATLAS Strategy Engine - Grid strategy implementation."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict, List, Optional

from atlas.connector.models import Ticker
from atlas.execution.models import OrderRequest, OrderSide, OrderType, TimeInForce
from atlas.portfolio.manager import ExchangeRegistry, PortfolioManager
from atlas.execution.router import ExecutionRouter
from atlas.core.events import EventBus, TickEvent

logger = logging.getLogger(__name__)


class GridStrategy:
    """Simple grid strategy: place buy/sell limit orders around mid price."""

    def __init__(
        self,
        strategy_id: str,
        symbols: List[str],
        exchanges: List[str],
        params: dict,
        event_bus: EventBus,
    ):
        self.strategy_id = strategy_id
        self.symbols = symbols
        self.exchanges = exchanges
        self.params = params
        self.event_bus = event_bus
        self._levels = int(params.get("grid_levels", params.get("levels", 5)))
        self._spread_pct = float(params.get("spread_pct", 0.005))
        self._per_level_pct = float(params.get("per_level_pct", 0.15))
        self._order_size = float(params.get("order_size", 0.0))
        self._min_notional = float(params.get("min_notional", 10.0))
        self._running = False
        self._last_signal_time: Dict[str, int] = {}

    def _resolve_order_size(self, ticker: Ticker, portfolio_manager: PortfolioManager) -> float:
        """Derive order size from per_level_pct of total equity, or use explicit order_size."""
        if self._order_size and self._order_size > 0:
            return self._order_size
        equity = portfolio_manager.get_total_equity()
        if equity <= 0:
            return 0.0
        return (equity * self._per_level_pct) / max(ticker.last, 1e-12)

    async def on_tick(self, symbol: str, exchange: str, ticker: Ticker) -> List[OrderRequest]:
        """Generate grid orders around the current mid price."""
        # Throttle signals to avoid spamming (one per 60s per symbol)
        key = f"{exchange}:{symbol}"
        now = int(time.time())
        if now - self._last_signal_time.get(key, 0) < 60:
            return []
        self._last_signal_time[key] = now

        mid_price = ticker.last
        if mid_price <= 0:
            return []

        orders = []
        for i in range(1, self._levels + 1):
            buy_price = mid_price * (1 - self._spread_pct * i)

            orders.append(OrderRequest(
                symbol=symbol,
                side=OrderSide.BUY,
                type=OrderType.LIMIT,
                amount=self._order_size,
                price=buy_price,
                time_in_force=TimeInForce.GTC,
                exchange=exchange,
                strategy_id=self.strategy_id,
            ))

        logger.info(f"Grid signal: {symbol} mid={mid_price:.2f} -> {len(orders)} buy orders")
        return orders


class StrategyEngine:
    """Manages strategy lifecycle and tick processing."""

    def __init__(
        self,
        exchange_registry: ExchangeRegistry,
        portfolio_manager: PortfolioManager,
        execution_router: ExecutionRouter,
        event_bus: EventBus,
    ):
        self.exchange_registry = exchange_registry
        self.portfolio_manager = portfolio_manager
        self.execution_router = execution_router
        self.event_bus = event_bus
        self._strategies: Dict[str, GridStrategy] = {}
        self._running = False
        self._tasks: set[asyncio.Task] = set()

    @property
    def strategy_ids(self) -> List[str]:
        return list(self._strategies.keys())

    async def add_strategy(self, config: dict) -> None:
        class_path = config.get("class_path", "atlas.strategy.engine.GridStrategy")
        if class_path.endswith("DCAStrategy"):
            from atlas.strategy.dca import DCAStrategy
            strat = DCAStrategy(
                strategy_id=config["strategy_id"],
                symbols=config["symbols"],
                exchanges=config["exchanges"],
                params=config.get("params", {}),
                event_bus=self.event_bus,
            )
        else:
            strat = GridStrategy(
                strategy_id=config["strategy_id"],
                symbols=config["symbols"],
                exchanges=config["exchanges"],
                params=config.get("params", {}),
                event_bus=self.event_bus,
            )
        self._strategies[strat.strategy_id] = strat
        logger.info(f"Strategy added: {strat.strategy_id} ({class_path})")

    async def _run_strategy_loop(self, strat: GridStrategy) -> None:
        """Run tick loop for a single strategy."""
        while self._running:
            try:
                for symbol in strat.symbols:
                    for exchange_name in strat.exchanges:
                        connector = self.exchange_registry.get(exchange_name)
                        if not connector:
                            continue

                        # Dedup: check existing open orders before placing new ones
                        try:
                            open_orders = await connector.fetch_open_orders(symbol)
                            if len(open_orders) >= strat._levels:
                                logger.debug(f"{exchange_name}:{symbol} already has {len(open_orders)} open orders, skipping")
                                continue
                        except Exception as e:
                            logger.warning(f"fetch_open_orders failed ({exchange_name}:{symbol}): {e}")

                        ticker = await connector.fetch_ticker(symbol)
                        orders = await strat.on_tick(symbol, exchange_name, ticker)
                        for order in orders:
                            try:
                                await self.execution_router.submit(order)
                            except Exception as e:
                                logger.warning(f"Order submit failed: {e}")
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Strategy loop error for {strat.strategy_id}: {e}")
                await asyncio.sleep(30)

    async def start(self) -> None:
        self._running = True
        for strat in self._strategies.values():
            task = asyncio.create_task(self._run_strategy_loop(strat))
            self._tasks.add(task)
        logger.info(f"StrategyEngine started with {len(self._strategies)} strategies")

    async def stop(self) -> None:
        self._running = False
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        logger.info("StrategyEngine stopped")
