#!/usr/bin/env python3
"""Crea in Zabbix item e trigger per i SERVIZI systemd monitorati.

Perche' serve: gli item svc.<unit> venivano pushati dal cron di MARCODG1 ma NON
aveva nessun trigger. Lo stato veniva raccolto e nessuno veniva avvisato: un
servizio morto restava morto finche' qualcuno non apriva la dashboard.

Creazione idempotente: item e trigger gia' presenti non vengono toccati.

Uso: python3 tools/zabbix_services.py [--apply]
"""
from __future__ import annotations
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

URL = "http://localhost:1080/api_jsonrpc.php"

# unit -> host Zabbix. Stessa lista del feeder (push_metrics.py su MARCODG1).
SERVIZI = {
    "MARCODG1": [
        "denaro-node-marcodg1-xrp", "denaro-dashboard-marcodg1",
        "cloudflared-denaro", "denaro-aggregator-marcodg1",
        "denaro-health-marcodg1", "denaro-node-paper", "denaro-node-trend",
        "zabbix-agent",
    ],
    "nuvola": [
        "denaro-node-nuvola-trade", "denaro-health-nuvola", "zabbix-agent",
    ],
    "mc2": [
        "denaro-node-mc2", "denaro-aggregator-mc2", "denaro-dashboard-mc2",
        "denaro-feeder-mc2", "denaro-health-mc2", "cloudflared-home",
        "zabbix-agent",
    ],
}


def api(method, params, auth=None):
    pl = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
    if auth:
        pl["auth"] = auth
    req = urllib.request.Request(URL, data=json.dumps(pl).encode(),
                                 headers={"Content-Type": "application/json-rpc"})
    out = json.load(urllib.request.urlopen(req, timeout=25))
    if "error" in out:
        raise RuntimeError("%s -> %s" % (method, out["error"]))
    return out["result"]


def main():
    apply_ = "--apply" in sys.argv
    tok = api("user.login", {"username": "Admin", "password": "zabbix"})
    creati_item = creati_trig = 0
    for host, units in SERVIZI.items():
        h = api("host.get", {"output": ["hostid"], "filter": {"host": host}}, tok)
        if not h:
            print("  host %s NON esiste: salto" % host)
            continue
        hid = h[0]["hostid"]
        item_esistenti = {i["key_"] for i in api(
            "item.get", {"output": ["key_"], "hostids": hid}, tok)}
        trig_esistenti = {t["description"] for t in api(
            "trigger.get", {"output": ["description"], "hostids": hid}, tok)}
        for u in units:
            chiave = "svc.%s" % u
            if chiave not in item_esistenti:
                if apply_:
                    api("item.create", {
                        "hostid": hid, "name": "Servizio %s (1=attivo)" % u,
                        "key_": chiave, "type": 2, "value_type": 3,
                        "delay": "0", "history": "31d", "trends": "365d"}, tok)
                creati_item += 1
            attesi = [
                ("SERVIZIO %s: non in esecuzione" % u,
                 "last(/%s/%s)=0" % (host, chiave), 4),
                ("SERVIZIO %s: nessun dato da 10m" % u,
                 "nodata(/%s/%s,10m)=1" % (host, chiave), 4),
            ]
            for desc, expr, prio in attesi:
                if desc in trig_esistenti:
                    continue
                if apply_:
                    api("trigger.create", {"description": desc, "expression": expr,
                                           "priority": prio}, tok)
                creati_trig += 1
        print("  %-9s %d servizi" % (host, len(units)))
    print("da creare: %d item, %d trigger  (%s)"
          % (creati_item, creati_trig, "APPLY" if apply_ else "DRY-RUN"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
