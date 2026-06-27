#!/usr/bin/env python3
"""
TOOL: portfolio_tracker
Layer 3 — Full portfolio accounting including ALL crypto assets
"""
import sys
import json
import sqlite3
import ccxt
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent.parent / "trades.db"
ENV_PATH = Path(__file__).parent.parent / ".env"

# Assets to track for full portfolio valuation
TRACKED_ASSETS = [
    'EUR', 'BTC', 'ETH', 'BNB', 'SOL', 'ATOM', 'DOT', 'APT',
    'ADA', 'LINK', 'XRP', 'AVAX', 'NEAR', 'DOGE', 'USDC', 'USDT',
]

def get_client():
    from dotenv import load_dotenv
    load_dotenv(ENV_PATH)
    return ccxt.binance({
        'apiKey': __import__('os').getenv('BINANCE_API_KEY'),
        'secret': __import__('os').getenv('BINANCE_API_SECRET'),
        'enableRateLimit': True,
        'options': {'defaultType': 'spot'},
    })

def get_balances(client):
    """Fetch all balances and live prices for full portfolio."""
    bal = client.fetch_balance()
    prices = {}

    # Fetch EUR/USD for USDT/USDC conversion
    try:
        eurusd = client.fetch_ticker('EUR/USDT')['last']
    except:
        eurusd = 0.92  # fallback

    # Fetch prices for all tracked assets
    for sym in TRACKED_ASSETS:
        if sym in ['EUR', 'USDT', 'USDC']:
            prices[sym] = 1.0 / eurusd if sym != 'EUR' else 1.0
            continue
        try:
            t = client.fetch_ticker(f"{sym}/EUR")
            prices[sym] = t['last']
        except:
            try:
                t = client.fetch_ticker(f"{sym}/USDT")
                prices[sym] = t['last'] * eurusd
            except:
                prices[sym] = 0

    # Build balance dict including locked amounts
    result = {}
    for sym in TRACKED_ASSETS:
        free = bal['free'].get(sym, 0) if sym in bal['free'] else 0
        used = bal.get('used', {}).get(sym, 0) if isinstance(bal.get('used'), dict) else 0
        total = free + used
        if total > 0:
            result[sym] = {'free': free, 'locked': used, 'price': prices.get(sym, 0)}

    result['prices'] = prices
    result['eurusd'] = eurusd
    return result

def get_portfolio_summary(balances, state):
    """Calculate full portfolio value including ALL crypto assets."""
    eurusd = balances.get('eurusd', 0.92)

    # Sum all asset values in EUR
    total_eur = 0.0
    components = {}
    for sym, data in balances.items():
        if sym in ['prices', 'eurusd'] or not isinstance(data, dict):
            continue
        price = data.get('price', 0)
        total_hold = data.get('free', 0) + data.get('locked', 0)
        if total_hold <= 0 or price <= 0:
            continue
        val = total_hold * price
        total_eur += val
        components[sym] = round(val, 2)

    # Separate EUR component (this is the trading capital)
    eur_balance = balances.get('EUR', {})
    eur_free = eur_balance.get('free', 0) if isinstance(eur_balance, dict) else 0
    eur_locked = eur_balance.get('locked', 0) if isinstance(eur_balance, dict) else 0
    eur_total = eur_free + eur_locked

    # Peak tracking
    peak = state.get('accounting', {}).get('peak_portfolio_eur', total_eur)
    if total_eur > peak:
        peak = total_eur

    drawdown = ((peak - total_eur) / peak * 100) if peak > 0 else 0

    total_invested = state.get('accounting', {}).get('total_invested_eur', 0)
    total_fees = state.get('accounting', {}).get('total_fees_eur', 0)
    net_pnl = state.get('accounting', {}).get('net_pnl_eur', 0)

    return {
        "total_eur": round(total_eur, 2),
        "eur_free": round(eur_free, 2),
        "eur_locked": round(eur_locked, 2),
        "eur_total": round(eur_total, 2),
        "crypto_total": round(total_eur - eur_total, 2),
        "components": components,
        "peak_eur": round(peak, 2),
        "drawdown_pct": round(drawdown, 2),
        "total_invested_eur": round(total_invested, 2),
        "total_fees_eur": round(total_fees, 2),
        "net_pnl_eur": round(net_pnl, 2),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "get_summary"
    client = get_client()

    if action == "get_balances":
        print(json.dumps(get_balances(client)))
    elif action == "get_summary":
        from tools.state_manager import read_state
        state = read_state() or {}
        balances = get_balances(client)
        summary = get_portfolio_summary(balances, state)
        print(json.dumps(summary, indent=2))
    else:
        print(json.dumps({"error": f"Unknown action: {action}"}))

if __name__ == "__main__":
    main()
