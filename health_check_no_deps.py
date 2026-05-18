import sys
sys.path.insert(0, '/home/sergio/denaro/venv/lib/python3.12/site-packages')

# Skip dateparser import; directly access binance
from binance.client import Client
import os

# Read API keys from .env
env_path = os.path.expanduser('~/denaro/.env')
with open(env_path, 'r') as f:
    for line in f:
        line = line.strip()
        if line.startswith('BINANCE_API_KEY='):
            api_key = line.split('=', 1)[1]
        elif line.startswith('BINANCE_API_SECRET='):
            api_secret = line.split('=', 1)[1]

# Initialize client
client = Client(api_key, api_secret)
print('Client initialized successfully')