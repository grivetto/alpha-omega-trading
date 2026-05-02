#!/usr/bin/env python3
"""
tools/fetch_node_balances.py
Fetch Binance balances for a node.
Usage: fetch_node_balances.py [env_path]
Output: JSON {eur, usdt, sol, bnb, error}
"""
import sys
import json
import subprocess

def main():
    env_path = sys.argv[1] if len(sys.argv) > 1 else "/home/sergio/denaro/.env"
    
    code = """
import ccxt, os, json
from dotenv import load_dotenv
load_dotenv('{}')
c = ccxt.binance({{
    'apiKey': os.getenv('BINANCE_API_KEY'),
    'secret': os.getenv('BINANCE_API_SECRET'),
    'enableRateLimit': True,
    'options': {{'defaultType': 'spot', 'defaultFeeCurrency': 'BNB'}}
}})
try:
    b = c.fetch_balance()
    result = {{
        'eur': round(b['free'].get('EUR', 0), 2),
        'usdt': round(b['free'].get('USDT', 0), 2),
        'sol': round(b['free'].get('SOL', 0), 6),
        'bnb': round(b['free'].get('BNB', 0), 4)
    }}
    print(json.dumps(result))
except Exception as e:
    print(json.dumps({{'error': str(e)}}))
""".format(env_path)
    
    try:
        result = subprocess.run(
            ["python3", "-c", code],
            capture_output=True, text=True, timeout=15,
            cwd="/home/sergio/denaro"
        )
        data = json.loads(result.stdout.strip())
        print(json.dumps(data))
    except Exception as e:
        print(json.dumps({"error": str(e)}))

if __name__ == "__main__":
    main()
