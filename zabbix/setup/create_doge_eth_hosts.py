#!/usr/bin/env python3
"""Crea host Zabbix per i bot live DOGE/ETH (con item trapper base + ATLAS v6)."""
import json
import urllib.request

API = "http://127.0.0.1:1080/api_jsonrpc.php"
USER, PASS = "Admin", "zabbix"
GROUP = "Denaro Trading"

NEW_HOSTS = {
    "alpha-omega-bot-doge-eur": "bot.doge",
    "alpha-omega-bot-eth-eur": "bot.eth",
}
BASE_KEYS = ["status", "equity", "free", "buys", "sells", "pnl", "trades",
             "wins", "losses", "volume", "drawdown", "uptime"]
ATLAS_KEYS = ["regime", "adx", "atr_pct", "rsi", "ema200", "strategy",
              "stop_loss", "cap_locked", "cap_available"]


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
    groups = rpc("hostgroup.get", {"output": ["groupid", "name"]}, auth) or []
    gid = next((g["groupid"] for g in groups if g["name"] == GROUP), None)
    existing = rpc("host.get", {"output": ["hostid", "host"]}, auth) or []
    have = {h["host"]: h["hostid"] for h in existing}

    for host, prefix in NEW_HOSTS.items():
        if host in have:
            print(f"{host} esiste gia' ({have[host]})")
            continue
        r = rpc("host.create", {
            "host": host,
            "groups": [{"groupid": gid}],
            "interfaces": [{
                "type": 1, "main": 1,
                "useip": 1, "ip": "127.0.0.1", "dns": "", "port": "10050",
            }],
        }, auth)
        if not (r and r.get("hostids")):
            print(f"{host} NON creato: {r}")
            continue
        hid = r["hostids"][0]
        items = []
        for key in BASE_KEYS + ATLAS_KEYS:
            items.append({
                "name": f"{prefix}.{key} ({host})",
                "key_": f"{prefix}.{key}",
                "hostid": hid,
                "type": 2, "value_type": 0, "history": "7d", "trends": "30d",
            })
        r2 = rpc("item.create", items, auth)
        print(f"{host} creato ({hid}) con {len(items)} item -> {r2}")


if __name__ == "__main__":
    main()

