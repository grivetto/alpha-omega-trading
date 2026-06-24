"""Denaro v3 Main — Multi-machine grid trading engine.

One loop per machine. Leader election for shared pairs.
Each machine can run its own local pair + compete for the primary pair.

Usage:
    MACHINE_ID=mc2 BINANCE_API_KEY=xxx BINANCE_API_SECRET=yyy python -m denaro_v3.main
"""

import asyncio
import os
import signal
import socket
import sys
import time
from typing import Optional

import ccxt
from loguru import logger

from .config import GridConfig, PRODUCTION
from .data_feeder import DataFeeder
from .circuit_breaker import CircuitBreaker
from .grid_engine import GridEngine
from .leader_election import LeaderElection
from .websocket_client import WebSocketClient, EventType

# ── Logging ────────────────────────────────────────────────
logger.remove()
logger.add(sys.stderr, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
           level="INFO", colorize=True)


# ── Per-machine pair configuration ─────────────────────────
# (machine_id) -> list of (pair, is_shared)
# Shared pairs use leader election (only 1 instance trades them).
# Local pairs are exclusive to that machine.
MACHINE_PAIRS = {
    "mc2":      [("SOL/USDC", False)],
    "nuvola":   [("DOGE/USDC", False)],
    "marcodg1": [("ADA/USDC", False)],
}


class DenaroV3:
    """Trading engine for one machine. Can manage multiple pairs."""

    def __init__(self, machine_id: str):
        self._machine = machine_id
        self._exchange = None
        self._feeder = None
        self._breaker = None
        self._engines: dict[str, GridEngine] = {}
        self._leaders: dict[str, LeaderElection] = {}
        self._ws_client: Optional[WebSocketClient] = None
        self._running = False
        self._start_time = 0.0

    def _init_exchange(self):
        key = os.environ.get("BINANCE_API_KEY", "").strip()
        sec = os.environ.get("BINANCE_API_SECRET", "").strip()
        if not key or not sec:
            logger.critical("BINANCE_API_KEY and BINANCE_API_SECRET required")
            sys.exit(1)
        self._exchange = ccxt.binance({
            "apiKey": key, "secret": sec,
            "enableRateLimit": True,
            "options": {"defaultType": "spot"},
        })
        logger.info(f"Exchange connected | machine={self._machine}")

    def _init_modules(self):
        self._feeder = DataFeeder(self._exchange, PRODUCTION.api)
        self._breaker = CircuitBreaker(PRODUCTION.risk)

        pairs = MACHINE_PAIRS.get(self._machine, [])
        pair_list = []
        for pair, is_shared in pairs:
            base, quote = pair.split("/")
            cfg = GridConfig(symbol=pair, base_asset=base, quote_asset=quote)
            self._engines[pair] = GridEngine(cfg, self._feeder, self._breaker)
            if is_shared:
                self._leaders[pair] = LeaderElection(self._machine, pair)
            pair_list.append(pair)
            logger.info(f"Pair configured: {pair} | shared={is_shared}")

        if not self._engines:
            logger.critical(f"No pairs configured for machine={self._machine}")
            sys.exit(1)

        # Initialize WebSocket client
        self._ws_client = WebSocketClient(self._exchange, pair_list)

    async def _loop(self):
        self._running = True
        self._start_time = time.time()
        logger.info(f"Denaro v3 started | machine={self._machine} | "
                     f"pairs={list(self._engines.keys())}")

        # Start WebSocket streams (real-time price + fills)
        if self._ws_client:
            await self._ws_client.start()
            logger.info("WebSocket streams active — latency < 1s")

        # Initialize equity tracking BEFORE grid setup (needed by CircuitBreaker.can_trade)
        quote = "USDC"
        total = self._feeder.get_total_balance(quote)
        for pair, engine in self._engines.items():
            base = pair.split("/")[0]
            base_qty = self._feeder.get_total_balance(base)
            ticker = self._feeder.get_ticker(pair)
            if ticker and ticker.get("last", 0) > 0:
                total += base_qty * ticker["last"]
        self._breaker.update_equity(total)

        # Initial grid setup for each pair
        for pair, engine in self._engines.items():
            leader = self._leaders.get(pair)
            if leader and not leader.try_acquire():
                logger.info(f"Skipping {pair} — not leader (leader={leader.get_current_leader()})")
                continue
            engine.reset_grid()

        cycle = 0
        while self._running:
            cycle += 1
            loop_start = time.time()

            try:
                # ── Process WebSocket events (real-time) ──
                if self._ws_client:
                    ws_events = await self._ws_client.drain_events()
                    for event in ws_events:
                        if event.type == EventType.TICKER:
                            symbol = event.data.get("symbol", "")
                            pair = symbol  # Use raw symbol from WS
                            self._feeder.inject_ws_ticker(pair, event.data)
                        elif event.type == EventType.FILL:
                            # Forward to all engines (each filters by symbol)
                            for engine in self._engines.values():
                                engine.on_ws_fill(event.data)

                # Update equity once per cycle — include ALL assets, not just USDC
                quote = "USDC"
                total = self._feeder.get_total_balance(quote)
                for pair, engine in self._engines.items():
                    base = pair.split("/")[0]
                    base_qty = self._feeder.get_total_balance(base)
                    ticker = self._feeder.get_ticker(pair)
                    if ticker and ticker.get("last", 0) > 0:
                        total += base_qty * ticker["last"]
                self._breaker.update_equity(total)

                # Process each pair
                for pair, engine in self._engines.items():
                    leader = self._leaders.get(pair)

                    # Leader election check
                    if leader:
                        if not leader.is_leader:
                            if leader.try_acquire():
                                logger.info(f"Acquired leadership for {pair} — initializing grid")
                                engine.reset_grid()
                            else:
                                continue  # Skip — not leader
                        leader.heartbeat()

                    # Sync orders
                    if self._breaker.state != CircuitBreaker.STATE_OPEN:
                        engine.sync_orders()

                    # Reset dead grid
                    if engine.needs_reset():
                        logger.warning(f"[{pair}] Grid has no active levels — resetting")
                        engine.reset_grid()

                # Status log every 10 cycles
                if cycle % 10 == 0:
                    breaker_summary = self._breaker.summary()
                    parts = [f"Cycle {cycle}", f"Equity=${breaker_summary['equity']:.2f}",
                             f"CB={breaker_summary['state']}", f"PnL=${breaker_summary['total_pnl']:.2f}"]
                    for pair, engine in self._engines.items():
                        gs = engine.summary()
                        leader_info = ""
                        if pair in self._leaders:
                            leader = self._leaders[pair]
                            leader_info = f" [{'L' if leader.is_leader else 'S'}]"
                        parts.append(f"{pair}={gs['active_buys']}B/{gs['active_sells']}S{leader_info}")
                    logger.info(" | ".join(parts))

            except Exception as e:
                logger.error(f"Loop error (cycle {cycle}): {e}")

            # Sleep responsive to shutdown
            elapsed = time.time() - loop_start
            sleep_time = max(1, PRODUCTION.api.loop_interval - elapsed)
            for _ in range(int(sleep_time)):
                if not self._running:
                    break
                await asyncio.sleep(1)

    async def stop(self):
        logger.info(f"Shutting down Denaro v3 [{self._machine}]...")
        self._running = False
        for leader in self._leaders.values():
            if leader.is_leader:
                leader.release()
        if self._ws_client:
            await self._ws_client.stop()
        self._breaker._save_state()
        uptime = time.time() - self._start_time
        logger.info(f"Stopped | uptime={uptime:.0f}s | pnl=${self._breaker.total_pnl:.2f}")


async def main():
    machine_id = os.environ.get("MACHINE_ID", socket.gethostname().split(".")[0].lower())
    if machine_id not in MACHINE_PAIRS:
        logger.error(f"Unknown MACHINE_ID={machine_id}. Known: {list(MACHINE_PAIRS.keys())}")
        # Fallback: guess from hostname
        if "mc2" in machine_id:
            machine_id = "mc2"
        elif "nuvola" in machine_id:
            machine_id = "nuvola"
        elif "marcodg1" in machine_id.lower():
            machine_id = "marcodg1"
        else:
            logger.critical("Cannot determine machine role")
            sys.exit(1)

    app = DenaroV3(machine_id)
    logger.info("Denaro v3 — Starting...")
    app._init_exchange()
    app._init_modules()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(app.stop()))
        except NotImplementedError:
            pass  # Windows doesn't support add_signal_handler

    try:
        await app._loop()
    except KeyboardInterrupt:
        await app.stop()
    except Exception as e:
        logger.critical(f"Fatal: {e}")
        await app.stop()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
