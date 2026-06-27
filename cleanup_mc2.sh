#!/bin/bash
for svc in denaro-mc2-grid denaro-unified denaro-v2 denaro-mc2-arb; do
    systemctl stop $svc 2>/dev/null || true
    systemctl disable $svc 2>/dev/null || true
done
pkill -9 -f orchestrator.py 2>/dev/null || true
pkill -9 -f mc2_bot.py 2>/dev/null || true
pkill -9 -f unified_bot.py 2>/dev/null || true
sleep 2
echo "Ghost bots killed"
ps aux | grep -E "orchestrator|mc2_bot|unified_bot" | grep -v grep || echo "Clean"
systemctl is-active denaro-v6
