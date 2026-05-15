#!/bin/bash
# _launch_legion.sh - eseguirlo via: ssh host "bash /path/_launch_legion.sh"
# Nessun & esterno, tutto gestito internamente
BASE=$(dirname "$0")
cd "$BASE"
source venv/bin/activate
nohup python3 -u legion_manager_production.py >> legion_production.log 2>&1 &
echo "PID=$!"
sleep 4
if ps -p $! > /dev/null 2>&1; then
    echo "RUNNING"
else
    echo "FAILED"
    tail -10 legion_production.log
fi