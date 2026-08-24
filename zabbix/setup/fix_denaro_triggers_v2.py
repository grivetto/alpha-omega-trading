#!/usr/bin/env python3
"""Ricrea i trigger Denaro (forme nominali /host/key) e verifica gli itemid."""
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


def main():
    auth = rpc("user.login", {"username": "Admin", "password": "zabbix"})
    if not auth:
        print("LOGIN FALLITO"); sys.exit(1)

    trigs = rpc("trigger.get", {"output": ["triggerid", "description"],
                                "search": {"description": "Denaro"},
                                "searchByAny": True}, auth)
    ids = [t["triggerid"] for t in trigs or []]
    print("elimino trigger:", ids)
    if ids:
        rpc("trigger.delete", ids, auth)

    def off(host, key):
        return f"nodata(/{host}/{key},300)=1 or last(/{host}/{key})=0"

    new = [
        ("Denaro SOL/EUR OKX: bot OFFLINE",
         off("alpha-omega-bot-sol-eur", "bot.sol.status"), "4"),
        ("Denaro ADA/EUR OKX: bot OFFLINE",
         off("alpha-omega-bot-ada-eur", "bot.ada.status"), "4"),
        ("Denaro SOL/EUR Kraken: bot OFFLINE",
         off("alpha-omega-bot-kraken", "bot.kraken.status"), "4"),
        ("Denaro Paper ADA: bot OFFLINE",
         off("alpha-omega-paper-ada", "paper.ada.status"), "3"),
        ("Denaro Paper SOL: bot OFFLINE",
         off("alpha-omega-paper-sol", "paper.sol.status"), "3"),
        ("Denaro Paper XRP: bot OFFLINE",
         off("alpha-omega-paper-xrp", "paper.xrp.status"), "3"),
        ("Denaro Node ADA: bot OFFLINE",
         off("alpha-omega-node-paper", "node.ada.status"), "4"),
        ("Denaro Node SOL: bot OFFLINE",
         off("alpha-omega-node-paper", "node.sol.status"), "4"),
        ("Denaro Node XRP: bot OFFLINE",
         off("alpha-omega-node-paper", "node.xrp.status"), "4"),
        ("Denaro SOL/EUR OKX: drawdown critico (>25%)",
         "last(/alpha-omega-bot-sol-eur/bot.sol.drawdown)>0.25", "4"),
        ("Denaro ADA/EUR OKX: drawdown critico (>25%)",
         "last(/alpha-omega-bot-ada-eur/bot.ada.drawdown)>0.25", "4"),
        ("Denaro SOL/EUR Kraken: drawdown critico (>25%)",
         "last(/alpha-omega-bot-kraken/bot.kraken.drawdown)>0.25", "4"),
        ("Denaro: equity totale sotto 50€",
         "last(/alpha-omega-project/project.equity)<50", "3"),
    ]

    for desc, expr, prio in new:
        r = rpc("trigger.create", {"description": desc, "expression": expr,
                                   "priority": prio}, auth)
        print(("OK  " if r else "FAIL") + desc)

    expected = {
        "53697", "53707", "53729", "53739", "53748", "53757",
        "53778", "53784", "53790", "53766", "53768", "53770", "53717",
    }
    trigs = rpc("trigger.get", {"output": ["triggerid", "description", "expression", "value"],
                                "search": {"description": "Denaro"},
                                "searchByAny": True}, auth)
    problems = 0
    print("\n=== VERIFICA ESPRESSIONI RISOLTE ===")
    for t in trigs or []:
        expr = t["expression"]
        ids_in = [x for x in expr.replace("{", " ").replace("}", " ").split() if x.isdigit()]
        bad = [i for i in ids_in if i not in expected]
        if bad:
            problems += 1
            print(f"  !! {t['description'][:48]:48s} item non attesi: {bad}")
        else:
            print(f"  ok {t['description'][:48]:48s} value={t['value']} expr={expr}")
    print(f"\nproblemi: {problems} / {len(trigs or [])}")
    print("DONE")


if __name__ == "__main__":
    main()
