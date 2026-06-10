#!/usr/bin/env python3
"""
Hedger for Binance Futures - opens opposite position on futures to hedge spot fill.
Usage: python hedger_futures.py SYMBOL SIDE SIZE
Example: python hedger_futures.py BTC/USDT buy 0.001
"""
import os
import sys
import asyncio
import ccxt.pro as ccxt

API_KEY = os.getenv('BINANCE_FUTURES_API_KEY')
API_SECRET = os.getenv('BINANCE_FUTURES_API_SECRET')

if not API_KEY or not API_SECRET:
    print('ERROR: Binance Futures API keys not found. Set BINANCE_FUTURES_API_KEY and BINANCE_FUTURES_API_SECRET.')
    sys.exit(1)

async def hedge(symbol: str, side: str, size: float):
    """Open a market order on futures opposite to the spot side."""
    # Map spot side to opposite futures side
    futures_side = 'sell' if side.lower() == 'buy' else 'buy'
    try:
        exchange = ccxt.binance({
            'apiKey': API_KEY,
            'secret': API_SECRET,
            'enableRateLimit': True,
            'options': {'defaultType': 'future'}
        })
        # Get market info for contract size
        market = exchange.market(symbol.replace('/', ''))  # e.g., BTC/USDT -> BTCUSDT
        contract_size = market['contractSize']  # amount of base currency per contract
        quantity = size / contract_size
        order = await exchange.create_order(
            symbol=symbol.replace('/', ''),  # futures symbol format
            type='market',
            side=futures_side,
            amount=quantity,
            params={'reduceOnly': False}
        )
        print(f'Hedged {side} {size} {symbol} on futures with {futures_side} {quantity} contracts. Order ID: {order["id"]}')
        return order
    except Exception as e:
        print(f'Error hedging {side} {size} {symbol}: {e}')
        return None

if __name__ == '__main__':
    if len(sys.argv) != 4:
        print('Usage: hedger_futures.py SYMBOL SIDE SIZE')
        print('Example: hedger_futures.py BTC/USDT buy 0.001')
        sys.exit(1)
    sym = sys.argv[1]
    side = sys.argv[2]
    try:
        sz = float(sys.argv[3])
    except ValueError:
        print('SIZE must be a number')
        sys.exit(1)
    asyncio.run(hedge(sym, side, sz))