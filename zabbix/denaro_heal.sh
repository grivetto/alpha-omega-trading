#!/bin/bash
# Denaro Auto-Heal — riavvia l'unit systemd del bot su MARCODG1/nuvola via SSH.
# Chiamato da Zabbix (global script, eseguito sul server) con argomento {HOST.NAME}.
# Uso: denaro_heal.sh <hostname-zabbix>
HOST="$1"
[ -z "$HOST" ] && { echo "usage: denaro_heal.sh <host>"; exit 2; }

case "$HOST" in
  alpha-omega-bot-sol-eur) T="marco@87.106.222.123"; U="denaro-solo-sol-marcodg1" ;;
  alpha-omega-bot-ada-eur) T="marco@87.106.222.123"; U="denaro-solo-ada-marcodg1" ;;
  alpha-omega-bot-kraken)  T="sergio@87.106.3.15";    U="denaro-kraken-sol" ;;
  alpha-omega-paper-ada)   T="marco@87.106.222.123"; U="denaro-paper-ada" ;;
  alpha-omega-paper-sol)   T="marco@87.106.222.123"; U="denaro-paper-sol" ;;
  alpha-omega-paper-xrp)   T="marco@87.106.222.123"; U="denaro-paper-xrp" ;;
  nuvola)                  T="sergio@87.106.3.15";    U="atlas-engine" ;;
  *) echo "host sconosciuto: $HOST"; exit 2 ;;
esac

echo "$(date -Is) heal: $HOST -> $T restart $U"
if ssh -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new "$T" "sudo systemctl restart $U && systemctl is-active $U"; then
  echo "$(date -Is) heal OK: $U attivo su $HOST"
  exit 0
else
  echo "$(date -Is) heal FAIL: $T $U"
  exit 1
fi
