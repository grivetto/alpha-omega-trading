#!/usr/bin/env python3
"""Trigger ATLAS con sintassi corretta."""
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


auth = rpc("user.login", {"username": "Admin", "password": "zabbix"})
if not auth:
    print("LOGIN FALLITO"); sys.exit(1)

r = rpc("trigger.create", {
    "description": "ATLAS: health check FAIL (auto-heal)",
    "expression": "str(/nuvola/atlas.health,\"healthy\")=0",
    "priority": "4",
}, auth)
print("trigger.create:", r)
print("DONE")
