#!/usr/bin/env bash
# =============================================================================
# Denaro Deploy Script — Push to nuvola + MARCODG1 and restart service
#
# Usage:
#   ./deploy.sh              # Dry run (default)
#   ./deploy.sh --live       # Actual deploy + restart
#   ./deploy.sh --nuvola     # Deploy only to nuvola
#   ./deploy.sh --marcodg1   # Deploy only to MARCODG1
#
# Prerequisites:
#   - SSH keys configured for sergio@nuvola and marco@MARCODG1
#   - sergio has sudo on nuvola, marco has sudo on MARCODG1
#   - Both machines have denaro code at /home/{user}/denaro/
# =============================================================================

set -euo pipefail

# ─── Config ──────────────────────────────────────────────────────────────────
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
EXCLUDE="--exclude=__pycache__ --exclude=.git --exclude=_archive --exclude=.ruff_cache --exclude=*.pyc --exclude=.env --exclude=venv"

NUVOLA_HOST="nuvola"
NUVOLA_USER="sergio"
NUVOLA_PATH="/home/sergio/denaro"
NUVOLA_SERVICE="denaro-kraken.service"

MARCO_HOST="MARCODG1"
MARCO_USER="marco"
MARCO_PATH="/home/marco/denaro"
MARCO_SERVICE="denaro-kraken-marcodg1.service"

# ─── Bybit v5 (MARCODG1) ─────────────────────────────────────────────────────
MARCO_BYBIT_SERVICE="denaro-bybit-marcodg1.service"
MARCO_BYBIT_HEALTH_PORT=8911

# ─── Flags ───────────────────────────────────────────────────────────────────
DRY_RUN=true
DEPLOY_NUVOLA=false
DEPLOY_MARCO=false
DEPLOY_MARCO_BYBIT=false

for arg in "$@"; do
    case "$arg" in
        --live)          DRY_RUN=false ;;
        --nuvola)        DEPLOY_NUVOLA=true ;;
        --marcodg1)      DEPLOY_MARCO=true ;;
        --marcodg1-bybit) DEPLOY_MARCO_BYBIT=true ;;
        --dry-run|--help)
            echo "Usage: $0 [--live] [--nuvola] [--marcodg1] [--marcodg1-bybit]"
            echo ""
            echo "  --live            Execute deploy (default: dry-run)"
            echo "  --nuvola          Deploy only to nuvola (Kraken v4)"
            echo "  --marcodg1        Deploy only to MARCODG1 (Kraken v4)"
            echo "  --marcodg1-bybit  Deploy Bybit v5 to MARCODG1"
            exit 0
            ;;
    esac
done

# Default: deploy to both Kraken nodes
if ! $DEPLOY_NUVOLA && ! $DEPLOY_MARCO && ! $DEPLOY_MARCO_BYBIT; then
    DEPLOY_NUVOLA=true
    DEPLOY_MARCO=true
fi

# ─── Functions ───────────────────────────────────────────────────────────────

deploy_to() {
    local host="$1"
    local user="$2"
    local path="$3"
    local service="$4"
    local health_port="${5:-8909}"

    echo ""
    echo "══════════════════════════════════════════════════════════════"
    echo "  → $host ($user@$host:$path)"
    echo "══════════════════════════════════════════════════════════════"

    # Step 1: Rsync code (excluding __pycache__, .env, etc.)
    echo "  [1/4] Rsyncing code..."
    if $DRY_RUN; then
        echo "        rsync -avz $EXCLUDE $REPO_DIR/ $user@$host:$path/"
        echo "        [DRY-RUN — skipped]"
    else
        rsync -avz $EXCLUDE "$REPO_DIR/" "$user@$host:$path/"
        echo "        ✅ Done"
    fi

    # Step 2: Install/update Python deps
    echo "  [2/4] Installing Python dependencies..."
    if $DRY_RUN; then
        echo "        ssh $user@$host 'cd $path && pip install -r requirements.txt --quiet'"
        echo "        [DRY-RUN — skipped]"
    else
        ssh "$user@$host" "cd $path && pip install -r requirements.txt --quiet" || true
        echo "        ✅ Done"
    fi

    # Step 3: Restart systemd service
    echo "  [3/4] Restarting $service..."
    if $DRY_RUN; then
        echo "        ssh $user@$host 'sudo systemctl restart $service'"
        echo "        [DRY-RUN — skipped]"
    else
        ssh "$user@$host" "sudo systemctl restart $service"
        echo "        ✅ Done"
    fi

    # Step 4: Verify service + logs + health endpoint
    echo "  [4/4] Verifying..."
    if $DRY_RUN; then
        echo "        ssh $user@$host 'systemctl is-active $service && journalctl -u $service -n 10 --no-pager && curl -sf http://127.0.0.1:${health_port}/health'"
        echo "        [DRY-RUN — skipped]"
    else
        echo ""
        echo "  ── Service status ──"
        ssh "$user@$host" "systemctl is-active $service"
        echo ""
        echo "  ── Last 8 log lines ──"
        ssh "$user@$host" "journalctl -u $service -n 8 --no-pager"
        echo ""
        echo "  ── Health endpoint (port ${health_port}) ──"
        # Retry a few times — service may still be starting
        for i in 1 2 3; do
            result=$(ssh "$user@$host" "curl -sf http://127.0.0.1:${health_port}/health 2>/dev/null || echo 'FAIL'")
            if [ "$result" != "FAIL" ]; then
                echo "       $result"
                break
            fi
            [ "$i" -lt 3 ] && echo "       (retry $i: waiting for service...) " && sleep 3
        done
        [ "$result" = "FAIL" ] && echo "       ⚠️  Health endpoint not reachable (service may still be starting)"
    fi
}

# ─── Main ────────────────────────────────────────────────────────────────────

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║           Denaro Deploy Script                             ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "  Mode:    $($DRY_RUN && echo 'DRY-RUN (add --live to deploy)' || echo 'LIVE')"
echo "  Target:  $($DEPLOY_NUVOLA && echo 'nuvola ')$($DEPLOY_MARCO && echo 'MARCODG1(Kraken) ')$($DEPLOY_MARCO_BYBIT && echo 'MARCODG1(Bybit) ')"
echo "  Repo:    $REPO_DIR"
echo ""

if ! $DRY_RUN; then
    echo "  WARNING: LIVE mode! Press Ctrl+C within 3 seconds to abort..."
    sleep 3
fi

$DEPLOY_NUVOLA && deploy_to "$NUVOLA_HOST" "$NUVOLA_USER" "$NUVOLA_PATH" "$NUVOLA_SERVICE"
$DEPLOY_MARCO && deploy_to "$MARCO_HOST" "$MARCO_USER" "$MARCO_PATH" "$MARCO_SERVICE"
$DEPLOY_MARCO_BYBIT && deploy_to "$MARCO_HOST" "$MARCO_USER" "$MARCO_PATH" "$MARCO_BYBIT_SERVICE" "$MARCO_BYBIT_HEALTH_PORT"

echo ""
echo "══════════════════════════════════════════════════════════════"
echo "  ✅ Deploy complete"
echo "══════════════════════════════════════════════════════════════"
