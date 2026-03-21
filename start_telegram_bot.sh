#!/bin/bash
cd /root/.openclaw/workspace
python3 telegram_bot.py > telegram_bot.out 2>&1 &
