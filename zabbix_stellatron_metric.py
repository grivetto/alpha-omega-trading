#!/usr/bin/env python3
"""Zabbix metric parser for Stellatron log.
Usage: zabbix_stellatron_metric.py <key>
Keys: buys, sells, invested, profit, fills, eur_free, compound, errors, today_pnl, running
"""
import re
import sys
import subprocess

LOG = "/home/sergio/denaro/stellatron.log"
KEYS = {"buys", "sells", "invested", "profit", "fills", "eur_free", "compound", "errors", "today_pnl", "running"}


def get_last_status_line():
    try:
        with open(LOG) as f:
            for line in reversed(f.readlines()):
                if "Price=" in line and "profit=" in line:
                    return line
    except Exception:
        return None
    return None


def extract(key):
    if key == "running":
        try:
            r = subprocess.run(["pgrep", "-f", "stellatron.py"],
                               capture_output=True, text=True, timeout=5)
            print(1 if r.returncode == 0 else 0)
        except Exception:
            print(0)
        return

    if key == "errors":
        try:
            with open(LOG) as f:
                lines = f.readlines()
            print(sum(1 for l in lines[-200:] if "ERROR" in l))
        except Exception:
            print(0)
        return

    line = get_last_status_line()
    if not line:
        print(0)
        return

    patterns = {
        "buys": r"B=(\d+)",
        "sells": r"S=(\d+)",
        "invested": r"inv=([0-9.]+)",
        "profit": r"profit=([0-9.-]+)",
        "fills": r"fills=(\d+)",
        "eur_free": r"EUR_free=([0-9.]+)",
        "compound": r"compound=([0-9.]+)x",
        "today_pnl": r"today=([+-]?[0-9.]+)",
    }

    m = re.search(patterns[key], line)
    if m:
        print(m.group(1))
    else:
        print(0)


if __name__ == "__main__":
    key = sys.argv[1] if len(sys.argv) > 1 else ""
    if key not in KEYS:
        print(0)
    else:
        extract(key)
