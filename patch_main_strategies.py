#!/usr/bin/env python3
"""Patch main.py to add BTC/USDT and ETH/USDT grid and RSI strategies"""

import os
import sys

# Read the main.py file
with open('/home/sergio/denaro/main.py', 'r') as f:
    lines = f.readlines()

# Find the position to insert new strategy loading logic
# Look for the RSI Mean Reversion Strategy section
insert_pos = None
for i, line in enumerate(lines):
    if '# Load RSI Mean Reversion Strategy' in line:
        insert_pos = i
        break

if insert_pos is not None:
    # Insert new strategy loading logic after RSI section
    new_lines = [
        '\n',
        '        # Load BTC/USDT Grid Strategy\n        ',
        '        if settings.enable_btc_grid:\n        ',
        '            for ex_name, exchange in required_exchanges.items():\n        ',
        '                if exchange:\n        ',
        '                    try:\n        ',
        '                        # Load BTC/USDT Grid Strategy\n        ',
        '                        capital_setting = getattr(settings, f\'{ex_name.lower()}_btc_grid_capital_usdt\', settings.btc_grid_capital_usdt)\n        ',
        '                        grid_symbol = getattr(settings, f\'{ex_name.lower()}_btc_grid_symbol\', settings.btc_grid_symbol)\n        ',
        '                        grid_levels = getattr(settings, f\'{ex_name.lower()}_btc_grid_levels\', settings.btc_grid_levels)\n        ',
        '                        grid_spacing = getattr(settings, f\'{ex_name.lower()}_btc_grid_spacing_pct\', settings.btc_grid_spacing_pct)\n        ',
        '                        grid_take_profit = getattr(settings, f\'{ex_name.lower()}_btc_grid_take_pct\', settings.btc_grid_take_pct)\n        ',
        '                        grid_trailing_stop = getattr(settings, f\'{ex_name.lower()}_btc_grid_trailing_stop\', settings.btc_grid_trailing_stop)\n        ',
        '\n        ',
        '                        strategy = GridTraderStrategy(exchange, self.db, initial_capital=capital_setting, symbol=grid_symbol, levels=grid_levels, spacing_pct=grid_spacing, take_profit_pct=grid_take_profit, trailing_stop=grid_trailing_stop)\n        ',
        '                        await strategy.set_initial_capital(capital_setting)\n        ',
        '                        self.strategies.append(strategy)\n        ',
        '                        logger.info(f\"Loaded BTC/USDT Grid Strategy on exchange {ex_name} | Symbol: {grid_symbol} | Capital: {capital_setting:.2f} USDT | Levels: {grid_levels}\")\n        ',
        '                    except Exception as e:\n        ',
        '                        logger.error(f\"Failed to load BTC/USDT Grid Strategy on {ex_name}: {e}\")\n        ',
        '\n',
        '        # Load ETH/USDT Grid Strategy\n        ',
        '        if settings.enable_eth_grid:\n        ',
        '            for ex_name, exchange in required_exchanges.items():\n        ',
        '                if exchange:\n        ',
        '                    try:\n        ',
        '                        # Load ETH/USDT Grid Strategy\n        ',
        '                        capital_setting = getattr(settings, f\'{ex_name.lower()}_eth_grid_capital_usdt\', settings.eth_grid_capital_usdt)\n        ',
        '                        grid_symbol = getattr(settings, f\'{ex_name.lower()}_eth_grid_symbol\', settings.eth_grid_symbol)\n        ',
        '                        grid_levels = getattr(settings, f\'{ex_name.lower()}_eth_grid_levels\', settings.eth_grid_levels)\n        ',
        '                        grid_spacing = getattr(settings, f\'{ex_name.lower()}_eth_grid_spacing_pct\', settings.eth_grid_spacing_pct)\n        ',
        '                        grid_take_profit = getattr(settings, f\'{ex_name.lower()}_eth_grid_take_pct\', settings.eth_grid_take_pct)\n        ',
        '                        grid_trailing_stop = getattr(settings, f\'{ex_name.lower()}_eth_grid_trailing_stop\', settings.eth_grid_trailing_stop)\n        ',
        '\n        ',
        '                        strategy = GridTraderStrategy(exchange, self.db, initial_capital=capital_setting, symbol=grid_symbol, levels=grid_levels, spacing_pct=grid_spacing, take_profit_pct=grid_take_profit, trailing_stop=grid_trailing_stop)\n        ',
        '                        await strategy.set_initial_capital(capital_setting)\n        ',
        '                        self.strategies.append(strategy)\n        ',
        '                        logger.info(f\"Loaded ETH/USDT Grid Strategy on exchange {ex_name} | Symbol: {grid_symbol} | Capital: {capital_setting:.2f} USDT | Levels: {grid_levels}\")\n        ',
        '                    except Exception as e:\n        ',
        '                        logger.error(f\"Failed to load ETH/USDT Grid Strategy on {ex_name}: {e}\")\n        ',
        '\n',
        '        # Load BTC/USDT RSI Mean Reversion Strategy\n        ',
        '        if settings.enable_btc_rsi:\n        ',
        '            for ex_name, exchange in required_exchanges.items():\n        ',
        '                if exchange:\n        ',
        '                    try:\n        ',
        '                        # Load BTC/USDT RSI Strategy\n        ',
        '                        capital_setting = getattr(settings, f\'{ex_name.lower()}_btc_rsi_capital_usdt\', settings.btc_rsi_capital_usdt)\n        ',
        '                        rsi_symbol = getattr(settings, f\'{ex_name.lower()}_btc_rsi_symbol\', settings.btc_rsi_symbol)\n        ',
        '                        strategy = RSIReversionStrategy(exchange, self.db, initial_capital=capital_setting, symbol=rsi_symbol)\n        ',
        '                        await strategy.set_initial_capital(capital_setting)\n        ',
        '                        self.strategies.append(strategy)\n        ',
        '                        logger.info(f\"Loaded BTC/USDT RSI Reversion Strategy on exchange {ex_name} | Symbol: {rsi_symbol} | Capital: {capital_setting:.2f} USDT\")\n        ',
        '                    except Exception as e:\n        ',
        '                        logger.error(f\"Failed to load BTC/USDT RSI Reversion Strategy on {ex_name}: {e}\")\n        ',
        '\n',
        '        # Load ETH/USDT RSI Mean Reversion Strategy\n        ',
        '        if settings.enable_eth_rsi:\n        ',
        '            for ex_name, exchange in required_exchanges.items():\n        ',
        '                if exchange:\n        ',
        '                    try:\n        ',
        '                        # Load ETH/USDT RSI Strategy\n        ',
        '                        capital_setting = getattr(settings, f\'{ex_name.lower()}_eth_rsi_capital_usdt\', settings.eth_rsi_capital_usdt)\n        ',
        '                        rsi_symbol = getattr(settings, f\'{ex_name.lower()}_eth_rsi_symbol\', settings.eth_rsi_symbol)\n        ',
        '                        strategy = RSIReversionStrategy(exchange, self.db, initial_capital=capital_setting, symbol=rsi_symbol)\n        ',
        '                        await strategy.set_initial_capital(capital_setting)\n        ',
        '                        self.strategies.append(strategy)\n        ',
        '                        logger.info(f\"Loaded ETH/USDT RSI Reversion Strategy on exchange {ex_name} | Symbol: {rsi_symbol} | Capital: {capital_setting:.2f} USDT\")\n        ',
        '                    except Exception as e:\n        ',
        '                        logger.error(f\"Failed to load ETH/USDT RSI Reversion Strategy on {ex_name}: {e}\")\n        ',
        '\n'
    ]
    
    # Insert the new lines after the RSI section
    lines = lines[:insert_pos+15] + new_lines + lines[insert_pos+15:]
    
    # Write the modified file
    with open('/home/sergio/denaro/main.py', 'w') as f:
        f.writelines(lines)
    
    print("MAIN_PATCHED_WITH_NEW_STRATEGIES")
else:
    print("ERROR: Could not find RSI Mean Reversion Strategy section")