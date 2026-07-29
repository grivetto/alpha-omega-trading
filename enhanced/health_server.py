#!/usr/bin/env python3
"""
Health check HTTP server for Denaro bots.
Serves /health endpoint for Zabbix/nginx monitoring.
Supports both in-memory bot_ref and file-based state fallback.
"""
import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional
from aiohttp import web

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("health_server")


class HealthServer:
    def __init__(self, port: int = 8909, bot_ref=None, state_path: Optional[str] = None):
        self.port = port
        self.bot_ref = bot_ref
        self.state_path = Path(state_path) if state_path else None
        self.app = web.Application()
        self.app.router.add_get("/health", self.health_handler)
        self.app.router.add_get("/metrics", self.metrics_handler)
        self.runner = None

    def _read_state_from_file(self) -> Optional[dict]:
        """Read bot state from JSON file (fallback when no bot_ref)."""
        if not self.state_path or not self.state_path.exists():
            return None
        try:
            with open(self.state_path) as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError, PermissionError) as e:
            logger.warning(f"Could not read state file {self.state_path}: {e}")
            return None

    def _extract_metrics(self, state: dict) -> tuple:
        """Extract (cb_status, equity, dd, total_trades, win_rate) from state dict."""
        cb_data = state.get("cb", {})
        cb_status = cb_data.get("state", "UNKNOWN")
        equity = state.get("current_capital", 0.0)
        peak = state.get("peak_capital", 0.0)
        dd = ((peak - equity) / peak * 100) if peak > 0 else 0.0
        perf = state.get("perf", {})
        total_trades = perf.get("total_trades", 0)
        win_rate = perf.get("win_rate", 0.0)
        return cb_status, equity, dd, total_trades, win_rate

    async def health_handler(self, request: web.Request) -> web.Response:
        """Health endpoint - returns bot status."""
        try:
            # Priority 1: in-memory bot_ref
            if self.bot_ref and hasattr(self.bot_ref, "state"):
                state = self.bot_ref.state
                cb_state = getattr(state, "cb", None)
                cb_status = cb_state.state.value if cb_state else "UNKNOWN"
                equity = getattr(state, "current_capital", 0.0)
                peak = getattr(state, "peak_capital", 0.0)
                dd = ((peak - equity) / peak * 100) if peak > 0 else 0.0
                trades = getattr(state, "perf", None)
                total_trades = trades.total_trades if trades else 0
            # Priority 2: file-based fallback
            else:
                file_state = self._read_state_from_file()
                if file_state:
                    cb_status, equity, dd, total_trades, _ = self._extract_metrics(file_state)
                else:
                    cb_status = "NO_BOT_REF"
                    equity = 0.0
                    dd = 0.0
                    total_trades = 0

            health = {
                "status": "healthy" if cb_status != "OPEN" else "circuit_breaker_open",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "circuit_breaker": cb_status,
                "equity": round(equity, 2),
                "drawdown_pct": round(dd, 2),
                "total_trades": total_trades,
                "port": self.port,
            }
            return web.json_response(health)
        except Exception as e:
            logger.error(f"Health check error: {e}")
            return web.json_response(
                {"status": "error", "error": str(e), "timestamp": datetime.utcnow().isoformat() + "Z"},
                status=500,
            )

    async def metrics_handler(self, request: web.Request) -> web.Response:
        """Prometheus-style metrics endpoint."""
        try:
            if self.bot_ref and hasattr(self.bot_ref, "state"):
                state = self.bot_ref.state
                equity = getattr(state, "current_capital", 0.0)
                peak = getattr(state, "peak_capital", 0.0)
                dd = ((peak - equity) / peak * 100) if peak > 0 else 0.0
                trades = getattr(state, "perf", None)
                total_trades = trades.total_trades if trades else 0
                win_rate = trades.win_rate if trades else 0.0
            else:
                file_state = self._read_state_from_file()
                if file_state:
                    _, equity, dd, total_trades, win_rate = self._extract_metrics(file_state)
                else:
                    equity = 0.0
                    dd = 0.0
                    total_trades = 0
                    win_rate = 0.0

            metrics = f"""# HELP denaro_equity Current equity in USDT
# TYPE denaro_equity gauge
denaro_equity {equity:.2f}
# HELP denaro_drawdown_pct Current drawdown percentage
# TYPE denaro_drawdown_pct gauge
denaro_drawdown_pct {dd:.2f}
# HELP denaro_total_trades Total number of trades
# TYPE denaro_total_trades counter
denaro_total_trades {total_trades}
# HELP denaro_win_rate Win rate
# TYPE denaro_win_rate gauge
denaro_win_rate {win_rate:.4f}
"""
            return web.Response(text=metrics, content_type="text/plain")
        except Exception as e:
            logger.error(f"Metrics error: {e}")
            return web.Response(text=f"# Error: {e}", status=500)

    async def start(self):
        """Start the health server."""
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "0.0.0.0", self.port)
        await site.start()
        logger.info(f"Health server started on port {self.port}")

    async def stop(self):
        """Stop the health server."""
        if self.runner:
            await self.runner.cleanup()
            logger.info("Health server stopped")


async def run_health_server(port: int = 8909, bot_ref=None, state_path: str = None):
    """Standalone runner for health server."""
    server = HealthServer(port, bot_ref, state_path)
    await server.start()
    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        await server.stop()


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8909
    state_path = sys.argv[2] if len(sys.argv) > 2 else None
    asyncio.run(run_health_server(port, state_path=state_path))