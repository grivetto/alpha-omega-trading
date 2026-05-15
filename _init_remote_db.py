#!/usr/bin/env python3
"""Init DB - copiare su ogni host e lanciare prima del bot."""
import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from trade_db import TradeDB
import sqlite3

DB_PATH = os.path.join(BASE_DIR, "trades.db")
POS_DIR = os.path.join(BASE_DIR, "positions")

os.makedirs(POS_DIR, exist_ok=True)

# Forza ricrea DB pulito se esiste
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

db = TradeDB(DB_PATH)
with sqlite3.connect(DB_PATH) as c:
    cols = c.execute("PRAGMA table_info(bot_state)").fetchall()
    print("Schema bot_state:", [col[1] for col in cols])
    c.execute("SELECT * FROM bot_exposure")
    print("bot_exposure: OK")
    c.execute("SELECT * FROM vault_balance")
    print("vault_balance: OK")
    c.execute("SELECT * FROM trades")
    print("trades: OK")

print("=== DB inizializzato ===")