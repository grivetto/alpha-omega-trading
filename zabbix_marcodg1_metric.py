#!/usr/bin/env python3
"""Zabbix metrics for MARCODG1 Trend Grid Bot"""
import json, os, sys
from pathlib import Path
BASE = Path("/home/marco/denaro")
sys.path.insert(0, str(BASE))
from denaro_shared import make_client

try:
    client = make_client()
    bal = client.fetch_balance()
    ticker = client.fetch_ticker("ADA/EUR")
    price = ticker["last"]
    eur = bal["free"].get("EUR", 0)
    ada = bal["free"].get("ADA", 0) + bal.get("used", {}).get("ADA", 0)
    port = eur + ada * price
    state_file = BASE / ".tmp" / "marcodg1_grid_state.json"
    pnl = 0
    trades = 0
    regime = "unknown"
    if state_file.exists():
        with open(state_file) as f:
            s = json.load(f)
            pnl = s.get("pnl", 0)
            trades = s.get("trades", 0)
            regime = s.get("regime", "unknown")
    orders = client.fetch_open_orders("ADA/EUR")
    n_orders = len(orders)
    print(json.dumps({"price": round(price, 4), "eur": round(eur, 2), "ada": round(ada, 2), "portfolio": round(port, 2), "pnl": round(pnl, 2), "trades": trades, "regime": regime, "open_orders": n_orders, "bots_alive": 1}))
except Exception as e:
    print(json.dumps({"error": str(e)}))
