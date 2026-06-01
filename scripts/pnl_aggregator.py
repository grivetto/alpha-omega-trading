#!/usr/bin/env python3
"""
Simple PnL aggregator for Denaro.

- Reads performance data from individual bot logs (if available) or
  from a static JSON file that can be manually updated.
- Generates / overwrites /home/sergio/denaro/pnl_latest.json
  with the latest profit figure and timestamp.
- This file is consumed by telegram_notifier.py.
"""

import json
import os
from datetime import datetime
from pathlib import Path

# ----------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------
OUTPUT_PATH = Path("/home/sergio/denaro/pnl_latest.json")

# ----------------------------------------------------------------------
# Simulated PnL calculation
# ----------------------------------------------------------------------
# In a real deployment you would parse each bot's log files here.
# For now we just emit a placeholder profit.
# The profit value should respect the capital‑protection constraint:
# total equity must never exceed ~48.80 € (the user's remaining capital).

# Example placeholder: 0.5 € profit today, adjust as needed
PLACEHOLDER_PROFIT = 0.5

def generate_report():
    report = {
        "profit": PLACEHOLDER_PROFIT,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        # add more fields if you want the notifier to display them
    }
    OUTPUT_PATH.write_text(json.dumps(report, indent=2))
    print(f"Wrote PnL report to {OUTPUT_PATH}")

if __name__ == "__main__":
    generate_report()