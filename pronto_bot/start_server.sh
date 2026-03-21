#!/bin/bash
source /root/.openclaw/workspace/trading_bot_env/bin/activate
pip install flask python-dotenv requests
nohup python3 /root/.openclaw/workspace/pronto_bot/app.py > /root/.openclaw/workspace/pronto_bot/bot.log 2>&1 &
echo $! > /root/.openclaw/workspace/pronto_bot/bot.pid
