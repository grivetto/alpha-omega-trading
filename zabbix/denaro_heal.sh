#!/bin/bash
# Denaro Auto-Heal — riavvia l'unit systemd del bot/nodo via SSH.
# Chiamato da Zabbix (global script, eseguito nel container zabbix-server su mc2)
# con argomento {HOST.NAME}. Le chiavi ssh (user zabbix) sono in /var/lib/zabbix/.ssh.
HOST="$1"
[ -z "$HOST" ] && { echo "usage: denaro_heal.sh <host>"; exit 2; }

case "$HOST" in
  # MARCODG1 — tutti i bot live/paper girano nel Node unificato (denaro-node-paper)
  alpha-omega-bot-sol-eur|alpha-omega-bot-ada-eur|alpha-omega-bot-doge-eur|alpha-omega-bot-eth-eur|alpha-omega-node-paper|alpha-omega-paper-ada|alpha-omega-paper-sol|alpha-omega-paper-xrp)
    T="marco@87.106.222.123"; U="denaro-node-paper" ;;
  # nuvola — node unificato (Kraken SOL incluso)
  alpha-omega-bot-kraken|alpha-omega-node-nuvola|nuvola)
    T="sergio@87.106.3.15"; U="denaro-node-nuvola" ;;
  # mc2 — node locale (ssh dal container all'host)
  alpha-omega-node-mc2|mc2)
    T="sergio@192.168.1.99"; U="denaro-node-mc2" ;;
  *) echo "host sconosciuto: $HOST"; exit 2 ;;
esac

echo "$(date -Is) heal: $HOST -> $T restart $U"
if ssh -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new "$T" "sudo -n systemctl restart $U && systemctl is-active $U"; then
  echo "$(date -Is) heal OK: $U attivo su $HOST"
  exit 0
else
  echo "$(date -Is) heal FAIL: $T $U"
  exit 1
fi
