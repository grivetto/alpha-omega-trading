#!/usr/bin/env python3
"""Configura l'auto-healing Denaro su Zabbix (mc2):
- elimina trigger rotti (item morti)
- crea trigger OFFLINE sugli item reali (nodata 300s OR status=0)
- crea global script 'Denaro Auto-Heal' (scope=action operation, esecuzione server)
- crea azione 'Denaro Auto-Heal' (heal via script + notifica Telegram)
"""
import json
import sys
import urllib.request

API = "http://127.0.0.1:1080/api_jsonrpc.php"
USER = "Admin"
PASS = "zabbix"


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


def main():
    auth = rpc("user.login", {"username": USER, "password": PASS})
    if not auth:
        print("LOGIN FALLITO"); sys.exit(1)
    print("login ok")

    # 1. Elimina trigger rotti (puntavano a item morti 37327/37329/37331)
    for tid in ["25957", "25959", "25961"]:
        r = rpc("trigger.delete", [tid], auth)
        print(f"trigger.delete {tid}: {r}")

    # 2. Trigger OFFLINE nuovi
    trigs = [
        ("Denaro SOL/EUR OKX: bot OFFLINE",
         "nodata(/alpha-omega-bot-sol-eur/bot.sol.status,300)=1 or last(/alpha-omega-bot-sol-eur/bot.sol.status)=0", "4"),
        ("Denaro ADA/EUR OKX: bot OFFLINE",
         "nodata(/alpha-omega-bot-ada-eur/bot.ada.status,300)=1 or last(/alpha-omega-bot-ada-eur/bot.ada.status)=0", "4"),
        ("Denaro SOL/EUR Kraken: bot OFFLINE",
         "nodata(/alpha-omega-bot-kraken/bot.kraken.status,300)=1 or last(/alpha-omega-bot-kraken/bot.kraken.status)=0", "4"),
        ("Denaro Paper ADA: bot OFFLINE",
         "nodata(/alpha-omega-paper-ada/paper.ada.status,300)=1 or last(/alpha-omega-paper-ada/paper.ada.status)=0", "3"),
        ("Denaro Paper SOL: bot OFFLINE",
         "nodata(/alpha-omega-paper-sol/paper.sol.status,300)=1 or last(/alpha-omega-paper-sol/paper.sol.status)=0", "3"),
        ("Denaro Paper XRP: bot OFFLINE",
         "nodata(/alpha-omega-paper-xrp/paper.xrp.status,300)=1 or last(/alpha-omega-paper-xrp/paper.xrp.status)=0", "3"),
    ]
    new_ids = []
    for desc, expr, prio in trigs:
        r = rpc("trigger.create", {"description": desc, "expression": expr, "priority": prio}, auth)
        print(f"trigger.create '{desc}': {r}")
        if isinstance(r, dict) and r.get("triggerids"):
            new_ids.append(r["triggerids"][0])

    # 3. Global script Denaro Auto-Heal (scope=5 action operation, execute_on=1 server)
    r = rpc("script.create", {
        "name": "Denaro Auto-Heal (restart bot)",
        "type": 0,
        "execute_on": 1,
        "command": "/usr/lib/zabbix/alertscripts/denaro_heal.sh {HOST.NAME}",
        "scope": 5,
        "timeout": "30s",
    }, auth)
    print(f"script.create: {r}")
    scriptid = (r or {}).get("scriptids", [None])[0] if isinstance(r, dict) else None
    if not scriptid:
        print("NON POSSO CONTINUARE SENZA SCRIPTID"); sys.exit(2)

    # 4. Azione Denaro Auto-Heal: filter trigger name like 'bot OFFLINE'
    r = rpc("action.create", {
        "name": "Denaro Auto-Heal (restart + notifica)",
        "eventsource": 0,
        "status": 1,
        "esc_period": "0",
        "filter": {
            "evaltype": 2,
            "conditions": [{"conditiontype": 5, "operator": 2, "value": "bot OFFLINE"}],
        },
        "operations": [
            {
                "operationtype": 2,   # esegui global script sul server
                "esc_period": "0",
                "esc_step_from": 1,
                "esc_step_to": 1,
                "opcommand": {"scriptid": scriptid},
                "opcommand_hst": [{"hostid": "0"}],  # host corrente
            },
            {
                "operationtype": 0,   # messaggio (Telegram)
                "esc_period": "0",
                "esc_step_from": 1,
                "esc_step_to": 1,
                "opmessage": {
                    "default_msg": 0,
                    "subject": "🛠 DENARO AUTO-HEAL: {TRIGGER.NAME}",
                    "message": "<b>{TRIGGER.NAME}</b>\nSeverity: {TRIGGER.SEVERITY}\nHost: {HOST.NAME}\nIl sistema sta riavviando il bot via systemd.",
                    "mediatypeid": "65",
                },
                "opmessage_usr": [{"userid": "1"}],
            },
        ],
    }, auth)
    print(f"action.create: {r}")

    print("DONE")


if __name__ == "__main__":
    main()
