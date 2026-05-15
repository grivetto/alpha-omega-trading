#!/bin/bash
# deploy_legion.sh - Lanciato DIRETTAMENTE sulla macchina remota
set -e

BASE_DIR=$(cd "$(dirname "$0")" && pwd)
echo "[$(hostname)] Deploy LegionManager PROD - $(date)"

# 1. Rimuovi vecchio DB
rm -f "$BASE_DIR/trades.db"

# 2. Inizializza DB
source "$BASE_DIR/venv/bin/activate"
cd "$BASE_DIR"

python3 -c "
import sys; sys.path.insert(0, '.')
from trade_db import TradeDB
db = TradeDB('trades.db')
from sqlite3 import connect
with connect('trades.db') as c:
    t = c.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()
    print('Tabelle:', [r[0] for r in t])
    c.execute('SELECT * FROM bot_state')
    print('bot_state: OK')
    c.execute('SELECT * FROM bot_exposure')
    print('bot_exposure: OK')
    c.execute('SELECT * FROM vault_balance')
    print('vault_balance: OK')
print('DB inizializzato correttamente')
"

# 3. Crea directory
mkdir -p "$BASE_DIR/positions"

# 4. Kill eventuali istanze precedenti
pkill -f "legion_manager_production.py" 2>/dev/null || true
sleep 1

# 5. Avvia LegionManager PROD
nohup python3 -u "$BASE_DIR/legion_manager_production.py" >> "$BASE_DIR/legion_production.log" 2>&1 &
NEW_PID=$!
sleep 4

# 6. Verifica
echo "--- Verifica ---"
if ps -p $NEW_PID > /dev/null 2>&1; then
    echo "✅ LegionManager avviato (PID $NEW_PID)"
    tail -5 "$BASE_DIR/legion_production.log"
else
    echo "❌ LegionManager NON avviato! Log:"
    tail -10 "$BASE_DIR/legion_production.log"
    exit 1
fi