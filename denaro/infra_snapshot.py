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

    # TUTTI i bot (live + paper + trend, locali e remoti) dall'aggregator —
    # stessa fonte di /infra.json: un unico set di verita'.
    bots = agg.collect_node_bots()
    data["bots"] = bots
    balances = {}
    for label, (path, prefix) in agg.ENV_FILES.items():
        env = agg.load_env(path)
        acct = {k[len(prefix):]: v for k, v in env.items() if k.startswith(prefix)} if prefix else env
        if acct.get("OKX_API_KEY"):
            balances[label] = agg.fetch_okx_balance(acct)
        else:
            balances[label] = {"ok": False, "error": "no key"}
    for label, (ssh_target, ssh_port, remote_env, remote_py) in agg.REMOTE_ENV_SOURCES.items():
        res = agg.fetch_remote_okx_balance(ssh_target, ssh_port, remote_env, remote_py)
        balances[label] = res if res else {"ok": False, "error": "ssh/ccxt fallito"}
    for path, key_attr, sec_attr in agg.KRAKEN_ENV_FILES:
        e = agg.load_env(path)
        k, s = e.get(key_attr), e.get(sec_attr)
        if not k or not s:
            continue
        r = agg.fetch_kraken_balance({key_attr: k, sec_attr: s}, key_attr, sec_attr)
        if r.get("ok"):
            if not any(v.get("acct") and v.get("acct") == r.get("acct")
                       for kk, v in balances.items() if kk.lower().startswith("kraken")):
                balances["kraken"] = r
            break
    data["balances"] = balances

    real_total, equity_detail, unpriced = agg.balance_eur(balances)
    data["equity_breakdown"] = equity_detail
    data["equity_unpriced"] = unpriced

    data["prices"] = agg.fetch_prices()
    data["nodes"] = {n: {"reachable": agg.ping_host(h, p), "host": h} for n, (h, p) in agg.NODES.items()}
    data["zabbix"] = agg.zabbix_state()
    data["docker"] = agg.docker_state()
    data["system"] = agg.system_state()

    # Node (Fase 3) — stessa logica dell'aggregator
    node_bots = agg.collect_node_bots()
    data["node_bots"] = node_bots

    # CAPITALE TOTALE REALE = somma dei SALDI reali (account deduplicati),
    # non piu' la somma dei total_equity per-bot (che duplica il saldo del
    # subaccount su ogni bot e non vede i conti non presidiati da un bot).
    okx_eq = sum(b.get("total_equity", 0) for k, b in node_bots.items()
                 if k.startswith("okx:") and b.get("status") == "running"
                 and not b.get("stale"))
    kraken_eq = sum(b.get("total_equity", 0) for k, b in node_bots.items()
                    if (k.startswith("kraken:") or k.startswith("trend-live:"))
                    and b.get("status") == "running" and not b.get("stale"))
    data["bot_equity"] = round(okx_eq, 2)
    data["kraken_equity"] = round(kraken_eq, 2)
    if real_total > 0:
        data["total_equity"] = round(real_total, 2)
        data["equity_source"] = "balances"
    else:
        data["total_equity"] = round(okx_eq + kraken_eq, 2)
        data["equity_source"] = "bots"

    # Totali ONESTI: unica implementazione condivisa con l'aggregatore
    # (live/paper separati, stale esclusi). Prima questa logica era duplicata
    # qui e le due copie potevano divergere: e' il motivo per cui la dashboard
    # pubblica mostrava +74,99 EUR di PnL contro -0,30 reali.
    # Totali ONESTI. Osservato dal vivo il 2026-09-16: la dashboard pubblica
    # mostrava +74,99 EUR di PnL mentre il risultato realizzato era ~-0,30 EUR.
    # Due cause:
    #  - i bot con health VECCHIO contavano come "running" (nodi spenti da
    #    giorni apparivano attivi): ora serve health non stale;
    #  - il PnL dei bot PAPER (equity virtuali da 100-300 EUR) veniva sommato a
    #    quello reale: ora e' una voce separata.
    # Logica volutamente inline e non importata dall'aggregatore: il cron che
    # genera lo snapshot deve restare autonomo.
    _live = [b for b in node_bots.values()
             if b.get("status") == "running" and not b.get("stale")
             and b.get("mode") == "live"]
    _paper = [b for b in node_bots.values()
              if b.get("status") == "running" and not b.get("stale")
              and b.get("mode") != "live"]
    data["node_total_pnl"] = round(sum(b.get("pnl", 0) for b in _live), 4)
    data["node_paper_pnl"] = round(sum(b.get("pnl", 0) for b in _paper), 4)
    data["node_live_bots"] = len(_live)
    data["node_paper_bots"] = len(_paper)
    data["node_stale_bots"] = sorted(k for k, b in node_bots.items()
                                     if isinstance(b, dict) and b.get("stale"))
    data["node_total_trades"] = sum(b.get("trades", 0) for b in _live)
    _wins = sum(b.get("wins", 0) for b in _live)
    _losses = sum(b.get("losses", 0) for b in _live)
    data["node_win_rate"] = (round(_wins / (_wins + _losses) * 100, 1)
                             if (_wins + _losses) else 0)
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
        running = [b for b in nb.values()
                   if b.get("status") == "running" and not b.get("stale")]
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
