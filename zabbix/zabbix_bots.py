#!/usr/bin/env python3
"""zabbix_bots.py — Sync automatico dei bot Denaro (officina paper + live) su Zabbix.

Ogni run (cron 1/min su MARCODG1):
  1. legge il payload dell'aggregator (http://127.0.0.1:8912/api/infra.json)
  2. per OGNI bot nel payload crea (se manca) host, item trapper, grafo, trigger
  3. pusha i valori via API history.push (cosi' nasce la storia di trading)
  4. disabilita i host "bot-*" non piu' presenti (la storia resta)

Scala a qualunque numero di bot: le entita' mancanti vengono create al volo.

Sicurezza: credenziali SOLO in ~/.zbx_cred (formato "Utente:Password").
Nessun ordine viene inviato: solo lettura del payload + scrittura su Zabbix.
Nota API 7.0: graph.create vuole "gitems" (non "items").
NOTA: svc.zabbix_bots (heartbeat di questo sync) e' pushato da push_metrics.py,
che ne misura l'eta' del log — non da questo script (un solo scrittore per item).
"""
import json
import re
import time
import urllib.request
from pathlib import Path

API = "http://127.0.0.1:1080/api_jsonrpc.php"
INFRA = "http://127.0.0.1:8912/api/infra.json"
CRED = Path.home() / ".zbx_cred"
GROUP_MONEY = "28"   # gruppo Money (unico gruppo di progetto, dal 02/10)
PREFIX = "bot-"
GRAPH_NAME = "Trading (equity/pnl/trades)"

# key, nome, value_type (2=trapper; 0=float, 3=unsigned), history, trends
ITEMS = [
    ("bot.running",  "bot attivo (0/1)",       3, "30d", "365d"),
    ("bot.stale",    "bot fermo/stale (0/1)",  3, "30d", "365d"),
    ("bot.age_s",    "eta' ultimo tick (s)",   3, "7d",  "30d"),
    ("bot.equity",   "equity (EUR)",           0, "90d", "365d"),
    ("bot.pnl",      "PnL realizzato (EUR)",   0, "90d", "365d"),
    ("bot.trades",   "numero trade",           3, "30d", "365d"),
    ("bot.win_rate", "win rate (%)",           0, "30d", "365d"),
    ("bot.in_pos",   "in posizione (0/1)",     3, "30d", "365d"),
]


def rpc(method, params, auth=None):
    body = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
    if auth:
        body["auth"] = auth
    req = urllib.request.Request(API, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            out = json.loads(resp.read())
    except Exception as e:
        print(f"RPC {method} error: {e}")
        return None
    if "error" in out:
        print(f"RPC {method} error: {out['error'].get('data', out['error'])}")
        return None
    return out.get("result")


def chunked(seq, n=100):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def sanitize(s):
    return re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")


def bot_entries(payload):
    """Dal dict bots -> {host: meta} con display/node/mode/symbol/data."""
    out = {}
    for key, b in (payload.get("bots") or {}).items():
        parts = str(key).split(":")
        if len(parts) != 3:
            continue
        node, mode, symbol = parts
        host = f"{PREFIX}{sanitize(node)}-{sanitize(mode)}-{sanitize(symbol)}"
        out[host] = {"display": f"{node} {mode} {symbol}",
                     "node": node, "mode": mode, "symbol": symbol, "data": b or {}}
    return out


def refresh_hostids(auth, wanted):
    got = rpc("host.get", {"search": {"host": PREFIX},
                           "output": ["hostid", "host"]}, auth) or []
    byhost = {h["host"]: h["hostid"] for h in got}
    for host, meta in wanted.items():
        meta["hostid"] = meta.get("hostid") or byhost.get(host)
        meta["host"] = host
    return byhost


def ensure_hosts(auth, wanted, byhost):
    created = 0
    for host, meta in wanted.items():
        if meta.get("hostid"):
            continue
        res = rpc("host.create", {
            "host": host, "name": meta["display"],
            "groups": [{"groupid": GROUP_MONEY}],
            "tags": [{"tag": "node", "value": meta["node"]},
                     {"tag": "mode", "value": meta["mode"]},
                     {"tag": "symbol", "value": meta["symbol"]}],
            "description": "Bot Denaro (auto-sync zabbix_bots.py)",
        }, auth)
        if res and res.get("hostids"):
            meta["hostid"] = res["hostids"][0]
            byhost[host] = meta["hostid"]
            created += 1
    return created


def ensure_items(auth, wanted):
    hostids = [m["hostid"] for m in wanted.values() if m.get("hostid")]
    if not hostids:
        return 0
    got = rpc("item.get", {"hostids": hostids, "output": ["itemid", "key_", "hostid"]}, auth) or []
    have = {(i["hostid"], i["key_"]) for i in got}
    missing = []
    for meta in wanted.values():
        if not meta.get("hostid"):
            continue
        for key, name, vt, hist, trend in ITEMS:
            if (meta["hostid"], key) in have:
                continue
            missing.append({"name": name, "key_": key, "hostid": meta["hostid"],
                            "type": 2, "value_type": vt, "history": hist, "trends": trend})
    made = 0
    for batch in chunked(missing):
        r = rpc("item.create", batch, auth)
        if r:
            made += len(r.get("itemids") or [])
    return made


def ensure_graphs(auth, wanted):
    hostids = [m["hostid"] for m in wanted.values() if m.get("hostid")]
    if not hostids:
        return 0
    g = rpc("graph.get", {"hostids": hostids, "output": ["graphid", "name"],
                          "selectHosts": ["hostid"]}, auth) or []
    have = {h.get("hostid") for x in g if x.get("name") == GRAPH_NAME
            for h in (x.get("hosts") or [])}
    it = rpc("item.get", {"hostids": hostids, "output": ["itemid", "key_", "hostid"]}, auth) or []
    by = {}
    for i in it:
        by.setdefault(i["hostid"], {})[i["key_"]] = i["itemid"]
    colors = {"bot.equity": "00AA00", "bot.pnl": "0000EE", "bot.trades": "CC0000"}
    made = 0
    for meta in wanted.values():
        hid = meta.get("hostid")
        if not hid or hid in have or hid not in by:
            continue
        ids = by[hid]
        if not all(k in ids for k in colors):
            continue
        res = rpc("graph.create", {
            "name": GRAPH_NAME, "width": 900, "height": 220, "graphtype": 0,
            "gitems": [{"itemid": ids[k], "color": c, "drawtype": 0} for k, c in colors.items()],
        }, auth)
        if res:
            made += 1
    return made


def ensure_triggers(auth, wanted):
    """Trigger 'bot muto' per i soli bot paper (i live possono stare blocked)."""
    made = 0
    tget = rpc("trigger.get", {"search": {"description": "Bot paper muto"},
                               "output": ["triggerid"], "selectHosts": ["hostid"]}, auth) or []
    have = {h["hostid"] for t in tget for h in (t.get("hosts") or [])}
    for meta in wanted.values():
        hid = meta.get("hostid")
        if not hid or meta["mode"] != "paper" or hid in have:
            continue
        res = rpc("trigger.create", {
            "description": f"Bot paper muto >10m: {meta['display']}",
            "expression": f"last(/{meta['host']}/bot.age_s)>600",
            "priority": 2,
        }, auth)
        if res:
            made += 1
    return made


def push_values(auth, wanted):
    now = int(time.time())
    data = []
    for meta in wanted.values():
        if not meta.get("hostid"):
            continue
        b = meta["data"]
        host = meta["host"]
        running = 1 if b.get("status") == "running" else 0
        age = b.get("age_s")
        stale = 1 if (b.get("stale") or (isinstance(age, (int, float)) and age > 300)) else 0
        data += [{"host": host, "key": "bot.running", "value": running},
                 {"host": host, "key": "bot.stale", "value": stale}]
        if isinstance(age, (int, float)):
            data.append({"host": host, "key": "bot.age_s", "value": int(age)})
        for field, key in (("total_equity", "bot.equity"), ("pnl", "bot.pnl"),
                           ("trades", "bot.trades"), ("win_rate_pct", "bot.win_rate"),
                           ("in_posizione", "bot.in_pos")):
            v = b.get(field)
            if isinstance(v, (int, float)):
                data.append({"host": host, "key": key, "value": v})
    for d in data:
        d["clock"] = now
    res = rpc("history.push", data, auth)
    ok = res is not None and res.get("response") == "success"
    return len(data) if ok else 0


STATE_FILE = Path("/tmp/zabbix_bots_missing.json")
MISSING_GRACE_S = 1800  # disabilita solo dopo 30 min di assenza continuativa


def load_state():
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {}


def save_state(st):
    try:
        STATE_FILE.write_text(json.dumps(st))
    except Exception:
        pass


def sync_host_status(auth, wanted):
    """Riabilita gli host tornati nel payload; disabilita (con grazia 30m)
    i bot spariti. Un singolo campione mancante NON basta: l'aggregator puo'
    avere buchi transitori (visto il 02/10: 6 bot nuvola assenti per un ciclo)."""
    now = time.time()
    st = load_state()
    existing = rpc("host.get", {"search": {"host": PREFIX},
                                "output": ["hostid", "host", "status"]}, auth) or []
    off = 0
    re_on = 0
    for h in existing:
        name = h["host"]
        if name in wanted:
            st.pop(name, None)
            if str(h.get("status")) == "1":
                if rpc("host.update", {"hostid": h["hostid"], "status": 0}, auth):
                    re_on += 1
                    print(f"riabilitato (tornato nel payload): {name}")
            continue
        first = st.get(name)
        if first is None:
            st[name] = now
            continue
        if str(h.get("status")) != "1" and now - first > MISSING_GRACE_S:
            if rpc("host.update", {"hostid": h["hostid"], "status": 1}, auth):
                off += 1
                print(f"disabilitato (assente da {int(now - first)}s): {name}")
    save_state(st)
    return off, re_on


def main():
    try:
        user, password = CRED.read_text().strip().split(":", 1)
    except Exception as e:
        print(f"CREDENZIALI: impossibile leggere {CRED}: {e}")
        return 1
    auth = rpc("user.login", {"username": user, "password": password})
    if not auth:
        print("LOGIN FALLITO")
        return 1
    try:
        with urllib.request.urlopen(INFRA, timeout=20) as r:
            payload = json.loads(r.read())
    except Exception as e:
        print(f"infra.json non leggibile: {e}")
        return 1

    wanted = bot_entries(payload)
    if not wanted:
        print("nessun bot nel payload")
        return 1

    byhost = refresh_hostids(auth, wanted)
    hc = ensure_hosts(auth, wanted, byhost)
    refresh_hostids(auth, wanted)
    ic = ensure_items(auth, wanted)
    gc = ensure_graphs(auth, wanted)
    tc = ensure_triggers(auth, wanted)
    pushed = push_values(auth, wanted)
    off, re_on = sync_host_status(auth, wanted)
    print(f"BOTS SYNC OK: bot={len(wanted)} host+{hc} item+{ic} grafi+{gc} "
          f"trigger+{tc} push={pushed} off={off} riabili={re_on}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
