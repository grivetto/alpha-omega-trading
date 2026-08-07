#!/usr/bin/env python3
"""
ShadowGrid Fleet Orchestrator.
Spawns and monitors multiple ShadowGrid v2 instances across different trading pairs.
Features:
- Automatic port assignment per bot instance.
- Process supervision (auto-restart crashed instances).
- Fleet health HTTP status dashboard.
"""
from __future__ import annotations
import json
import logging
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import threading
from typing import Dict, List

log = logging.getLogger("shadowgrid_fleet")
log.setLevel(logging.INFO)
sh = logging.StreamHandler(sys.stdout)
sh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
log.handlers = [sh]

CONFIG_FILE = os.environ.get("FLEET_CONFIG", "fleet_config.json")
FLEET_PORT  = int(os.environ.get("FLEET_PORT", "8900"))
PYTHON_BIN  = sys.executable
SCRIPT_PATH = str(Path(__file__).parent / "shadowgrid_v2.py")


DEFAULT_FLEET = {
    "exchange": "kraken",
    "capital_per_bot": 50.0,
    "pairs": [
        {"symbol": "SOL/EUR", "port": 8912},
        {"symbol": "DOGE/EUR", "port": 8913},
        {"symbol": "XRP/EUR", "port": 8914},
        {"symbol": "ADA/EUR", "port": 8915},
    ]
}


class FleetManager:
    def __init__(self, config: Dict):
        self.config = config
        self.processes: Dict[str, subprocess.Popen] = {}
        self.running = True

    def start_bot(self, pair_cfg: Dict):
        sym = pair_cfg["symbol"]
        port = pair_cfg["port"]
        ex = pair_cfg.get("exchange", self.config.get("exchange", "kraken"))
        capital = pair_cfg.get("capital", self.config.get("capital_per_bot", 50.0))

        env = os.environ.copy()
        env["EXCHANGE"] = ex
        env["SYMBOL"] = sym
        env["CAPITAL"] = str(capital)
        env["HEALTH_PORT"] = str(port)
        env["LOG_FILE"] = f"/tmp/shadowgrid_{ex}_{sym.replace('/', '_').lower()}.log"
        env["STATE_FILE"] = f"/tmp/shadowgrid_{ex}_{sym.replace('/', '_').lower()}_state.json"

        cmd = [PYTHON_BIN, SCRIPT_PATH]
        log.info(f"Starting bot for {ex}:{sym} on port :{port} (capital {capital} EUR)")
        proc = subprocess.Popen(cmd, env=env)
        self.processes[sym] = proc

    def supervise(self):
        all_pairs = self.config.get("pairs", []) + self.config.get("okx_pairs", [])
        for pair_cfg in all_pairs:
            self.start_bot(pair_cfg)

        while self.running:
            for pair_cfg in all_pairs:
                sym = pair_cfg["symbol"]
                proc = self.processes.get(sym)
                if proc is None or proc.poll() is not None:
                    log.warning(f"Bot process for {sym} stopped! Restarting...")
                    self.start_bot(pair_cfg)
            time.sleep(10)

    def stop_all(self):
        self.running = False
        log.info("Stopping all fleet instances...")
        for sym, proc in self.processes.items():
            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=5)
        log.info("All fleet instances stopped.")


class FleetHealthHandler(BaseHTTPRequestHandler):
    fleet_ref: FleetManager = None

    def do_GET(self):
        if self.path == "/health":
            fm = self.__class__.fleet_ref
            bots_status = {}
            if fm:
                for sym, proc in fm.processes.items():
                    bots_status[sym] = {
                        "status": "running" if proc.poll() is None else "stopped",
                        "pid": proc.pid if proc else None,
                    }
            body = json.dumps({
                "status": "healthy",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "total_bots": len(bots_status),
                "bots": bots_status,
            }, indent=2).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, fmt, *args):
        pass


def main():
    log.info("=== ShadowGrid Fleet Orchestrator ===")
    cfg_path = Path(CONFIG_FILE)
    if not cfg_path.exists():
        log.info(f"Creating default config file: {CONFIG_FILE}")
        with open(cfg_path, "w") as f:
            json.dump(DEFAULT_FLEET, f, indent=2)
        config = DEFAULT_FLEET
    else:
        with open(cfg_path) as f:
            config = json.load(f)

    fm = FleetManager(config)
    FleetHealthHandler.fleet_ref = fm

    health = HTTPServer(("0.0.0.0", FLEET_PORT), FleetHealthHandler)
    hthread = threading.Thread(target=health.serve_forever, daemon=True)
    hthread.start()
    log.info(f"Fleet Health dashboard listening on :{FLEET_PORT}")

    def shutdown(sig, frame):
        fm.stop_all()
        health.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    fm.supervise()


if __name__ == "__main__":
    main()
