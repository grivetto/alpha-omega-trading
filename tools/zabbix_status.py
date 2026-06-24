#!/usr/bin/env python3
"""Zabbix agent helper — Denaro metrics for Zabbix.
Usage: zabbix_status.py <metric> [pair]
  metric: usdc | sol | ada | grid | trades | status | mem | load
"""
import ccxt, os, sys

metric = sys.argv[1] if len(sys.argv) > 1 else "status"
pair = sys.argv[2] if len(sys.argv) > 2 else "SOL/USDC"
denaro = os.path.dirname(os.path.abspath(__file__))

def load_env():
    env = {}
    env_path = os.path.join(denaro, ".env")
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip(chr(34)).strip("'")
    return env

try:
    if metric == "mem":
        with open("/proc/meminfo") as f:
            lines = f.readlines()
        total = int(lines[0].split()[1])
        avail = int(lines[2].split()[1])  # MemAvailable line 3
        pct = (total - avail) / total * 100
        print(f"{pct:.0f}")
    elif metric == "load":
        with open("/proc/loadavg") as f:
            print(f.read().split()[0])
    else:
        env = load_env()
        e = ccxt.binance({"apiKey": env["BINANCE_API_KEY"], "secret": env["BINANCE_API_SECRET"]})

        if metric == "usdc":
            b = e.fetch_balance()
            print(b.get("USDC", {}).get("total", 0))
        elif metric == "sol":
            b = e.fetch_balance()
            print(b.get("SOL", {}).get("total", 0))
        elif metric == "ada":
            b = e.fetch_balance()
            print(b.get("ADA", {}).get("total", 0))
        elif metric == "grid":
            orders = e.fetch_open_orders(pair)
            print(len(orders))
        elif metric == "trades":
            print(0)
        elif metric == "status":
            b = e.fetch_balance()
            orders = e.fetch_open_orders(pair)
            usdc = b.get("USDC", {}).get("total", 0)
            base = pair.split("/")[0]
            base_qty = b.get(base, {}).get("total", 0)
            ticker = e.fetch_ticker(pair)
            equity = usdc + base_qty * ticker["last"]
            buys = sum(1 for o in orders if o["side"] == "buy")
            sells = len(orders) - buys
            print(f"{pair} | Grid: {buys}B/{sells}S | Equity: ${equity:.0f} | CB: closed")
        else:
            print(0)
except Exception as ex:
    if metric == "status":
        print("OFFLINE")
    else:
        print(0)
