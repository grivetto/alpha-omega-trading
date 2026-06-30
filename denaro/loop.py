"""DENARO Trading Loop — per-pair async cycle. Adaptive, self-healing, compounding.

Flow per cycle:
1. Feed: WS price + depth → state
2. Risk: per-pair CB check
3. Balance refresh (every 30s)
4. Grid sync (deploy / re-deploy)
5. Scalp tick
6. Update capital (RiskManager)
7. Health write
8. Performance log"""

from __future__ import annotations
import asyncio
import logging
import os
import time
from typing import Optional

from .config import Config
from .exchange import Exchange
from .feeder import Feeder
from .grid import GridEngine
from .models import CBState, PairState
from .risk import RiskManager
from .scalper import ScalpEngine

log = logging.getLogger("denaro.loop")

HEALTH_FILE = "/tmp/denaro.health"

PERF_LOG_INTERVAL = 60  # Log perf summary every N cycles


class TradingLoop:
    """One trading loop per pair. Runs indefinitely."""

    def __init__(self, pair: str, cfg: Config,
                 exchange: Exchange, ws, state: PairState) -> None:
        self.pair = pair
        self.cfg = cfg
        self.exchange = exchange
        self.ws = ws
        self.state = state
        self.num_pairs = len(cfg.pairs)

        self.feeder = Feeder(ws, state)
        self.grid = GridEngine(exchange, cfg.grid, cfg)
        self.scalper = ScalpEngine(exchange, ws, cfg)
        self.risk = cfg.risk

        self._cycle_count = 0
        self._last_balance_refresh = 0.0
        self._last_health_write = 0.0
        self._last_perf_log = 0.0
        self._running = True

    # ── Main Run ──────────────────────────────────────────────────────

    async def run(self) -> None:
        """One cycle. Called in a while True with asyncio.sleep."""
        if not self._running:
            return

        self._cycle_count += 1

        try:
            # 1. Feed: update WS data
            self.feeder.update()
            state = self.state

            # 2. Risk check
            state = self.risk.check(state)
            if self.risk.is_global_stopped:
                log.critical("[%s] GLOBAL STOP — all trading halted", self.pair)
                os._exit(1)

            # 3. Balance refresh (every 30s)
            now = time.time()
            if now - self._last_balance_refresh > self.cfg.balance_interval:
                await self._refresh_balance()
                self._last_balance_refresh = now

            # 4. Grid sync
            if state.cb_state != CBState.OPEN:
                state = await self.grid.sync(state)
                # Update state reference if grid returned new
                self.state = state

            # 5. Scalp tick
            if state.cb_state not in (CBState.OPEN, CBState.GLOBAL_STOP):
                state = await self.scalper.tick(state)
                self.state = state

            # 6. Update capital (RiskManager)
            self.risk.update_capital({self.pair: state})

            # 7. Health write (every 5s)
            if now - self._last_health_write > self.cfg.health_interval:
                self._write_health()
                self._last_health_write = now

            # 8. Performance log
            if self._cycle_count % max(self.cfg.perf_log_interval, 10) == 0:
                self._log_performance(state)

        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("[%s] Fatal loop error", self.pair)
            await asyncio.sleep(2)

    def stop(self) -> None:
        self._running = False

    # ── Balance ───────────────────────────────────────────────────────

    async def _refresh_balance(self) -> None:
        try:
            bal = await self.exchange.balance()
        except Exception as e:
            log.warning("[%s] Balance fetch: %s", self.pair, e)
            return

        base = self.pair.split("/")[0]
        quote = self.pair.split("/")[1]

        self.state.free_base = float(bal.get(base, {}).get("free", 0.0))
        self.state.free_quote = float(bal.get(quote, {}).get("free", 0.0))
        self.state.locked_base = float(bal.get(base, {}).get("locked", 0.0))
        self.state.locked_quote = float(bal.get(quote, {}).get("locked", 0.0))

    # ── Health ────────────────────────────────────────────────────────

    def _write_health(self) -> None:
        try:
            with open(HEALTH_FILE, "w") as f:
                f.write(f"{time.time():.1f}\n")
        except OSError:
            pass

    # ── Performance ───────────────────────────────────────────────────

    def _log_performance(self, state: PairState) -> None:
        dd = 0.0
        if state.peak_equity > 0:
            dd = (state.peak_equity - state.total_equity) / state.peak_equity * 100

        log.info(
            "=== [%s] CYCLE %d === Price=%.6f "
            "| Grid=%d orders | CB=%s "
            "| DD=%.1f%% | CAPITAL=%.2f | Peak=%.2f "
            "| DailyPnL=%.2f | TotalPnL=%.2f "
            "| ATR=%.3f%% | WinRate=%.0f%% "
            "| ConsLoss=%d | SizeMult=%.2f",
            self.pair, self._cycle_count, state.last_price,
            state.grid_active_orders, state.cb_state.value,
            dd, state.total_equity, state.peak_equity,
            state.perf.daily_pnl, state.perf.total_pnl,
            state.adaptive.atr_pct * 100,
            state.perf.win_rate * 100,
            state.perf.consecutive_losses,
            state.adaptive.sizing_multiplier,
        )
