#!/bin/bash
KEY=
SECRET=
grep -v -E 'BINANCE_API_KEY_MAIN|BINANCE_API_SECRET_MAIN' /home/sergio/denaro/.env > /home/sergio/denaro/.env.tmp
echo "BINANCE_API_KEY_MAIN=" >> /home/sergio/denaro/.env.tmp
echo "BINANCE_API_SECRET_MAIN=" >> /home/sergio/denaro/.env.tmp
mv /home/sergio/denaro/.env.tmp /home/sergio/denaro/.env
echo "MAIN KEYS UPDATED"
