#!/usr/bin/env bash
# fleet_audit.sh - controllo generale READ-ONLY dell'infrastruttura Denaro.
host=$(hostname)
echo "##### HOST: $host   $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "--- sistema ---"
uptime | sed 's/^/  /'
free -m | awk 'NR<=2{printf "  %s\n",$0}'
df -h / /home 2>/dev/null | awk 'NR==1||/\/$|\/home/{printf "  %s\n",$0}'
echo "--- unit denaro/atlas/hermes/tunnel/cloudflared ---"
systemctl list-units --all --no-pager --plain 'denaro*' 'atlas*' 'hermes*' '*tunnel*' 'cloudflared*' 2>/dev/null | grep -E '\.service' | head -30 | sed 's/^/  /'
echo "--- unit FAILED ---"
f=$(systemctl --failed --no-pager --plain 2>/dev/null | grep -c '\.service')
echo "  failed count: $f"
systemctl --failed --no-pager --plain 2>/dev/null | head -12 | sed 's/^/  /'
echo "--- restart count per unit denaro*/atlas* ---"
for u in $(systemctl list-unit-files --no-pager --plain 'denaro*' 'atlas*' 2>/dev/null | awk '{print $1}'); do
  n=$(systemctl show "$u" -p NRestarts --value 2>/dev/null)
  s=$(systemctl is-active "$u" 2>/dev/null)
  e=$(systemctl is-enabled "$u" 2>/dev/null)
  printf "  %-38s active=%-10s enabled=%-10s restarts=%s\n" "$u" "$s" "$e" "$n"
done
echo "--- porte in ascolto (rilevanti) ---"
ss -ltnp 2>/dev/null | grep -E ':(8911|8912|8913|1080|8642|3080|50080|2222|10051)\b' | sed 's/^/  /' || echo "  nessuna"
echo "--- health / node_data (eta file) ---"
for d in /home/*/denaro/health /home/*/alpha-omega-trading/node_data /home/*/denaro_node_app/node_data /var/lib/denaro; do
  [ -d "$d" ] || continue
  echo "  [$d]"
  find "$d" -maxdepth 1 -name '*.json' -printf '    %TY-%Tm-%Td %TH:%TM  %8s  %f\n' 2>/dev/null | sort | tail -25
done
echo "--- dimensioni log/coda ---"
for f in /home/*/hermes_bridge/inbox.md /home/*/hermes_bridge/outbox.md /home/*/hermes_bridge/state.json /home/*/hermes_bridge/ds_heartbeat.log /home/*/denaro/*.log /var/log/syslog; do
  [ -f "$f" ] && printf "  %10s  %s\n" "$(du -h "$f" | cut -f1)" "$f"
done
echo "--- errori recenti (journal, ultimi 60 min) ---"
journalctl --since '-60 min' -p err --no-pager 2>/dev/null | tail -12 | sed 's/^/  /' || echo "  (nessun accesso al journal)"
echo "--- cron utente ---"
crontab -l 2>/dev/null | grep -v '^#' | grep -v '^$' | sed 's/^/  /' || echo "  (nessun crontab)"
echo
