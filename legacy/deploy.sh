#!/usr/bin/env bash
# =============================================================================
# Denaro Deploy Script v5 — Push to nuvola + MARCODG1 and restart services
#
# v5 improvements:
#   - MARCODG1 deploy via nuvola jump-host (proxy jump)
#   - Nuvola: rsync diretto (funziona da Windows)
#   - MARCODG1: rsync via `ssh nuvola` come jump host
#   - Better error handling: non abortisce su errori pip non-critical
#   - Forza stop del servizio prima del deploy (evita lockout loop)
#   - Verifica stato dopo deploy con retry
#   - Aggiunge variabili d'ambiente v5 automaticamente a .env
#
# Usage:
#   ./deploy.sh              # Dry run (default)
#   ./deploy.sh --live       # Deploy a tutte le macchine
#   ./deploy.sh --nuvola     # Solo nuvola
#   ./deploy.sh --marcodg1   # Solo MARCODG1 (via nuvola jump)
#
# Prerequisites:
#   - SSH keys configured for sergio@nuvola
#   - From nuvola: SSH keys for marco@MARCODG1
#   - sergio has sudo on nuvola, marco has sudo on MARCODG1
#   - Both machines have denaro code at /home/{user}/denaro/
# =============================================================================

set -euo pipefail

# ─── Config ──────────────────────────────────────────────────────────────────
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
EXCLUDE="--exclude=__pycache__ --exclude=.git --exclude=_archive --exclude=.ruff_cache --exclude=*.pyc --exclude=.env --exclude=venv --exclude=*.log --exclude=*.log.* --exclude=dashboard --exclude=state --exclude=__pycache__"

NUVOLA_HOST="nuvola"
NUVOLA_USER="sergio"
NUVOLA_PATH="/home/sergio/denaro"
NUVOLA_SERVICE="denaro-kraken.service"

MARCO_HOST="MARCODG1"
MARCO_USER="marco"
MARCO_PATH="/home/marco/denaro"
MARCO_SERVICE="denaro-kraken-marcodg1.service"

# ─── Flags ───────────────────────────────────────────────────────────────────
DRY_RUN=true
DEPLOY_NUVOLA=false
DEPLOY_MARCO=false

for arg in "$@"; do
    case "$arg" in
        --live)          DRY_RUN=false ;;
        --nuvola)        DEPLOY_NUVOLA=true ;;
        --marcodg1)      DEPLOY_MARCO=true ;;
        --dry-run|--help)
            echo "Usage: $0 [--live] [--nuvola] [--marcodg1]"
            echo ""
            echo "  --live            Execute deploy (default: dry-run)"
            echo "  --nuvola          Deploy only to nuvola (Kraken v5)"
            echo "  --marcodg1        Deploy only to MARCODG1 (via nuvola jump)"
            exit 0
            ;;
    esac
done

# Default: deploy to both
if ! $DEPLOY_NUVOLA && ! $DEPLOY_MARCO; then
    DEPLOY_NUVOLA=true
    DEPLOY_MARCO=true
fi

# ─── Functions ───────────────────────────────────────────────────────────────

ensure_env_v5() {
    local host="$1"
    local user="$2"
    local path="$3"
    echo "  [env] Checking v5 env vars..."
    # Add v5 cache config if missing
    ssh "$user@$host" "grep -q 'BALANCE_CACHE_TTL' $path/.env 2>/dev/null || \
        echo -e '\n# v5: Cache config\nBALANCE_CACHE_TTL=15\nORDERS_CACHE_TTL=10\nLOCKOUT_BACKOFF_MIN=30\nLOCKOUT_BACKOFF_MAX=600' >> $path/.env"
}

deploy_to() {
    local host="$1"
    local user="$2"
    local path="$3"
    local service="$4"
    local health_port="${5:-8909}"
    local jump="${6:-}"  # jump host (optional)

    local rsync_cmd="rsync -avz $EXCLUDE"
    local ssh_target="$user@$host"
    local ssh_prefix="ssh $user@$host"
    local rsync_full

    if [ -n "$jump" ]; then
        # Via jump host
        rsync_full="$rsync_cmd -e 'ssh -J $jump' $REPO_DIR/ $ssh_target:$path/"
        ssh_prefix="ssh -J $jump $user@$host"
    else
        rsync_full="$rsync_cmd $REPO_DIR/ $ssh_target:$path/"
    fi

    echo ""
    echo "══════════════════════════════════════════════════════════════"
    echo "  → $host ($ssh_target:$path)"
    [ -n "$jump" ] && echo "    via jump: $jump"
    echo "══════════════════════════════════════════════════════════════"

    # Step 0: Stop service gracefully
    echo "  [0/5] Stopping $service..."
    if $DRY_RUN; then
        echo "        $ssh_prefix 'sudo systemctl stop $service || true'"
    else
        $ssh_prefix "sudo systemctl stop $service || true" && echo "        ✅ Stopped" || echo "        ⚠️  Could not stop (may already be down)"
    fi

    # Step 1: Rsync code
    echo "  [1/5] Rsyncing code..."
    if $DRY_RUN; then
        echo "        $rsync_full"
    else
        # Use pipefail-safe rsync
        if [ -n "$jump" ]; then
            rsync -avz $EXCLUDE -e "ssh -J $jump" "$REPO_DIR/" "$ssh_target:$path/" || echo "        ⚠️  rsync had non-zero exit (continuing)"
        else
            rsync -avz $EXCLUDE "$REPO_DIR/" "$ssh_target:$path/" || echo "        ⚠️  rsync had non-zero exit (continuing)"
        fi
        echo "        ✅ Done"
    fi

    # Step 2: Install deps
    echo "  [2/5] Installing Python dependencies..."
    if $DRY_RUN; then
        echo "        $ssh_prefix 'cd $path && pip install -r requirements.txt --quiet 2>/dev/null || true'"
    else
        $ssh_prefix "cd $path && pip install -r requirements.txt --quiet 2>/dev/null" || true
        echo "        ✅ Done"
    fi

    # Step 3: Add v5 env vars
    echo "  [3/5] Ensuring v5 environment variables..."
    if $DRY_RUN; then
        echo "        [DRY-RUN — skipped]"
    else
        $ssh_prefix "grep -q 'BALANCE_CACHE_TTL' $path/.env 2>/dev/null || echo -e '\n# v5: Cache config\nBALANCE_CACHE_TTL=15\nORDERS_CACHE_TTL=10\nLOCKOUT_BACKOFF_MIN=30\nLOCKOUT_BACKOFF_MAX=600' >> $path/.env"
        echo "        ✅ Done"
    fi

    # Step 4: Restart service
    echo "  [4/5] Restarting $service..."
    if $DRY_RUN; then
        echo "        $ssh_prefix 'sudo systemctl restart $service'"
    else
        $ssh_prefix "sudo systemctl restart $service" && echo "        ✅ Restarted" || echo "        ⚠️  Restart failed"
    fi

    # Step 5: Verify
    echo "  [5/5] Verifying..."
    if $DRY_RUN; then
        echo "        [DRY-RUN — skipped]"
    else
        echo ""
        echo "  ── Service status ──"
        sleep 2
        $ssh_prefix "systemctl is-active $service" || echo "       ⚠️  Not active (may still be starting)"
        echo ""
        echo "  ── Last 8 log lines ──"
        $ssh_prefix "journalctl -u $service -n 8 --no-pager --output=short-iso" || echo "       ⚠️  Cannot read journalctl"
        echo ""
        echo "  ── Health endpoint (port ${health_port}) ──"
        for i in 1 2 3 4 5; do
            result=$($ssh_prefix "curl -sf http://127.0.0.1:${health_port}/health 2>/dev/null || echo 'FAIL'")
            if [ "$result" != "FAIL" ]; then
                echo "       $result"
                break
            fi
            [ "$i" -lt 5 ] && echo "       (retry $i: waiting for service...) " && sleep 3
        done
        [ "$result" = "FAIL" ] && echo "       ⚠️  Health endpoint not reachable (service may still be starting)"
    fi
}

# ─── Main ────────────────────────────────────────────────────────────────────

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║           Denaro Deploy Script v5                          ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "  Mode:    $($DRY_RUN && echo 'DRY-RUN (add --live to deploy)' || echo 'LIVE')"
echo "  Target:  $($DEPLOY_NUVOLA && echo 'nuvola ')$($DEPLOY_MARCO && echo 'MARCODG1')"
echo "  Repo:    $REPO_DIR"
echo ""

if ! $DRY_RUN; then
    echo "  WARNING: LIVE mode! Press Ctrl+C within 3 seconds to abort..."
    sleep 3
fi

# Nuvola: direct deploy
$DEPLOY_NUVOLA && deploy_to "$NUVOLA_HOST" "$NUVOLA_USER" "$NUVOLA_PATH" "$NUVOLA_SERVICE" "8909"

# MARCODG1: deploy via nuvola as jump host
if $DEPLOY_MARCO; then
    # Verify nuvola can reach MARCODG1
    echo ""
    echo "Checking nuvola→MARCODG1 connectivity..."
    if $DRY_RUN; then
        echo "  ssh sergio@nuvola 'ssh -o ConnectTimeout=5 marco@MARCODG1 echo OK'"
    else
        SSH_RESULT=$(ssh sergio@nuvola "ssh -o ConnectTimeout=5 marco@MARCODG1 'echo OK'" 2>&1) || true
        if echo "$SSH_RESULT" | grep -q "OK"; then
            echo "  ✅ nuvola can reach MARCODG1"
        else
            echo "  ⚠️  nuvola→MARCODG1: $SSH_RESULT"
            echo "  Will try deploy anyway via proxy jump..."
        fi
    fi
    deploy_to "$MARCO_HOST" "$MARCO_USER" "$MARCO_PATH" "$MARCO_SERVICE" "8910" "sergio@nuvola"
fi

echo ""
echo "══════════════════════════════════════════════════════════════"
echo "  ✅ Deploy complete"
echo "══════════════════════════════════════════════════════════════"
