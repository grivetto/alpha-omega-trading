#!/usr/bin/env python3
"""Zabbix metric parser for MarcoSOL log on MARCODG1.
Usage: zabbix_marco_sol.py <key>
Keys: price, sol_free, eur_free, profit, fills, cycle, sell_target, buy_target, running, errors
"""
import re, sys, subprocess
from pathlib import Path

LOG = "/home/sergio/denaro/marco_sol.log"
KEYS = {"price", "sol_free", "eur_free", "profit", "fills", "cycle", "sell_target", "buy_target", "running", "errors"}


def last_line_with(keyword):
    try:
        with open(LOG) as f:
            for line in reversed(f.readlines()):
                if keyword in line:
                    return line
    except: return None
    return None


def extract(key):
    if key == "running":
        r = subprocess.run(["pgrep", "-f", "marco_sol.py"], capture_output=True, text=True, timeout=5)
        print(1 if r.returncode == 0 else 0); return
    if key == "errors":
        try:
            with open(LOG) as f:
                lines = f.readlines()
            print(sum(1 for l in lines[-200:] if "ERROR" in l))
        except: print(0)
        return

    line = last_line_with("SOL/EUR=") or last_line_with("SELL") or last_line_with("BUY")
    if not line: print(0); return

    pats = {
        "price": r"SOL/EUR=([0-9.]+)",
        "sol_free": r"SOL=([0-9.]+)",
        "eur_free": r"EUR=([0-9.]+)",
        "profit": r"PnL=([0-9.-]+)",
        "fills": r"fills=(\d+)",
        "cycle": r"cycles=(\d+)",
        "sell_target": r"sell=([0-9.]+)",
        "buy_target": r"buy=([0-9.]+)",
    }
    m = re.search(pats.get(key, r""), line)
    if m: print(m.group(1))
    else: print(0)


if __name__ == "__main__":
    extract(sys.argv[1] if len(sys.argv) > 1 else "")
