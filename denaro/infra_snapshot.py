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
import types
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

    bot_eq = 0.0
    for name, b in bots.items():
        if name == "sol_kraken":
            continue
        if b.get("status") == "running":
            bot_eq += b.get("total_equity", 0)
    kraken_eur = 0.0
    if balances.get("kraken (nuvola)") and balances["kraken (nuvola)"].get("total_eur"):
        kraken_eur = balances["kraken (nuvola)"]["total_eur"]
    data["bot_equity"] = round(bot_eq, 2)
    data["kraken_equity"] = round(kraken_eur, 2)
    data["total_equity"] = round(bot_eq + kraken_eur, 2)

    tmp = str(OUT) + ".tmp"
    Path(tmp).write_text(json.dumps(data))
    Path(tmp).replace(OUT)
    print(f"snapshot scritto: {data['total_equity']} EUR")


if __name__ == "__main__":
    build()
