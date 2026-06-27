#!/usr/bin/env python3
"""
tools/atr_calculator.py
Calculate ATR for dynamic grid spacing.
Usage: atr_calculator.py [symbol] [timeframe] [lookback] [multiplier] [min] [max]
Output: JSON {atr, atr_pct, current_price, grid_spacing_pct}
"""
import sys
import json
import ccxt
import os
from dotenv import load_dotenv

def main():
    load_dotenv('/home/sergio/denaro/.env')
    
    symbol = sys.argv[1] if len(sys.argv) > 1 else "SOL/EUR"
    timeframe = sys.argv[2] if len(sys.argv) > 2 else "1h"
    lookback = int(sys.argv[3]) if len(sys.argv) > 3 else 14
    multiplier = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0
    min_spacing = float(sys.argv[5]) if len(sys.argv) > 5 else 0.005
    max_spacing = float(sys.argv[6]) if len(sys.argv) > 6 else 0.03
    
    try:
        c = ccxt.binance({
            'apiKey': os.getenv('BINANCE_API_KEY'),
            'secret': os.getenv('BINANCE_API_SECRET'),
            'enableRateLimit': True
        })
        
        ohlcv = c.fetch_ohlcv(symbol, timeframe=timeframe, limit=lookback+1)
        if len(ohlcv) < lookback:
            print(json.dumps({'error': f'Insufficient data: {len(ohlcv)} candles'}))
            return
        
        trs = []
        for i in range(1, len(ohlcv)):
            high = ohlcv[i][2]
            low = ohlcv[i][3]
            prev_close = ohlcv[i-1][4]
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            trs.append(tr)
        
        atr = sum(trs) / len(trs)
        current_price = ohlcv[-1][4]
        atr_pct = atr / current_price
        grid_spacing_pct = max(min_spacing, min(max_spacing, atr_pct * multiplier))
        per_level = grid_spacing_pct / 6
        
        result = {
            'atr': round(atr, 4),
            'atr_pct': round(atr_pct, 4),
            'current_price': round(current_price, 2),
            'grid_spacing_pct': round(grid_spacing_pct, 4),
            'per_level_spacing_pct': round(per_level, 4),
            'num_levels': 6,
            'symbol': symbol,
            'timeframe': timeframe
        }
        print(json.dumps(result, indent=2))
        
    except Exception as e:
        print(json.dumps({'error': str(e)}))

if __name__ == "__main__":
    main()
