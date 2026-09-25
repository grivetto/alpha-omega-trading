#!/usr/bin/env bash
# deploy/scripts/install.sh — Installa i servizi Money con PROJECT_ROOT parametrico
# Uso: ./install.sh [--dry-run] [--project-root /path] [--node NODE] [--help]

set -euo pipefail

# Defaults
PROJECT_ROOT="${PROJECT_ROOT:-/home/sergio/alpha-omega-trading}"
DRY_RUN=false
NODE="mc2"  # nodo dove gira il banco (mc2, MARCODG1, nuvola)
INSTALL_SYSTEMD="/etc/systemd/system"
SERVICE_NAME="money-banco-secco.service"

usage() {
    cat <<EOF
Usage: $0 [OPTIONS]

Installa i servizi Money (systemd + timer) con PROJECT_ROOT parametrico.

OPTIONS:
    --dry-run              Mostra diff senza applicare (exit 0 se ok, 1 se cambiamenti)
    --project-root PATH    Root del progetto (default: $PROJECT_ROOT)
    --node NODE            Nodo target: mc2, MARCODG1, nuvola (default: mc2)
    --install-dir DIR      Directory systemd (default: /etc/systemd/system)
    --service-name NAME    Nome servizio (default: money-banco-secco.service)
    -h, --help             Questo help

ESEMPI:
    $0 --dry-run --project-root /home/sergio/alpha-omega-trading
    sudo $0 --project-root /home/sergio/alpha-omega-trading --node MARCODG1

EOF
}

# Parse args
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run) DRY_RUN=true; shift ;;
        --project-root) PROJECT_ROOT="$2"; shift 2 ;;
        --node) NODE="$2"; shift 2 ;;
        --install-dir) INSTALL_SYSTEMD="$2"; shift 2 ;;
        --service-name) SERVICE_NAME="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Errore: opzione sconosciuta $1" >&2; usage; exit 1 ;;
    esac
done

# Validazione
if [[ ! -d "$PROJECT_ROOT" ]]; then
    echo "ERRORE: PROJECT_ROOT '$PROJECT_ROOT' non esiste" >&2
    exit 1
fi

if [[ ! -f "$PROJECT_ROOT/deploy/templates/money-banco-secco.service" ]]; then
    echo "ERRORE: template service non trovato in $PROJECT_ROOT/deploy/templates/" >&2
    exit 1
fi

if [[ ! -f "$PROJECT_ROOT/deploy/scripts/money_banco_secco.sh" ]]; then
    echo "ERRORE: script banco non trovato in $PROJECT_ROOT/deploy/scripts/" >&2
    exit 1
fi

# Prepara file service interpolato
TMP_SERVICE=$(mktemp)
sed -e "s|{{PROJECT_ROOT}}|$PROJECT_ROOT|g" \
    "$PROJECT_ROOT/deploy/templates/money-banco-secco.service" > "$TMP_SERVICE"

TARGET_SERVICE="$INSTALL_SYSTEMD/$SERVICE_NAME"
TARGET_TIMER="$INSTALL_SYSTEMD/money-banco-secco.timer"
TMP_TIMER=$(mktemp)
sed -e "s|{{PROJECT_ROOT}}|$PROJECT_ROOT|g" \
    "$PROJECT_ROOT/deploy/templates/money-banco-secco.timer" > "$TMP_TIMER"

if [[ "$DRY_RUN" == true ]]; then
    echo "=== DRY-RUN: confronto $TARGET_SERVICE ==="
    if [[ -f "$TARGET_SERVICE" ]]; then
        diff -u "$TARGET_SERVICE" "$TMP_SERVICE" || true
        echo "--- Diff sopra: se vuoto, nulla da fare ---"
    else
        echo "File non esiste: verrebbe creato"
        cat "$TMP_SERVICE"
    fi
    echo ""
    echo "=== DRY-RUN: confronto $TARGET_TIMER ==="
    if [[ -f "$TARGET_TIMER" ]]; then
        diff -u "$TARGET_TIMER" "$TMP_TIMER" || true
        echo "--- Diff sopra: se vuoto, nulla da fare ---"
    else
        echo "File non esiste: verrebbe creato"
        cat "$TMP_TIMER"
    fi
    rm -f "$TMP_SERVICE" "$TMP_TIMER"
    exit 0
fi

# Installa service
echo "Installazione $SERVICE_NAME -> $TARGET_SERVICE"
cp "$TMP_SERVICE" "$TARGET_SERVICE"
rm -f "$TMP_SERVICE"

# Installa timer
echo "Installazione money-banco-secco.timer -> $TARGET_TIMER"
cp "$TMP_TIMER" "$TARGET_TIMER"
rm -f "$TMP_TIMER"

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl enable money-banco-secco.timer

echo "Fatto. Per testare: systemctl start $SERVICE_NAME"
echo "Per vedere log: journalctl -u $SERVICE_NAME -f"
echo "Timer attivo: systemctl list-timers | grep money-banco"