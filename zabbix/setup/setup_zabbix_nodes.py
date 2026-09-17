#!/usr/bin/env python3
"""setup_zabbix_nodes.py — crea gli host Zabbix per i nodi Denaro remoti
(nuvola, mc2) con gli item trapper identici al node paper di MARCODG1.

Uso:  python3 setup_zabbix_nodes.py
Eseguito da MARCODG1 (tunnel 1080 verso Zabbix).
"""
import json
import sys
import urllib.request

API = "http://127.0.0.1:1080/api_jsonrpc.php"
USER, PASS = "Admin", "zabbix"
GROUP = "Denaro Trading"

# host -> unit systemd (per auto-heal remoto)
NODE_HOSTS = {
    "alpha-omega-node-nuvola": "denaro-node-nuvola",
    "alpha-omega-node-mc2": "denaro-node-mc2",
}

# key trapper replicate dal node paper di MARCODG1
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
        sys.exit(1)

    # Trova il gruppo
    groups = rpc("hostgroup.get", {"output": ["groupid", "name"]}, auth) or []
    gid = next((g["groupid"] for g in groups if g["name"] == GROUP), None)
    if not gid:
        print(f"Gruppo '{GROUP}' non trovato")
        sys.exit(1)

    existing = rpc("host.get", {"output": ["hostid", "host"]}, auth) or []
    have = {h["host"]: h["hostid"] for h in existing}

    for host, unit in NODE_HOSTS.items():
        items = []
        for sym in SYMS:
            for key in KEYS:
                items.append({
                    "name": f"node.{sym}.{key} ({host})",
                    "key_": f"node.{sym}.{key}",
                    "type": 2,          # trapper
                    "value_type": 3,    # float
                    "history": "7d",
                    "trends": "30d",
                })
        if host in have:
            print(f"Host {host} esiste gia' ({have[host]}) — aggiorno item mancanti")
            got = rpc("item.get", {"output": ["itemid", "key_"], "hostids": have[host]}, auth) or []
            have_keys = {i["key_"] for i in got}
            missing = [it for it in items if it["key_"] not in have_keys]
            if missing:
                for it in missing:
                    it["hostid"] = have[host]
                r = rpc("item.create", missing, auth)
                print(f"  creati {len(missing)} item: {r}")
            else:
                print("  item gia' tutti presenti")
            continue
        # Host nuovo: host.create SOLO host (l'API non crea gli item annidati),
        # poi item.create separato.
        r = rpc("host.create", {
            "host": host,
            "groups": [{"groupid": gid}],
            "interfaces": [{
                "type": 1, "main": 1,
                "useip": 1, "ip": "127.0.0.1", "dns": "", "port": "10050",
            }],
        }, auth)
        if r and r.get("hostids"):
            hid = r["hostids"][0]
            print(f"Host {host} creato: {hid}")
            for it in items:
                it["hostid"] = hid
            r2 = rpc("item.create", items, auth)
            print(f"  creati {len(items)} item: {r2}")
        else:
            print(f"Host {host} NON creato: {r}")


if __name__ == "__main__":
    main()
