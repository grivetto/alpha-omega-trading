#!/usr/bin/env python3
"""Fix value_type degli item ATLAS v6: 3 (unsigned int) -> 0 (float).
I decimali (atr_pct 0.558, rsi 39.7, adx 18.98) venivano troncati."""
import json
import urllib.request

API = "http://127.0.0.1:1080/api_jsonrpc.php"
USER, PASS = "Admin", "zabbix"


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
    # item ATLAS v6 su TUTTI gli host (search per chiavi atlas)
    keys = ["regime", "adx", "atr_pct", "rsi", "ema200", "strategy",
            "stop_loss", "cap_locked", "cap_available", "equity", "pnl",
            "free", "volume", "drawdown", "uptime"]
    fixed = 0
    for k in keys:
        items = rpc("item.get", {"output": ["itemid", "key_", "value_type"],
                                 "search": {"key_": k}}, auth) or []
        for it in items:
            if it.get("value_type") != "0":
                r = rpc("item.update", {"itemid": it["itemid"], "value_type": 0}, auth)
                if r:
                    fixed += 1
    print(f"item aggiornati a float: {fixed}")


if __name__ == "__main__":
    main()
