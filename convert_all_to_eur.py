#!/usr/bin/env python3
"""Vendi TUTTI gli asset per EUR (conti MiCA Binance Italia)."""
import ccxt, os, time, sys
from dotenv import load_dotenv

env_path = os.path.expanduser('~/denaro/.env')
load_dotenv(env_path)

exchange = ccxt.binance({
    'apiKey': os.getenv('BINANCE_API_KEY'),
    'secret': os.getenv('BINANCE_API_SECRET'),
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'}
})

# Verify EUR pairs work
try:
    perm = exchange.sapiGetAccountApiRestrictions()
    can_trade = perm.get('enableSpotAndMarginTrading', False)
    print(f"Permessi trading spot: {'✓' if can_trade else '✗'}")
except Exception as e:
    print(f"Permessi: {e}")

tickers = exchange.fetch_tickers()
balance = exchange.fetch_balance()
total = balance.get('total', {})

# Only try assets that have an EUR pair
assets = [(a, float(v)) for a, v in total.items() if float(v) > 0.000001 and a not in ('USDT', 'EUR')]

print(f"\n=== VENDO TUTTO PER EUR ===")

sold_count = 0
sold_value = 0

for asset, qty in sorted(assets, key=lambda x: -float(x[1])):
    pair = f'{asset}/EUR'
    price_info = tickers.get(pair, {})
    price = price_info.get('last') if price_info else 0
    if not price:
        # Try alternative: maybe asset needs to be sold to USDT first? No, use EUR directly
        print(f"  ✗ {asset}: nessun prezzo EUR trovato, skip")
        continue
    
    val = qty * price
    if val < 0.5:
        print(f"  ✗ {asset}: {qty} ≈ €{val:.2f} (dust, skip)")
        continue
    
    try:
        market = exchange.market(pair)
        prec_amt = market['precision']['amount']
        
        # Calculate decimal precision
        if prec_amt >= 1:
            prec = int(prec_amt)
        else:
            prec_str = f"{prec_amt:.10f}".rstrip('0')
            prec = len(prec_str.split('.')[1]) if '.' in prec_str else 0
        
        qty_sell = round(qty, prec)
        if qty_sell <= 0:
            print(f"  ✗ {asset}: qty troppo piccola dopo arrotondamento")
            continue
        
        # Check min notional
        min_notional = market.get('limits', {}).get('cost', {}).get('min', 0) or 0
        if min_notional > 0 and qty_sell * price < min_notional:
            print(f"  ✗ {asset}: €{qty_sell*price:.2f} < minimo €{min_notional}, skip")
            continue
        
        print(f"  → {pair}: vendendo {qty_sell} (€{val:.2f})...", end=' ', flush=True)
        order = exchange.create_market_sell_order(pair, qty_sell)
        sold_count += 1
        sold_value += val
        print(f"✓ order {order['id'][:10]}")
        time.sleep(0.3)
    except ccxt.InsufficientFunds:
        print(f"✗ saldo insufficiente")
    except ccxt.BadSymbol:
        print(f"✗ pair non esiste")
    except Exception as e:
        err = str(e)
        if 'not permitted' in err.lower():
            print(f"✗ non permesso (forse solo USDT?)")
        elif 'balance' in err.lower() or 'funds' in err.lower():
            print(f"✗ saldo insufficiente")
        else:
            print(f"✗ {err[:120]}")

time.sleep(2)
balance2 = exchange.fetch_balance()
final_eur = float(balance2.get('EUR', {}).get('total', 0))
final_usdt = float(balance2.get('USDT', {}).get('total', 0))
remaining = [(a, float(balance2.get('total', {}).get(a, 0))) for a in balance2.get('total', {}) 
             if float(balance2.get('total', {}).get(a, 0)) > 0.000001 and a not in ('USDT', 'EUR')]

print(f"\n{'='*50}")
print(f"VENDITE COMPLETATE: {sold_count}")
print(f"VALORE VENDUTO: €{sold_value:.2f}")
print(f"EUR FINALE: €{final_eur:.2f}")
print(f"USDT RIMASTO: ${final_usdt:.2f}")
if remaining:
    print(f"REMANENTI ({len(remaining)}):")
    for a, v in remaining:
        print(f"  {a}: {v}")
else:
    print("TUTTO VENDUTO IN EUR! 🎉")
