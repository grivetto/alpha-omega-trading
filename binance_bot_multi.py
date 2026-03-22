#!/usr/bin/env python3
import os
import time
import json
import logging
import pandas as pd
import pandas_ta as ta
from binance.client import Client
from dotenv import load_dotenv
from datetime import datetime, timedelta
import sys

load_dotenv()

API_KEY = os.getenv('BINANCE_API_KEY')
API_SECRET = os.getenv('BINANCE_API_SECRET')

TRADING_PAIRS = [
    'ETHBTC', 'SOLBTC', 'BNBBTC', 'ADABTC', 'DOGEBTC', 'AVAXBTC', 'DOTBTC', 'LINKBTC', 'MATICBTC', 'SHIBBTC',
    'LTCBTC', 'UNIBTC', 'ATOMBTC', 'FILBTC', 'AAVEBTC', 'APTBTC', 'NEARBTC', 'ARBBTC', 'OPBTC', 'MKRBTC'
]

QUOTE_ASSET = 'BTC'
INTERVAL = '5m'
SLEEP_TIME = 45

# Indicatori (GOD MODE MAX)
RSI_PERIOD = 14
RSI_BUY_THRESHOLD = 58
RSI_SELL_THRESHOLD = 45

RISK_PER_TRADE = 0.95
STOP_LOSS_PCT = 0.08
TAKE_PROFIT_PCT = 0.045
TRAILING_STOP_PCT = 0.005

STATUS_FILE = '/root/.openclaw/workspace/multi_status.json'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s',
                   handlers=[logging.FileHandler('trading_bot.log'), logging.StreamHandler()])
logger = logging.getLogger(__name__)

client = Client(API_KEY, API_SECRET)
coin_states = {}

class CoinState:
    def __init__(self, symbol):
        self.symbol = symbol
        self.in_position = False
        self.entry_price = 0.0
        self.position_quantity = 0.0
        self.highest_price = 0.0
        self.total_pnl = 0.0

for pair in TRADING_PAIRS:
    coin_states[pair] = CoinState(pair)

def get_data(symbol):
    try:
        klines = client.get_klines(symbol=symbol, interval=INTERVAL, limit=100)
        df = pd.DataFrame(klines, columns=['ts', 'open', 'high', 'low', 'close', 'volume', 'ct', 'qv', 'nt', 'tb', 'tq', 'i'])
        df['close'] = pd.to_numeric(df['close'])
        df['high'] = pd.to_numeric(df['high'])
        df['low'] = pd.to_numeric(df['low'])
        df['volume'] = pd.to_numeric(df['volume'])
        return df
    except: return None

def main():
    logger.info("🚀 GOD MODE MAX - ALPHA SQUAD OVERDRIVE")
    while True:
        try:
            btc_balance = float(client.get_asset_balance(asset='BTC')['free'])
            for symbol in TRADING_PAIRS:
                df = get_data(symbol)
                if df is None: continue
                
                df['rsi'] = ta.rsi(df['close'], length=RSI_PERIOD)
                price = df['close'].iloc[-1]
                rsi = df['rsi'].iloc[-1]
                state = coin_states[symbol]

                if rsi < RSI_BUY_THRESHOLD and not state.in_position:
                    qty_to_buy_btc = btc_balance * 0.3 # Usa il 30% per permettere più trade pesanti
                    if qty_to_buy_btc > 0.0001:
                        try:
                            order = client.create_order(symbol=symbol, side='BUY', type='MARKET', quoteOrderQty=round(qty_to_buy_btc, 6))
                            state.in_position = True
                            state.entry_price = price
                            state.position_quantity = float(order['executedQty'])
                            state.highest_price = price
                            logger.info(f"🟢 OVERDRIVE BUY {symbol} @ {price} BTC")
                        except Exception as e: logger.error(f"❌ BUY ERROR {symbol}: {e}")

                elif state.in_position:
                    if price > state.highest_price: state.highest_price = price
                    pnl = (price - state.entry_price) / state.entry_price
                    trail = (state.highest_price - price) / state.highest_price
                    
                    should_sell = False
                    if pnl >= TAKE_PROFIT_PCT: should_sell = True
                    elif pnl <= -STOP_LOSS_PCT: should_sell = True
                    elif trail >= TRAILING_STOP_PCT and pnl > 0.005: should_sell = True
                    
                    if should_sell:
                        try:
                            client.create_order(symbol=symbol, side='SELL', type='MARKET', quantity=state.position_quantity)
                            logger.info(f"🔴 OVERDRIVE SELL {symbol} | PnL: {pnl:.2%}")
                            state.in_position = False
                            with open('/root/.openclaw/workspace/strike_alert.flag', 'w') as f:
                                f.write(f"{(state.position_quantity * price * pnl * 59500):.2f}")
                        except Exception as e: logger.error(f"❌ SELL ERROR {symbol}: {e}")
            
            time.sleep(SLEEP_TIME)
        except Exception as e:
            logger.error(f"Loop Error: {e}")
            time.sleep(30)

if __name__ == "__main__":
    main()
