#!/usr/bin/env python3
"""
Fleet Dynamic Capital Rebalancer.
Periodically inspects performance metrics across all active ShadowGrid v2 instances.
Reallocates capital allocation in fleet_config.json towards high win-rate / positive PnL pairs
and scales down capital on stagnating/loss-making pairs.
"""
from __future__ import annotations
import json
import logging
import os
import sys
import time
import urllib.request
from pathlib import Path
from typing import Dict, List

log = logging.getLogger("fleet_rebalancer")
log.setLevel(logging.INFO)
sh = logging.StreamHandler(sys.stdout)
sh.setFormatter(logging.Formatter("%(asctime)s [Rebalancer] %(message)s"))
log.handlers = [sh]

CONFIG_FILE = os.environ.get("FLEET_CONFIG", "fleet_config.json")
TOTAL_CAPITAL = float(os.environ.get("TOTAL_CAPITAL", "100.0"))
MIN_BOT_CAPITAL = 15.0
MAX_BOT_CAPITAL = 45.0


def fetch_bot_health(port: int) -> Dict:
    try:
        url = f"http://127.0.0.1:{port}/health"
        req = urllib.request.Request(url, headers={"User-Agent": "FleetRebalancer/1.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status == 200:
                return json.loads(resp.read().decode())
    except Exception:
        pass
    return {}


def rebalance_fleet():
    cfg_path = Path(CONFIG_FILE)
    if not cfg_path.exists():
        log.warning(f"Config file {CONFIG_FILE} not found!")
        return

    with open(cfg_path) as f:
        config = json.load(f)

    pairs = config.get("pairs", [])
    if not pairs:
        return

    log.info(f"Analyzing performance for {len(pairs)} bots...")
    scores = []
    
    for p in pairs:
        sym = p["symbol"]
        port = p["port"]
        health = fetch_bot_health(port)
        
        pnl = health.get("realized_pnl", 0.0)
        trades = health.get("total_trades", 0)
        rsi = health.get("rsi", 50.0)
        adx = health.get("adx", 15.0)
        momentum_ok = health.get("momentum_ok", True)
        
        # Performance score: Base 1.0 + PnL bonus + activity bonus
        score = 1.0 + (pnl * 2.0) + (0.1 if trades > 5 else 0.0) + (0.2 if momentum_ok else -0.3)
        score = max(0.1, score)
        
        scores.append({"symbol": sym, "port": port, "score": score, "pnl": pnl, "trades": trades})
        log.info(f"Bot {sym} (:port {port}): PnL={pnl:+.4f}, Trades={trades}, Score={score:.2f}")

    total_score = sum(s["score"] for s in scores) or 1.0
    log.info("Rebalancing capital based on performance scores...")
    
    # Distribute capital proportional to score
    for i, s in enumerate(scores):
        weight = s["score"] / total_score
        raw_cap = TOTAL_CAPITAL * weight
        alloc_cap = max(MIN_BOT_CAPITAL, min(MAX_BOT_CAPITAL, round(raw_cap, 1)))
        pairs[i]["capital"] = alloc_cap
        log.info(f"Allocated {alloc_cap} EUR to {s['symbol']} (Weight: {weight*100:.1f}%)")

    config["pairs"] = pairs
    with open(cfg_path, "w") as f:
        json.dump(config, f, indent=2)
        
    log.info("Updated fleet_config.json successfully.")


if __name__ == "__main__":
    rebalance_fleet()
