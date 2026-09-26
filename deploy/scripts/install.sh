#!/usr/bin/env bash
# deploy/scripts/install.sh — installa il banco a secco (systemd) su un nodo.
# Interpola {{PROJECT_ROOT}} e {{BANCO_USER}} nei template; esegue le guardie
# statiche PRIMA di toccare il sistema. Il banco non invia ordini: il divieto
# e' verificato qui e in CI (deploy/tests/), non promesso.
#
# Uso: ./install.sh [--dry-run] [--project-root PATH] [--user NAME] [--node NODO]
#                   [--install-dir DIR] [--start] [--help]
set -euo pipefail

PROJECT_ROOT=""
DRY_RUN=false
BANCO_USER=""
NODE="MARCODG1"
INSTALL_SYSTEMD="/etc/systemd/system"
START=false
SERVICE_NAME="money-banco-secco.service"
TIMER_NAME="money-banco-secco.timer"

usage() {
    cat <<EOF
Usage: $0 [OPTIONS]

Installa il banco di prova a secco (Money) su questo nodo.

OPTIONS:
    --dry-run              mostra cosa verrebbe scritto, non tocca nulla
    --project-root PATH    root del progetto (default: due livelli sopra lo script)
    --user NAME            utente che esegue il servizio (default: proprietario di PROJECT_ROOT)
    --node NODO            nodo dichiarato: MARCODG1 o nuvola (informativo)
    --install-dir DIR      dove stanno le unit (default: /etc/systemd/system)
    --start                avvia subito il service dopo l'installazione
    -h, --help             questo help
EOF
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run) DRY_RUN=true; shift ;;
        --project-root) PROJECT_ROOT="$2"; shift 2 ;;
        --user) BANCO_USER="$2"; shift 2 ;;
        --node) NODE="$2"; shift 2 ;;
        --install-dir) INSTALL_SYSTEMD="$2"; shift 2 ;;
        --start) START=true; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Errore: opzione sconosciuta $1" >&2; usage; exit 1 ;;
    esac
done

if [[ -z "$PROJECT_ROOT" ]]; then
    PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
fi
[[ -d "$PROJECT_ROOT" ]] || { echo "ERRORE: PROJECT_ROOT '$PROJECT_ROOT' non esiste" >&2; exit 1; }

if [[ -z "$BANCO_USER" ]]; then
    BANCO_USER="$(stat -c '%U' "$PROJECT_ROOT" 2>/dev/null || id -un)"
fi
[[ "$NODE" == "mc2" ]] && echo "ATTENZIONE: la chiave e' whitelistata per MARCODG1/nuvola, non per mc2: il banco qui fallira' con 50119." >&2

TEMPLATE_SERVICE="$PROJECT_ROOT/deploy/templates/money-banco-secco.service"
TEMPLATE_TIMER="$PROJECT_ROOT/deploy/templates/money-banco-secco.timer"
BANCO_SCRIPT="$PROJECT_ROOT/deploy/scripts/money_banco_secco.sh"
BANCO_MODULE="$PROJECT_ROOT/deploy/banco/money_banco_secco.py"

for f in "$TEMPLATE_SERVICE" "$TEMPLATE_TIMER" "$BANCO_SCRIPT" "$BANCO_MODULE"; do
    [[ -f "$f" ]] || { echo "ERRORE: file mancante: $f" >&2; exit 1; }
done

# --- Guardie statiche: il divieto e' verificato, non promesso -------------------
# (pattern spezzato: questo file non contiene il token in chiaro)
FORB="create_""order|create""Order|place_""order|private""PostTrade"
set +e
grep -rnE "$FORB" "$PROJECT_ROOT/deploy/banco" "$PROJECT_ROOT/deploy/scripts" \
    --include='*.py' --include='*.sh' >/dev/null 2>&1
RC_GREP=$?
set -e
if [[ "$RC_GREP" -eq 0 ]]; then
    echo "ERRORE: trovata una chiamata di invio ordini in deploy/ — installazione rifiutata" >&2
    exit 1
elif [[ "$RC_GREP" -gt 1 ]]; then
    echo "ERRORE: guardia statica non eseguibile (grep rc=$RC_GREP): installazione rifiutata" >&2
    exit 1
fi
bash -n "$BANCO_SCRIPT" || { echo "ERRORE: $BANCO_SCRIPT: sintassi bash invalida" >&2; exit 1; }
PY_BANCO="$PROJECT_ROOT/venv/bin/python3"
[[ -x "$PY_BANCO" ]] || PY_BANCO="python3"
"$PY_BANCO" -m py_compile "$BANCO_MODULE" || { echo "ERRORE: $BANCO_MODULE non compila" >&2; exit 1; }
echo "Guardie statiche: OK (nessuna chiamata di invio in deploy/, script e modulo compilano)"

interpola() {
    sed -e "s|{{PROJECT_ROOT}}|$PROJECT_ROOT|g" \
        -e "s|{{BANCO_USER}}|$BANCO_USER|g" "$1"
}

TMP_SERVICE="$(mktemp)"; TMP_TIMER="$(mktemp)"
trap 'rm -f "$TMP_SERVICE" "$TMP_TIMER"' EXIT
interpola "$TEMPLATE_SERVICE" > "$TMP_SERVICE"
interpola "$TEMPLATE_TIMER" > "$TMP_TIMER"
if grep -q "{{" "$TMP_SERVICE" "$TMP_TIMER"; then
    echo "ERRORE: placeholder non interpolati nei template" >&2
    exit 1
fi

TARGET_SERVICE="$INSTALL_SYSTEMD/$SERVICE_NAME"
TARGET_TIMER="$INSTALL_SYSTEMD/$TIMER_NAME"

if [[ "$DRY_RUN" == true ]]; then
    echo "=== DRY-RUN su $NODE (user=$BANCO_USER, root=$PROJECT_ROOT) ==="
    for coppia in "$TARGET_SERVICE:$TMP_SERVICE" "$TARGET_TIMER:$TMP_TIMER"; do
        target="${coppia%%:*}"; nuovo="${coppia##*:}"
        echo "--- $target ---"
        if [[ -f "$target" ]]; then
            diff -u "$target" "$nuovo" || true
            echo "--- (diff sopra: se vuoto, gia' aggiornato) ---"
        else
            echo "(da creare)"
            cat "$nuovo"
        fi
    done
    exit 0
fi

if [[ "$(id -u)" != "0" ]]; then
    echo "ERRORE: serve root per scrivere in $INSTALL_SYSTEMD (sudo $0 ...)" >&2
    exit 1
fi

install -d -m 0755 "$INSTALL_SYSTEMD"
install -m 0644 "$TMP_SERVICE" "$TARGET_SERVICE"
install -m 0644 "$TMP_TIMER" "$TARGET_TIMER"
mkdir -p "$PROJECT_ROOT/logs"

systemctl daemon-reload
systemctl enable "$SERVICE_NAME" "$TIMER_NAME"

echo "Installato: $TARGET_SERVICE + $TARGET_TIMER (user=$BANCO_USER)"
echo "Prossimi passi:"
echo "  1. creare $PROJECT_ROOT/config/.env_banco da config/.env_banco.example"
echo "     (chiave DEDICATA SOLO Read, whitelist IP del nodo) e chmod 600"
echo "  2. test manuale: systemctl start $SERVICE_NAME && journalctl -u $SERVICE_NAME -f"
echo "  3. il timer parte ogni 5 minuti: systemctl list-timers | grep money"
if [[ "$START" == true ]]; then
    systemctl start "$SERVICE_NAME"
fi
