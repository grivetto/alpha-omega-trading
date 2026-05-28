#!/bin/bash
# Watchdog MARCODG1: controlla screen marcobots ogni 5 minuti
BOT_LOG="/home/marco/denaro/grid_marcodg1.log"
BOT_DIR="/home/marco/denaro"
BOT_SCRIPT="grid_bot_marcodg1.py"
STATE_FILE="$BOT_DIR/grid_state.json"

if [ -f "$STATE_FILE" ]; then
    STATE_AGE=$(($(date +%s) - $(stat -c %Y "$STATE_FILE")))
else
    STATE_AGE=9999
fi

if ! screen -list | grep -q "marcobots"; then
    echo "[$(date)] Watchdog: screen marcobots non trovato, avvio..." >> "$BOT_LOG"
    cd "$BOT_DIR" && screen -S marcobots -dm bash -c "cd $BOT_DIR && python3 $BOT_SCRIPT 2>&1 | tee -a $BOT_DIR/grid_marcodg1_screen.log"
elif [ $STATE_AGE -gt 600 ]; then
    echo "[$(date)] Watchdog: stato inattivo da ${STATE_AGE}s, riavvio..." >> "$BOT_LOG"
    screen -S marcobots -X quit 2>/dev/null
    sleep 2
    cd "$BOT_DIR" && screen -S marcobots -dm bash -c "cd $BOT_DIR && python3 $BOT_SCRIPT 2>&1 | tee -a $BOT_DIR/grid_marcodg1_screen.log"
else
    echo "[$(date)] Watchdog: OK (state_age=${STATE_AGE}s)" >> "$BOT_LOG" 2>/dev/null
fi
