"""Observability: health check, metrics, structured logging."""
from http.server import HTTPServer, BaseHTTPRequestHandler
import json, time, os, threading
from typing import Optional

_metrics = {
    "equity": 0.0,
    "regime": "unknown",
    "open_orders": 0,
    "risk_status": "ok",
    "daily_pnl": 0.0,
    "consecutive_losses": 0,
    "var_95": 0.0,
    "uptime_seconds": 0,
    "trades_today": 0,
    "last_error": "",
    "mode": "grid",
    "symbol": "",
}

_start = time.time()
_lock = threading.Lock()

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            with _lock:
                m = dict(_metrics)
                m["uptime_seconds"] = int(time.time() - _start)
            self.send_response(200 if m["risk_status"] == "ok" else 503)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(m).encode())
        elif self.path == "/metrics":
            with _lock:
                m = dict(_metrics)
            lines = [
                f"denaro_equity {m['equity']}",
                f"denaro_open_orders {m['open_orders']}",
                f"denaro_daily_pnl {m['daily_pnl']}",
                f"denaro_consecutive_losses {m['consecutive_losses']}",
                f"denaro_trades_today {m['trades_today']}",
                f"denaro_var_95 {m['var_95']}",
                f"denaro_uptime {int(time.time() - _start)}",
            ]
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write("\n".join(lines).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):
        pass

def start_health_server(port: int = 8909):
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server

def update(key: str, value):
    with _lock:
        _metrics[key] = value

class Observability:
    """Unified observability interface for the trading system."""

    def __init__(self, symbol: str = "SOL/USDC", port: int = 8909):
        self.symbol = symbol
        update("symbol", symbol)
        self.server = start_health_server(port)

    def update_equity(self, equity: float):
        update("equity", round(equity, 2))

    def update_regime(self, regime: str):
        update("regime", regime)

    def update_open_orders(self, count: int):
        update("open_orders", count)

    def update_risk(self, status: str):
        update("risk_status", status)

    def update_pnl(self, pnl: float):
        update("daily_pnl", round(pnl, 2))

    def update_losses(self, count: int):
        update("consecutive_losses", count)

    def update_var(self, var: float):
        update("var_95", round(var, 4))

    def update_trades(self, count: int):
        update("trades_today", count)

    def update_error(self, msg: str):
        update("last_error", msg[:100])

    def update_mode(self, mode: str):
        update("mode", mode)
