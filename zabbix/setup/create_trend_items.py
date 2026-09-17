#!/usr/bin/env python3
"""Crea host + item Zabbix per: istanza TREND paper (alpha-omega-node-trend)
e TREND LIVE Kraken (alpha-omega-bot-trend-live). Eseguito su MARCODG1."""
import json
import urllib.request

API = "http://127.0.0.1:1080/api_jsonrpc.php"
USER, PASS = "Admin", "zabbix"
GROUP = "Denaro Bots"


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
        print(f"RPC {method} error: {out['error'].get('data', out['error'])}")
        return None
    return out.get("result")


def ensure_host(auth, name, groupid):
    got = rpc("host.get", {"filter": {"host": name}, "output": ["hostid"]}, auth)
    if got:
        return got[0]["hostid"]
    r = rpc("host.create", {"host": name,
                            "groups": [{"groupid": groupid}],
                            "status": 0}, auth)
    print(f"host creato {name}: {r}")
    return r["hostids"][0] if r else None


def ensure_items(auth, hostid, host, keys, prefix):
    existing = rpc("item.get", {"hostids": hostid, "output": ["key_"]}, auth) or []
    have = {i["key_"] for i in existing}
    to_create = []
    for k in keys:
        if k not in have:
            to_create.append({"hostid": hostid, "name": f"{host} {k}",
                              "key_": k, "type": 2, "value_type": 0,
                              "history": "7d", "trends": "30d"})
    if to_create:
        r = rpc("item.create", to_create, auth)
        print(f"  items {host}: {len(to_create)} -> {r}")
    else:
        print(f"  items {host}: tutti presenti")


def main():
    auth = rpc("user.login", {"username": USER, "password": PASS})
    if not auth:
        print("LOGIN FALLITO")
        return
    groups = rpc("hostgroup.get", {"filter": {"name": GROUP}, "output": ["groupid"]}, auth)
    groupid = groups[0]["groupid"] if groups else None
    if not groupid:
        r = rpc("hostgroup.create", {"name": GROUP}, auth)
        groupid = r["groupids"][0]
    keys = ["status", "equity", "buys", "sells", "pnl", "trades",
            "regime", "adx", "atr_pct", "rsi", "ema200", "strategy",
            "stop_loss", "cap_locked", "cap_available",
            "sharpe", "sortino", "calmar", "profit_factor", "win_rate", "hurst"]

    hid = ensure_host(auth, "alpha-omega-node-trend", groupid)
    if hid:
        ensure_items(auth, hid, "alpha-omega-node-trend",
                     [f"trend.{s}.{k}" for s in ("sol", "eth", "ada", "xrp")
                      for k in keys], "trend.")
    hid2 = ensure_host(auth, "alpha-omega-bot-trend-live", groupid)
    if hid2:
        ensure_items(auth, hid2, "alpha-omega-bot-trend-live",
                     [f"bot.trend_live.{k}" for k in keys], "bot.trend_live.")
    print("DONE")


if __name__ == "__main__":
    main()
