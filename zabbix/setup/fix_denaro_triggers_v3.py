#!/usr/bin/env python3
"""Trigger Denaro con ITEMID REALI in formato crudo {id} (fix definitivo).

Zabbix 7 accetta {itemid} crudo nelle espressioni; la forma nominale
/host/key risolve male gli item trapper (itemid fittizi). Il push_metrics
spinge gia' status=0 quando l'health e' stale, quindi last=0 rileva il
bot OFFLINE entro ~1-2 min (il nodata e' ridondante).
"""
import json
import sys
import urllib.request

API = "http://127.0.0.1:1080/api_jsonrpc.php"


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
        print(f"  RPC {method} ERROR network: {e}")
        return None
    if "error" in out:
        print(f"  RPC {method} ERROR: {out['error'].get('data', out['error'])}")
        return None
    return out.get("result")


def find_item(auth, host, key):
    res = rpc("item.get", {"output": ["itemid", "key_"], "hostids": host,
                           "search": {"key_": key}}, auth)
    for it in res or []:
        if it["key_"] == key:
            return it["itemid"]
    return None


def main():
    auth = rpc("user.login", {"username": "Admin", "password": "zabbix"})
    if not auth:
        print("LOGIN FALLITO"); sys.exit(1)

    wanted = [
        ("10690", "bot.sol.status"), ("10690", "bot.sol.drawdown"),
        ("10691", "bot.ada.status"), ("10691", "bot.ada.drawdown"),
        ("10693", "bot.kraken.status"), ("10693", "bot.kraken.drawdown"),
        ("10694", "paper.ada.status"), ("10695", "paper.sol.status"),
        ("10696", "paper.xrp.status"),
        ("10697", "node.ada.status"), ("10697", "node.sol.status"),
        ("10697", "node.xrp.status"),
        ("10692", "project.equity"),
    ]
    ids = {}
    for hid, key in wanted:
        iid = find_item(auth, hid, key)
        if iid:
            ids[key] = iid
        else:
            print(f"  !! item mancante {key}")
    for k in sorted(ids):
        print(f"  item {k} = {ids[k]}")

    trigs = rpc("trigger.get", {"output": ["triggerid"],
                                "search": {"description": "Denaro"},
                                "searchByAny": True}, auth)
    old = [t["triggerid"] for t in trigs or []]
    if old:
        print("elimino:", old)
        rpc("trigger.delete", old, auth)

    def off(key):
        return f"{{{ids[key]}}}=0"

    def dd(key):
        return f"{{{ids[key]}}}>0.25"

    new = [
        ("Denaro SOL/EUR OKX: bot OFFLINE", off("bot.sol.status"), "4"),
        ("Denaro ADA/EUR OKX: bot OFFLINE", off("bot.ada.status"), "4"),
        ("Denaro SOL/EUR Kraken: bot OFFLINE", off("bot.kraken.status"), "4"),
        ("Denaro Paper ADA: bot OFFLINE", off("paper.ada.status"), "3"),
        ("Denaro Paper SOL: bot OFFLINE", off("paper.sol.status"), "3"),
        ("Denaro Paper XRP: bot OFFLINE", off("paper.xrp.status"), "3"),
        ("Denaro Node ADA: bot OFFLINE", off("node.ada.status"), "4"),
        ("Denaro Node SOL: bot OFFLINE", off("node.sol.status"), "4"),
        ("Denaro Node XRP: bot OFFLINE", off("node.xrp.status"), "4"),
        ("Denaro SOL/EUR OKX: drawdown critico (>25%)", dd("bot.sol.drawdown"), "4"),
        ("Denaro ADA/EUR OKX: drawdown critico (>25%)", dd("bot.ada.drawdown"), "4"),
        ("Denaro SOL/EUR Kraken: drawdown critico (>25%)", dd("bot.kraken.drawdown"), "4"),
        ("Denaro: equity totale sotto 50€", f"{{{ids['project.equity']}}}<50", "3"),
    ]

    for desc, expr, prio in new:
        r = rpc("trigger.create", {"description": desc, "expression": expr,
                                   "priority": prio}, auth)
        print(("OK  " if r else "FAIL") + desc)

    trigs = rpc("trigger.get", {"output": ["triggerid", "description", "expression", "value", "state"],
                                "search": {"description": "Denaro"},
                                "searchByAny": True}, auth)
    print("\n=== VERIFICA ===")
    ok = 0
    for t in trigs or []:
        expr = t["expression"]
        refs = [x for x in expr.replace("{", " ").replace("}", " ").split() if x.isdigit()]
        real = all(r in ids.values() for r in refs)
        if real:
            ok += 1
        print(f"  {'ok ' if real else '!! '}{t['description'][:48]:48s} value={t['value']} state={t['state']} expr={expr}")
    print(f"\ncorretti: {ok}/{len(trigs or [])}")
    print("DONE")


if __name__ == "__main__":
    main()
