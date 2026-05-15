#!/bin/bash
# Ares Bot Watchdog — checks if bot is alive, restarts if dead
BOT_NAME="ares_bot"
BOT_DIR="/home/sergio/denaro/ares"
BOT_CMD="/home/sergio/denaro/venv/bin/python3 ares_intraday_bot.py"
LOG_FILE="$BOT_DIR/ares_bot.log"

# Check screen session
if ! screen -ls "$BOT_NAME" 2>/dev/null | grep -q "$BOT_NAME"; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Ares bot NOT running. Restarting..."
    cd "$BOT_DIR" && screen -dmS "$BOT_NAME" bash -c "$BOT_CMD >> $LOG_FILE 2>&1"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Restarted."
fi

# Check if log is stale (>5 min without update)
if [ -f "$LOG_FILE" ]; then
    AGE=$(( $(date +%s) - $(stat -c %Y "$LOG_FILE") ))
    if [ $AGE -gt 600 ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Log stale ($AGE s). Killing and restarting..."
        screen -XS "$BOT_NAME" quit 2>/dev/null
        cd "$BOT_DIR" && screen -dmS "$BOT_NAME" bash -c "$BOT_CMD >> $LOG_FILE 2>&1"
    fi
fi
