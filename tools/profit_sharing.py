#!/usr/bin/env python3
"""Profit sharing and compounding script for Denaro trading bots."""

import os
import sys
import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path

# Load environment variables from .env file
from dotenv import load_dotenv
BASE = Path(__file__).resolve().parents[1]
load_dotenv(BASE / ".env")

import ccxt.pro as ccxt

# --- Configuration ---
# Binance API keys (MAIN account, with sub-account transfer permissions)
API_KEY_MAIN = os.getenv('BINANCE_API_KEY_MAIN')
API_SECRET_MAIN = os.getenv('BINANCE_API_SECRET_MAIN')

# Sub-account emails and their corresponding node names for mapping
SUB_ACCOUNT_EMAILS = {
    'mc2orion_virtual@85origvknoemail.com': 'MC2',
    'nuvolatrading_virtual@2lyv5fu2noemail.com': 'Nuvola',
    'marcodg1marcosol_virtual@pwomuqu6noemail.com': 'MARCODG1',
}

# Recipient for profit share
PROFIT_SHARE_RECIPIENT_EMAIL = 'sergio@grivetto.eu'
PROFIT_SHARE_PERCENTAGE = 0.33  # 33% of daily profit

# Minimum profit in USDT to trigger a transfer (to recipient or for compounding)
MIN_PROFIT_FOR_TRANSFER = 0.40  # Increased threshold to prevent micro-transfers

# Initial baseline equity for each sub-account (stored in a JSON file)
BASELINE_FILE = '/home/sergio/denaro/.profit_baseline.json'

# Enable reinvestment of profits back into the main trading account (compounding)
REINVEST_PROFITS = True # Set to True for compounding

# Path to the portfolio.json for overall balance tracking
PORTFOLIO_FILE = '/var/www/html/denaro/portfolio.json'

# --- Logging --- #
def log(message):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]
    print(f'{timestamp} | INFO     | {message}')

async def get_total_equity(exchange: ccxt.Exchange) -> float:
    """Fetches the total USDT equivalent equity of the account (SPOT)."""
    try:
        balance = await exchange.fetch_total_balance()
        total_usdt = balance.get('USDT', 0.0)
        if total_usdt == 0.0:
            for asset, amount in balance.items():
                if asset != 'USDT' and amount > 0:
                    try:
                        ticker = await exchange.fetch_ticker(f'{asset}/USDT')
                        total_usdt += amount * ticker['last']
                    except Exception:
                        pass
        return total_usdt
    except Exception as e:
        log(f"Error fetching total equity: {e}")
        return 0.0

async def load_baselines() -> dict:
    """Loads baseline equity from file."""
    if os.path.exists(BASELINE_FILE):
        with open(BASELINE_FILE, 'r') as f:
            return json.load(f)
    return {}

async def save_baselines(baselines: dict):
    """Saves baseline equity to file."""
    with open(BASELINE_FILE, 'w') as f:
        json.dump(baselines, f, indent=4)

async def main():
    log("==================================================")
    log(f"PROFIT SHARING — {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    log("==================================================")

    if not API_KEY_MAIN or not API_SECRET_MAIN:
        log("Binance Main API keys not found. Exiting.")
        return

    exchange_main = ccxt.binance({
        'apiKey': API_KEY_MAIN,
        'secret': API_SECRET_MAIN,
        'enableRateLimit': True,
        'options': {'defaultType': 'spot'}
    })

    current_equity = await get_total_equity(exchange_main)
    log(f"Equity attuale: {current_equity:.2f} USDT")

    baselines = await load_baselines()
    today_date = datetime.utcnow().strftime('%Y-%m-%d')

    if today_date not in baselines:
        baselines[today_date] = current_equity
        await save_baselines(baselines)
        log("Prima esecuzione — salvo baseline senza trasferire")
        return

    yesterday_date = (datetime.utcnow() - timedelta(days=1)).strftime('%Y-%m-%d')
    yesterday_equity = baselines.get(yesterday_date, 0.0)

    if yesterday_equity == 0.0:
        log("Baseline di ieri non trovata. Impossibile calcolare profitto giornaliero.")
        return

    daily_profit = current_equity - yesterday_equity
    log(f"Equity ieri: {yesterday_equity:.2f} USDT")
    log(f"Profitto giornaliero: {daily_profit:+.2f} USDT")

    if daily_profit < MIN_PROFIT_FOR_TRANSFER:
        log(f"Profitto troppo piccolo per trasferimento ({MIN_PROFIT_FOR_TRANSFER:.2f} USDT). Saltato.")
        return

    if REINVEST_PROFITS:
        log(f"Reinvesting {daily_profit:+.2f} USDT back into trading capital.")
    else:
        profit_for_recipient = daily_profit * PROFIT_SHARE_PERCENTAGE
        if profit_for_recipient >= MIN_PROFIT_FOR_TRANSFER:
            log(f"Trasferisco {profit_for_recipient:.2f} USDT a {PROFIT_SHARE_RECIPIENT_EMAIL}")
        else:
            log(f"Profitto per destinatario ({profit_for_recipient:.2f} USDT) troppo piccolo. Saltato.")
    
    baselines[today_date] = current_equity
    await save_baselines(baselines)
    log("Profit sharing completato.")

if __name__ == "__main__":
    if '--yesterday' in sys.argv:
        log("Calcolo profitto di ieri...")
        log("Per il calcolo esatto del profitto di ieri, questo script deve essere eseguito dopo le 23:59 UTC del giorno corrente.")
        log("Per ora, il profitto giornaliero viene calcolato rispetto alla baseline salvata.")
    
    asyncio.run(main())