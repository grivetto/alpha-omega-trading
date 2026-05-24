#!/usr/bin/env python3
"""Zabbix metrics for Nuvola Grid Bot (SOL/EUR Regime-Adaptive)"""
import json, os, sys
from pathlib import Path
BASE = Path("/home/sergio/denaro")
sys.path.insert(0, str(BASE))
from denaro_shared import make_client

try:
    client = make_client()
    bal = client.fetch_balance()
    ticker = client.fetch_ticker("SOL/EUR")
    price = ticker["last"]
    eur = bal["free"].get("EUR", 0)
    sol = bal["free"].get("SOL", 0) + bal.get("used", {}).get("SOL", 0)
    port = eur + sol * price
    state_file = BASE / ".tmp" / "nuvola_grid_state.json"
    pnl = 0
    trades = 0
    regime = "unknown"
    if state_file.exists():
        with open(state_file) as f:
            s = json.load(f)
            pnl = s.get("pnl", 0)
            trades = s.get("trades", 0)
            regime = s.get("regime", "unknown")
    orders = client.fetch_open_orders("SOL/EUR")
    n_orders = len(orders)
    print(json.dumps({"price": round(price, 2), "eur": round(eur, 2), "sol": round(sol, 4), "portfolio": round(port, 2), "pnl": round(pnl, 2), "trades": trades, "regime": regime, "open_orders": n_orders, "bots_alive": 1}))
except Exception as e:
    print(json.dumps({"error": str(e)}))
