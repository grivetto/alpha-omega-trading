#!/usr/bin/env python3
"""Crea in Zabbix gli host dei 15 bot Denaro (item trapper + trigger).

Idempotente: crea solo cio' che manca. Senza --apply mostra cosa farebbe.

Uso: python3 tools/zabbix_setup.py [--apply] [--keep-old]

Gli host della generazione precedente (okx-doge, nuvola-sol, marcodg1-xrp)
vengono RIMOSSI, perche' i loro item non ricevono piu' dati e i loro trigger
"nodata" facevano riavviare nodi sani in loop. --keep-old li conserva.
"""
from __future__ import annotations
import json, sys, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from denaro_bots import BOTS, METRICHE, host_of, key_of  # noqa: E402

URL = "http://localhost:1080/api_jsonrpc.php"
GRUPPO = "Denaro Bots"
VECCHI = ["alpha-omega-bot-okx-doge", "alpha-omega-bot-nuvola-sol",
          "alpha-omega-bot-marcodg1-xrp"]
OUT_ITEMS = Path("/home/sergio/denaro/health/zbx_items.json")


def api(method, params, auth=None):
    pl = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
    if auth:
        pl["auth"] = auth
    req = urllib.request.Request(URL, data=json.dumps(pl).encode(),
                                 headers={"Content-Type": "application/json-rpc"})
    out = json.load(urllib.request.urlopen(req, timeout=20))
    if "error" in out:
        raise RuntimeError("%s -> %s" % (method, out["error"]))
    return out["result"]


def assicura_gruppo(tok):
    g = api("hostgroup.get", {"output": ["groupid", "name"],
                              "filter": {"name": GRUPPO}}, tok)
    if g:
        return g[0]["groupid"]
    return api("hostgroup.create", {"name": GRUPPO}, tok)["groupids"][0]


def assicura_host(tok, host, gid, apply_):
    h = api("host.get", {"output": ["hostid"], "filter": {"host": host}}, tok)
    if h:
        return h[0]["hostid"], False
    if not apply_:
        return None, True
    r = api("host.create", {"host": host, "name": host,
                            "groups": [{"groupid": gid}], "status": 0}, tok)
    return r["hostids"][0], True


def assicura_item(tok, hid, host, slug, apply_):
    """Crea gli item mancanti; ritorna {suffisso: itemid}."""
    esistenti = {i["key_"]: i["itemid"] for i in api(
        "item.get", {"output": ["itemid", "key_"], "hostids": hid}, tok)}
    creati, mappa = 0, {}
    for suf, label, vtype, units in METRICHE:
        k = key_of(slug, suf)
        if k in esistenti:
            mappa[suf] = esistenti[k]
            continue
        if not apply_:
            creati += 1
            continue
        # Zabbix NON ammette i trend per gli item di TESTO (value_type 4):
        # item.create risponde "Invalid parameter /1/trends: value must be 0".
        trends = "0" if vtype == 4 else "365d"
        r = api("item.create", {"hostid": hid, "name": "Bot %s: %s" % (slug, label),
                                "key_": k, "type": 2, "value_type": vtype,
                                "delay": "0", "units": units,
                                "history": "31d", "trends": trends}, tok)
        mappa[suf] = r["itemids"][0]
        creati += 1
    return mappa, creati


def assicura_trigger(tok, hid, host, slug, apply_):
    esistenti = {t["description"] for t in api(
        "trigger.get", {"output": ["description"], "hostids": hid}, tok)}
    attesi = [
        ("BOT %s: ERRORE riportato" % slug,
         "length(last(/%s/%s))>0" % (host, key_of(slug, "error")), 3),
        ("BOT %s: non in esecuzione" % slug,
         "last(/%s/%s)=0" % (host, key_of(slug, "status")), 4),
        ("BOT %s: nessun dato da 5m (nodo giu'?)" % slug,
         "nodata(/%s/%s,5m)=1" % (host, key_of(slug, "status")), 4),
        ("BOT %s: STOP LOSS scattato" % slug,
         "last(/%s/%s)=1" % (host, key_of(slug, "stop_loss")), 5),
    ]
    creati = 0
    for desc, expr, prio in attesi:
        if desc in esistenti:
            continue
        if not apply_:
            creati += 1
            continue
        api("trigger.create", {"description": desc, "expression": expr,
                               "priority": prio}, tok)
        creati += 1
    return creati


def main():
    apply_ = "--apply" in sys.argv
    keep_old = "--keep-old" in sys.argv
    tok = api("user.login", {"username": "Admin", "password": "zabbix"})
    gid = assicura_gruppo(tok) if apply_ else "26"
    print("gruppo %r groupid=%s  modalita'=%s"
          % (GRUPPO, gid, "APPLY" if apply_ else "DRY-RUN"))

    item_map = {}
    n_host = n_item = n_trig = 0
    for slug, asset, mac, src in BOTS:
        host = host_of(slug)
        hid, nuovo = assicura_host(tok, host, gid, apply_)
        if nuovo:
            n_host += 1
        if hid is None:
            print("  + %-34s (host da creare)" % host)
            continue
        mappa, ci = assicura_item(tok, hid, host, slug, apply_)
        ct = assicura_trigger(tok, hid, host, slug, apply_)
        n_item += ci
        n_trig += ct
        item_map[slug] = mappa
        stato = "nuovo" if nuovo else "esistente"
        print("  %s %-34s %-9s item+%d trigger+%d"
              % ("+" if nuovo else "=", host, stato, ci, ct))

    print("creati: %d host, %d item, %d trigger" % (n_host, n_item, n_trig))

    if not keep_old:
        for vecchio in VECCHI:
            h = api("host.get", {"output": ["hostid"], "filter": {"host": vecchio}}, tok)
            if not h:
                print("  vecchio host %s: gia' assente" % vecchio)
                continue
            if apply_:
                api("host.delete", [h[0]["hostid"]], tok)
                print("  RIMOSSO host storico %s" % vecchio)
            else:
                print("  (dry-run) rimuoverei %s" % vecchio)

    if apply_ and item_map:
        OUT_ITEMS.parent.mkdir(parents=True, exist_ok=True)
        OUT_ITEMS.write_text(json.dumps(item_map, indent=1), encoding="utf-8")
        print("mappa item scritta in", OUT_ITEMS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
