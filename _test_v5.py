#!/usr/bin/env python3
"""Quick mock test for Denaro v5."""
import sys, os
sys.path.insert(0, '.')

os.environ['MOCK_MODE'] = '1'
os.environ['SHADOW_MODE'] = '0'
os.environ['CAPITAL'] = '100'
os.environ['LEVELS'] = '3'
os.environ['COOLDOWN'] = '1'
os.environ['BALANCE_CACHE_TTL'] = '5'
os.environ['ORDERS_CACHE_TTL'] = '3'

from mock_runner import run_mock_test
result = run_mock_test(cycles=50, verbose=True)
print('\n=== MOCK TEST RESULT ===')
for k, v in result.items():
    print(f'  {k}: {v}')
