#!/usr/bin/env python3
"""
DENARO V2 - Main Orchestrator
Coordinates all trading strategies, manages lifecycle,
and provides real-time status monitoring.
"""
import asyncio
import json
import logging
import os
import signal
import sys
import time
from pathlib import Path

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import ExchangeClient, MarketScanner, SignalEngine, ExecutionEngine, RiskManager, PortfolioManager
from strategies import GridMarketMaker, MomentumScalper, MeanReversion
from config import load_config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('denaro_v2.log'),
    ],
    force=True,
)
logger = logging.getLogger("Denaro.Orchestrator")


class DenaroV2:
    """Main trading system orchestrator."""

    def __init__(self, config_path: str = None):
        self.config = load_config(config_path)
        self.running = False
        self.start_time = time.time()

        # Core components
        self.exchange = None
        self.scanner = None
        self.signals = SignalEngine()
        self.execution = None
        self.risk = None
        self.portfolio = None

        # Strategies
        self.grid_mms = {}
        self.momentum_scalpers = {}
        self.mean_reversions = {}

        # Status tracking
        self.cycle_count = 0
        self.last_status = time.time()
        self._status_file = self.config.get('monitoring', {}).get(
            'state_file', '.tmp/denaro_v2_status.json'
        )

    async def initialize(self):
        """Initialize all components."""
        logger.info("=" * 60)
        logger.info("DENARO V2 - Professional Trading System")
        logger.info("=" * 60)

        # Load API keys
        api_key = os.getenv("BINANCE_API_KEY", "")
        api_secret = os.getenv("BINANCE_API_SECRET", "")

        if not api_key or not api_secret:
            # Try loading from .env file
            env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
            if os.path.exists(env_path):
                with open(env_path) as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("BINANCE_API_KEY="):
                            api_key = line.split("=", 1)[1]
                        elif line.startswith("BINANCE_API_SECRET="):
                            api_secret = line.split("=", 1)[1]

        if not api_key or not api_secret:
            logger.error("BINANCE_API_KEY and BINANCE_API_SECRET required")
            sys.exit(1)

        # Initialize exchange
        testnet = self.config.get('exchange', {}).get('testnet', False)
        self.exchange = ExchangeClient(api_key, api_secret, testnet)
        await self.exchange.connect()

        # Load markets
        await self.exchange.exchange.load_markets()

        # Initialize risk manager
        risk_config = self.config.get('risk', {})
        self.risk = RiskManager(risk_config)

        # Initialize execution engine
        self.execution = ExecutionEngine(self.exchange, self.risk)

        # Initialize scanner
        self.scanner = MarketScanner(self.exchange)

        # Initialize portfolio manager
        self.portfolio = PortfolioManager(self.exchange, self.config.get('monitoring', {}))

        # Update portfolio value
        portfolio_data = await self.portfolio.get_portfolio_value()
        self.risk.update_portfolio_value(portfolio_data['total_eur'])
        logger.info(f"Portfolio value: {portfolio_data['total_eur']:.2f} EUR")

        # Initialize strategies
        await self._init_strategies()

        logger.info("DENARO V2 initialized successfully")
        logger.info(f"Mode: {'TESTNET' if testnet else 'LIVE'}")

    async def _init_strategies(self):
        """Initialize all enabled strategies."""
        strategies_config = self.config.get('strategies', {})

        # Grid Market Makers
        grid_config = strategies_config.get('grid_mm', {})
        if grid_config.get('enabled'):
            for symbol in grid_config.get('symbols', ['SOL/EUR']):
                cfg = {**grid_config, 'symbol': symbol}
                mm = GridMarketMaker(self.exchange, self.execution, self.risk, cfg)
                self.grid_mms[symbol] = mm
                logger.info(f"Grid MM initialized: {symbol}")

        # Momentum Scalpers
        momentum_config = strategies_config.get('momentum', {})
        if momentum_config.get('enabled'):
            for symbol in momentum_config.get('symbols', ['SOL/EUR']):
                cfg = {**momentum_config, 'symbol': symbol}
                scalper = MomentumScalper(
                    self.exchange, self.execution, self.risk,
                    self.scanner, self.signals, cfg
                )
                self.momentum_scalpers[symbol] = scalper
                logger.info(f"Momentum Scalper initialized: {symbol}")

        # Mean Reversion
        mr_config = strategies_config.get('mean_reversion', {})
        if mr_config.get('enabled'):
            for symbol in mr_config.get('symbols', ['ETH/EUR']):
                cfg = {**mr_config, 'symbol': symbol}
                mr = MeanReversion(
                    self.exchange, self.execution, self.risk,
                    self.scanner, self.signals, cfg
                )
                self.mean_reversions[symbol] = mr
                logger.info(f"Mean Reversion initialized: {symbol}")

    async def run(self):
        """Main trading loop."""
        self.running = True
        logger.info("Trading loop started")

        try:
            while self.running:
                try:
                    cycle_start = time.time()

                    # 1. Scan market
                    try:
                        opportunities = await self.scanner.scan()
                    except Exception as e:
                        logger.error(f"Scan error: {e}")
                        opportunities = {}

                    # 2. Get balance
                    try:
                        balance = await self.exchange.fetch_balance()
                    except Exception as e:
                        logger.error(f"Balance fetch error: {e}")
                        await asyncio.sleep(5)
                        continue

                    # 3. Update portfolio value
                    try:
                        portfolio_data = await self.portfolio.get_portfolio_value()
                        self.risk.update_portfolio_value(portfolio_data['total_eur'])
                    except Exception as e:
                        logger.error(f"Portfolio update error: {e}")

                    # 4. Run Grid Market Makers
                    for symbol, mm in self.grid_mms.items():
                        try:
                            price = opportunities.get(symbol, {}).get('price', 0)
                            if price > 0:
                                result = await mm.run_cycle(price, balance)
                                if result:
                                    logger.info(f"Grid MM {symbol}: cycle completed")
                        except Exception as e:
                            logger.error(f"Grid MM {symbol} error: {e}")

                    # 5. Run Momentum Scalpers
                    for symbol, scalper in self.momentum_scalpers.items():
                        try:
                            price = opportunities.get(symbol, {}).get('price', 0)
                            if price > 0:
                                result = await scalper.run_cycle(price, balance)
                                if result:
                                    logger.info(f"Momentum {symbol}: cycle completed")
                        except Exception as e:
                            logger.error(f"Momentum {symbol} error: {e}")

                    # 6. Run Mean Reversion
                    for symbol, mr in self.mean_reversions.items():
                        try:
                            price = opportunities.get(symbol, {}).get('price', 0)
                            if price > 0:
                                result = await mr.run_cycle(price, balance)
                                if result:
                                    logger.info(f"MeanRev {symbol}: cycle completed")
                        except Exception as e:
                            logger.error(f"MeanRev {symbol} error: {e}")

                    # 7. Check fills
                    try:
                        await self.execution.check_fills()
                    except Exception as e:
                        logger.error(f"Fill check error: {e}")

                    # 8. Status output
                    self.cycle_count += 1
                    if self.cycle_count % 10 == 0:
                        logger.info(f"Cycle {self.cycle_count} | "
                                     f"Grids={len(self.grid_mms)} | "
                                     f"Momentum={len(self.momentum_scalpers)} | "
                                     f"MeanRev={len(self.mean_reversions)}")

                    if time.time() - self.last_status >= 60:
                        await self._print_status(portfolio_data)
                        self.last_status = time.time()

                    # Sleep to next cycle
                    elapsed = time.time() - cycle_start
                    sleep_time = max(0.5, 3 - elapsed)
                    await asyncio.sleep(sleep_time)

                except Exception as e:
                    logger.error(f"Cycle error: {e}", exc_info=True)
                    await asyncio.sleep(5)

        except KeyboardInterrupt:
            logger.info("Shutdown requested")
        except Exception as e:
            logger.error(f"Trading loop error: {e}", exc_info=True)
        finally:
            await self.shutdown()

    async def _print_status(self, portfolio_data: dict):
        """Print system status."""
        risk_status = self.risk.get_status()
        perf = self.portfolio.get_performance()

        logger.info("=" * 60)
        logger.info(f"PORTFOLIO: {portfolio_data['total_eur']:.2f} EUR | "
                     f"Drawdown: {risk_status['drawdown']:.1%} | "
                     f"Trades: {risk_status['daily_trades']}")
        logger.info(f"PERFORMANCE: PnL={perf['total_profit']:.2f} | "
                     f"WR={perf['win_rate']:.0f}% | "
                     f"Uptime={perf['uptime_hours']:.1f}h")

        # Strategy status
        for symbol, mm in self.grid_mms.items():
            status = mm.get_status()
            logger.info(f"  Grid {symbol}: {status['buy_orders']}B/{status['sell_orders']}S | "
                         f"invested={status['total_invested']:.2f} | "
                         f"profit={status['total_profit']:.2f} | "
                         f"fills={status['fills']}")

        for symbol, scalper in self.momentum_scalpers.items():
            status = scalper.get_status()
            if status['in_position']:
                logger.info(f"  Momentum {symbol}: IN POSITION @ {status['entry_price']}")
            else:
                logger.info(f"  Momentum {symbol}: WAITING")

        for symbol, mr in self.mean_reversions.items():
            status = mr.get_status()
            if status['in_position']:
                logger.info(f"  MeanRev {symbol}: IN POSITION @ {status['entry_price']} (RSI={status['rsi_entry']:.0f})")
            else:
                logger.info(f"  MeanRev {symbol}: WAITING")

        logger.info("=" * 60)

        # Save status
        self._save_status(portfolio_data)

    def _save_status(self, portfolio_data: dict):
        """Save status to file."""
        try:
            os.makedirs(os.path.dirname(self._status_file), exist_ok=True)
            status = {
                'portfolio': portfolio_data,
                'risk': self.risk.get_status(),
                'performance': self.portfolio.get_performance(),
                'timestamp': time.time(),
            }
            with open(self._status_file, 'w') as f:
                json.dump(status, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save status: {e}")

    async def shutdown(self):
        """Graceful shutdown."""
        logger.info("Shutting down DENARO V2...")
        self.running = False

        # Cancel all open orders
        if self.execution:
            await self.execution.cancel_all_orders()

        # Close exchange
        if self.exchange:
            await self.exchange.close()

        logger.info("DENARO V2 stopped")


def main():
    """Entry point."""
    # Load .env
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env')
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

    system = DenaroV2()

    # Handle signals
    def signal_handler(sig, frame):
        logger.info(f"Signal {sig} received")
        system.running = False

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        asyncio.run(system.initialize())
        asyncio.run(system.run())
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
