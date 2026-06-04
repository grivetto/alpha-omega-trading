#!/usr/bin/env python3
"""
MC2 Scalper Bot — ETH/EUR (DIVERSIFIED)
EMA 9/26 + RSI 14, SL 1.5%, TP 3%, max 1 posizione
Diversificato da Nuvola (SOL/EUR) e MARCODG1 (ADA/EUR)
"""
import os, sys, time, logging
from pathlib import Path
from dotenv import load_dotenv
import ccxt

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('mc2_scalper.log')
    ]
)
log = logging.getLogger('MC2')

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / '.env')

API_KEY = os.getenv('BINANCE_API_KEY', '')
API_SECRET = os.getenv('BINANCE_API_SECRET', '')
SYMBOL = os.getenv('SCALPER_SYMBOL', 'ETH/EUR')
CAPITAL = float(os.getenv('TOTAL_CAPITAL_EUR', '17.0'))
MAX_DD = float(os.getenv('MAX_DAILY_LOSS_PCT', '5.0')) / 100
DRY_RUN = os.getenv('DRY_RUN', 'false').lower() == 'true'

if not API_KEY or not API_SECRET:
    log.error('Missing API keys in .env')
    sys.exit(1)

ex = ccxt.binance({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'options': {'defaultType': 'spot'},
    'enableRateLimit': True
})

def get_balance():
    bal = ex.fetch_balance()
    return bal['free'].get('EUR', 0)

def get_price():
    return ex.fetch_ticker(SYMBOL)['last']

def get_ema(period):
    ohlcv = ex.fetch_ohlcv(SYMBOL, '5m', limit=period + 10)
    closes = [c[4] for c in ohlcv]
    if len(closes) < period:
        return None
    k = 2 / (period + 1)
    ema = closes[0]
    for c in closes[1:]:
        ema = c * k + ema * (1 - k)
    return ema

def get_rsi(period=14):
    ohlcv = ex.fetch_ohlcv(SYMBOL, '5m', limit=period + 20)
    closes = [c[4] for c in ohlcv]
    if len(closes) < period + 1:
        return 50
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i-1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100
    return 100 - (100 / (1 + avg_gain / avg_loss))

def place_buy(eur_amount):
    price = get_price()
    qty = round(eur_amount / price, 4)
    if DRY_RUN:
        log.info(f'DRY-RUN BUY {qty} {SYMBOL} @ {price}')
        return {'id': 'dry-run', 'price': price, 'qty': qty}
    try:
        return ex.create_market_buy_order(SYMBOL, qty)
    except Exception as e:
        log.error(f'BUY error: {e}')
        return None

def place_sell(qty):
    price = get_price()
    if DRY_RUN:
        log.info(f'DRY-RUN SELL {qty} {SYMBOL} @ {price}')
        return {'id': 'dry-run'}
    try:
        return ex.create_market_sell_order(SYMBOL, qty)
    except Exception as e:
        log.error(f'SELL error: {e}')
        return None

def main():
    log.info(f'MC2 Scalper started | {SYMBOL} | capital={CAPITAL}€ | dry_run={DRY_RUN}')
    
    position = None
    daily_pnl = 0
    max_loss_eur = CAPITAL * MAX_DD
    
    while True:
        try:
            eur = get_balance()
            price = get_price()
            ema9 = get_ema(9)
            ema26 = get_ema(26)
            rsi = get_rsi(14)
            
            log.info(f'EUR={eur:.2f} | {SYMBOL}={price:.2f} | EMA9={ema9:.2f} EMA26={ema26:.2f} | RSI={rsi:.1f} | pos={position is not None}')
            
            if daily_pnl < -max_loss_eur:
                log.critical(f'KILL SWITCH: loss {daily_pnl:.2f} < -{max_loss_eur:.2f}')
                if position:
                    place_sell(position['qty'])
                break
            
            if position:
                pnl_pct = (price - position['buy_price']) / position['buy_price']
                if pnl_pct <= -0.015:  # SL 1.5%
                    log.warning(f'SL hit at {pnl_pct:.2%}')
                    sell_order = place_sell(position['qty'])
                    if sell_order:
                        daily_pnl += position['qty'] * (price - position['buy_price'])
                        position = None
                elif pnl_pct >= 0.03:  # TP 3%
                    log.info(f'TP hit at {pnl_pct:.2%}')
                    sell_order = place_sell(position['qty'])
                    if sell_order:
                        daily_pnl += position['qty'] * (price - position['buy_price'])
                        position = None
            else:
                # Entry: EMA9 > EMA26 (bullish) + RSI < 35 (oversold) + EUR >= 5
                if ema9 and ema26 and ema9 > ema26 and rsi < 35 and eur >= 5:
                    trade_eur = min(eur * 0.4, 8)  # max 40% o 8€
                    if trade_eur >= 5:
                        order = place_buy(trade_eur)
                        if order:
                            position = {
                                'qty': order.get('qty', trade_eur / price),
                                'buy_price': price,
                                'sl': price * 0.985,
                                'tp': price * 1.03
                            }
                            log.info(f'Position: {position}')
            
            time.sleep(30)
            
        except KeyboardInterrupt:
            log.info('Shutting down...')
            if position:
                place_sell(position['qty'])
            break
        except Exception as e:
            log.error(f'Error: {e}')
            time.sleep(60)

if __name__ == '__main__':
    main()