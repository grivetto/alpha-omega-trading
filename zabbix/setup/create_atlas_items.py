#!/usr/bin/env python3
"""Crea gli item trapper ATLAS v6 (regime/adx/atr/rsi/ema200/strategy/
stop_loss/cap_*) per host node (paper, nuvola, mc2) e bot live (sol/ada/kraken)."""
import json
import urllib.request

API = "http://127.0.0.1:1080/api_jsonrpc.php"
USER, PASS = "Admin", "zabbix"

# host -> lista (base_key, simboli)
HOSTS = {
    "alpha-omega-node-paper": ("10697", "node.", ["ada", "sol", "xrp", "doge", "eth"]),
    "alpha-omega-node-nuvola": ("10698", "node.", ["ada", "sol", "xrp", "doge", "eth"]),
    "alpha-omega-node-mc2": ("10699", "node.", ["ada", "sol", "xrp", "doge", "eth"]),
    "alpha-omega-bot-sol-eur": ("10690", "bot.sol.", [""]),
    "alpha-omega-bot-ada-eur": ("10691", "bot.ada.", [""]),
    "alpha-omega-bot-kraken": ("10693", "bot.kraken.", [""]),
    "alpha-omega-bot-doge-eur": ("10700", "bot.doge.", [""]),
    "alpha-omega-bot-eth-eur": ("10701", "bot.eth.", [""]),
}
ATLAS_KEYS = ["regime", "adx", "atr_pct", "rsi", "ema200",
              "strategy", "stop_loss", "cap_locked", "cap_available"]


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
    total = 0
    for host, (hid, prefix, syms) in HOSTS.items():
        got = rpc("item.get", {"output": ["itemid", "key_"], "hostids": hid}, auth) or []
        have = {i["key_"] for i in got}
        missing = []
        for sym in syms:
            base = f"{prefix}{sym}" if sym else prefix.rstrip(".")
            for key in ATLAS_KEYS:
                k = f"{base}.{key}"
                if k not in have:
                    missing.append({
                        "name": f"{base}.{key} ({host})",
                        "key_": k,
                        "type": 2,          # trapper
                        "value_type": 0,    # float
                        "history": "7d",
                        "trends": "30d",
                    })
        if missing:
            for it in missing:
                it["hostid"] = hid
            r = rpc("item.create", missing, auth)
            n = len(missing)
            total += n
            print(f"{host}: creati {n} item -> {r}")
        else:
            print(f"{host}: tutti presenti ({len(have)})")
    print(f"TOTALE creati: {total}")


if __name__ == "__main__":
    main()

