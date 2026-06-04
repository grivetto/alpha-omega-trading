#!/bin/bash

# MARCODG1 Monitor Script - Bash version for cron
# This script monitors MARCODG1 bot and sends Telegram alerts

SSH_HOST="marco@87.106.222.123"
SSH_KEY="~/.ssh/id_ed25519"
TELEGRAM_TOKEN="871585...qlmw"
TELEGRAM_CHAT_ID="277954993"
TELEGRAM_URL="https://api.telegram.org/bot$TELEGRAM_TOKEN/sendMessage"

# Function to send Telegram alert
send_alert() {
    local message="$1"
    local timestamp=$(date -u +"%Y-%m-%d %H:%M:%S UTC")
    local full_message="🤖 MARCODG1 BOT ALERT 🤖

$message

⏰ $timestamp"
    
    curl -s -X POST "$TELEGRAM_URL" \
        -d "chat_id=$TELEGRAM_CHAT_ID" \
        -d "text=$full_message" \
        -d "parse_mode=HTML" > /dev/null
}

# Check SSH connection
echo "Testing SSH connection..."
if ! ssh -o ConnectTimeout=5 -i "$SSH_KEY" "$SSH_HOST" "echo 'SSH OK'" 2>/dev/null; then
    echo "SSH connection failed"
    send_alert "❌ SSH connection failed to MARCODG1 server"
    exit 1
fi

# Check bot status
echo "Checking bot status..."
BOT_STATUS=$(ssh -o ConnectTimeout=5 -i "$SSH_KEY" "$SSH_HOST" "ps aux | grep marcodg1_bot | grep -v grep" 2>/dev/null)
if [ -z "$BOT_STATUS" ]; then
    echo "Bot is NOT running"
    send_alert "❌ BOT NON ATTIVO"
    BOT_RUNNING=0
else
    echo "Bot is running"
    BOT_RUNNING=1
fi

# Get log data
echo "Getting log data..."
LOG_DATA=$(ssh -o ConnectTimeout=5 -i "$SSH_KEY" "$SSH_HOST" "tail -20 /home/marco/denaro/marcodg1.log" 2>/dev/null)

if [ -z "$LOG_DATA" ]; then
    REGIME="unknown"
    VOLATILITY=0
    PORTFOLIO_FLOOR=0
else
    REGIME=$(echo "$LOG_DATA" | grep -oP 'Regime: \K\w+' | head -1)
    VOLATILITY=$(echo "$LOG_DATA" | grep -oP 'Volatility: \K[\d\.]+%' | head -1 | sed 's/%//')
    PORTFOLIO_FLOOR=$(echo "$LOG_DATA" | grep -oP 'floor=\K[\d\.]+' | head -1)
fi

# Get balance
echo "Getting balance..."
BALANCE_CMD='import ccxt; ex = ccxt.binance({"apiKey": "SY7AUMAlUH0k37BLmyJUiWEZQP84nN2A9ZwYET3jtwMdOE7bdAjRe955smWw18N2", "secret": "aY6LEb6ETOm4DcgGFrYOKI8oofRsKKt5ttHYdbA3EjBQri0UtJRGjTYsuZj8vLI7", "options": {"defaultType": "spot"}, "enableRateLimit": True}); bal = ex.fetch_balance(); print(f"EUR:{bal["free"].get("EUR",0):.2f}"); ex.close()'

BALANCE=$(ssh -o ConnectTimeout=5 -i "$SSH_KEY" "$SSH_HOST" "python3 -c \"$BALANCE_CMD\"" 2>/dev/null)
EUR_BALANCE=$(echo "$BALANCE" | grep -oP 'EUR:\K[\d\.]+')

# Check for alerts
ALERTS=""

if [ "$BOT_RUNNING" -eq 0 ]; then
    ALERTS="$ALERTS❌ BOT NON ATTIVO\n"
    send_alert "MARCODG1 bot non risponde - controllare subito!"
fi

if [ "$REGIME" = "bear" ]; then
    ALERTS="$ALERTS⚠️ Regime BEAR (${VOLATILITY}% vol)\n"
    send_alert "Attenzione: regime BEAR con volatilità ${VOLATILITY}% su MARCODG1"
fi

if [ "$(echo "$VOLATILITY" < 1.0 | bc -l)" = 1 ]; then
    ALERTS="$ALERTS⚠️ Bassa volatilità: ${VOLATILITY}%\n"
    send_alert "Attenzione: volatilità bassa (${VOLATILITY}%) su MARCODG1"
fi

if [ $(echo "$EUR_BALANCE < 1.0" | bc -l) -eq 1 ]; then
    ALERTS="$ALERTS⚠️ Basso saldo EUR: ${EUR_BALANCE}€\n"
    send_alert "Attenzione: saldo EUR basso (${EUR_BALANCE}€) su MARCODG1"
fi

# Status report
if [ -z "$ALERTS" ]; then
    STATUS="✅ OK"
else
    STATUS="$ALERTS"
fi

echo "MARCODG1 STATUS: $STATUS"
echo "Regime: $REGIME"
echo "Volatilità: ${VOLATILITY}%"
echo "Saldo EUR: ${EUR_BALANCE}€"
echo "Portfolio floor: ${PORTFOLIO_FLOOR}"

if [ -z "$ALERTS" ]; then
    exit 0
else
    exit 1
fi