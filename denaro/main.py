"""DENARO main — entry point. Starts WS, pairs, loops. Zero-touch orchestration.
Graceful shutdown, systemd health file, auto-recovery on errors."""

from __future__ import annotations
import asyncio
import logging
import os
import signal
import sys
import time
from typing import Optional

import aiohttp

from .config import Config, load_config
from .exchange import Exchange, WSClient
from .loop import HEALTH_FILE, TradingLoop
from .models import PairState
from .risk import CBState

log = logging.getLogger("denaro.main")


class DenaroApp:
    """Orchestrator — owns connections, loops, cleanup."""

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.exchange: Optional[Exchange] = None
        self.ws: Optional[WSClient] = None
        self.loops: list[TradingLoop] = []
        self._running = True

    # ── Startup ───────────────────────────────────────────────────────

    async def start(self) -> None:
        log.info("┌─ DENARO v3 ──────────────────────────────")
        log.info("│ Pairs: %s", self.cfg.pairs)
        log.info("│ Capital: %.2f USDC", self.cfg.total_capital)
        log.info("│ Dry-run: %s | Shadow-mode: %s",
                 self.cfg.dry_run, self.cfg.shadow_mode)
        log.info("├──────────────────────────────────────────")

        # 1. Exchange + WS
        self.exchange = Exchange(self.cfg)
        await self.exchange.start()
        log.info("│ Exchange connected")

        self.ws = WSClient(self.exchange)
        await self.ws.start(self.cfg.pairs)
        log.info("│ WebSocket subscribed")

        # 2. Wait for WS prices (bootstrap, up to 30s)
        log.info("│ Waiting for WS price feed...")
        await self._wait_for_prices(timeout=30)
        log.info("│ All prices received")

        # 3. Create pair states
        initial_capital = self.cfg.total_capital / max(len(self.cfg.pairs), 1)
        states = []
        for pair in self.cfg.pairs:
            state = PairState(symbol=pair, pair_capital=initial_capital)
            states.append(state)
            log.info("│   %s → %.2f USDC initial", pair, initial_capital)

        # 4. Balance fetch
        try:
            bal = await self.exchange.balance()
            for state in states:
                base = state.symbol.split("/")[0]
                quote = state.symbol.split("/")[1]
                b = bal.get(base, {})
                q = bal.get(quote, {})
                state.free_base = float(b.get("free", 0.0))
                state.free_quote = float(q.get("free", 0.0))
                state.locked_base = float(b.get("locked", 0.0))
                state.locked_quote = float(q.get("locked", 0.0))
                eq = state.total_equity
                if eq > 0:
                    state.pair_capital = eq
                    log.info("│   %s: equity=%.2f USDC", state.symbol, eq)
        except Exception as e:
            log.warning("Initial balance fetch: %s", e)

        # 5. Set initial peak equities
        for state in states:
            eq = state.total_equity
            if eq > 0:
                state.peak_equity = eq
                state.perf.peak_capital = self.cfg.total_capital

        log.info("├──────────────────────────────────────────")

        # 6. Trading loops
        self.loops = [
            TradingLoop(pair, self.cfg, self.exchange, self.ws, state)
            for pair, state in zip(self.cfg.pairs, states)
        ]

        tasks = [loop.run() for loop in self.loops]
        log.info("│ %d loops started │", len(tasks))

        # 7. Status print loop
        async def _status_loop():
            while self._running:
                await asyncio.sleep(10)
                if self.loops:
                    self._print_summary()
                    self._write_health()

        tasks.append(_status_loop())

        log.info("└──────────────────────────────────────────")

        # 8. Signal handling
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))

        # Run concurrently
        await asyncio.gather(*tasks, return_exceptions=True)

    async def stop(self) -> None:
        """Graceful shutdown."""
        log.info("Shutting down...")
        self._running = False
        for loop in self.loops:
            loop.stop()
        if self.ws:
            await self.ws.stop()
        if self.exchange:
            await self.exchange.close()
        try:
            os.remove(HEALTH_FILE)
        except OSError:
            pass
        log.info("Shutdown complete")

    # ── Helpers ───────────────────────────────────────────────────────

    async def _wait_for_prices(self, timeout: int = 30) -> None:
        """Wait until all pairs have a price from WS, or timeout."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            all_have = True
            for pair in self.cfg.pairs:
                p = self.ws.get_price(pair) if self.ws else 0.0
                if p <= 0:
                    all_have = False
                    break
            if all_have:
                return
            await asyncio.sleep(0.5)
        log.warning("WS price timeout after %ds — some prices may be stale", timeout)

    def _print_summary(self) -> None:
        """Pretty-print pair status."""
        if not self.loops:
            return

        total_cap = 0.0
        total_peak = 0.0

        log.info("")
        log.info("=== DENARO STATUS ===")

        for l in self.loops:
            s = l.state
            dd = 0.0
            if s.peak_equity > 0:
                dd = (s.peak_equity - s.total_equity) / s.peak_equity * 100

            pair_str = (
                f"    {s.symbol:>10s} | "
                f"Price={s.last_price:<10.6f} | "
                f"Grid={s.grid_active_orders}o | "
                f"CB={s.cb_state.value} | "
                f"DD={dd:.1f}% | "
                f"Trades={s.perf.total_trades}d"
            )
            log.info("%s", pair_str)

            total_cap += s.total_equity if s.total_equity > 0 else s.pair_capital
            total_peak += s.peak_equity if s.peak_equity > 0 else s.pair_capital

        risk = self.cfg.risk
        total_dd = total_cap / max(total_peak, 1) * 100
        log.info("  TOTAL: %.2f USDC | DD=%.1f%% | "
                 "GlobalCB=%s | Kelly=%.1f%%",
                 total_cap, 100 - total_dd,
                 "STOPPED" if risk._global_stopped else "OK",
                 risk.kelly_size * 100)
        log.info("====================")

    def _write_health(self) -> None:
        try:
            with open(HEALTH_FILE, "w") as f:
                f.write(f"{time.time():.1f}\n")
        except OSError:
            pass


# ── Entry Point ────────────────────────────────────────────────────────

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )
    # Less verbose for noisy modules
    logging.getLogger("denaro.exchange").setLevel(logging.WARNING)
    logging.getLogger("denaro.feeder").setLevel(logging.WARNING)
    logging.getLogger("denaro.grid").setLevel(logging.INFO)

    try:
        cfg = load_config()
    except Exception as e:
        log.critical("Config load failed: %s", e)
        sys.exit(1)

    if not cfg.api_key or not cfg.api_secret:
        log.critical("Missing API keys — set BINANCE_API_KEY and BINANCE_API_SECRET in .env")
        sys.exit(1)

    app = DenaroApp(cfg)

    try:
        asyncio.run(app.start())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        log.critical("Fatal: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
