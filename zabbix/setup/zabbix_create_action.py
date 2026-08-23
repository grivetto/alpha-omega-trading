#!/usr/bin/env python3
"""Crea l'azione 'Denaro Auto-Heal' su Zabbix (scriptid 6)."""
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

# Controlla che l'azione non esista gia'
existing = rpc("action.get", {"output": ["actionid", "name"], "search": {"name": "Denaro Auto-Heal"}}, auth)
if existing:
    print("azione gia' esistente:", existing)
    sys.exit(0)

r = rpc("action.create", {
    "name": "Denaro Auto-Heal (restart + notifica)",
    "eventsource": 0,
    "status": 1,
    "esc_period": "60",
    "filter": {
        "evaltype": 2,
        "conditions": [{"conditiontype": 3, "operator": 2, "value": "bot OFFLINE"}],
    },
    "operations": [
        {
            "operationtype": 1,
            "esc_period": "60",
            "esc_step_from": 1,
            "esc_step_to": 1,
            "opcommand": {
                "command": "/usr/lib/zabbix/alertscripts/denaro_heal.sh {HOST.NAME}",
                "execute_on": 1,
            },
            "opcommand_hst": [{"hostid": "0"}],
        },
        {
            "operationtype": 0,
            "esc_period": "60",
            "esc_step_from": 1,
            "esc_step_to": 1,
            "opmessage": {
                "default_msg": 0,
                "subject": "🛠 DENARO AUTO-HEAL: {TRIGGER.NAME}",
                "message": "<b>{TRIGGER.NAME}</b>\nSeverity: {TRIGGER.SEVERITY}\nHost: {HOST.NAME}\nRiavvio automatico del bot in corso via systemd.",
                "mediatypeid": "65",
            },
            "opmessage_usr": [{"userid": "1"}],
        },
    ],
}, auth)
print("action.create:", r)
print("DONE")
