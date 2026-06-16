#!/usr/bin/env python3
"""denaro-antigravity main.py – Main Trading Bot Orchestrator.

Combines strategies, SQLite DB, risk management, Telegram alerts, and FastAPI Web Dashboard into an integrated async runtime.
"""
from __future__ import annotations

import asyncio
import signal
import sys
import time
from typing import NoReturn, Dict, Any

from loguru import logger

from core.engine import ExchangeWrapper, RiskManager, TradeDB, settings
from services.dashboard import DashboardServer
from services.notifications import NotificationService
from strategies.base import BaseStrategy, Position, Side, Signal
from strategies.grid import GridTraderStrategy
from strategies.scalper import ScalperStrategy
from strategies.rsi_mean_rev import RSIReversionStrategy
from strategies.dynamic_grid import DynamicGridStrategy


class TradingBot:
    def __init__(self):
        self.exchanges: Dict[str, ExchangeWrapper] = {}
        self.strategies: list[BaseStrategy] = []
        self.db: TradeDB | None = None
        self.risk_manager: RiskManager | None = None
        self.dashboard: DashboardServer | None = None
        self.notification_service: NotificationService | None = None
        self.closing = False
        self._ohlcv_cache: Dict[str, list[list[float]]] = {}
        self._reconcile_task: asyncio.Task | None = None

    async def _initialize_services(self):
        logger.info("Initializing Denaro Bot Engine...")
        self.db = TradeDB(settings.db_path)
        await self.db.connect()

        # Load exchanges
        ex_name = settings.exchange_id
        try:
            exchange = ExchangeWrapper(settings)
            await exchange.connect()
            self.exchanges[ex_name] = exchange
            logger.info(f"Exchange {ex_name} initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize exchange {ex_name}: {e}")

        # Load Risk Manager
        self.risk_manager = RiskManager(self.db)

        # Load Notification Service
        self.notification_service = NotificationService(self)
        await self.notification_service.initialize()

        # Load Dashboard
        self.dashboard = DashboardServer(self)
        asyncio.create_task(self.dashboard.start())

        # Load Strategies and their required exchanges
        required_exchanges = {}
        ex_name = settings.exchange_id
        required_exchanges[ex_name] = self.exchanges.get(ex_name)

        # Helper to load strategies
        def load_strategy(strategy_cls, config_prefix, capital_attr, symbol_attr=None, **extra_kwargs):
            for ex_name, exchange in required_exchanges.items():
                if not exchange:
                    continue
                try:
                    capital_setting = getattr(settings, f'{ex_name.lower()}_{config_prefix}_{capital_attr}', 
                                            getattr(settings, f'{config_prefix}_{capital_attr}'))
                    if symbol_attr:
                        sym = getattr(settings, f'{ex_name.lower()}_{config_prefix}_{symbol_attr}',
                                    getattr(settings, f'{config_prefix}_{symbol_attr}'))
                    else:
                        sym = None
                    
                    kwargs = {'initial_capital': capital_setting}
                    if sym:
                        kwargs['symbol'] = sym
                    kwargs.update(extra_kwargs)
                    
                    strategy = strategy_cls(exchange, self.db, **kwargs)
                    if hasattr(strategy, 'set_initial_capital'):
                        asyncio.create_task(strategy.set_initial_capital(capital_setting))
                    self.strategies.append(strategy)
                    
                    sym_str = f" | Symbol: {sym}" if sym else ""
                    logger.info(f"Loaded {strategy_cls.__name__} on exchange {ex_name}{sym_str} | Capital: {capital_setting:.2f}")
                except Exception as e:
                    logger.error(f"Failed to load {strategy_cls.__name__} on {ex_name}: {e}")

        # Load Scalper Strategy
        if settings.enable_scalper:
            load_strategy(ScalperStrategy, 'scalper', 'capital')

        # Load Grid Strategy
        if settings.enable_grid:
            load_strategy(GridTraderStrategy, 'grid', 'capital', 'symbol')

        # Load Dynamic Grid Strategy
        if settings.enable_dynamic_grid:
            for ex_name, exchange in required_exchanges.items():
                if not exchange:
                    continue
                try:
                    capital_setting = getattr(settings, f'{ex_name.lower()}_dynamic_grid_capital_usdt', 
                                            settings.dynamic_grid_capital_usdt)
                    symbol = getattr(settings, f'{ex_name.lower()}_dynamic_grid_symbol', settings.dynamic_grid_symbol)
                    base_levels = getattr(settings, f'{ex_name.lower()}_dynamic_grid_levels', settings.dynamic_grid_levels)
                    min_spacing = getattr(settings, f'{ex_name.lower()}_dynamic_grid_min_spacing', settings.dynamic_grid_min_spacing)
                    max_spacing = getattr(settings, f'{ex_name.lower()}_dynamic_grid_max_spacing_pct', settings.dynamic_grid_max_spacing_pct)
                    price_precision = getattr(settings, f'{ex_name.lower()}_dynamic_grid_price_precision', settings.dynamic_grid_price_precision)
                    amount_precision = getattr(settings, f'{ex_name.lower()}_dynamic_grid_amount_precision', settings.dynamic_grid_amount_precision)
                    take_profit_pct = getattr(settings, f'{ex_name.lower()}_dynamic_grid_take_pct', settings.dynamic_grid_take_pct)
                    trailing_stop = getattr(settings, f'{ex_name.lower()}_dynamic_grid_trailing_stop', settings.dynamic_grid_trailing_stop)

                    strategy = DynamicGridStrategy(
                        exchange, self.db,
                        symbol=symbol,
                        capital=capital_setting,
                        base_levels=base_levels,
                        min_spacing=min_spacing,
                        max_spacing=max_spacing,
                        price_precision=price_precision,
                        amount_precision=amount_precision
                    )
                    if hasattr(strategy, 'set_initial_capital'):
                        asyncio.create_task(strategy.set_initial_capital(capital_setting))
                    strategy.take_profit_pct = take_profit_pct
                    strategy.trailing_stop = trailing_stop
                    self.strategies.append(strategy)
                    logger.info(f"Loaded DynamicGridStrategy on exchange {ex_name} | Symbol: {symbol} | Capital: {capital_setting:.2f} USDT")
                except Exception as e:
                    logger.error(f"Failed to load DynamicGridStrategy on {ex_name}: {e}")

        # Load RSI Mean Reversion Strategy
        if settings.enable_rsi_reversion:
            load_strategy(RSIReversionStrategy, 'rsi', 'capital', 'symbol')

        # Load BTC/USDT Grid Strategy
        if settings.enable_btc_grid:
            load_strategy(GridTraderStrategy, 'btc_grid', 'capital_usdt', 'symbol')

        # Load ETH/USDT Grid Strategy
        if settings.enable_eth_grid:
            load_strategy(GridTraderStrategy, 'eth_grid', 'capital_usdt', 'symbol')

        # Load BTC/USDT RSI Mean Reversion Strategy
        if settings.enable_btc_rsi:
            load_strategy(RSIReversionStrategy, 'btc_rsi', 'capital_usdt', 'symbol')

        # Load ETH/USDT RSI Mean Reversion Strategy
        if settings.enable_eth_rsi:
            load_strategy(RSIReversionStrategy, 'eth_rsi', 'capital_usdt', 'symbol')

        # Initialize Risk Manager
        if self.risk_manager and self.strategies:
            await self.risk_manager.initialize(self.strategies)

    async def _run_strategy_loop(self, strategy: BaseStrategy):
        while not self.closing:
            try:
                await asyncio.sleep(strategy.update_interval)
                if self.closing or strategy.is_paused:
                    continue

                # Fetch OHLCV data
                key = f"{strategy.symbol}:{strategy.timeframe}"
                if key in self._ohlcv_cache:
                    ohlcv = self._ohlcv_cache[key]
                else:
                    ohlcv = await strategy.exchange.fetch_ohlcv(strategy.symbol, strategy.timeframe)
                    if ohlcv:
                        self._ohlcv_cache[key] = ohlcv
                    else:
                        logger.warning(f"No OHLCV data received for {strategy.symbol}")
                        continue

                if not ohlcv:
                    logger.warning(f"No OHLCV data received for {strategy.symbol}")
                    continue

                # Update capital and check SL
                try:
                    current_capital = await strategy.get_quote_capital()
                    if hasattr(strategy, 'set_initial_capital'):
                        await strategy.set_initial_capital(current_capital)
                    if hasattr(strategy, '_check_sl'):
                        await strategy._check_sl(ohlcv[-1][4])
                except Exception as e:
                    logger.error(f"Error updating capital/checking SL for {strategy.symbol}: {e}")
                    continue

                # Run strategy
                signals = None
                if hasattr(strategy, 'on_candle'):
                    signals = await strategy.on_candle(ohlcv)
                elif hasattr(strategy, 'run'):
                    await strategy.run()
                    continue
                
                if signals:
                    for sig in signals:
                        await self._execute_signal(sig, strategy)
            except asyncio.CancelledError:
                logger.info(f"Strategy loop for {strategy.symbol} cancelled.")
                break
            except Exception as e:
                logger.error(f"Error in strategy loop for {strategy.symbol}: {e}")
                await asyncio.sleep(5)

    async def _execute_signal(self, sig: Signal, strategy: BaseStrategy) -> None:
        if not self.risk_manager:
            logger.warning(f"No risk manager configured, skipping trade for {sig.symbol}")
            return
        
        is_safe = True
        try:
            is_safe = await self.risk_manager.is_safe(strategy.symbol, sig.side, sig.amount)
        except Exception as e:
            logger.warning(f"Risk manager check failed: {e}, allowing trade")
        
        if not is_safe:
            logger.warning(f"Trade blocked by risk manager for {sig.symbol}: {sig.side} {sig.amount}")
            return

        try:
            logger.info(f"Executing signal: {sig.side.value} {sig.amount} {sig.symbol} @ {sig.entry_price}")
            order = await strategy.exchange.create_order(
                sig.symbol, 'limit', sig.side.value, sig.amount, sig.entry_price
            )
            
            new_pos = Position(sig.symbol, sig.side, sig.amount, sig.entry_price, 
                             sig.tp_price, sig.sl_price, sig.source, order_id=order['id'])
            strategy._positions[order['id']] = new_pos
            logger.info(f"Order placed: {order['id']} for {sig.symbol}")
        except Exception as e:
            logger.error(f"Failed to execute signal for {sig.symbol}: {e}")

    async def run(self):
        await self._initialize_services()

        # Start strategy loops
        strategy_tasks = []
        for strategy in self.strategies:
            task = asyncio.create_task(self._run_strategy_loop(strategy))
            strategy_tasks.append(task)
            logger.info(f"Started strategy loop for {strategy.symbol}")

        # Start order reconciliation task
        self._reconcile_task = asyncio.create_task(self._reconcile_orders())
        logger.info("Started order reconciliation task")

        # Keep the main loop running
        while not self.closing:
            await asyncio.sleep(1)

        # Wait for all tasks to complete
        if strategy_tasks:
            await asyncio.gather(*strategy_tasks, return_exceptions=True)

    async def _reconcile_orders(self) -> None:
        """Periodically reconcile local order state with exchange."""
        while not self.closing:
            try:
                await asyncio.sleep(60)
                for strategy in self.strategies:
                    if not hasattr(strategy, '_positions'):
                        continue
                    
                    for oid, pos in list(strategy._positions.items()):
                        try:
                            if oid.startswith("MOCK-"):
                                continue
                            
                            order = await strategy.exchange.fetch_order(oid, pos.symbol)
                            status = order.get('status', '')
                            
                            if status == 'closed' and oid in strategy._positions:
                                if pos.side == Side.BUY and pos.tp_order_id == oid:
                                    exec_price = order.get('price', pos.tp_price) or pos.tp_price
                                    gross_pnl = (exec_price - pos.entry_price) * pos.amount
                                    fees = (pos.entry_price + exec_price) * pos.amount * 0.00075
                                    net_pnl = gross_pnl - fees
                                    
                                    logger.info(f"RECONCILE: TP filled for {pos.symbol} @ {exec_price:.4f}. Net PnL: {net_pnl:+.4f} USD.")
                                    try:
                                        strategy.db.save_trade(
                                            symbol=pos.symbol,
                                            side="sell",
                                            price=exec_price,
                                            amount=pos.amount,
                                            value_usd=pos.amount * exec_price,
                                            fee_usd=fees,
                                            net_pnl=net_pnl,
                                            strategy=strategy.name
                                        )
                                    except Exception:
                                        pass
                                    del strategy._positions[oid]
                                elif pos.side == Side.SELL and pos.tp_order_id == oid:
                                    pass
                            elif status == 'canceled':
                                logger.warning(f"RECONCILE: Order {oid} was canceled on exchange")
                                if oid in strategy._positions:
                                    del strategy._positions[oid]
                        except Exception as e:
                            logger.debug(f"Reconcile check for {oid} failed: {e}")
                            continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Order reconciliation error: {e}")

    def stop(self):
        self.closing = True
        logger.info("Shutting down trading bot...")
        # Close exchange connections
        for exchange in self.exchanges.values():
            try:
                exchange.close()
            except Exception as e:
                logger.debug(f"Exchange close error: {e}")
        # Close DB connection
        if self.db:
            try:
                self.db.close()
            except Exception as e:
                logger.debug(f"DB close error: {e}")
        logger.info("Trading bot shut down.")

async def main():
    bot = TradingBot()
    # Handle shutdown signals
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(bot.stop()))

    await bot.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped manually.")
    except Exception as e:
        logger.critical(f"Unhandled exception in main: {e}")
        sys.exit(1)
