#!/usr/bin/env python3
"""Zabbix metric parser for ORION log on mc2.
Usage: zabbix_orion.py <key>
Keys: running, profit, fills, btc_state, eth_state, bnb_state, eur_free, errors
"""
import re, sys, subprocess
from pathlib import Path

LOG = "/home/sergio/denaro/orion.log"

def last_matching(keyword):
    try:
        with open(LOG) as f:
            for line in reversed(f.readlines()):
                if keyword in line: return line
    except: return None
    return None

def extract(key):
    if key == "running":
        r = subprocess.run(["pgrep", "-f", "orion.py"], capture_output=True, text=True, timeout=5)
        print(1 if r.returncode == 0 else 0); return
    if key == "errors":
        try:
            with open(LOG) as f:
                lines = f.readlines()
            print(sum(1 for l in lines[-200:] if "ERROR" in l))
        except: print(0)
        return
    if key == "btc_state":
        l = last_matching("BTC=")
        m = re.search(r"BTC=(\w+)", l or "")
        print(m.group(1) if m else "IDLE"); return
    if key == "eth_state":
        l = last_matching("ETH=")
        m = re.search(r"ETH=(\w+)", l or "")
        print(m.group(1) if m else "IDLE"); return
    if key == "bnb_state":
        l = last_matching("BNB=")
        m = re.search(r"BNB=(\w+)", l or "")
        print(m.group(1) if m else "IDLE"); return
    pats = {
        "profit": r"profit=(-?[0-9.]+)",
        "fills": r"fills=(\d+)",
        "eur_free": r"EUR=([0-9.]+)",
    }
    l = last_matching("profit=") or last_matching("EUR=")
    if not l: print(0); return
    m = re.search(pats.get(key, r""), l)
    print(m.group(1) if m else 0)

if __name__ == "__main__":
    extract(sys.argv[1] if len(sys.argv) > 1 else "")
