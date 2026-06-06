#!/usr/bin/env python3
"""Update .env with v4 parameters on Denaro host, then start everything"""
import os, sys, json

denaro = os.path.expanduser("~")
if not os.path.exists(os.path.join(denaro, "denaro")):
    for p in ["/home/sergio/denaro", "/home/marco/denaro"]:
        if os.path.exists(p):
            denaro = p
            break

env_path = os.path.join(denaro, ".env")
if not os.path.exists(env_path):
    print(f"ERROR: {env_path} not found")
    sys.exit(1)

# Read existing .env
with open(env_path) as f:
    existing = f.read()

# Check if v4 params already present
if "INITIAL_CAPITAL" in existing:
    print("v4 params already in .env, skipping update")
else:
    # Append v4 params
    v4_params = """

# ═══════════════════════════════════════════════════════════
# STRATEGIA — v4.0 (auto-adaptive engine)
# ═══════════════════════════════════════════════════════════
INITIAL_CAPITAL=500.0
MAX_GLOBAL_EXPOSURE=200.0
MAX_CONCURRENT_POSITIONS=4
DAILY_LOSS_LIMIT_PCT=-3.0
PER_SYMBOL_MAX_EUR=30.0

# ─── Indicator parameters ────────────────────────────────
RSI_LENGTH=9
EMA_LENGTH=20
ATR_LENGTH=7
OHLCV_LIMIT=100

# ─── TP/SL ───────────────────────────────────────────────
TP_ATR_MULT=1.5
SL_ATR_MULT=0.75
TRAILING_ACTIVATION=1.5
BREAKEVEN_BUFFER=0.004

# ─── Volume filter ───────────────────────────────────────
MIN_VOLUME_MULT=1.5

# ─── Trading hours (UTC) ────────────────────────────────
TRADING_HOURS_START=6
TRADING_HOURS_END=22

# ─── Heartbeat ───────────────────────────────────────────
HEARTBEAT_INTERVAL=3600
"""
    with open(env_path, "a") as f:
        f.write(v4_params)
    print(f".env aggiornato con v4 params [{len(v4_params)} chars]")

print("OK")
