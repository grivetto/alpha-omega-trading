#!/usr/bin/env python3
"""fleet_snapshot.py - istantanea leggibile dello stato della flotta (solo lettura).

Sorgenti:
  - mc2 :8912 /api/infra.json  (aggregatore: nodi, bot, balances, zcash...)
  - health file locali ~/denaro/health/*.json (mtime = freschezza reale)
Stampa: per ogni nodo i bot dichiarati, la freschezza dei dati e i numeri di equity/pnl.
Nessuna scrittura, nessun ordine.
"""
from __future__ import annotations

import json
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HEALTH = Path("/home/sergio/denaro/health")


def get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=15) as r:
        return json.loads(r.read().decode())


def age(ts: float) -> str:
    if not ts:
        return "n/d"
    d = datetime.now(timezone.utc).timestamp() - ts
    if d < 3600:
        return f"{d/60:.0f} min"
    if d < 86400:
        return f"{d/3600:.1f} h"
    return f"{d/86400:.1f} giorni"


def main() -> int:
    print("== AGGREGATORE mc2 :8912 ==")
    try:
        d = get("http://127.0.0.1:8912/api/infra.json")
        print("generato:", d.get("ts_iso"), "| nodi:", len(d.get("nodes") or []))
        nodes = d.get("nodes") or {}
        items = nodes.items() if isinstance(nodes, dict) else [(n.get("name") or n.get("node"), n) for n in nodes]
        for name, n in items:
            if not isinstance(n, dict):
                print("  nodo:", name, "->", n)
                continue
            print("  nodo:", name, "| reachable:", n.get("reachable"), "| status:", n.get("status"),
                  "| stale:", n.get("stale"), "| host:", n.get("host"),
                  "| bots:", len(n.get("bots") or []))
        for name, b in (d.get("bots") or {}).items():
            if isinstance(b, dict):
                print(f"  bot {name}: eq={b.get('total_equity')} pnl={b.get('pnl')} trades={b.get('trades')} status={b.get('status')}")
        print("  balances:", json.dumps(d.get("balances"), ensure_ascii=False)[:300])
        print("  bot_equity:", d.get("bot_equity"), "| kraken_equity:", d.get("kraken_equity"))
    except Exception as e:  # noqa: BLE001
        print("  errore aggregatore:", type(e).__name__, e)

    print("\n== HEALTH FILE LOCALI (mtime = freschezza) ==")
    for p in sorted(HEALTH.glob("*.json")):
        try:
            h = json.loads(p.read_text())
        except Exception:  # noqa: BLE001
            continue
        mtime = p.stat().st_mtime
        ts = h.get("timestamp")
        print(f"  {p.name:24s} mtime={datetime.fromtimestamp(mtime):%Y-%m-%d %H:%M} "
              f"ts_dato={age(ts):>10s} status={h.get('status')} pnl={h.get('pnl')} "
              f"trades={h.get('trades')} eq={h.get('total_equity')}")

    print("\n== PROCESSI BOT SU mc2 ==")
    out = subprocess.run("pgrep -af 'denaro_node|health_server|infra_aggregator' | grep -v pgrep",
                         shell=True, capture_output=True, text=True).stdout.strip()
    print(out or "  (nessuno)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
