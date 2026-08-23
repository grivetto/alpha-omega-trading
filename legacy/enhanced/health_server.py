#!/usr/bin/env python3
"""
HEALTH SERVER --- Lightweight HTTP endpoint for systemd HEALTHCHECK / monitoring.

Uses stdlib http.server (zero extra dependencies).

Endpoints:
  GET /health      -> {"status":"ok|degraded|down", "version":"v2", ...}
  GET /metrics     -> Prometheus-style text dump (basic)
  GET /status      -> Human-readable HTML summary
  GET /ready       -> 200 if engine is healthy, 503 if not

Usage:
  server = HealthServer(port=8909)
  server.start()   # non-blocking daemon thread
  server.update(equity=100.5, cb_state="CLOSED", ...)
"""

from __future__ import annotations

import json
import logging
import os
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread, Lock
from typing import Any

log = logging.getLogger("kraken_v2")

# Shared state --- updated by main loop
_state: dict[str, Any] = {
    "status": "starting",
    "version": "v2",
    "symbol": "DOGE/EUR",
    "mode": "unknown",
    "equity": 0.0,
    "pnl_pct": 0.0,
    "grid_levels": 0,
    "max_levels": 5,
    "cb_state": "CLOSED",
    "kelly_pct": 0.0,
    "atr_pct": 0.0,
    "last_cycle_ts": 0.0,
    "last_cycle_ok": True,
    "uptime_sec": 0.0,
    "ws_connected": False,
    "error_count": 0,
    "started_at": time.time(),
}

_lock = Lock()


def _safe_update(**kwargs: Any) -> None:
    """Thread-safe state update."""
    with _lock:
        _state.update(kwargs)


class _Handler(BaseHTTPRequestHandler):
    """Minimal HTTP handler --- no deps."""

    def log_message(self, fmt: str, *args: Any) -> None:
        log.debug(f"health:{fmt % args}")

    def _send_json(self, data: dict, status: int = 200) -> None:
        body = json.dumps(data, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, text: str, status: int = 200) -> None:
        body = text.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        with _lock:
            s = dict(_state)

        # Auto-compute uptime from started_at
        s["uptime_sec"] = time.time() - s.get("started_at", time.time())
        s["started_at_iso"] = time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime(s.get("started_at", 0))
        )

        path = self.path.rstrip("/")

        if path == "/health":
            status_code = 200 if s["status"] in ("ok", "degraded") else 503
            self._send_json(s, status=status_code)

        elif path == "/ready":
            if s["status"] == "ok" and s["last_cycle_ok"]:
                self._send_text("ready\n", 200)
            else:
                self._send_text("not ready\n", 503)

        elif path == "/metrics":
            lines = [
                f"# HELP denaro_equity Current portfolio equity in EUR",
                f"# TYPE denaro_equity gauge",
                f"denaro_equity {s['equity']:.2f}",
                f"# HELP denaro_pnl_pct Total P&L percentage",
                f"# TYPE denaro_pnl_pct gauge",
                f"denaro_pnl_pct {s['pnl_pct']:.4f}",
                f"# HELP denaro_grid_levels Active grid levels",
                f"# TYPE denaro_grid_levels gauge",
                f"denaro_grid_levels {s['grid_levels']}",
                f"# HELP denaro_error_count Total error count",
                f"# TYPE denaro_error_count counter",
                f"denaro_error_count {s['error_count']}",
                f"# HELP denaro_kelly_pct Kelly fraction percent",
                f"# TYPE denaro_kelly_pct gauge",
                f"denaro_kelly_pct {s['kelly_pct']:.2f}",
                f"# HELP denaro_up_seconds Uptime in seconds",
                f"# TYPE denaro_up_seconds gauge",
                f"denaro_up_seconds {s['uptime_sec']:.0f}",
                f"# HELP denaro_cb_state Circuit breaker state "
                f"0=CLOSED 1=HALF 2=OPEN",
                f"# TYPE denaro_cb_state gauge",
                f"denaro_cb_state "
                f"{'0' if s['cb_state'] == 'CLOSED' else '1' if s['cb_state'] == 'HALF_OPEN' else '2'}",
                f"# HELP denaro_ws_connected WebSocket connected",
                f"# TYPE denaro_ws_connected gauge",
                f"denaro_ws_connected "
                f"{'1' if s['ws_connected'] else '0'}",
            ]
            self._send_text("\n".join(lines) + "\n")

        elif path == "/status":
            uptime = s.get("uptime_sec", 0)
            days = int(uptime // 86400)
            hours = int((uptime % 86400) // 3600)
            mins = int((uptime % 3600) // 60)
            _cb_class = ("ok" if s["cb_state"] == "CLOSED"
                         else "warn" if s["cb_state"] == "HALF_OPEN"
                         else "err")
            html = (
                "<!DOCTYPE html>\n<html><head>"
                "<title>Denaro Health</title>"
                "<meta charset=\"utf-8\">"
                "<style>"
                "body{font-family:monospace;margin:2em}"
                ".ok{color:green}.warn{color:orange}.err{color:red}"
                "pre{background:#f5f5f5;padding:1em;border-radius:4px}"
                "</style></head><body>"
                "<h1>Denaro <small>Kraken Grid v2</small></h1><pre>\n"
                f"Status:      <b class=\"{'ok' if s['status']=='ok' else 'warn' if s['status']=='degraded' else 'err'}\">{s['status']}</b>\n"
                f"Symbol:      {s['symbol']}\n"
                f"Mode:        {s['mode']}\n"
                f"Equity:      EUR {s['equity']:.2f}\n"
                f"PnL:         {s['pnl_pct']:+.2f}%\n"
                f"Grid:        {s['grid_levels']}/{s['max_levels']}\n"
                f"CB:          <b class=\"{_cb_class}\">{s['cb_state']}</b>\n"
                f"Kelly:       {s['kelly_pct']:.0f}%\n"
                f"ATR:         {s['atr_pct']*100:.2f}%\n"
                f"WS:          {'connected' if s['ws_connected'] else 'disconnected'}\n"
                f"Errors:      {s['error_count']}\n"
                f"Uptime:      {days}d {hours}h {mins}m\n"
                f"Last cycle:  "
                f"{time.strftime('%H:%M:%S', time.localtime(s['last_cycle_ts'])) if s['last_cycle_ts'] else 'never'}\n"
                "</pre>"
                "<p><i>Denaro Kraken Grid v2 . enhanced/health_server.py</i></p>"
                "</body></html>"
            )
            self._send_text(html)

        else:
            self._send_json({"error": "not found", "path": self.path}, 404)


class HealthServer:
    """Lightweight health HTTP server in a daemon thread."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8909):
        self.host = host
        self.port = port
        self._server: HTTPServer | None = None
        self._thread: Thread | None = None

    def update(self, **kwargs: Any) -> None:
        """Thread-safe update of shared health state."""
        _safe_update(**kwargs)

    def set_ok(self) -> None:
        _safe_update(status="ok")

    def set_degraded(self, reason: str = "") -> None:
        _safe_update(status="degraded" if not reason else f"degraded:{reason}")

    def set_down(self, reason: str = "") -> None:
        _safe_update(status="down" if not reason else f"down:{reason}")

    def start(self) -> None:
        """Start HTTP server in a daemon thread (non-blocking)."""
        if self._thread and self._thread.is_alive():
            return

        try:
            self._server = HTTPServer((self.host, self.port), _Handler)
            self._server.timeout = 0.5  # allow clean shutdown
            self._thread = Thread(
                target=self._server.serve_forever,
                daemon=True,
                name="health-http",
            )
            self._thread.start()
            log.info(f"Health server listening on http://{self.host}:{self.port}")
        except OSError as e:
            log.warning(f"Health server on {self.host}:{self.port} failed: {e}")
            self._server = None

    def stop(self) -> None:
        """Shut down the health server."""
        if self._server:
            self._server.shutdown()
            self._server = None
        log.info("Health server stopped")


# --- Convenience singleton -------------------------------------------------------

_default_server: HealthServer | None = None


def start_default(port: int = 8909) -> HealthServer:
    """Start a global HealthServer instance on the given port."""
    global _default_server
    if _default_server is None:
        _default_server = HealthServer(port=port)
        _default_server.start()
    return _default_server


def get_default() -> HealthServer | None:
    """Return the global HealthServer instance, if started."""
    return _default_server
