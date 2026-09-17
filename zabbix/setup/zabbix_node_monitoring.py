#!/usr/bin/env python3
"""Zabbix: host 'alpha-omega-node-paper' + items + trigger OFFLINE (M7)."""
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

    # 1. gruppo del primo host bot (per coerenza)
    h = rpc("host.get", {"output": ["host"], "hostids": "10690",
                         "selectGroups": ["groupid", "name"]}, auth)
    groupid = h[0]["groups"][0]["groupid"] if h and h[0].get("groups") else None
    print("groupid:", groupid)

    # 2. host (se non esiste)
    existing = rpc("host.get", {"output": ["hostid", "host"],
                                "filter": {"host": "alpha-omega-node-paper"}}, auth)
    if existing:
        hostid = existing[0]["hostid"]
        print("host esistente:", hostid)
    else:
        r = rpc("host.create", {
            "host": "alpha-omega-node-paper",
            "name": "Denaro Node — paper (M7)",
            "groups": [{"groupid": groupid}],
        }, auth)
        print("host.create:", r)
        hostid = (r or {}).get("hostids", [None])[0]

    # 3. items trapper
    keys = [
        ("status", 3), ("equity", 0), ("buys", 3),
        ("sells", 3), ("pnl", 0), ("trades", 3),
    ]
    items = []
    for sym in ("ADA", "SOL", "XRP"):
        for key, vt in keys:
            items.append({
                "hostid": hostid,
                "name": f"Node {sym}: {key}",
                "key_": f"node.{sym.lower()}.{key}",
                "type": 2,          # trapper
                "value_type": vt,
                "history": "7d",
            })
    r = rpc("item.create", items, auth)
    print("item.create:", (r or {}).get("itemids", r))

    # 4. trigger OFFLINE (nodata 300s OR status=0)
    for sym in ("ADA", "SOL", "XRP"):
        key = f"node.{sym.lower()}.status"
        expr = (f"nodata(/alpha-omega-node-paper/{key},300)=1 or "
                f"last(/alpha-omega-node-paper/{key})=0")
        r = rpc("trigger.create", {
            "description": f"Denaro Node {sym}: bot OFFLINE",
            "expression": expr,
            "priority": "4",
        }, auth)
        print(f"trigger {sym}:", r)

    print("DONE")


if __name__ == "__main__":
    main()
