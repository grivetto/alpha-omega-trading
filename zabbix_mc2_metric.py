#!/usr/bin/env python3
"""Zabbix metrics for Mc2 Multi-Pair Scalper (28 USDT pairs)"""
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
    usdt = bal["free"].get("USDT", 0)
    eur = bal["free"].get("EUR", 0)
    orders = client.fetch_open_orders()
    n_orders = len(orders)
    state_file = BASE / ".tmp" / "mc2_scalper_state.json"
    pnl = 0
    trades = 0
    if state_file.exists():
        with open(state_file) as f:
            s = json.load(f)
            pnl = s.get("pnl", 0)
            trades = s.get("trades", 0)
    print(json.dumps({"price": round(price, 2), "usdt": round(usdt, 2), "eur": round(eur, 2), "pnl": round(pnl, 2), "trades": trades, "open_orders": n_orders, "bots_alive": 1}))
except Exception as e:
    print(json.dumps({"error": str(e)}))
