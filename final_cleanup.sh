#!/bin/bash
set -e

echo "=== STOPPING ALL DENARO SERVICES ==="
for svc in $(systemctl list-units --type=service --no-pager | grep denaro | awk '{print $1}'); do
    systemctl stop $svc 2>/dev/null || true
    systemctl disable $svc 2>/dev/null || true
    echo "  Stopped: $svc"
done

echo "=== KILLING ALL PYTHON DENARO PROCESSES ==="
pkill -9 -f "denaro" 2>/dev/null || true
sleep 2

echo "=== CANCELING ALL ORDERS ==="
cd /home/sergio/denaro
for sym in SOLUSDC ADAUSDC DOGEUSDC; do
    ./venv/bin/python3 -c "
import os,requests,hmac,hashlib,time,urllib.parse
with open('.env') as f:
    for l in f:
        l=l.strip()
        if l and not l.startswith('#') and '=' in l:
            k,v=l.split('=',1); os.environ[k.strip()]=v.strip()
a=os.environ['BINANCE_API_KEY']; s=os.environ['BINANCE_API_SECRET']
def sd(ep,params):
    params['timestamp']=int(time.time()*1000)
    qs=urllib.parse.urlencode(params); sig=hmac.new(s.encode(),qs.encode(),hashlib.sha256).hexdigest()
    return requests.delete(f'https://api.binance.com{ep}?{qs}&signature={sig}',headers={'X-MBX-APIKEY':a},timeout=10).json()
orders=requests.get(f'https://api.binance.com/api/v3/openOrders?symbol={sym}',headers={'X-MBX-APIKEY':a},timeout=10).json()
if isinstance(orders,list):
    for o in orders:
        sd('/api/v3/order',{'symbol':sym,'orderId':o['orderId']})
        print(f'  Cancelled {sym} {o[\"side\"]} {o[\"origQty\"]}')
else:
    print(f'  {sym}: no orders')
" 2>/dev/null
done

sleep 3

echo "=== VERIFYING NO OPEN ORDERS ==="
./venv/bin/python3 -c "
import os,requests
with open('.env') as f:
    for l in f:
        l=l.strip()
        if l and not l.startswith('#') and '=' in l:
            k,v=l.split('=',1); os.environ[k.strip()]=v.strip()
a=os.environ['BINANCE_API_KEY']
for sym in ['SOLUSDC','ADAUSDC','DOGEUSDC']:
    o=requests.get(f'https://api.binance.com/api/v3/openOrders?symbol={sym}',headers={'X-MBX-APIKEY':a},timeout=10).json()
    if isinstance(o,list) and o:
        print(f'  WARN: {sym} STILL HAS {len(o)} orders')
    else:
        print(f'  {sym}: CLEAN')
"

echo "=== CHECKING FREE USDC ==="
./venv/bin/python3 -c "
import os,requests,hmac,hashlib,time,urllib.parse
with open('.env') as f:
    for l in f:
        l=l.strip()
        if l and not l.startswith('#') and '=' in l:
            k,v=l.split('=',1); os.environ[k.strip()]=v.strip()
a=os.environ['BINANCE_API_KEY']; s=os.environ['BINANCE_API_SECRET']
p={'timestamp':int(time.time()*1000)}
qs=urllib.parse.urlencode(p); sig=hmac.new(s.encode(),qs.encode(),hashlib.sha256).hexdigest()
acct=requests.get(f'https://api.binance.com/api/v3/account?{qs}&signature={sig}',headers={'X-MBX-APIKEY':a},timeout=10).json()
usdc_free=sum(float(b['free']) for b in acct['balances'] if b['asset']=='USDC')
usdc_locked=sum(float(b['locked']) for b in acct['balances'] if b['asset']=='USDC')
print(f'  USDC free={usdc_free:.2f} locked={usdc_locked:.2f}')
"
