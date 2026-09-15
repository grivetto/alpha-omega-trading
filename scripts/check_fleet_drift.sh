#!/usr/bin/env bash
# check_fleet_drift.sh — verifica READ-ONLY che il deploy coincida col git.
#
# Perche' esiste: al 2026-09-15 la produzione era divergente dal repository
# (config live con XRP enabled:true mentre il repo lo disabilitava, unit systemd
# che puntavano a una root di deploy dismessa, tree con modifiche non committate).
# La deriva non era visibile finche' non la si cercava a mano su tre macchine.
#
# Uso:  bash scripts/check_fleet_drift.sh
# Esce 0 se non rileva deriva sui file di interesse, 1 altrimenti.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOSTS="${HOSTS:-mc2 nuvola MARCODG1}"
FILES=(
  config/node_mc2.yaml
  config/node_nuvola.yaml
  config/node_trend.yaml
  config/node_trend_live_kraken.yaml
  config/node.yaml
)

DRIFT=0
for h in $HOSTS; do
  case "$h" in
    MARCODG1) root="/home/marco/alpha-omega-trading" ;;
    *)        root="/home/sergio/alpha-omega-trading" ;;
  esac
  echo "───────────────────────────────────────────────"
  echo "HOST $h  root=$root"
  for f in "${FILES[@]}"; do
    local_md5="$(md5sum "$REPO_ROOT/$f" 2>/dev/null | cut -d' ' -f1)"
    remote_md5="$(ssh -o BatchMode=yes -o ConnectTimeout=8 "$h" "md5sum $root/$f 2>/dev/null | cut -d' ' -f1" 2>/dev/null)"
    if [ -z "$remote_md5" ]; then
      printf '  %-38s %s\n' "$f" "ASSENTE sul deploy"
      continue
    fi
    if [ "$local_md5" = "$remote_md5" ]; then
      printf '  %-38s %s\n' "$f" "ok"
    else
      printf '  %-38s %s\n' "$f" "DRIFT (git=${local_md5:0:8} deploy=${remote_md5:0:8})"
      DRIFT=1
    fi
  done
done
echo "───────────────────────────────────────────────"
if [ $DRIFT -ne 0 ]; then
  echo "ESITO: deriva rilevata — allineare il deploy al commit prima di operare."
  exit 1
fi
echo "ESITO: git e deploy allineati."
