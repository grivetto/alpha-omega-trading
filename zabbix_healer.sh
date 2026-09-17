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
# GUARDIA ANTI-FLAP (per SERVIZIO, non per evento). Il cooldown sopra e' keyed
# sull'eventid: quando un problema si RIPETE arriva un eventid NUOVO, quindi non
# protegge da un trigger che oscilla. E' successo il 2026-09-17: i trigger dei
# bot con dati stantii facevano riavviare denaro-node-nuvola-trade OGNI 2
# MINUTI, in loop, su un nodo perfettamente sano. Questa finestra limita i
# riavvii dello STESSO servizio a uno ogni FLAP_COOLDOWN secondi.
FLAP_COOLDOWN="${FLAP_COOLDOWN:-1800}"
DRY_RUN="${DRY_RUN:-false}"

# Mapping host Zabbix -> (ssh alias | "local" | "skip", servizio da restartare)
# Mappa aggiornata 2026-09-17: un nodo di TRADING per macchina.
# Le unit decommissionate (denaro-node-nuvola, denaro-node-trend-live,
# denaro-brain) restano fuori: la guardia 'disabled' le salta comunque.
declare -A HOST_SERVICE=(
  ["alpha-omega-nuvola"]="nuvola|denaro-node-nuvola-trade"
  ["nuvola"]="nuvola|denaro-node-nuvola-trade"
  ["alpha-omega-marcodg1"]="MARCODG1|denaro-node-marcodg1-xrp"
  ["marcodg1"]="MARCODG1|denaro-node-marcodg1-xrp"
  ["MARCODG1"]="MARCODG1|denaro-node-marcodg1-xrp"
  ["alpha-omega-mc2"]="local|denaro-node-mc2"
  ["mc2"]="local|denaro-node-mc2"
  # --- i 15 bot di TREND in produzione (5 per macchina) ---
  # Host creati da tools/zabbix_setup.py a partire dal registro unico
  # tools/denaro_bots.py. Gli host della generazione precedente
  # (okx-doge, nuvola-sol, marcodg1-xrp) sono stati RIMOSSI da Zabbix.
  ["alpha-omega-bot-mc2-btc"]="local|denaro-node-mc2"
  ["alpha-omega-bot-mc2-eth"]="local|denaro-node-mc2"
  ["alpha-omega-bot-mc2-sol"]="local|denaro-node-mc2"
  ["alpha-omega-bot-mc2-xrp"]="local|denaro-node-mc2"
  ["alpha-omega-bot-mc2-doge"]="local|denaro-node-mc2"
  ["alpha-omega-bot-nuvola-link"]="nuvola|denaro-node-nuvola-trade"
  ["alpha-omega-bot-nuvola-avax"]="nuvola|denaro-node-nuvola-trade"
  ["alpha-omega-bot-nuvola-dot"]="nuvola|denaro-node-nuvola-trade"
  ["alpha-omega-bot-nuvola-ltc"]="nuvola|denaro-node-nuvola-trade"
  ["alpha-omega-bot-nuvola-uni"]="nuvola|denaro-node-nuvola-trade"
  ["alpha-omega-bot-marcodg1-ada"]="MARCODG1|denaro-node-marcodg1-xrp"
  ["alpha-omega-bot-marcodg1-atom"]="MARCODG1|denaro-node-marcodg1-xrp"
  ["alpha-omega-bot-marcodg1-aave"]="MARCODG1|denaro-node-marcodg1-xrp"
  ["alpha-omega-bot-marcodg1-arb"]="MARCODG1|denaro-node-marcodg1-xrp"
  ["alpha-omega-bot-marcodg1-xlm"]="MARCODG1|denaro-node-marcodg1-xrp"
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
  local key="$1" finestra="${2:-$HEAL_COOLDOWN}"
  [ -f "$STATE_FILE" ] || return 1
  python3 - "$key" "$finestra" "$STATE_FILE" << 'PYEOF'
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

# GUARDIA ANTI-FLAP: blocca il riavvio dello STESSO servizio se e' gia' stato
# riavviato da meno di FLAP_COOLDOWN secondi, a prescindere dall'eventid. E' la
# rete di sicurezza contro un trigger che oscilla (o un monitoraggio rotto):
# senza, un problema che si riapre con un eventid nuovo riavvia il nodo
# all'infinito.
guardia_flap() {
  local node="$1" service="$2"
  if is_in_cooldown "flap|$node|$service" "$FLAP_COOLDOWN"; then
    log "ANTI-FLAP: $service riavviato da meno di ${FLAP_COOLDOWN}s — nessuna azione"
    return 1
  fi
  return 0
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
  # </dev/null e' ESSENZIALE. Il chiamante esegue questa funzione dentro un
  # "while read" alimentato da una pipe: senza la redirezione, ssh CONSUMA lo
  # stdin del ciclo e il loop termina dopo il PRIMO problema. Il 2026-09-17 e'
  # esattamente cosi' che la dashboard spenta non e' stata ripresa per due cicli:
  # ogni ciclo curava un problema e usciva.
  eval "$action" </dev/null >> "$LOG_FILE" 2>&1 && log "OK restart $service su $host" || log "FAIL restart $service su $host"
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
  eval "$action" </dev/null >> "$LOG_FILE" 2>&1 && log "OK cleanup zombie su $host"
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

  # ── SERVIZI SYSTEMD ──────────────────────────────────────────────────────
  # I trigger dei servizi hanno la forma "SERVIZIO <unit>: <problema>". Il unit
  # da riavviare e' NOMINATO nel trigger. Senza questo ramo, un problema su
  # denaro-dashboard-marcodg1 finiva nel case generico e riavviava il servizio
  # di DEFAULT dell'host mappato — cioe' il nodo di trading: la cosa sbagliata,
  # e per giunta un riavvio che non cura il guasto segnalato.
  if [[ "$name" =~ ^SERVIZIO[[:space:]]+([A-Za-z0-9@._-]+): ]]; then
    local unit="${BASH_REMATCH[1]}"
    log "servizio nominato dal trigger: $unit"
    if guardia_flap "$node" "$unit"; then
      restart_service "$node" "$unit" "$host"
      mark_healed "flap|$node|$unit"
    fi
    mark_healed "$key"
    return
  fi

  case "$trigger" in
    *zombie*|*hung*|*unresponsive*|*multi*|*fork*)
      if guardia_flap "$node" "$service"; then
        kill_zombies "$node" "$host"
        restart_service "$node" "$service" "$host"
        mark_healed "flap|$node|$service"
      fi ;;
    *down*|*DOWN*|*CRASHED*|*crashed*|*dead*|*DEAD*|*stale*|*STALE*|*"not running"*|*inactive*|*"non in esecuzione"*|*"nessun dato"*)
      if guardia_flap "$node" "$service"; then
        restart_service "$node" "$service" "$host"
        mark_healed "flap|$node|$service"
      fi ;;
    *equity*|*profit*|*drawdown*|*balance*)
      log "alert finanziario — solo log, nessuna azione automatica" ;;
    # Un MESSAGGIO d'errore non significa nodo morto: il bot e' vivo e sta
    # riportando un problema (es. fondi insufficienti). Riavviarlo non cura
    # nulla e rischia un loop. Si logga e basta: il restart scatta su
    # down/nodata, cioe' quando il nodo e' davvero fermo.
    *ERRORE*|*error*|*Error*)
      log "errore riportato dal bot — solo log (nessun restart)" ;;
    *)
      if guardia_flap "$node" "$service"; then
        log "trigger non riconosciuto — restart cautelativo"
        restart_service "$node" "$service" "$host"
        mark_healed "flap|$node|$service"
      fi ;;
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
  RESP_FILE="${HEALER_RESP:-/tmp/zabbix_healer_resp.json}"
  printf %s "$RESP" > "$RESP_FILE"
  python3 - "$DRY_RUN" << 'PYEOF'
import sys, json
try:
    data = json.load(open(sys.argv[2] if len(sys.argv) > 2 else "/tmp/zabbix_healer_resp.json"))
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
  python3 -c "
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
 " < "$RESP_FILE" | while IFS='|' read -r trigger host prio; do
    [ -z "$trigger" ] && continue
    if [ "$trigger" = "SKIP" ]; then
        log "ignoro trigger non-Denaro: $host: $prio"
        continue
    fi
    handle_problem "$(date +%s)" "$trigger" "$host" "$trigger" "$prio"
  done
}

main "$@"
