"""Denaro v3 Main — Single-process grid trading engine.

One loop. One strategy. One machine. Full capital. No bullshit.

Usage:
    BINANCE_API_KEY=xxx BINANCE_API_SECRET=yyy python -m denaro_v3.main
"""

import asyncio
import os
import signal
import sys
import time
from datetime import datetime, timezone

import ccxt
from loguru import logger

from .config import Config, PRODUCTION
from .data_feeder import DataFeeder
from .circuit_breaker import CircuitBreaker
from .grid_engine import GridEngine

# ── Logging Setup ──────────────────────────────────────────
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    level="INFO",
    colorize=True,
)


class DenaroV3:
    """Main application. Single responsibility: run the grid trading loop."""

    def __init__(self, config: Config = PRODUCTION):
        self._config = config
        self._exchange = None
        self._feeder = None
        self._breaker = None
        self._engine = None
        self._running = False
        self._start_time = 0.0

    def _init_exchange(self):
        """Initialize ccxt exchange connection."""
        api_key = os.environ.get("BINANCE_API_KEY", "").strip()
        api_secret = os.environ.get("BINANCE_API_SECRET", "").strip()

        if not api_key or not api_secret:
            logger.critical("BINANCE_API_KEY and BINANCE_API_SECRET must be set")
            sys.exit(1)

        self._exchange = ccxt.binance({
            "apiKey": api_key,
            "secret": api_secret,
            "enableRateLimit": True,
            "options": {"defaultType": "spot"},
        })
        logger.info(f"Connected to Binance | pair={self._config.grid.symbol}")

    def _init_modules(self):
        """Initialize all sub-modules."""
        self._feeder = DataFeeder(self._exchange, self._config.api)
        self._breaker = CircuitBreaker(self._config.risk)
        self._engine = GridEngine(self._config.grid, self._feeder, self._breaker)

    async def _loop(self):
        """Main trading loop. Runs every loop_interval seconds."""
        self._running = True
        self._start_time = time.time()

        logger.info(f"Denaro v3 started | {self._config.grid.symbol} | "
                     f"levels={self._config.grid.levels} | "
                     f"spacing={self._config.grid.spacing_pct}%")

        # Initial grid setup
        self._engine.reset_grid()

        cycle = 0
        while self._running:
            cycle += 1
            loop_start = time.time()

            try:
                # 1. Update equity tracker
                quote = self._config.grid.quote_asset
                total = self._feeder.get_total_balance(quote)
                self._breaker.update_equity(total)

                # 2. Log status every 10 cycles
                if cycle % 10 == 0:
                    breaker_summary = self._breaker.summary()
                    grid_summary = self._engine.summary()
                    logger.info(
                        f"Cycle {cycle} | "
                        f"Equity=${breaker_summary['equity']:.2f} | "
                        f"CB={breaker_summary['state']} | "
                        f"PnL=${breaker_summary['total_pnl']:.2f} | "
                        f"Grid={grid_summary['active_buys']}B/{grid_summary['active_sells']}S"
                    )

                # 3. Sync orders (detect fills, place new)
                if not self._breaker.state == self._breaker.STATE_OPEN:
                    self._engine.sync_orders()

                # 4. Reset grid if dead
                if self._engine.needs_reset():
                    logger.warning("Grid has no active levels — resetting")
                    self._engine.reset_grid()

            except Exception as e:
                logger.error(f"Loop error (cycle {cycle}): {e}")
                # Don't crash the loop — continue next cycle

            # 5. Sleep until next cycle
            elapsed = time.time() - loop_start
            sleep_time = max(1, self._config.api.loop_interval - elapsed)
            await asyncio.sleep(sleep_time)

    def stop(self):
        """Graceful shutdown."""
        logger.info("Shutting down Denaro v3...")
        self._running = False
        self._breaker._save_state()
        uptime = time.time() - self._start_time
        logger.info(f"Denaro v3 stopped | uptime={uptime:.0f}s | "
                     f"total_pnl=${self._breaker.total_pnl:.2f} | "
                     f"trades={self._feeder.trade_count}")


async def main():
    """Entry point with signal handling."""
    app = DenaroV3()

    # Initialize
    logger.info("Denaro v3 — Starting...")
    app._init_exchange()
    app._init_modules()

    # Signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, app.stop)

    try:
        await app._loop()
    except KeyboardInterrupt:
        app.stop()
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
        app.stop()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
