#!/usr/bin/env python3
"""One-shot Zabbix setup: host + trapper items + push simulator data. Idempotent."""
import json, os, subprocess, sys, urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
env = {}
with open(os.path.join(BASE, ".env")) as f:
    for line in f:
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()

URL = env["ZABBIX_URL"]
USER = env["ZABBIX_USER"]
PASS = env["ZABBIX_PASS"]
HOST = "airdrop-farm"

KEYS = [
    "aug5.median", "aug5.p10", "aug5.p90",
    "m6.median", "m6.p10", "m6.p90", "m6.prob_profit", "m6.prob_10x",
    "m12.median", "m12.p10", "m12.p90", "m12.prob_profit", "m12.prob_10x",
]

def api(method, params, auth=None):
    body = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
    if auth:
        body["auth"] = auth
    req = urllib.request.Request(URL, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json-rpc"})
    with urllib.request.urlopen(req, timeout=20) as r:
        out = json.load(r)
    if "error" in out:
        raise RuntimeError(f"{method}: {out['error']}")
    return out["result"]

token = api("user.login", {"username": USER, "password": PASS})
print("auth OK")

# host (create if missing)
hosts = api("host.get", {"filter": {"host": HOST}}, token)
if hosts:
    hostid = hosts[0]["hostid"]
    print(f"host exists: {hostid}")
else:
    groups = api("hostgroup.get", {"output": ["groupid"], "limit": 1}, token)
    gid = groups[0]["groupid"]
    hostid = api("host.create", {"host": HOST, "name": "Airdrop Farm (Monte Carlo)",
                                 "groups": [{"groupid": gid}]}, token)["hostids"][0]
    print(f"host created: {hostid}")

existing = api("item.get", {"hostids": hostid, "output": ["itemid", "key_"]}, token)
existing_keys = {i["key_"]: i["itemid"] for i in existing}

itemids = {}
for k in KEYS:
    zk = f"airdrop.{k}"
    if zk in existing_keys:
        itemids[k] = existing_keys[zk]
        continue
    iid = api("item.create", {
        "hostid": hostid, "name": f"Airdrop {k}", "key_": zk,
        "type": 2, "value_type": 0, "delay": "0",
    }, token)["itemids"][0]
    itemids[k] = iid
print(f"items ready: {len(itemids)}")

# run simulator -> metrics
out = subprocess.run([sys.executable, os.path.join(BASE, "simulator.py"), "--json"],
                     capture_output=True, text=True)
data = json.loads(out.stdout)

payload = []
for k in KEYS:
    full = f"{k.split('.')[0]}.{k.split('.')[1]}"
    # simulator output keys are like "m12.median" == k; direct lookup:
    if k in data:
        payload.append({"itemid": int(itemids[k]), "value": data[k]})
res = api("history.push", payload, token)
print(f"pushed {len(payload)} values: {res}")
print("DONE")
