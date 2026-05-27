#!/bin/bash
# Sync dashboard data from mc2 to nuvola web server
set -e

MC2_DATA="/home/sergio/denaro/dashboard/public"
NUVOLA_WEB="/var/www/html/denaro"
NUVOLA_HOST="sergio@nuvola"

# Sync all JSON files + last 200 lines of squadra.log
scp -o ConnectTimeout=5 -q "$MC2_DATA/mc2.json" "$NUVOLA_HOST:$NUVOLA_WEB/mc2.json"
scp -o ConnectTimeout=5 -q "$MC2_DATA/nuvola.json" "$NUVOLA_HOST:$NUVOLA_WEB/nuvola.json"
scp -o ConnectTimeout=5 -q "$MC2_DATA/marcodg1.json" "$NUVOLA_HOST:$NUVOLA_WEB/marcodg1.json"
tail -200 /home/sergio/denaro/squadra/squadra.log | ssh -o ConnectTimeout=5 "$NUVOLA_HOST" "cat > $NUVOLA_WEB/squadra.log"

echo "$(date '+%Y-%m-%d %H:%M:%S') - Dashboard sync OK"
