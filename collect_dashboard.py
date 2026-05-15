#!/usr/bin/env python3
"""DENARO Dashboard Collector Wrapper - runs all 3 collectors"""
import subprocess, sys, os

BASE_DIR = "/home/sergio/denaro"
VENV_PYTHON = f"{BASE_DIR}/venv/bin/python3"
DASHBOARD_DIR = f"{BASE_DIR}/dashboard/public"

def main():
    os.makedirs(DASHBOARD_DIR, exist_ok=True)
    # MC2 collector (local)
    try:
        r = subprocess.run([VENV_PYTHON, f"{BASE_DIR}/collect_dashboard_data.py"],
            capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            print(f"MC2 collector error: {r.stderr[:200]}", file=sys.stderr)
    except Exception as e:
        print(f"MC2 collector failed: {e}", file=sys.stderr)
    # NUVOLA collector (SSH)
    try:
        r = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=5", "sergio@nuvola",
             f"{VENV_PYTHON} {BASE_DIR}/collect_dashboard_nuvola.py"],
            capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            subprocess.run(
                ["scp", "-o", "ConnectTimeout=5",
                 "sergio@nuvola:/home/sergio/denaro/dashboard/public/nuvola.json",
                 f"{DASHBOARD_DIR}/nuvola.json"],
                capture_output=True, timeout=15)
    except Exception as e:
        print(f"NUVOLA collector failed: {e}", file=sys.stderr)
    # MARCODG1 collector (SSH)
    try:
        r = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=5", "marco@marcodg1",
             f"/home/marco/denaro/venv/bin/python3 /home/marco/denaro/collect_dashboard_marcodg1.py"],
            capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            subprocess.run(
                ["scp", "-o", "ConnectTimeout=5",
                 "marco@marcodg1:/home/marco/denaro/dashboard/public/marcodg1.json",
                 f"{DASHBOARD_DIR}/marcodg1.json"],
                capture_output=True, timeout=15)
    except Exception as e:
        print(f"MARCODG1 collector failed: {e}", file=sys.stderr)
    print("Dashboard collection complete")

if __name__ == "__main__":
    main()
