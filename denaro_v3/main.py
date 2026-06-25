'''Denaro v3 Main – Multi‑machine grid engine with audit fixes.

Fixes applied:
- Accurate equity calculation across all assets.
- Circuit‑breaker size‑reduction respected in order placement.
- Graceful shutdown and leader release.
- WebSocket client uses async HTTP for listen‑key.
- DataFeeder cache invalidates ticker on trade.
- Zero‑price guard and robust rounding.
'''

import asyncio, os, signal, socket, sys, time
from typing import Optional

import ccxt
from loguru import logger

from config import GridConfig, PRODUCTION
from data_feeder import DataFeeder
from circuit_breaker import CircuitBreaker
from grid_engine import GridEngine
from leader_election import LeaderElection
from websocket_client import WebSocketClient, EventType

logger.remove()
logger.add(sys.stderr, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>", level="INFO", colorize=True)

MACHINE_PAIRS = {
    "mc2": [("SOL/USDC", False)],
    "nuvola": [("DOGE/USDC", False)],
    "marcodg1": [("ADA/USDC", False)],
}

class DenaroV3:
    """Engine for a single machine handling multiple pairs."""

    def __init__(self, machine_id: str):
        self._machine = machine_id
        self._exchange = None
        self._feeder: Optional[DataFeeder] = None
        self._breaker: Optional[CircuitBreaker] = None
        self._engines: dict[str, GridEngine] = {}
        self._leaders: dict[str, LeaderElection] = {}
        self._ws_client: Optional[WebSocketClient] = None
        self._running = False
        self._start_time = 0.0

    def _init_exchange(self):
        key = os.getenv("BINANCE_API_KEY", "").strip()
        secret = os.getenv("BINANCE_API_SECRET", "").strip()
        if not key or not secret:
            logger.critical("BINANCE_API_KEY and BINANCE_API_SECRET required")
            sys.exit(1)
        self._exchange = ccxt.binance({"apiKey": key, "secret": secret, "enableRateLimit": True, "options": {"defaultType": "spot"}})
        logger.info(f"Exchange connected | machine={self._machine}")

    def _init_modules(self):
        self._feeder = DataFeeder(self._exchange, PRODUCTION.api)
        self._breaker = CircuitBreaker(PRODUCTION.risk)
        pairs_cfg = MACHINE_PAIRS.get(self._machine, [])
        pair_list = []
        for pair, shared in pairs_cfg:
            base, quote = pair.split('/')
            cfg = GridConfig(symbol=pair, base_asset=base, quote_asset=quote)
            self._engines[pair] = GridEngine(cfg, self._feeder, self._breaker)
            if shared:
                self._leaders[pair] = LeaderElection(self._machine, pair)
            pair_list.append(pair)
            logger.info(f"Pair configured: {pair} | shared={shared}")
        if not self._engines:
            logger.critical(f"No pairs for machine={self._machine}")
            sys.exit(1)
        self._ws_client = WebSocketClient(self._exchange, pair_list)

    async def _total_equity(self) -> float:
        balances = self._feeder.get_balance()
        totals = balances.get('total', {}) or balances.get('free', {})
        total = 0.0
        for asset, amount in totals.items():
            if not amount:
                continue
            if asset.upper() == 'USDC':
                total += amount
            else:
                try:
                    ticker = self._feeder.get_ticker(f"{asset}/USDC")
                    price = ticker.get('last') if ticker else 0
                    if price and price > 0:
                        total += amount * price
                except Exception:
                    pass
        return total or 0.1  # Never return zero to avoid division errors

    async def _loop(self):
        self._running = True
        self._start_time = time.time()
        logger.info(f"Denaro v3 started | machine={self._machine} | pairs={list(self._engines)}")
        if self._ws_client:
            # Start WS in background — don't block the main loop
            asyncio.create_task(self._ws_client.start())
            await asyncio.sleep(2)  # Let WS init its first attempt
        equity = await self._total_equity()
        self._breaker.update_equity(equity)
        for pair, engine in self._engines.items():
            leader = self._leaders.get(pair)
            if leader and not leader.try_acquire():
                continue
            engine.reset_grid()
        cycle = 0
        while self._running:
            cycle += 1
            start = time.time()
            try:
                if self._ws_client:
                    events = await self._ws_client.drain_events()
                    for ev in events:
                        if ev.type == EventType.TICKER:
                            self._feeder.inject_ws_ticker(ev.data['symbol'], ev.data)
                        elif ev.type == EventType.FILL:
                            self._feeder.on_trade_executed()
                            for eng in self._engines.values():
                                eng.on_ws_fill(ev.data)
                equity = await self._total_equity()
                self._breaker.update_equity(equity)
                for pair, engine in self._engines.items():
                    leader = self._leaders.get(pair)
                    if leader:
                        if not leader.is_leader:
                            if leader.try_acquire():
                                logger.info(f"Acquired leadership for {pair}")
                                engine.reset_grid()
                            else:
                                continue
                        leader.heartbeat()
                    if self._breaker.state != CircuitBreaker.STATE_OPEN:
                        engine.sync_orders()
                    if engine.needs_reset():
                        logger.warning(f"[{pair}] Grid empty – resetting")
                        engine.reset_grid()
                if cycle % 10 == 0:
                    s = self._breaker.summary()
                    parts = [f"Cycle {cycle}", f"Equity=${s['equity']:.2f}", f"CB={s['state']}", f"PnL=${s['total_pnl']:.2f}"]
                    for p, e in self._engines.items():
                        gs = e.summary()
                        flag = "[L]" if p in self._leaders and self._leaders[p].is_leader else "[S]" if p in self._leaders else ""
                        parts.append(f"{p}={gs['active_buys']}B/{gs['active_sells']}S{flag}")
                    logger.info(" | ".join(parts))
            except Exception as exc:
                logger.error(f"Loop error (cycle {cycle}): {exc}")
            elapsed = time.time() - start
            sleep = max(1, PRODUCTION.api.loop_interval - elapsed)
            for _ in range(int(sleep)):
                if not self._running:
                    break
                await asyncio.sleep(1)

    async def stop(self):
        logger.info(f"Shutting down Denaro v3 [{self._machine}]…")
        self._running = False
        for leader in self._leaders.values():
            if leader.is_leader:
                leader.release()
        if self._ws_client:
            await self._ws_client.stop()
        if self._breaker:
            self._breaker._save_state()
        uptime = time.time() - self._start_time
        logger.info(f"Stopped | uptime={uptime:.0f}s | pnl=${self._breaker.total_pnl:.2f}")

async def main():
    machine = os.getenv("MACHINE_ID", socket.gethostname().split('.')[0].lower())
    if machine not in MACHINE_PAIRS:
        logger.error(f"Unknown MACHINE_ID={machine}")
        sys.exit(1)
    app = DenaroV3(machine)
    app._init_exchange()
    app._init_modules()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(app.stop()))
        except NotImplementedError:
            pass
    try:
        await app._loop()
    except Exception as e:
        logger.critical(f"Fatal: {e}")
        await app.stop()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())