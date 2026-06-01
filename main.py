"""denaro-antigravity main.py – Main Trading Bot Orchestrator.

Combines strategies, SQLite DB, risk management, Telegram alerts, and FastAPI Web Dashboard into an integrated async runtime.
"""
from __future__ import annotations

import asyncio
import signal
import sys
import time
from typing import NoReturn

from loguru import logger

from core.engine import ExchangeWrapper, RiskManager, TradeDB, settings
from services.dashboard import DashboardServer
from services.notifications import NotificationService
from strategies.base import BaseStrategy, Position, Side, Signal
from strategies.grid import GridTraderStrategy
from strategies.scalper import ScalperStrategy

class TradingBot:
    def __init__(self):
        self.running = False
        self.db = TradeDB("denaro")
        self.risk = RiskManager(self.db)
        self.notify = NotificationService(self)
        self.dashboard = DashboardServer(self)
        
        self.exchanges: dict[str, ExchangeWrapper] = {}
        self.strategies: list[BaseStrategy] = []

    # ── Bootstrap ─────────────────────────────────────────────────────────────
    async def _setup_exchanges(self) -> None:
        """Initializes unique exchange adapters defined by active strategies."""
        required = set()
        if "scalper" in settings.active_strategies:
            required.add((settings.scalper_exchange.lower(), "SCALPER"))
        if "grid" in settings.active_strategies:
            required.add((settings.grid_exchange.lower(), "GRID"))

        for name, _ in required:
            if name not in self.exchanges:
                key = settings.binance_api_key if name == "binance" else settings.cryptocom_api_key
                secret = settings.binance_api_secret if name == "binance" else settings.cryptocom_api_secret
                wrapper = ExchangeWrapper(name, key, secret, settings.dry_run)
                await wrapper.connect()
                self.exchanges[name] = wrapper

    async def _load_strategies(self) -> None:
        """Instantiates active strategies and registers their capital allocation."""
        active = settings.active_strategies

        if "scalper" in active:
            ex_name = settings.scalper_exchange.lower()
            strategy = ScalperStrategy(self.exchanges[ex_name], self.db)
            self.strategies.append(strategy)
            logger.info(f"Loaded Scalper Strategy on exchange {ex_name} | Capital: {settings.scalper_capital:.2f} EUR")

        if "grid" in active:
            ex_name = settings.grid_exchange.lower()
            strategy = GridTraderStrategy(self.exchanges[ex_name], self.db)
            self.strategies.append(strategy)
            logger.info(f"Loaded GridTrader Strategy on exchange {ex_name} | Capital: {settings.grid_capital:.2f} EUR")

    # ── Candle Data Loop ──────────────────────────────────────────────────────
    async def _data_loop(self) -> NoReturn:
        """Fetches candle ticks, feeds active strategies, and handles entry order triggers."""
        logger.info("Starting Candle Data tick loop...")
        
        while self.running:
            try:
                for strategy in self.strategies:
                    if strategy.is_paused or self.risk.is_halted:
                        continue
                    
                    # Fetch OHLCV history
                    ohlcv = await strategy.exchange.fetch_ohlcv(
                        symbol=strategy.symbol,
                        timeframe="1m",
                        limit=200
                    )
                    
                    if not ohlcv:
                        continue
                        
                    # Process indicators and return trade signals
                    signals = await strategy.on_candle(ohlcv)
                    
                    for sig in signals:
                        # Count total active positions across strategies to enforce risk
                        total_open = sum(len(s._positions) for s in self.strategies)
                        
                        if not self.risk.can_open_position(total_open):
                            continue
                            
                        await self._execute_signal(sig, strategy)
                        
            except Exception as e:
                logger.error(f"Candle Data Loop Error: {e}")
                await self.notify.alert_error("MAIN", f"Data Loop Exception: {e}")
                
            await asyncio.sleep(15)  # Fetch/Process every 15 seconds

    async def _execute_signal(self, sig: Signal, strategy: BaseStrategy) -> None:
        """Creates an entry limit order on the exchange and registers it in self._positions."""
        try:
            logger.info(f"Executing trade signal: {sig}")
            order = await strategy.exchange.create_order(
                symbol=sig.symbol,
                order_type="limit",
                side=sig.side.value,
                amount=sig.amount,
                price=sig.price
            )
            
            # Register in active positions tracker
            pos = Position(
                symbol=sig.symbol,
                side=sig.side,
                amount=sig.amount,
                entry_price=sig.price if sig.price else order["price"],
                tp_price=sig.tp_price,
                sl_price=sig.sl_price,
                order_id=order["id"],
                entry_time=time.time()
            )
            strategy._positions[order["id"]] = pos
            
            await self.notify.alert_trade(
                strategy=strategy.name,
                side=sig.side.value,
                symbol=sig.symbol,
                amount=sig.amount,
                price=pos.entry_price,
                reason=sig.reason
            )
        except Exception as e:
            logger.error(f"Signal execution failed: {e}")
            await self.notify.alert_error(strategy.name, f"Entry Order Placement Failed: {e}")

    # ── Order Update Loop ─────────────────────────────────────────────────────
    async def _order_update_loop(self) -> None:
        """Polls open orders to track execution fills and delegates to strategy update handlers."""
        logger.info("Starting Active Order update loop...")
        
        while self.running:
            try:
                # Gather all open order references across strategies
                all_open_positions: list[tuple[str, Position, BaseStrategy]] = []
                for s in self.strategies:
                    # Entry order tracking
                    for oid, pos in list(s._positions.items()):
                        all_open_positions.append((oid, pos, s))
                    # Opposing Grid limit order tracking
                    if s.name == "GridTrader":
                        for lvl in s._grid:
                            if lvl.order_id and not lvl.filled:
                                # Wrap grid level as a dummy Position reference for polling
                                dummy = Position(s.symbol, lvl.side, lvl.amount, lvl.price, order_id=lvl.order_id)
                                all_open_positions.append((lvl.order_id, dummy, s))

                for oid, pos, strategy in all_open_positions:
                    try:
                        order = await strategy.exchange.fetch_order(oid, pos.symbol)
                        status = order.get("status", "")
                        
                        if status == "closed":
                            # Handle standard strategy fills
                            await strategy.on_order_update(order)
                            
                            # Update realized risk baseline
                            if hasattr(pos, "pnl") and pos.pnl != 0.0:
                                self.risk.record_trade_pnl(pos.pnl)
                                await self.notify.alert_pnl(strategy.name, pos.pnl, pos.symbol)
                                
                        elif status == "canceled":
                            # Clean up canceled items from memory
                            if oid in strategy._positions:
                                del strategy._positions[oid]
                                logger.info(f"Cleaned up canceled order: {oid} from strategy {strategy.name}")
                                
                    except Exception as e:
                        logger.warning(f"Could not poll order status for {oid}: {e}")
                        
            except Exception as e:
                logger.error(f"Order Update Loop Error: {e}")
                
            await asyncio.sleep(5)  # Poll order updates every 5 seconds

    # ── Daily Reset Loop ──────────────────────────────────────────────────────
    async def _daily_reset_loop(self) -> None:
        """Enforces UTC midnight safety reset and audits total portfolio value."""
        while self.running:
            now = time.gmtime()
            # Seconds remaining until next UTC midnight
            seconds_to_midnight = 86400 - (now.tm_hour * 3600 + now.tm_min * 60 + now.tm_sec)
            await asyncio.sleep(seconds_to_midnight)
            
            try:
                # Query aggregate account equity in USDT equivalent
                total_equity = 0.0
                for ex in self.exchanges.values():
                    total_equity += await ex.get_total_equity_usdt()
                
                # Settle new daily risk baseline
                self.risk.set_daily_baseline(total_equity)

                await self.notify.send(f"🌅 <b>Nuovo Giorno Tradato</b> | Equity Baseline auditata: <code>{total_equity:.2f} USD</code>")
            except Exception as e:
                logger.error(f"Daily reset baseline update failed: {e}")

    # ── Main Entrypoint ───────────────────────────────────────────────────────
    async def run(self) -> None:
        logger.info("Initializing denaro-antigravity trading bot engine...")
        self.running = True

        # Signal handlers for graceful shutdown on SIGINT/SIGTERM
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, lambda: asyncio.ensure_future(self.shutdown()))
            except NotImplementedError:
                # Windows standard compatibility fallback
                pass

        # 1. Setup Exchanges
        await self._setup_exchanges()

        # 2. Setup Risk Baseline
        total_equity = 0.0
        for name, ex in self.exchanges.items():
            total_equity += await ex.get_total_equity_usdt()
        
        # Settle fallback for dry-run or empty balances
        if total_equity <= 0:
            total_equity = settings.total_capital_eur * 1.08  # Approx EUR to USDT rate
            
        self.risk.set_daily_baseline(total_equity)

        # 3. Load Strategies
        await self._load_strategies()

        # 4. Start Services (Telegram Bot & FastAPI Server)
        await self.notify.start()
        await self.dashboard.start()

        # 5. Execute Async Service Loops Concurrently
        logger.info("denaro-antigravity bot engine online and active.")
        await asyncio.gather(
            self._data_loop(),
            self._order_update_loop(),
            self._daily_reset_loop()
        )

    async def shutdown(self) -> None:
        if not self.running:
            return
        logger.critical("Shutdown request received. Terminating trading operations gracefully...")
        self.running = False

        # Gracefully shutdown active strategies (liquidate naked active trades)
        for s in self.strategies:
            await s.shutdown()

        # Stop FastAPI Server and Telegram updater
        await self.dashboard.stop()
        await self.notify.stop()

        # Terminate exchange connection client pools
        for name, ex in self.exchanges.items():
            await ex.close()

        logger.info("denaro-antigravity engine successfully offline. Shutdown complete.")
        sys.exit(0)

if __name__ == "__main__":
    # Customizing log format via Loguru
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level:7}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=settings.log_level
    )
    
    bot = TradingBot()
    try:
        asyncio.run(bot.run())
    except (KeyboardInterrupt, SystemExit):
        pass
