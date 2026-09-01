#!/usr/bin/env python3
"""Crea gli item trapper mancanti per gli host node nuvola/mc2 (item.create)."""
import json
import urllib.request

API = "http://127.0.0.1:1080/api_jsonrpc.php"
USER, PASS = "Admin", "zabbix"

NODE_HOSTS = {
    "alpha-omega-node-nuvola": "10698",
    "alpha-omega-node-mc2": "10699",
}
KEYS = ["status", "equity", "buys", "sells", "pnl", "trades"]
SYMS = ["ada", "sol", "xrp"]


def rpc(method, params, auth=None):
    body = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
    if auth:
        body["auth"] = auth
    req = urllib.request.Request(API, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            out = json.loads(resp.read())
    except Exception as e:
        print(f"RPC {method} error: {e}")
        return None
    if "error" in out:
        print(f"RPC {method} error: {out['error']}")
        return None
    return out.get("result")


def main():
    auth = rpc("user.login", {"username": USER, "password": PASS})
    if not auth:
        print("LOGIN FALLITO")
        return
    for host, hid in NODE_HOSTS.items():
        # item esistenti
        got = rpc("item.get", {"output": ["itemid", "key_"], "hostids": hid}, auth) or []
        have = {i["key_"] for i in got}
        missing = []
        for sym in SYMS:
            for key in KEYS:
                k = f"node.{sym}.{key}"
                if k not in have:
                    missing.append({
                        "name": f"node.{sym}.{key} ({host})",
                        "key_": k,
                        "type": 2,          # trapper
                        "value_type": 0,    # float
                        "history": "7d",
                        "trends": "30d",
                    })
        if missing:
            # item.create vuole l'array direttamente, hostid dentro ogni item
            for it in missing:
                it["hostid"] = hid
            r = rpc("item.create", missing, auth)
            print(f"{host}: creati {len(missing)} item -> {r}")
        else:
            print(f"{host}: tutti gli item gia' presenti ({len(have)})")


if __name__ == "__main__":
    main()

