#!/usr/bin/env python3
"""
Alpha-Omega Health Server — espone lo stato dei bot via HTTP.
Nodo: mc2 (host locale) — file reali: doge_mc2.json

GET /health      → stato aggregato di tutti i bot
GET /health/doge → stato bot DOGE/EUR
"""
import json
import os
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HEALTH_DIR = Path(os.getenv("HEALTH_DIR", "/home/sergio/denaro/health"))
PORT = int(os.getenv("HEALTH_PORT", "8911"))
HOST = os.getenv("HEALTH_HOST", "127.0.0.1")
# Nomi file reali su mc2 (verificati 2026-08-26)
BOTS = {"doge": "doge_mc2"}


def read_health(name: str):
    p = HEALTH_DIR / f"{name}.json"
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, payload: dict):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/")
        try:
            if path in ("/health", ""):
                bots = {}
                for alias, fname in BOTS.items():
                    h = read_health(fname)
                    if h:
                        bots[alias] = h
                all_running = all(b.get("status") == "running" for b in bots.values()) and len(bots) > 0
                self._send(200, {
                    "status": "healthy" if all_running else "degraded",
                    "timestamp": time.time(),
                    "bots": bots,
                })
            elif path.startswith("/health/"):
                alias = path.split("/")[-1]
                fname = BOTS.get(alias)
                h = read_health(fname) if fname else None
                if h:
                    self._send(200, h)
                else:
                    self._send(404, {"status": "not_found", "bot": alias})
            else:
                self._send(404, {"status": "not_found"})
        except Exception as e:
            self._send(500, {"status": "error", "error": str(e)})

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    HEALTH_DIR.mkdir(parents=True, exist_ok=True)
    srv = HTTPServer((HOST, PORT), Handler)
    print(f"Health server on {HOST}:{PORT} (dir={HEALTH_DIR}, bots={BOTS})", flush=True)
    srv.serve_forever()
