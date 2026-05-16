#!/bin/bash
# Collect dashboard data from all servers
# Pulls nuvola.json and marcodg1.json to mc2, then generates mc2.json locally
# All go into public/ for sync_dashboard.sh to push to nuvola web

cd /home/sergio/denaro || exit 1
PUBLIC="dashboard/public"
mkdir -p "$PUBLIC"

# 1. Run local collector (mc2)
/usr/sbin/python3 collect_dashboard_data.py >/dev/null 2>&1

# 2. Pull nuvola.json from nuvola
scp -o ConnectTimeout=5 -q "sergio@nuvola:/home/sergio/denaro/dashboard/public/nuvola.json" "$PUBLIC/nuvola.json" 2>/dev/null || \
  echo "WARN: nuvola.json pull failed"

# 3. Pull marcodg1.json from MARCODG1
scp -o ConnectTimeout=5 -q "marco@MARCODG1:/home/marco/denaro/dashboard/public/marcodg1.json" "$PUBLIC/marcodg1.json" 2>/dev/null || \
  echo "WARN: marcodg1.json pull failed"

echo "Collect all done: $(ls $PUBLIC/*.json 2>/dev/null | wc -l) files"
