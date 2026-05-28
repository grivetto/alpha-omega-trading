#!/bin/bash
# Squadra Denaro Opportunistico — Watchdog (tmux, mc2 ha tmux installato)
BOT_NAME="squadra_bot"
BOT_DIR="/home/sergio/denaro"
BOT_CMD="cd /home/sergio/denaro/squadra && /home/sergio/denaro/venv/bin/python3 run_squadra.py"
LOG_FILE="$BOT_DIR/squadra/squadra_watchdog.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

if tmux has-session -t "$BOT_NAME" 2>/dev/null; then
    log "OK: $BOT_NAME running."
    exit 0
fi

log "⚠️  $BOT_NAME not running! Restarting..."
cd "$BOT_DIR" && tmux new-session -d -s "$BOT_NAME" "$BOT_CMD" 2>/dev/null
sleep 3

if tmux has-session -t "$BOT_NAME" 2>/dev/null; then
    log "✅ Restarted successfully."
else
    log "❌ Failed to restart!"
fi
