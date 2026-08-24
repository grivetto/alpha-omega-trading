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

    def _resolve_order_size(self, ticker: Ticker, portfolio_manager: Optional[PortfolioManager] = None) -> float:
        """Derive order size from per_level_pct of total equity, or use explicit order_size."""
        if self._order_size and self._order_size > 0:
            return self._order_size
        if portfolio_manager is None:
            return 0.0
        equity = portfolio_manager.get_total_equity()
        if equity <= 0:
            return 0.0
        return (equity * self._per_level_pct) / max(ticker.last, 1e-12)

    async def on_tick(self, symbol: str, exchange: str, ticker: Ticker,
                      balances: Optional[dict] = None) -> List[OrderRequest]:
        """Generate grid orders around the current mid price.

        Buy ladder sotto il mid, sell ladder sopra il mid.
        amount = _resolve_order_size() (order_size esplicito o equity-based).
        Filtro saldo: buy solo se finanziabile con la quote free, sell solo se
        possediamo la base. Niente ordini impossibili -> niente Insufficient funds.
        """
        # Throttle signals to avoid spamming (one per 60s per symbol)
        key = f"{exchange}:{symbol}"
        now = int(time.time())
        if now - self._last_signal_time.get(key, 0) < 60:
            return []
        self._last_signal_time[key] = now

        mid_price = ticker.last
        if mid_price <= 0:
            return []

        # ---- amount: order_size esplicito o equity-based ----
        amount = self._resolve_order_size(ticker, None)
        if amount <= 0:
            logger.warning(f"Grid {symbol}: order_size<=0 ({self._order_size}) e nessuna equity, skip")
            return []
        notional = amount * mid_price
        if notional < self._min_notional:
            logger.warning(f"Grid {symbol}: notional {notional:.2f} < min_notional {self._min_notional}, skip")
            return []

        # ---- saldi reali per il filtro ----
        base_ccy, _, quote_ccy = symbol.partition("/")
        quote_free = 0.0
        base_free = 0.0
        if balances:
            if quote_ccy and quote_ccy in balances:
                quote_free = float(balances[quote_ccy].free)
            if base_ccy and base_ccy in balances:
                base_free = float(balances[base_ccy].free)

        orders = []
        for i in range(1, self._levels + 1):
            buy_price = mid_price * (1 - self._spread_pct * i)
            sell_price = mid_price * (1 + self._spread_pct * i)

            buy_cost = amount * buy_price
            if buy_cost <= quote_free:
                orders.append(OrderRequest(
                    symbol=symbol,
                    side=OrderSide.BUY,
                    type=OrderType.LIMIT,
                    amount=amount,
                    price=buy_price,
                    time_in_force=TimeInForce.GTC,
                    exchange=exchange,
                    strategy_id=self.strategy_id,
                ))
            else:
                logger.info(f"Grid {symbol}: buy @{buy_price:.2f} cost {buy_cost:.2f} > quote free {quote_free:.2f}, skip")

            if amount <= base_free:
                orders.append(OrderRequest(
                    symbol=symbol,
                    side=OrderSide.SELL,
                    type=OrderType.LIMIT,
                    amount=amount,
                    price=sell_price,
                    time_in_force=TimeInForce.GTC,
                    exchange=exchange,
                    strategy_id=self.strategy_id,
                ))
            else:
                logger.info(f"Grid {symbol}: sell @{sell_price:.2f} richiede {amount} {base_ccy}, disponibili {base_free}, skip")

        n_buy = sum(1 for o in orders if o.side == OrderSide.BUY)
        n_sell = sum(1 for o in orders if o.side == OrderSide.SELL)
        logger.info(f"Grid signal: {symbol} mid={mid_price:.2f} -> {len(orders)} orders ({n_buy} buy, {n_sell} sell)")
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
        strat = GridStrategy(
            strategy_id=config["strategy_id"],
            symbols=config["symbols"],
            exchanges=config["exchanges"],
            params=config.get("params", {}),
            event_bus=self.event_bus,
        )
        self._strategies[strat.strategy_id] = strat
        logger.info(f"Strategy added: {strat.strategy_id}")

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
                        balances = None
                        try:
                            balances = await connector.fetch_balance()
                        except Exception as e:
                            logger.warning(f"fetch_balance failed ({exchange_name}:{symbol}): {e}")
                        orders = await strat.on_tick(symbol, exchange_name, ticker, balances)
                        for order in orders:
                            # dedup per lato+prezzo: se il livello e' gia' aperto, salta
                            if any(abs(o.price - order.price) < 1e-9 and o.side == order.side
                                   for o in open_orders):
                                logger.debug(f"{exchange_name}:{symbol} level {order.price} ({order.side}) gia' aperto, skip")
                                continue
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
