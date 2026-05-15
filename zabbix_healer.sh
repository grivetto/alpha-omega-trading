#!/bin/bash
# Denaro Zabbix Self-Healer
# Polls Zabbix for alerts and auto-repairs Denaro infrastructure
# Runs every 5 minutes via cron

ZABBIX_URL="http://localhost:1080/api_jsonrpc.php"
LOG="/home/sergio/denaro/healer.log"
AUTH='{"jsonrpc":"2.0","method":"user.login","params":{"username":"Admin","password":"zabbix"},"id":1}'

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG"; echo "$1"; }

# Get Zabbix auth token
TOKEN=$(curl -s -X POST "$ZABBIX_URL" -H 'Content-Type: application/json' -d "$AUTH" | python3 -c "import sys,json; print(json.load(sys.stdin).get('result',''))" 2>/dev/null)
if [ -z "$TOKEN" ]; then
    log "❌ Healer: Zabbix auth failed"
    exit 1
fi

# Get active Denaro problems
PROBLEMS_JSON='{"jsonrpc":"2.0","method":"problem.get","params":{"output":["name","clock"],"selectHosts":["host"],"recent":true},"id":1,"auth":"'"$TOKEN"'"}'
PROBLEMS=$(curl -s -X POST "$ZABBIX_URL" -H 'Content-Type: application/json' -d "$PROBLEMS_JSON" | python3 -c "
import sys,json,time
data = json.load(sys.stdin)
for p in data.get('result',[]):
    name = p.get('name','')
    host = p.get('hosts',[{}])[0].get('host','?') if p.get('hosts') else '?'
    if 'Denaro' not in name and 'denaro' not in name.lower(): continue
    clock = int(p.get('clock',0))
    age = (time.time() - clock) / 60
    print(f'{host}|{name}|{age:.0f}')
" 2>/dev/null)

if [ -z "$PROBLEMS" ]; then
    log "✅ Healer: No Denaro problems detected"
    exit 0
fi

HEALED=false

while IFS='|' read -r host problem age_min; do
    [ -z "$host" ] && continue
    log "⚠️  Problem: [$host] $problem (${age_min}m old)"
    
    case "$host" in
        nuvola|NUVOLA|87.106.3.15)
            NODE="nuvola"
            USER="sergio"
            SERVICE="wdg-watchdog.service"
            WDG_SCRIPT="/home/sergio/denaro/watchdog.sh"
            MON_LOG="/home/sergio/denaro/monitor/monitor.log"
            ;;
        marcodg1|MARCODG1|87.106.222.123)
            NODE="MARCODG1"
            USER="marco"
            SERVICE="denaro-watchdog.service"
            WDG_SCRIPT="/home/marco/denaro/watchdog.sh"
            MON_LOG="/home/marco/denaro/monitor/monitor.log"
            ;;
        *)
            log "  Unknown host: $host, skipping"
            continue
            ;;
    esac

    if echo "$problem" | grep -qi "CRASHED\|DOWN\|DEAD\|STALE\|SERVICE DOWN"; then
        log "  🔧 ACTION: Restarting $SERVICE on $NODE..."
        ssh "$NODE" "systemctl --user restart $SERVICE 2>&1" && log "  ✅ Restarted $SERVICE" || log "  ❌ Failed to restart $SERVICE"
        HEALED=true
        
    elif echo "$problem" | grep -qi "WATCHDOG LOW"; then
        log "  🔧 ACTION: Restarting watchdog on $NODE..."
        ssh "$NODE" "pkill -9 -f watchdog.sh 2>/dev/null; sleep 2; nohup bash $WDG_SCRIPT > /dev/null 2>&1 &" 2>/dev/null
        ssh "$NODE" "systemctl --user restart $SERVICE 2>&1" && log "  ✅ Watchdog restarted" || log "  ⚠️ Watchdog restart attempted"
        HEALED=true
        
    elif echo "$problem" | grep -qi "TREND CRASH"; then
        log "  ℹ️  Trend CRASH is market condition, no action needed - grid paused automatically"
        
    elif echo "$problem" | grep -qi "MEMORY HIGH\|DISK FULL"; then
        log "  ⚠️  System resource alert - checking..."
        ssh "$NODE" "df -h / | tail -1" | log
        HEALED=true  # System issues are informational
    fi
done <<< "$PROBLEMS"

if [ "$HEALED" = true ]; then
    log "✅ Healer: Actions completed"
    # Wait for services to stabilize then verify
    sleep 10
    # Check if problems resolved by re-running Zabbix check
    PROBLEMS_AFTER=$(curl -s -X POST "$ZABBIX_URL" -H 'Content-Type: application/json' -d "$PROBLEMS_JSON" 2>/dev/null | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('result',[])))" 2>/dev/null)
    log "  Remaining problems: $PROBLEMS_AFTER"
else
    log "ℹ️  Healer: No action needed"
fi
