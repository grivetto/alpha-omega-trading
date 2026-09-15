#!/usr/bin/env bash
# port_guard.sh - termina le copie ESTRANEE di un servizio che occupano la sua
# porta, prima che systemd avvii l'istanza "buona".
#
# Perche' esiste (incident 2026-09-10): denaro-aggregator-mc2.service e' andato
# in restart-loop (NRestarts=17) con "OSError: [Errno 98] Address already in
# use" perche' un aggregator lanciato A MANO teneva la 127.0.0.1:8912. In quella
# finestra la dashboard non aveva dati (il proxy /api/infra.json rispondeva 502).
#
# Uso (da ExecStartPre):
#   port_guard.sh NOME_UNIT PATTERN_SCRIPT [PORTA]
# esempio:
#   port_guard.sh denaro-aggregator-mc2.service infra_aggregator.py 8912
#
# Sicurezza (lezione appresa il 2026-09-10 alle 23:58): NON si uccide per porta.
# Sulla 8912 ascoltava anche il tunnel SSH inverso zabbix-tunnel-reverse
# (-L 8912:127.0.0.1:8912 su IPv6) che NON va toccato. Quindi si uccide solo un
# processo il cui PRIMO ARGOMENTO (lo script interpretato) contiene PATTERN e
# che NON appartiene al cgroup della unit indicata.
#
# Esce sempre 0: il guard non deve mai impedire l'avvio del servizio.
set -u

UNIT="${1:?uso: port_guard.sh NOME_UNIT PATTERN_SCRIPT [PORTA]}"
PATTERN="${2:?uso: port_guard.sh NOME_UNIT PATTERN_SCRIPT [PORTA]}"
PORT="${3:-}"

self_pid="$$"
killed=0

for d in /proc/[0-9]*; do
  pid="${d#/proc/}"
  [ "${pid}" = "${self_pid}" ] && continue
  [ -r "${d}/cmdline" ] || continue

  # primo e secondo argomento del processo
  args=()
  while IFS= read -r -d '' a; do args+=("${a}"); done < "${d}/cmdline" 2>/dev/null
  [ "${#args[@]}" -ge 2 ] || continue
  script="${args[1]}"
  case "${script}" in
    *"${PATTERN}"*) ;;
    *) continue ;;
  esac

  # esclude i processi della unit stessa (quelli li gestisce systemd)
  if [ -n "${UNIT}" ] && grep -qs -- "${UNIT}" "${d}/cgroup" 2>/dev/null; then
    echo "port_guard: pid ${pid} appartiene a ${UNIT} -> nessuna azione"
    continue
  fi

  echo "port_guard: pid ${pid} e' una copia ESTRANEA di ${PATTERN} (avviata fuori da systemd) -> terminazione"
  kill -TERM "${pid}" 2>/dev/null || true
  for _ in 1 2 3 4 5 6; do
    kill -0 "${pid}" 2>/dev/null || break
    sleep 0.5
  done
  if kill -0 "${pid}" 2>/dev/null; then
    echo "port_guard: pid ${pid} ignora SIGTERM -> SIGKILL"
    kill -KILL "${pid}" 2>/dev/null || true
    sleep 0.5
  fi
  killed=$(( killed + 1 ))
done

if [ -n "${PORT}" ] && ss -ltnH "sport = :${PORT}" 2>/dev/null | grep -q .; then
  echo "port_guard: :${PORT} risulta ancora occupata (dopo ${killed} copie estranee terminate)"
else
  echo "port_guard: ok (copie estranee terminate: ${killed})"
fi
exit 0
