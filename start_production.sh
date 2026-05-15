#!/bin/bash
# Start the production bot for Denaro
# Usage: ssh machine "bash -s" < start_production.sh
cd "$HOME/denaro"
VENV_PYTHON="./venv/bin/python3"
if [ ! -x "$VENV_PYTHON" ]; then
    # Fallback to system python
    VENV_PYTHON="python3"
fi
# Kill existing instances
pkill -f "legion_manager_production.py" 2>/dev/null || true
sleep 1
nohup $VENV_PYTHON legion_manager_production.py >> legion_production.log 2>&1 &
echo "Started PID=$!"
