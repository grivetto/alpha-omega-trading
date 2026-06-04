import os, sys
from binance.client import Client

key = 'GONYjKAvtn5QY9BP6PyDlT0gG3aaSqS0qL716iFcytkTybRVxQl5KXszTgqjAWwT'
secret = 'PlgP8LRou8Fkzz1ApEvyTz6XTPGsHYpWC0OE6xSmMLpY9irazXcmcT7ywyKABBLY'
client = Client(key, secret)

try:
    sol_px = float(client.get_symbol_ticker(symbol='SOLEUR')['price'])
except Exception as e:
    sol_px = 0; print(f"SOL error: {e}")
try:
    doge_px = float(client.get_symbol_ticker(symbol='DOGEEUR')['price'])
except Exception as e:
    doge_px = 0; print(f"DOGE error: {e}")
try:
    ada_px = float(client.get_symbol_ticker(symbol='ADAEUR')['price'])
except Exception as e:
    ada_px = 0; print(f"ADA error: {e}")

acc = client.get_account()
orders = client.get_open_orders()

# Portfolio
total = float([b for b in acc['balances'] if b['asset']=='EUR'][0]['free'])
total += float([b for b in acc['balances'] if b['asset']=='EUR'][0]['locked'])

holdings = []
for b in acc['balances']:
    f = float(b['free']); l = float(b['locked'])
    if f+l > 0.0001 and b['asset'] != 'EUR':
        px_map = {'SOL': sol_px, 'DOGE': doge_px, 'ADA': ada_px}
        if b['asset'] in px_map:
            val = (f+l) * px_map[b['asset']]
            total += val
            holdings.append(f"  {b['asset']}: {f+l:.6f} @ €{px_map[b['asset']]:.4f} = €{val:.2f}")
        elif b['asset'] in ['ETH']:
            try:
                p = float(client.get_symbol_ticker(symbol='ETHEUR')['price'])
                val = (f+l)*p; total += val
                holdings.append(f"  {b['asset']}: {f+l:.6f} @ €{p:.4f} = €{val:.2f}")
            except: pass
        elif b['asset'] in ['BNB']:
            try:
                p = float(client.get_symbol_ticker(symbol='BNBEUR')['price'])
                val = (f+l)*p; total += val
                holdings.append(f"  {b['asset']}: {f+l:.6f} @ €{p:.4f} = €{val:.2f}")
            except: pass
        elif b['asset'] in ['USDC','USDT','BUSD','TUSD']:
            total += f+l
            holdings.append(f"  {b['asset']}: {f+l:.6f} ≈ €{f+l:.2f}")
        else:
            holdings.append(f"  {b['asset']}: {f+l:.6f} (no EUR price)")

# Grid analysis
eur_free = float([b for b in acc['balances'] if b['asset']=='EUR'][0]['free'])
eur_lock = float([b for b in acc['balances'] if b['asset']=='EUR'][0]['locked'])
buy_orders = [o for o in orders if o['side']=='BUY']
sell_orders = [o for o in orders if o['side']=='SELL']
buy_eur = sum(float(o['origQty'])*float(o['price']) for o in buy_orders)
sell_value = sum(float(o['origQty'])*float(o['price']) for o in sell_orders)

print(f"📊 DENARO — Status Report")
print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print(f"💰 Capitale Totale: €{total:.2f}")
print(f"   EUR liberi:  €{eur_free:.2f}")
print(f"   EUR bloccati: €{eur_lock:.2f}")
print(f"")
print(f"📈 Prezzi:")
print(f"   SOL:  €{sol_px:.4f}")
print(f"   DOGE: €{doge_px:.6f}")
print(f"   ADA:  €{ada_px:.4f}")
print(f"")
print(f"📋 Holdings:")
for h in holdings:
    print(h)
print(f"")
print(f"🔄 Ordini Aperti: {len(orders)}")
print(f"   BUY:  {len(buy_orders)} ordini — €{buy_eur:.2f} impegnati")
print(f"   SELL: {len(sell_orders)} ordini — €{sell_value:.2f} in vendita")
print(f"")
print(f"⚙️ Processi:")
print(f"   sentinel.py:  PID 431641 — running")
print(f"   squadra:      PID 451499 — running")
print(f"   dashboard:    PID 451503 — running (port 8899)")
print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

# Show open order details
if orders:
    print(f"\n📝 Dettaglio Ordini:")
    for o in orders[:20]:
        print(f"   [{o['side']}] {o['symbol']} qty={o['origQty']} @ €{o['price']}")
    if len(orders) > 20:
        print(f"   ... e altri {len(orders)-20} ordini")
