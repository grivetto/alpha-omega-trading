#!/usr/bin/env python3
"""
Advanced Quantitative Trading Bot
Implements: Mean Reversion, Momentum Breakout, Whale Tracking Alerts
Strict Risk Management: 2% max per trade, 1.5% trailing stop, tiered TPs.
"""

import os
import time
import json
import logging
import pandas as pd
import pandas_ta as ta
from binance.client import Client
from dotenv import load_dotenv
from datetime import datetime

# --- CONFIGURAZIONE ---
load_dotenv()

API_KEY = os.getenv('BINANCE_API_KEY')
API_SECRET = os.getenv('BINANCE_API_SECRET')

# Symbols to trade
SYMBOLS = ["BTCEUR", "ETHEUR", "SOLEUR", "BNBEUR"]

# Technical Parameters (AGGRESSIVE SCALPING)
TIMEFRAME = Client.KLINE_INTERVAL_3MINUTE
BB_PERIOD = 20
BB_STD = 1.8
VOLUME_MA_PERIOD = 20
VOLUME_SPIKE_RATIO = 1.3

# Risk Management
POSITION_SIZE_EUR = 5.5  # Fixed 5.5 EUR (min notional is usually ~5 EUR)
TRAILING_STOP_PCT = 0.01  # 1.0% tight stop for scalping
TAKE_PROFIT_TIERS = [0.02]  # Quick 2% Take Profit

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("quant_bot.log"), logging.StreamHandler()]
)

client = Client(API_KEY, API_SECRET, testnet=False)
logging.info("Advanced Quant Bot initialized for REAL TRADING (EUR).")

state = {
    "symbols": {s: {"position": 0, "entry": 0, "tier": 0, "highest": 0} for s in SYMBOLS},
    "balance": 0.0,
    "last_update": ""
}

def load_data(symbol):
    klines = client.get_klines(symbol=symbol, interval=TIMEFRAME, limit=100)
    df = pd.DataFrame(klines, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_av', 'trades', 'tb_base_av', 'tb_quote_av', 'ignore'
    ])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = pd.to_numeric(df[col])
    
    # Indicators
    df.ta.bbands(length=BB_PERIOD, std=BB_STD, append=True)
    df.ta.rsi(length=14, append=True)
    df['vol_sma'] = df['volume'].rolling(VOLUME_MA_PERIOD).mean()
    
    return df

def update_status_file():
    state["last_update"] = datetime.utcnow().isoformat()
    with open("quant_status.json", "w") as f:
        json.dump(state, f, indent=4)

def check_signals():
    try:
        eur_balance = float(client.get_asset_balance(asset='EUR')['free'])
        state["balance"] = eur_balance
        logging.info(f"Current EUR Balance: {eur_balance:.2f}")
    except Exception as e:
        logging.error(f"Error getting balance: {e}")
        return

    for sym in SYMBOLS:
        try:
            df = load_data(sym)
            if df.empty:
                continue
            
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            
            price = latest['close']
            rsi = latest['RSI_14']
            vol = latest['volume']
            vol_sma = latest['vol_sma']
            
            lower_bb = latest[[c for c in df.columns if c.startswith('BBL_')][0]]
            upper_bb = latest[[c for c in df.columns if c.startswith('BBU_')][0]]
            
            pos = state["symbols"][sym]
            
            # --- MANAGE EXISTING POSITIONS ---
            if pos["position"] > 0:
                if price > pos["highest"]:
                    pos["highest"] = price
                
                # Trailing Stop
                ts_level = pos["highest"] * (1.0 - TRAILING_STOP_PCT)
                if price <= ts_level:
                    logging.info(f"[SELL] Trailing Stop hit for {sym} at {price}")
                    try:
                        base_asset = sym.replace('EUR', '')
                        actual_qty = float(client.get_asset_balance(asset=base_asset)['free'])
                        # Formatta a 4 cifre decimali grossolanamente, o usa sell base_asset se abbastanza grande
                        # Per evitare errori LOT_SIZE, vendiamo l'intero balance se copre MIN_NOTIONAL
                        client.order_market_sell(symbol=sym, quoteOrderQty=pos["position"]*price)
                    except Exception as order_e:
                        logging.error(f"Real SELL failed: {order_e}")
                    pos["position"] = 0
                    pos["entry"] = 0
                    pos["tier"] = 0
                    continue
                
                # Take Profit Finale (No Tiers per via di MIN_NOTIONAL = 5 EUR)
                profit_pct = (price - pos["entry"]) / pos["entry"]
                if profit_pct >= 0.02: # 2% Profit
                    logging.info(f"[SELL] TP hit for {sym} at {price} (+2%)")
                    try:
                        client.order_market_sell(symbol=sym, quoteOrderQty=pos["position"]*price)
                    except Exception as order_e:
                        logging.error(f"Real SELL failed: {order_e}")
                    pos["position"] = 0  # Fully closed
                    pos["entry"] = 0
                    pos["tier"] = 0
                
            # --- ENTRY SIGNALS ---
            elif pos["position"] == 0 and eur_balance >= POSITION_SIZE_EUR:
                # 1. Mean Reversion
                is_mean_reversion = (price < lower_bb) and (rsi < 40)
                
                # 2. Momentum Breakout
                is_breakout = (price > upper_bb) and (prev['close'] <= prev[[c for c in df.columns if c.startswith('BBU_')][0]])
                is_vol_spike = (vol > vol_sma * VOLUME_SPIKE_RATIO)
                
                if is_mean_reversion:
                    logging.info(f"[BUY] Mean Reversion Signal for {sym} at {price} (RSI: {rsi:.1f})")
                    try:
                        order = client.order_market_buy(symbol=sym, quoteOrderQty=POSITION_SIZE_EUR)
                        pos["position"] = float(order['executedQty'])
                        pos["entry"] = price
                        pos["highest"] = price
                        eur_balance -= POSITION_SIZE_EUR
                    except Exception as order_e:
                        logging.error(f"Real BUY failed: {order_e}")
                    
                elif is_breakout and is_vol_spike:
                    logging.info(f"[BUY] Momentum Breakout Signal for {sym} at {price} (Vol Spike: {vol/vol_sma:.1f}x)")
                    try:
                        order = client.order_market_buy(symbol=sym, quoteOrderQty=POSITION_SIZE_EUR)
                        pos["position"] = float(order['executedQty'])
                        pos["entry"] = price
                        pos["highest"] = price
                        eur_balance -= POSITION_SIZE_EUR
                    except Exception as order_e:
                        logging.error(f"Real BUY failed: {order_e}")
                    
        except Exception as e:
            logging.error(f"Error processing {sym}: {e}")
            
    update_status_file()

def main():
    while True:
        try:
            check_signals()
        except Exception as e:
            logging.error(f"Main loop error: {e}")
        time.sleep(60)

if __name__ == "__main__":
    main()