#!/usr/bin/env python3
"""Su MARCODG1: genera snapshot completo (bot OKX + saldi + prezzi) ogni 30s.
La dashboard legge solo questo file → risposta istantanea."""
import json
import time
from pathlib import Path

sys_path = str(Path(__file__).resolve().parent)
import sys
sys.path.insert(0, sys_path)

import importlib.util
spec = importlib.util.spec_from_file_location("agg", sys_path + "/infra_aggregator.py")
agg = importlib.util.module_from_spec(spec)
# Non avviamo il server: importiamo solo le funzioni (il main e' guardato)
# Eseguiamo il modulo in modo sicuro: le funzioni sono a livello modulo
spec.loader.exec_module(agg)

HEALTH_DIR = Path(sys_path) / "health"
OUT = HEALTH_DIR / "infra_snapshot.json"


def build():
    data = {"generated": time.time(), "ts_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

    bots = {}
    for name in ("sol", "ada"):
        p = HEALTH_DIR / f"{name}.json"
        if p.exists():
            try:
                bots[name] = json.loads(p.read_text())
            except Exception:
                bots[name] = {"status": "error"}
        else:
            bots[name] = {"status": "no_file"}
    snap_path = HEALTH_DIR / "kraken_snapshot.json"
    if snap_path.exists():
        try:
            snap = json.loads(snap_path.read_text())
            if snap.get("bot"):
                bots["sol_kraken"] = snap["bot"]
        except Exception:
            snap = None
    data["bots"] = bots

    balances = {}
    for label, path in agg.ENV_FILES.items():
        env = agg.load_env(path)
        if env.get("OKX_API_KEY"):
            balances[label] = agg.fetch_okx_balance(env)
        else:
            balances[label] = {"ok": False, "error": "no key"}
    if snap_path.exists() and snap:
        balances["kraken (nuvola)"] = {
            "ok": True,
            "total": snap.get("balance", {}),
            "total_eur": snap.get("total_eur", 0),
        }
    data["balances"] = balances
    data["prices"] = agg.fetch_prices()
    data["nodes"] = {n: {"reachable": agg.ping_host(h, p), "host": h} for n, (h, p) in agg.NODES.items()}
    data["zabbix"] = agg.zabbix_state()
    data["docker"] = agg.docker_state()
    data["system"] = agg.system_state()

    # Node (Fase 3) — stessa logica dell'aggregator
    node_bots = agg.collect_node_bots()
    data["node_bots"] = node_bots

    # CAPITALE TOTALE REALE = bot LIVE del Node (okx:* + kraken:*), esclusi paper
    okx_eq = sum(b.get("total_equity", 0) for k, b in node_bots.items()
                 if k.startswith("okx:") and b.get("status") == "running")
    kraken_eq = sum(b.get("total_equity", 0) for k, b in node_bots.items()
                    if k.startswith("kraken:") and b.get("status") == "running")
    data["bot_equity"] = round(okx_eq, 2)
    data["kraken_equity"] = round(kraken_eq, 2)
    data["total_equity"] = round(okx_eq + kraken_eq, 2)

    node_running = [b for b in node_bots.values() if b.get("status") == "running"]
    data["node_total_pnl"] = round(sum(b.get("pnl", 0) for b in node_running), 4)
    data["node_total_trades"] = sum(b.get("trades", 0) for b in node_running)
    wins = sum(b.get("wins", 0) for b in node_running)
    losses = sum(b.get("losses", 0) for b in node_running)
    data["node_win_rate"] = round(wins / (wins + losses) * 100, 1) if (wins + losses) else 0
    data["node_errors"] = {sym: b.get("error", "")
                           for sym, b in node_bots.items() if b.get("error")}

    # Totali PER NODO (stessa logica dell'aggregator)
    node_totals = {}
    all_node_names = ["marcodg1"] + list(agg.REMOTE_NODES.keys())
    remote_prefixes = tuple(f"{n}:" for n in agg.REMOTE_NODES)
    for node_name in all_node_names:
        if node_name == "marcodg1":
            nb = {k: v for k, v in node_bots.items()
                  if not k.startswith(remote_prefixes)}
        else:
            prefix = f"{node_name}:"
            nb = {k: v for k, v in node_bots.items() if k.startswith(prefix)}
        running = [b for b in nb.values() if b.get("status") == "running"]
        node_totals[node_name] = {
            "bots": len(nb),
            "running": len(running),
            "pnl": round(sum(b.get("pnl", 0) for b in running), 4),
            "trades": sum(b.get("trades", 0) for b in running),
            "equity": round(sum(b.get("total_equity", 0) for b in running), 2),
            "reachable": (node_name == "marcodg1"
                          or any(h.get("timestamp") for h in nb.values())),
        }
    data["node_totals"] = node_totals
    data["services"] = agg.collect_services()

    # Trend storico (append, max 240 punti)
    trend = agg.read_trend()
    trend.append({"ts": int(time.time()), "equity": data["total_equity"],
                  "node_pnl": data["node_total_pnl"]})
    agg.write_trend(trend[-240:])
    data["trend"] = trend[-240:]

    tmp = str(OUT) + ".tmp"
    Path(tmp).write_text(json.dumps(data))
    Path(tmp).replace(OUT)
    print(f"snapshot scritto: {data['total_equity']} EUR (node pnl {data['node_total_pnl']})")


if __name__ == "__main__":
    build()
