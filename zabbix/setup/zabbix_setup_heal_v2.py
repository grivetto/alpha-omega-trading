#!/usr/bin/env python3
"""Crea script scope=1 (action operation) e azione Denaro Auto-Heal."""
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

# Pulisci script precedenti (id 6 scope=2)
old = rpc("script.get", {"output": ["scriptid", "name", "scope"]}, auth)
for s in old or []:
    if "Auto-Heal" in s["name"]:
        rpc("script.delete", [s["scriptid"]], auth)
        print(f"eliminato vecchio script {s['scriptid']} (scope={s['scope']})")

# Script con scope=1 (action operation), eseguito sul server
r = rpc("script.create", {
    "name": "Denaro Auto-Heal (restart bot)",
    "type": 0,
    "scope": 1,
    "execute_on": 1,
    "command": "/usr/lib/zabbix/alertscripts/denaro_heal.sh {HOST.NAME}",
    "timeout": "30s",
}, auth)
print("script.create:", r)
scriptid = (r or {}).get("scriptids", [None])[0] if isinstance(r, dict) else None
if not scriptid:
    print("SENZA SCRIPTID NON CONTINUO"); sys.exit(2)

# Rimuovi eventuali azioni probe/vecchie con lo stesso nome
existing = rpc("action.get", {"output": ["actionid", "name"], "search": {"name": "Denaro Auto-Heal"}}, auth)
for a in existing or []:
    rpc("action.delete", [a["actionid"]], auth)
    print(f"eliminata azione precedente {a['actionid']}")

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
            "opcommand": {"scriptid": scriptid},
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
