import ccxt, os
from dotenv import load_dotenv

load_dotenv('/home/sergio/denaro/.env')

ex = ccxt.binance({
    'apiKey': os.getenv('BINANCE_API_KEY'),
    'secret': os.getenv('BINANCE_API_SECRET'),
    'enableRateLimit': True
})

print('Annullamento ordini aperti...')
orders = ex.fetch_open_orders('BTC/EUR')
print(f'Trovati {len(orders)} ordini')

for o in orders:
    try:
        ex.cancel_order(o['id'], 'BTC/EUR')
        print(f"Cancellato: {o.get('side', '?')} @ {o.get('price', '?')}")
    except Exception as e:
        print(f"Errore: {e}")

print('Ordini annullati. Riavvio grid...')