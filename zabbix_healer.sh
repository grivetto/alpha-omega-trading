#!/bin/bash
# zabbix_healer.sh — Autohealing Denaro via Zabbix API (ONESHOT, per cron/systemd timer)
# Pattern corretto: oneshot + cron ogni 2 min (MAI daemon while-true = fork bomb risk).
# Uso: ./zabbix_healer.sh [--dry-run]
set -uo pipefail

ZABBIX_URL="${ZABBIX_URL:-http://localhost:1080/api_jsonrpc.php}"
ZABBIX_USER="${ZABBIX_USER:-Admin}"
ZABBIX_PASS="${ZABBIX_PASS:-zabbix}"
LOG_FILE="${HEALER_LOG:-/home/sergio/denaro/logs/zabbix_healer.log}"
STATE_FILE="${HEALER_STATE:-/tmp/zabbix_healer_state.json}"
HEAL_COOLDOWN="${HEAL_COOLDOWN:-300}"
DRY_RUN="${DRY_RUN:-false}"

# Mapping host Zabbix -> (ssh alias | "local" | "skip", servizio da restartare)
declare -A HOST_SERVICE=(
  ["alpha-omega-nuvola"]="nuvola|denaro-node-nuvola"
  ["nuvola"]="nuvola|denaro-node-nuvola"
  ["alpha-omega-marcodg1"]="MARCODG1|denaro-node-paper"
  ["marcodg1"]="MARCODG1|denaro-node-paper"
  ["MARCODG1"]="MARCODG1|denaro-node-paper"
  ["alpha-omega-mc2"]="local|denaro-node-mc2"
  ["mc2"]="local|denaro-node-mc2"
)
# SSH user per nodo remoto
declare -A SSH_USER=(
  ["nuvola"]="sergio"
  ["MARCODG1"]="marco"
)

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

zabbix_api() {
  local method="$1" params="$2" auth="$3"
  curl -s -m 10 -X POST "$ZABBIX_URL" -H 'Content-Type: application/json-rpc' \
    -d "{\"jsonrpc\":\"2.0\",\"method\":\"$method\",\"params\":$params,\"id\":1${auth:+,$auth}}"
}

get_auth() {
  zabbix_api "user.login" '{"username":"'"$ZABBIX_USER"'","password":"'"$ZABBIX_PASS"'"}' "" \
    | python3 -c "import sys,json; print(json.load(sys.stdin).get('result',''))" 2>/dev/null
}

get_active_problems() {
  # trigger.get con filter value=1 = problemi attivi (pattern verificato)
  zabbix_api "trigger.get" '{
    "output": ["description","priority","lastchange"],
    "selectHosts": ["host"],
    "filter": {"value": "1"},
    "monitored": true,
    "sortfield": ["priority"], "sortorder": "DESC"
  }' "$1"
}

is_in_cooldown() {
  local key="$1"
  [ -f "$STATE_FILE" ] || return 1
  python3 - "$key" "$HEAL_COOLDOWN" "$STATE_FILE" << 'PYEOF'
import json, sys, time
key, cd, path = sys.argv[1], int(sys.argv[2]), sys.argv[3]
try:
    st = json.load(open(path))
    last = st.get(key, 0)
    if time.time() - last < cd:
        sys.exit(0)  # in cooldown
except Exception:
    pass
sys.exit(1)
PYEOF
}

mark_healed() {
  local key="$1"
  python3 - "$key" "$STATE_FILE" << 'PYEOF'
import json, sys, time
key, path = sys.argv[1], sys.argv[2]
try:
    st = json.load(open(path))
except Exception:
    st = {}
st[key] = time.time()
json.dump(st, open(path, "w"))
PYEOF
}

restart_service() {
  local node="$1" service="$2" host="$3"
  local action=""
  if [ "$node" = "local" ]; then
    action="systemctl restart $service"
  else
    action="ssh -o ConnectTimeout=8 -o BatchMode=yes ${SSH_USER[$node]:-sergio}@$node 'sudo systemctl restart $service'"
  fi
  log "RIAVVIO [$host] $service"
  if [ "$DRY_RUN" = "true" ]; then log "[DRY-RUN] $action"; return 0; fi
  eval "$action" >> "$LOG_FILE" 2>&1 && log "OK restart $service su $host" || log "FAIL restart $service su $host"
}

kill_zombies() {
  local node="$1" host="$2"
  local action=""
  if [ "$node" = "local" ]; then
    # bracket pattern: [d]enaro NON matcha il proprio cmdline -> no self-kill
    action="pkill -9 -f '[d]enaro_node' ; pkill -9 -f '[e]ngine_solo' ; true"
  else
    action="ssh -o ConnectTimeout=8 -o BatchMode=yes ${SSH_USER[$node]:-sergio}@$node 'pkill -9 -f \"[d]enaro_node\" ; pkill -9 -f \"[e]ngine_solo\" ; true'"
  fi
  log "KILL ZOMBIE [$host]"
  if [ "$DRY_RUN" = "true" ]; then log "[DRY-RUN] $action"; return 0; fi
  eval "$action" >> "$LOG_FILE" 2>&1 && log "OK cleanup zombie su $host"
}

handle_problem() {
  local eventid="$1" name="$2" host="$3" trigger="$4"
  local key="$eventid|$host"
  is_in_cooldown "$key" && { log "cooldown: skip $name ($host)"; return; }

  log "PROBLEMA [P$5] $host: $name (trigger: ${trigger:0:80})"

  local node service
  IFS='|' read -r node service <<< "${HOST_SERVICE[$host]:-}"
  if [ -z "${node:-}" ]; then
    log "host $host non mappato — nessuna azione"
    return
  fi

  case "$trigger" in
    *zombie*|*hung*|*unresponsive*|*multi*|*fork*)
      kill_zombies "$node" "$host"; restart_service "$node" "$service" "$host" ;;
    *down*|*DOWN*|*CRASHED*|*crashed*|*dead*|*DEAD*|*stale*|*STALE*|*"not running"*|*inactive*)
      restart_service "$node" "$service" "$host" ;;
    *equity*|*profit*|*drawdown*|*balance*)
      log "alert finanziario — solo log, nessuna azione automatica" ;;
    *)
      log "trigger non riconosciuto — restart cautelativo"
      restart_service "$node" "$service" "$host" ;;
  esac
  mark_healed "$key"
}

main() {
  # flag --dry-run
  if [[ "$*" == *"--dry-run"* ]]; then DRY_RUN="true"; fi
  mkdir -p "$(dirname "$LOG_FILE")"
  log "=== zabbix_healer (dry_run=$DRY_RUN) ==="

  AUTH=$(get_auth)
  if [ -z "$AUTH" ]; then log "ERROR: auth Zabbix fallita"; exit 1; fi

  RESP=$(get_active_problems "\"auth\":\"$AUTH\"")
  echo "$RESP" | python3 - "$DRY_RUN" << 'PYEOF'
import sys, json
try:
    data = json.load(sys.stdin)
except Exception as e:
    print(f"parse error: {e}"); sys.exit(0)
res = data.get("result", [])
if not isinstance(res, list):
    print("resp:", str(data)[:200]); sys.exit(0)
print(f"problemi attivi: {len(res)}")
for t in res:
    host = (t.get("hosts") or [{}])[0].get("host", "unknown")
    prio = t.get("priority", "0")
    print(f"{t.get('lastchange','?')}|{t.get('description','?')}|{host}|{prio}")
PYEOF

  # Processa i problemi riga per riga (lastchange|desc|host|prio)
  # FILTRO: solo trigger Denaro/fleet/bot/health — mai restart per trigger generici Linux
  echo "$RESP" | python3 -c "
import sys, json
data = json.load(sys.stdin)
res = data.get('result', []) if isinstance(data, dict) else []
import re
denaro_pat = re.compile(r'(?i)(denaro|fleet|bot|health|kraken|okx|atlas|v33)')
for t in res:
    desc = t.get('description', '')
    host = (t.get('hosts') or [{}])[0].get('host', 'unknown')
    if not denaro_pat.search(desc) and not denaro_pat.search(host):
        print(f'SKIP|{desc}|{host}|{t.get(\"priority\",\"0\")}')
        continue
    print(f\"{desc}|{host}|{t.get('priority','0')}\")
" | while IFS='|' read -r trigger host prio; do
    [ -z "$trigger" ] && continue
    if [ "$trigger" = "SKIP" ]; then
        log "ignoro trigger non-Denaro: $host: $prio"
        continue
    fi
    handle_problem "$(date +%s)" "$trigger" "$host" "$trigger" "$prio"
  done
}

main "$@"
