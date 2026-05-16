#!/bin/bash
# Squadra Denaro Opportunistico — Watchdog (screen-based)
# mc2 usa screen, non tmux
BOT_NAME="squadra_bot"
BOT_DIR="/home/sergio/denaro"
BOT_CMD="source /home/sergio/denaro/venv/bin/activate && cd /home/sergio/denaro/squadra && python3 run_squadra.py"
LOG_FILE="$BOT_DIR/squadra/squadra_watchdog.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

if screen -list 2>/dev/null | grep -q "$BOT_NAME"; then
    log "OK: $BOT_NAME running."
    exit 0
fi

log "⚠️  $BOT_NAME not running! Restarting..."
cd "$BOT_DIR" && screen -dmS "$BOT_NAME" bash -c "$BOT_CMD >> $BOT_DIR/squadra/squadra.log 2>&1"
sleep 3

if screen -list 2>/dev/null | grep -q "$BOT_NAME"; then
    log "✅ Restarted successfully."
else
    log "❌ Failed to restart!"
fi
