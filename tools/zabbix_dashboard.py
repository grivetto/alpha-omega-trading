#!/usr/bin/env python3
"""Ricostruisce la dashboard Zabbix "Denaro" sui 15 bot di trend in produzione.

Prima conteneva widget della generazione precedente (griglie DOGE/SOL, bot
Kraken) agganciati a item che non ricevono piu' dati: la dashboard mostrava "no
data" a fianco di bot vivi. I widget sono agganciati per ITEMID, quindi vanno
ricostruiti ogni volta che gli host cambiano.

Uso: python3 tools/zabbix_dashboard.py [--apply]
"""
from __future__ import annotations
import json, sys, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from denaro_bots import BOTS  # noqa: E402

URL = "http://localhost:1080/api_jsonrpc.php"
NOME = "Denaro"
ITEM_MAP = Path("/home/sergio/denaro/health/zbx_items.json")


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


def campo(nome, valore):
    return {"type": 1, "name": nome, "value": str(valore)}


def main():
    apply_ = "--apply" in sys.argv
    tok = api("user.login", {"username": "Admin", "password": "zabbix"})
    item_map = json.loads(ITEM_MAP.read_text(encoding="utf-8"))

    widgets = [{
        "type": "problems", "name": "⚠ Problemi attivi",
        "x": 0, "y": 0, "width": 12, "height": 2,
        "fields": [campo("show", 1), campo("problem", 1)],
    }]

    # Riepilogo di progetto: solo se gli item sono FRESCHI (altrimenti si
    # mostrerebbe "no data" e la dashboard sembrerebbe rotta).
    import time
    proj = api("item.get", {"output": ["itemid", "key_", "lastclock"],
                            "search": {"key_": "project."}}, tok)
    meta = int(time.time()) - 1800
    freschi = {i["key_"]: i["itemid"] for i in proj
               if int(i.get("lastclock") or 0) > meta}
    if len(freschi) >= 4:
        f = []
        for n, (k, lbl) in enumerate([("project.equity", "Equity tot"),
                                      ("project.pnl_total", "PnL realizzato"),
                                      ("project.trades_total", "Trades"),
                                      ("project.win_rate", "Win rate %")]):
            if k not in freschi:
                continue
            suf = "" if n == 0 else str(n + 1)
            f += [campo("itemid" + suf, freschi[k]), campo("itemid" + suf + "_lbl", lbl)]
        f.append(campo("show", 1))
        widgets.append({"type": "item", "name": "🏆 DENARO — capitale e risultato",
                        "x": 0, "y": 2, "width": 12, "height": 3, "fields": f})
        y0 = 5
    else:
        y0 = 2
        print("riepilogo progetto saltato: item project.* non freschi (%d)" % len(freschi))

    x, y = 0, y0
    mancanti = []
    for slug, asset, mac, src in BOTS:
        m = item_map.get(slug) or {}
        if not all(k in m for k in ("equity", "pnl", "trades", "buys", "sells")):
            mancanti.append(slug)
            continue
        f = [campo("itemid", m["equity"]), campo("itemid_lbl", "Equity"),
             campo("itemid2", m["pnl"]), campo("itemid2_lbl", "PnL"),
             campo("itemid3", m["trades"]), campo("itemid3_lbl", "Trades"),
             campo("itemid4", m["buys"]), campo("itemid4_lbl", "Buy"),
             campo("itemid5", m["sells"]), campo("itemid5_lbl", "Sell"),
             campo("show", 1)]
        widgets.append({"type": "item",
                        "name": "🤖 %s/EUR — trend (%s)" % (asset, mac),
                        "x": x, "y": y, "width": 6, "height": 3, "fields": f})
        x += 6
        if x >= 12:
            x, y = 0, y + 3
    if mancanti:
        print("bot senza item (saltati):", ", ".join(mancanti))

    pagina = {"name": "Trading", "widgets": widgets}
    print("widget totali: %d" % len(widgets))

    esistenti = api("dashboard.get", {"output": ["dashboardid", "name"],
                                     "filter": {"name": NOME}}, tok)
    if not apply_:
        print("(dry-run) %s dashboard %r con %d widget"
              % ("aggiornerei" if esistenti else "creerei", NOME, len(widgets)))
        return 0
    for d in esistenti:
        api("dashboard.delete", [d["dashboardid"]], tok)
        print("rimossa dashboard %r (id %s)" % (d["name"], d["dashboardid"]))
    r = api("dashboard.create", {"name": NOME, "display_period": 30,
                                 "auto_start": 0, "pages": [pagina]}, tok)
    print("creata dashboard %r id=%s" % (NOME, r["dashboardids"][0]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
