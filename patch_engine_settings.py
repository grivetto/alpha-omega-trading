#!/usr/bin/env python3
"""Patch engine.py to add settings for BTC/USDT and ETH/USDT strategies"""

import os
import sys

# Read the engine.py file
with open('/home/sergio/denaro/core/engine.py', 'r') as f:
    lines = f.readlines()

# Find the Settings class definition
settings_class_start = None
settings_class_end = None
for i, line in enumerate(lines):
    if '@dataclass' in line and 'class Settings:' in lines[i+1]:
        settings_class_start = i+1
        break

if settings_class_start is not None:
    # Find the end of the Settings class (next @dataclass or class or end of file)
    for i in range(settings_class_start+1, len(lines)):
        if '@dataclass' in lines[i] or (lines[i].startswith('class ') and 'Settings' not in lines[i]) or i == len(lines)-1:
            settings_class_end = i
            break
    
    if settings_class_end is None:
        settings_class_end = len(lines)
    
    # Define the new settings to add
    new_settings = [
        '    # BTC/USDT Grid Settings\n',
        '    btc_grid_symbol: str = field(default_factory=lambda: _env(\"BTC_GRID_SYMBOL\", \"BTC/USDT\"))\n',
        '    btc_grid_capital_usdt: float = field(default_factory=lambda: _float(\"BTC_GRID_CAPITAL_USDT\", 5.0))\n',
        '    btc_grid_levels: int = field(default_factory=lambda: _int(\"BTC_GRID_LEVELS\", 3))\n',
        '    btc_grid_spacing_pct: float = field(default_factory=lambda: _float(\"BTC_GRID_SPACING_PCT\", 0.01))\n',
        '    btc_grid_take_pct: float = field(default_factory=lambda: _float(\"BTC_GRID_TAKE_PCT\", 0.8))\n',
        '    btc_grid_trailing_stop: bool = field(default_factory=lambda: _bool(\"BTC_GRID_TRAILING_STOP\", True))\n',
        '\n',
        '    # ETH/USDT Grid Settings\n',
        '    eth_grid_symbol: str = field(default_factory=lambda: _env(\"ETH_GRID_SYMBOL\", \"ETH/USDT\"))\n',
        '    eth_grid_capital_usdt: float = field(default_factory=lambda: _float(\"ETH_GRID_CAPITAL_USDT\", 3.0))\n',
        '    eth_grid_levels: int = field(default_factory=lambda: _int(\"ETH_GRID_LEVELS\", 3))\n',
        '    eth_grid_spacing_pct: float = field(default_factory=lambda: _float(\"ETH_GRID_SPACING_PCT\", 0.015))\n',
        '    eth_grid_take_pct: float = field(default_factory=lambda: _float(\"ETH_GRID_TAKE_PCT\", 0.9))\n',
        '    eth_grid_trailing_stop: bool = field(default_factory=lambda: _bool(\"ETH_GRID_TRAILING_STOP\", True))\n',
        '\n',
        '    # RSI Settings for BTC/ETH\n',
        '    btc_rsi_symbol: str = field(default_factory=lambda: _env(\"BTC_RSI_SYMBOL\", \"BTC/USDT\"))\n',
        '    btc_rsi_capital_usdt: float = field(default_factory=lambda: _float(\"BTC_RSI_CAPITAL_USDT\", 2.0))\n',
        '    eth_rsi_symbol: str = field(default_factory=lambda: _env(\"ETH_RSI_SYMBOL\", \"ETH/USDT\"))\n',
        '    eth_rsi_capital_usdt: float = field(default_factory=lambda: _float(\"ETH_RSI_CAPITAL_USDT\", 1.5))\n',
        '\n',
        '    # Feature flags for new strategies\n',
        '    enable_btc_grid: bool = field(default_factory=lambda: _bool(\"ENABLE_BTC_GRID\", True))\n',
        '    enable_eth_grid: bool = field(default_factory=lambda: _bool(\"ENABLE_ETH_GRID\", True))\n',
        '    enable_btc_rsi: bool = field(default_factory=lambda: _bool(\"ENABLE_BTC_RSI\", True))\n',
        '    enable_eth_rsi: bool = field(default_factory=lambda: _bool(\"ENABLE_ETH_RSI\", True))\n',
        '\n'
    ]
    
    # Insert the new settings before the closing of the Settings class
    # We'll insert them right before the last line of the class
    lines = lines[:settings_class_end] + new_settings + lines[settings_class_end:]
    
    # Write the modified file
    with open('/home/sergio/denaro/core/engine.py', 'w') as f:
        f.writelines(lines)
    
    print("ENGINE_PATCHED_WITH_NEW_SETTINGS")
else:
    print("ERROR: Could not find Settings class definition")