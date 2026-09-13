#!/usr/bin/env bash
# fleet_reconcile.sh — riconciliazione delle ISTANZE dei nodi Denaro.
#
# Caso reale (mc2, 2026-09-13): ogni config girava DUE volte — unita' di sistema
# in /etc/systemd/system E unita' utente in ~/.config/systemd/user con lo
# STESSO nome, WorkingDirectory e config diverse, sullo STESSO conto (due
# processi che piazzano ordini sullo stesso saldo e scrivono gli stessi file
# health). Il rischio e' concreto: due processi sullo stesso conto possono
# piazzare ordini duplicati; oggi non succedeva solo perche' il conto era in
# deadlock.
#
# Uso (dalla macchina target, dove lo script arriva con line-ending LF):
#   bash fleet_reconcile.sh           # DRY-RUN: solo report (default)
#   bash fleet_reconcile.sh --apply   # ferma le istanze duplicate e disabilita
#                                     # le unita' utente che le generano
#
# Da Windows, inviandolo in pipe (PowerShell converte i fine riga in CRLF):
#   ssh host 'tr -d "" | bash -s -- --apply'
#
# Regola di sicurezza: un'istanza viene fermata SOLO se un'altra istanza della
# stessa config e' viva e gestita da systemd. Gli orfani unici non vengono
# toccati: vengono segnalati (serve una unit per riavviarli/monitorarli).
set -uo pipefail

APPLY=0
[ "${1:-}" = "--apply" ] && APPLY=1
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"

declare -A KIND_OF UNIT_OF CFG_OF
PIDS=()

classify() {
  local pid="$1" cg
  cg="$(cat /proc/"$pid"/cgroup 2>/dev/null | head -1)"
  if [[ "$cg" == *"/system.slice/"* ]]; then
    KIND_OF[$pid]="system"
    UNIT_OF[$pid]="${cg##*/system.slice/}"; UNIT_OF[$pid]="${UNIT_OF[$pid]%.service}"
  elif [[ "$cg" == *"/app.slice/"* ]]; then
    KIND_OF[$pid]="user"
    UNIT_OF[$pid]="${cg##*/app.slice/}"; UNIT_OF[$pid]="${UNIT_OF[$pid]%.service}"
  else
    local ppid; ppid="$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')"
    if [ "$ppid" = "1" ]; then KIND_OF[$pid]="orfano"; else KIND_OF[$pid]="sessione"; fi
    UNIT_OF[$pid]="-"
  fi
}

echo "############ RICONCILIAZIONE NODI DENARO — $(hostname) — $(date -u '+%Y-%m-%dT%H:%M:%SZ') ############"
echo "modalita': $([ $APPLY -eq 1 ] && echo APPLY || echo 'DRY-RUN (nessuna modifica)')"
echo

while read -r pid ppid etime args; do
  [ -z "${pid:-}" ] && continue
  cfg="$(echo "$args" | sed -n 's/.*--config \([^ ]*\).*/\1/p')"
  [ -z "$cfg" ] && cfg="(nessuna --config)"
  PIDS+=("$pid"); CFG_OF[$pid]="$cfg"
  classify "$pid"
  printf '%-8s %-9s %-9s %-22s %s\n' "$pid" "$etime" "${KIND_OF[$pid]}" "${UNIT_OF[$pid]}" "$cfg"
done < <(ps -eo pid=,ppid=,etime=,args= | grep -E 'python -m denaro\.denaro_node' | grep -v grep)

echo
echo "---- duplicati per config ----"
declare -A COUNTS
for p in "${PIDS[@]}"; do COUNTS["${CFG_OF[$p]}"]=$(( ${COUNTS["${CFG_OF[$p]}"]:-0} + 1 )); done

DUP_FOUND=0
for cfg in "${!COUNTS[@]}"; do
  n="${COUNTS[$cfg]}"
  [ "$n" -le 1 ] && continue
  DUP_FOUND=1
  echo "!! $cfg  → $n istanze"
  local_keep=""
  for p in "${PIDS[@]}"; do
    [ "${CFG_OF[$p]}" != "$cfg" ] && continue
    printf '     pid=%-8s kind=%-8s unit=%s\n' "$p" "${KIND_OF[$p]}" "${UNIT_OF[$p]}"
    [ "${KIND_OF[$p]}" = "system" ] && local_keep="$p"
  done
  [ -z "$local_keep" ] && echo "     (nessuna istanza gestita da unita' di sistema: NON tocco nulla)"
  for p in "${PIDS[@]}"; do
    [ "${CFG_OF[$p]}" != "$cfg" ] && continue
    [ "$p" = "$local_keep" ] && continue
    case "${KIND_OF[$p]}" in
      user)
        echo "     → ${APPLY:+STOP} ${APPLY:-stop} unita' utente ${UNIT_OF[$p]} (pid $p)"
        if [ $APPLY -eq 1 ]; then
          systemctl --user disable --now "${UNIT_OF[$p]}.service" 2>&1 | sed 's/^/        /'
        fi ;;
      orfano|sessione)
        echo "     → ${APPLY:+KILL} ${APPLY:-kill} pid $p (avviato fuori da systemd)"
        if [ $APPLY -eq 1 ]; then kill "$p" 2>&1 | sed 's/^/        /'; fi ;;
      system)
        echo "     → ${APPLY:+STOP} ${APPLY:-stop} unita' di sistema ${UNIT_OF[$p]} (pid $p)"
        if [ $APPLY -eq 1 ]; then sudo -n systemctl stop "${UNIT_OF[$p]}.service" 2>&1 | sed 's/^/        /'; fi ;;
    esac
  done
done
[ $DUP_FOUND -eq 0 ] && echo "nessun duplicato rilevato"

echo
echo "---- istanze senza gestione systemd (orfane) ----"
ORPH=0
for p in "${PIDS[@]}"; do
  if [ "${KIND_OF[$p]}" = "orfano" ]; then
    ORPH=1
    echo "!! pid $p  config=${CFG_OF[$p]}  → nessuna unit attiva: niente restart automatico, niente avvio al boot"
  fi
done
[ $ORPH -eq 0 ] && echo "nessuna"

echo
echo "---- unita' denaro presenti ----"
echo "[sistema]"; systemctl list-unit-files 'denaro*' --no-legend 2>/dev/null | sed 's/^/  /'
echo "[utente]";  systemctl --user list-unit-files 'denaro*' --no-legend 2>/dev/null | sed 's/^/  /'
