"""One-shot: cancel ALL orders, check balance, transfer capital."""
import os, requests, hmac, hashlib, time, urllib.parse, base64

with open('/home/sergio/denaro/.env') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            os.environ[k.strip()] = v.strip()

API = os.environ['BINANCE_API_KEY']
SEC = os.environ['BINANCE_API_SECRET']

# Master key (base64 encoded)
M_API = base64.b64decode("aHZWYmZaeXZ3Vkt3cWpLcXo1dTAza0M3Vlg5YmV5YmhtMHhxRG5KVGVtOHUybmxLZU5hSjBwbHFHNGFJMHJXSg==").decode()
M_SEC = base64.b64decode("aG5VZm9pSFFFS2Y1ZVU2SjVFUTZTTlB6RU03SEhKSFkzYlNVdGJRWWFUSm5SaUR4Q2FRVWtubjk1cmRORTdSNA==").decode()

def signed_get(ep, params=None):
    params = params or {}
    params['timestamp'] = int(time.time() * 1000)
    qs = urllib.parse.urlencode(params)
    sig = hmac.new(SEC.encode(), qs.encode(), hashlib.sha256).hexdigest()
    return requests.get(f'https://api.binance.com{ep}?{qs}&signature={sig}',
                         headers={'X-MBX-APIKEY': API}, timeout=10).json()

def signed_delete(ep, params):
    params['timestamp'] = int(time.time() * 1000)
    qs = urllib.parse.urlencode(params)
    sig = hmac.new(SEC.encode(), qs.encode(), hashlib.sha256).hexdigest()
    return requests.delete(f'https://api.binance.com{ep}?{qs}&signature={sig}',
                           headers={'X-MBX-APIKEY': API}, timeout=10).json()

# 1. Cancel ALL open orders
print("=== CANCELING ALL ORDERS ===")
for sym in ['SOLUSDC', 'ADAUSDC', 'DOGEUSDC']:
    orders = signed_get('/api/v3/openOrders', {'symbol': sym})
    if isinstance(orders, list):
        for o in orders:
            r = signed_delete('/api/v3/order', {'symbol': sym, 'orderId': o['orderId']})
            print(f"  {sym} {o['side']} {o['origQty']} @{o['price']} -> {r.get('status', r.get('msg', 'OK'))}")

time.sleep(2)

# 2. Verify clean
print("\n=== VERIFYING ===")
for sym in ['SOLUSDC', 'ADAUSDC', 'DOGEUSDC']:
    orders = signed_get('/api/v3/openOrders', {'symbol': sym})
    count = len(orders) if isinstance(orders, list) else 0
    print(f"  {sym}: {count} open")

# 3. Check balance
acct = signed_get('/api/v3/account')
usdc_free = sum(float(b['free']) for b in acct['balances'] if b['asset'] == 'USDC')
usdc_locked = sum(float(b['locked']) for b in acct['balances'] if b['asset'] == 'USDC')
print(f"\n  USDC: free=${usdc_free:.2f} locked=${usdc_locked:.2f}")

# 4. Universal Transfer
print("\n=== UNIVERSAL TRANSFER ===")
def master_post(ep, params):
    params['timestamp'] = str(int(time.time() * 1000))
    qs = urllib.parse.urlencode(params)
    sig = hmac.new(M_SEC.encode(), qs.encode(), hashlib.sha256).hexdigest()
    return requests.post(f'https://api.binance.com{ep}?{qs}&signature={sig}',
                         headers={'X-MBX-APIKEY': M_API}, timeout=10).json()

mc2_email = "mc2orion_virtual@85origvknoemail.com"
targets = {
    "nuvolatrading_virtual@2lyv5fu2noemail.com": ("nuvola", 45),
    "marcodg1marcosol_virtual@pwomuqu6noemail.com": ("marcodg1", 45),
}

for email, (name, amount) in targets.items():
    r = master_post('/sapi/v1/sub-account/universalTransfer', {
        'fromEmail': mc2_email, 'toEmail': email,
        'fromAccountType': 'SPOT', 'toAccountType': 'SPOT',
        'asset': 'USDC', 'amount': amount
    })
    ok = r.get('tranId', 0) > 0
    print(f"  -> {name}: ${amount} {'OK tranId='+str(r.get('tranId')) if ok else 'FAIL: '+r.get('msg','?')}")

print("\n=== DONE ===")
