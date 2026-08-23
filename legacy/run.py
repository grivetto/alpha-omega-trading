#!/usr/bin/env python3
"""
DENARO EXCHANGE — Main loop exchange-agnostico.
Carica l'engine giusto in base a EXCHANGE dal .env:
  EXCHANGE=kraken  → main.py (KrakenEngine)
  EXCHANGE=bybit   → main_v5.py (BybitEngine)
  EXCHANGE=mexc    → main_mexc.py (MexcEngine)
"""
import os, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Legge EXCHANGE dal .env
env_path = Path(__file__).parent / ".env"
if not env_path.exists():
    env_path = Path.home() / "denaro" / ".env"
exchange = "kraken"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("EXCHANGE="):
                exchange = line.split("=", 1)[1].strip().strip('"').strip("'").lower()

print(f"Denaro Exchange Router: loading {exchange}")

if exchange == "kraken":
    import main as _main
    _main.main()
elif exchange == "bybit":
    import main_v5 as _main
    _main.main()
elif exchange == "mexc":
    import main_mexc as _main
    _main.main()
else:
    print(f"Unknown exchange: {exchange}")
    sys.exit(1)
