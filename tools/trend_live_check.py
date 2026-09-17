#!/usr/bin/env python3
"""Denaro — stato live dei bot trend di questa macchina.

Riporta, per ogni bot del config: lo stato dal file health, gli ordini REALI
sull'exchange e il saldo. Serve a verificare il PRIMO segnale quando arriva:
l'ordine piazzato deve avere il notional previsto dal sizing sul rischio e la
protezione a entry - stop_atr_mult*ATR.

Uso: python3 tools/trend_live_check.py config/node_mc2.yaml [--env .env]
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import ccxt  # noqa: E402
import yaml  # noqa: E402


def carica_env(path):
    if not path or not os.path.exists(path):
        return
    for riga in pathlib.Path(path).read_text(encoding="utf-8").splitlines():
        riga = riga.strip()
        if not riga or riga.startswith("#") or "=" not in riga:
            continue
        k, v = riga.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config")
    ap.add_argument("--env", default="")
    a = ap.parse_args()
    carica_env(a.env)
    cfg = yaml.safe_load(pathlib.Path(a.config).read_text(encoding="utf-8"))
    bots = [b for b in (cfg.get("bots") or []) if b.get("enabled", True)]

    print("=== stato health ===")
    for b in bots:
        hp = b.get("health_path") or ""
        if not hp or not os.path.exists(hp):
            print("  %-10s health assente" % b["symbol"]); continue
        h = json.load(open(hp))
        print("  %-10s strat=%-7s eq=%-9s free=%-9s buys=%s sells=%s trades=%s pnl=%s%s"
              % (b["symbol"], h.get("strategy"), h.get("total_equity"),
                 h.get("free_quote"), h.get("buys"), h.get("sells"),
                 h.get("trades"), h.get("pnl"),
                 ("  ERR=%s" % h["error"][:40]) if h.get("error") else ""))

    pref = (bots[0].get("env_prefix") or "") if bots else ""
    key = os.environ.get(pref + "OKX_API_KEY")
    if not key:
        print("\n(nessuna chiave con prefisso %r: salto la parte exchange)" % pref)
        return 0
    ex = ccxt.okx({"apiKey": key, "secret": os.environ[pref + "OKX_API_SECRET"],
                   "password": os.environ[pref + "OKX_PASSPHRASE"],
                   "hostname": "eea.okx.com", "enableRateLimit": True,
                   "options": {"defaultType": "spot"}})
    print("\n=== exchange: ordini aperti e saldi ===")
    tot = 0
    for b in bots:
        sym = b["symbol"]
        try:
            oo = ex.fetch_open_orders(sym)
        except Exception as e:
            print("  %-10s errore ordini: %s" % (sym, str(e)[:50])); continue
        tot += len(oo)
        for o in oo:
            n = (o.get("price") or 0) * (o.get("amount") or 0)
            print("  %-10s %-4s prezzo=%-12s qty=%-14s notional=%.4f" %
                  (sym, o.get("side"), o.get("price"), o.get("amount"), n))
        if not oo:
            print("  %-10s nessun ordine" % sym)
    print("  TOTALE ordini aperti: %d" % tot)
    bal = ex.fetch_balance()
    print("\n=== saldi ===")
    for c, v in (bal.get("total") or {}).items():
        if v and v > 1e-6:
            print("  %-6s %s" % (c, v))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
