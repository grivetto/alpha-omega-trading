import os
from binance.client import Client

key = 'GONYjKAvtn5QY9BP6PyDlT0gG3aaSqS0qL716iFcytkTybRVxQl5KXszTgqjAWwT'
secret = 'PlgP8LRou8Fkzz1ApEvyTz6XTPgsHYpWC0OE6xSmMLpY9irazXcmcT7ywyKABBLY'
client = Client(key, secret)

# get prices
sol_px = float(client.get_symbol_ticker(symbol='SOLEUR')['price'])
doge_px = float(client.get_symbol_ticker(symbol='DOGEEUR')['price'])
ada_px = float(client.get_symbol_ticker(symbol='ADAEUR')['price'])

acc = client.get_account()
orders = client.get_open_orders()

# Portfolio
total = 0.0
eur_bal = [b for b in acc['balances'] if b['asset']=='EUR'][0]
total += float(eur_bal['free']) + float(eur_bal['locked'])
for b in acc['balances']:
    f = float(b['free']); l = float(b['locked'])
    if f+l > 0:
        asset = b['asset']
        if asset == 'SOL': total += (f+l)*sol_px
        elif asset == 'DOGE': total += (f+l)*doge_px
        elif asset == 'ADA': total += (f+l)*ada_px
        elif asset == 'ETH': 
            try: total += (f+l)*float(client.get_symbol_ticker(symbol='ETHEUR')['price'])
            except: pass
        elif asset == 'BNB': 
            try: total += (f+l)*float(client.get_symbol_ticker(symbol='BNBEUR')['price'])
            except: pass
        elif asset == 'USDC': total += f+l

# Grid analysis
eur_free = float([b for b in acc['balances'] if b['asset']=='EUR'][0]['free'])
eur_lock = float([b for b in acc['balances'] if b['asset']=='EUR'][0]['locked'])
buy_eur = sum(float(o['origQty'])*float(o['price']) for o in orders if o['side']=='BUY')
sell_value = sum(float(o['origQty'])*float(o['price']) for o in orders if o['side']=='SELL')

msg = f"""DENARO Status Report

Capitale: €{total:.2f}
   EUR: €{eur_free:.2f} free, €{eur_lock:.2f} locked
   Buy EUR value: {buy_eur:.2f}
   Sell value: {sell_value:.2f}
"""

print(msg)