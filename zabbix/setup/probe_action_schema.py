#!/usr/bin/env python3
"""Probe: quale payload accetta action.create per remote command server-side."""
import json
import urllib.request

API = "http://127.0.0.1:1080/api_jsonrpc.php"


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
        return {"net_err": str(e)}
    return out


auth = rpc("user.login", {"username": "Admin", "password": "zabbix"})["result"]

base = {
    "name": "PROBE-action",
    "eventsource": 0,
    "status": 1,
    "esc_period": "60",
    "filter": {"evaltype": 2,
               "conditions": [{"conditiontype": 3, "operator": 2, "value": "bot OFFLINE"}]},
    "operations": [{"operationtype": 1, "esc_period": "60", "esc_step_from": 1, "esc_step_to": 1}],
}

variants = {
    "A opcommand{command}": {"opcommand": {"command": "echo hi"}, "opcommand_hst": [{"hostid": "0"}]},
    "B opcommand{scriptid}": {"opcommand": {"scriptid": "6"}, "opcommand_hst": [{"hostid": "0"}]},
    "C opcommand vuoto": {"opcommand": {}, "opcommand_hst": [{"hostid": "0"}]},
    "D senza opcommand": {},
    "E opcommand{command,execute_on}": {"opcommand": {"command": "echo hi", "execute_on": 1}, "opcommand_hst": [{"hostid": "0"}]},
}

for label, extra in variants.items():
    p = json.loads(json.dumps(base))
    p["operations"][0].update(extra)
    out = rpc("action.create", p, auth)
    if "result" in out:
        print(f"{label}: OK {out['result']}")
        # cleanup probe action
        rpc("action.delete", out["result"]["actionids"], auth)
    else:
        err = out.get("error", {}).get("data", out)
        print(f"{label}: ERR {str(err)[:180]}")
