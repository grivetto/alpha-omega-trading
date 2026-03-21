#!/bin/bash
# Script per avviare il Trading Bot
# Uso: ./run_bot.sh

cd /root/.openclaw/workspace
source trading_bot_env/bin/activate
python binance_trading_bot.py
