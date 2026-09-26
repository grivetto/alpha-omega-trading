#!/usr/bin/env bash
# deploy/scripts/money_banco_secco.sh — lancia il banco di prova a secco.
# La logica sta in deploy/banco/money_banco_secco.py (unit-testabile).
# Qui solo: venv + caricamento dei segreti. Nessun ordine viene mai inviato:
# l'invio e' assente dal codice, non disattivato da un flag.
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
ENV_FILE="${ENV_FILE:-$PROJECT_ROOT/config/.env_banco}"

PY="$PROJECT_ROOT/venv/bin/python3"
if [[ ! -x "$PY" ]]; then
    PY="$(command -v python3 || true)"
fi
if [[ -z "$PY" ]]; then
    echo "ERRORE: nessun python3 trovato" >&2
    exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
    echo "ERRORE: ENV_FILE '$ENV_FILE' non trovato: copiare config/.env_banco.example in config/.env_banco e riempirlo (chiave dedicata SOLO Read)" >&2
    exit 1
fi

# I segreti vivono solo in questo file: git-ignored, chmod 600, mai nel log.
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

export PROJECT_ROOT
exec "$PY" "$PROJECT_ROOT/deploy/banco/money_banco_secco.py" "$@"
