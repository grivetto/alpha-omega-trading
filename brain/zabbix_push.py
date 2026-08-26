"""Brain — push dello stato a Zabbix (trapper API) + creazione items/trigger."""
from __future__ import annotations

import json
import time
import urllib.request

from . import config

_auth: str | None = None


def rpc(method: str, params: dict, auth: bool = True) -> object:
    body = {"jsonrpc": "2.0", "method": method,
            "params": params if not auth else {**params, "auth": _auth},
            "id": 1}
    req = urllib.request.Request(config.ZABBIX_API,
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            out = json.loads(resp.read())
    except Exception as e:  # noqa: BLE001
        print(f"[zabbix] rpc {method} errore: {e}")
        return None
    if "error" in out:
        print(f"[zabbix] rpc {method} error: {out['error'].get('data', out['error'])}")
        return None
    return out.get("result")


def login() -> bool:
    global _auth
    res = rpc("user.login", {"username": config.ZABBIX_USER,
                             "password": config.ZABBIX_PASS}, auth=False)
    if isinstance(res, str):
        _auth = res
        return True
    return False


def push(state: dict, repairs: list[dict], hermes_age: float | None,
         strat_ret: float | None = None) -> None:
    if not _auth and not login():
        return
    clock = int(time.time())
    data: list[dict] = []
    for machine, ms in state.items():
        if machine.startswith("_"):
            continue
        host = config.ZABBIX_HOSTS.get(machine, machine)
        bots_down = sum(1 for b in ms.get("bots", {}).values()
                        if b.get("stale") or b.get("status") != "running")
        units_down = sum(1 for s in ms.get("units", {}).values() if s != "active")
        data += [
            {"host": host, "key": "brain.status", "value": 1 if ms.get("ok") else 0},
            {"host": host, "key": "brain.bots_down", "value": bots_down},
            {"host": host, "key": "brain.units_down", "value": units_down},
            {"host": host, "key": "brain.last_cycle", "value": clock},
        ]
    data += [
        {"host": "MARCODG1", "key": "brain.repairs_total",
         "value": len(repairs) + sum(1 for _ in _count_repairs())},
        {"host": "MARCODG1", "key": "brain.hermes_age",
         "value": hermes_age if hermes_age is not None else -1},
    ]
    if strat_ret is not None:
        data.append({"host": "MARCODG1", "key": "brain.strategy_ret", "value": strat_ret})
    for d in data:
        d["clock"] = clock
    res = rpc("history.push", {"data": data})
    if res and res.get("response") == "success":
        print(f"[zabbix] push OK: {len(data)} valori")
    else:
        print(f"[zabbix] push FALLITO: {res}")


def _count_repairs() -> list[str]:
    try:
        lines = config.REPAIR_LOG.read_text(encoding="utf-8").splitlines()
        return lines
    except Exception:  # noqa: BLE001
        return []


# ── items/trigger: tentativo con lookup itemid REALE (workaround nominale) ──

def ensure_items() -> None:
    """Crea gli items brain.* se mancano (best-effort; non blocca)."""
    if not _auth and not login():
        return
    wanted = {
        "MARCODG1": ["brain.status", "brain.bots_down", "brain.units_down",
                     "brain.last_cycle", "brain.repairs_total",
                     "brain.hermes_age", "brain.strategy_ret"],
        "nuvola": ["brain.status", "brain.bots_down", "brain.units_down", "brain.last_cycle"],
        "mc2": ["brain.status", "brain.bots_down", "brain.units_down", "brain.last_cycle"],
    }
    for host, keys in wanted.items():
        hosts = rpc("host.get", {"filter": {"host": host}, "output": ["hostid"]})
        if not hosts:
            print(f"[zabbix] host {host} non trovato")
            continue
        hostid = hosts[0]["hostid"]
        existing = rpc("item.get", {"hostids": hostid, "output": ["key_"]}) or []
        have = {i["key_"] for i in existing}
        # Zabbix 7.0: item.create vuole la LISTA diretta (niente wrapper
        # {"items": [...]}) e per gli item trapper (type 2) delay DEVE essere 0.
        to_create = [{"hostid": hostid, "name": k, "key_": k,
                      "type": 2, "value_type": 0, "history": "7d",
                      "trends": "30d", "delay": "0"}
                     for k in keys if k not in have]
        if to_create:
            res = rpc("item.create", to_create)
            print(f"[zabbix] items creati su {host}: {len(to_create)} -> {res}")


def ensure_triggers() -> None:
    """Trigger di riparazione/alert (best-effort; non blocca)."""
    if not _auth and not login():
        return
    expr_hosts = {"MARCODG1": "MARCODG1", "nuvola": "nuvola", "mc2": "mc2"}
    for host, expr_host in expr_hosts.items():
        hosts = rpc("host.get", {"filter": {"host": expr_host}, "output": ["hostid"]})
        if not hosts:
            print(f"[zabbix] trigger {host}: host non trovato")
            continue
        hostid = hosts[0]["hostid"]
        items = rpc("item.get", {"hostids": hostid,
                                 "filter": {"key_": "brain.bots_down"},
                                 "output": ["itemid"]})
        if not items:
            print(f"[zabbix] trigger {host}: item brain.bots_down non trovato")
            continue
        descr = f"Brain {host}: bot giu'"
        # evita duplicati tra restart del brain
        existing = rpc("trigger.get", {"filter": {"description": descr},
                                       "output": ["triggerid"]})
        if existing:
            continue
        trig = {
            "description": descr,
            # sintassi Zabbix 5+: last(/host/key) — niente {itemid} (bug nominale)
            "expression": f"last(/{expr_host}/brain.bots_down)>=1",
            "priority": 4,
            "recovery_mode": 1,
        }
        res = rpc("trigger.create", [trig])
        print(f"[zabbix] trigger creato su {host}: {res}")
