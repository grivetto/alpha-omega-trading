#!/usr/bin/env python3
"""Crea item trapper svc.<unit> sugli host macchina (10683 mc2, 10684 nuvola,
10688 MARCODG1) per monitorare lo stato dei servizi Denaro per ciascuna macchina.
Alimentati da push_metrics.py via SSH (systemctl is-active)."""
import json
import urllib.request

API = "http://127.0.0.1:1080/api_jsonrpc.php"
USER, PASS = "Admin", "zabbix"

# hostid -> lista unit
HOST_SERVICES = {
    "10688": [  # MARCODG1
        "denaro-node-paper", "denaro-health-marcodg1", "denaro-aggregator-marcodg1",
        "denaro-paper-ada", "denaro-paper-sol", "denaro-paper-xrp",
    ],
    "10684": [  # nuvola
        "denaro-node-nuvola", "zabbix-tunnel",
    ],
    "10683": [  # mc2
        "denaro-node-mc2", "zabbix-tunnel-reverse",
    ],
}


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
    for hid, units in HOST_SERVICES.items():
        got = rpc("item.get", {"output": ["itemid", "key_"], "hostids": hid}, auth) or []
        have = {i["key_"] for i in got}
        missing = []
        for u in units:
            k = f"svc.{u}"
            if k not in have:
                missing.append({
                    "name": f"stato servizio {u}",
                    "key_": k,
                    "hostid": hid,
                    "type": 2,          # trapper
                    "value_type": 0,    # float
                    "history": "7d",
                    "trends": "30d",
                })
        if missing:
            r = rpc("item.create", missing, auth)
            print(f"host {hid}: creati {len(missing)} item -> {r}")
        else:
            print(f"host {hid}: tutti gli item gia' presenti ({len(have)})")


if __name__ == "__main__":
    main()

