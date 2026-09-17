#!/usr/bin/env python3
"""Denaro — monitor del trend: quanto manca al primo segnale?

Per ogni bot trend del config legge le candele giornaliere dall'endpoint reale,
le passa alla STESSA TrendPolicy che gira in produzione e riporta:
  - chiusura, canale (massimo a N barre), media lunga, ATR
  - distanza percentuale dalla chiusura al canale: quanto deve salire perche'
    scatti il breakout
  - se il segnale e' ATTIVO adesso
  - lo stato live del bot (ordini aperti, equity, posizione) dal file health

Uso: python3 tools/trend_monitor.py config/node_mc2.yaml [--health-dir DIR]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import ccxt  # noqa: E402
import yaml  # noqa: E402

from denaro.domain.trend import TrendParams, TrendPolicy  # noqa: E402


def candele(ex, simbolo, bar="1D", limite=300):
    m = ex.market(simbolo)
    r = ex.publicGetMarketHistoryCandles({"instId": m["id"], "bar": bar,
                                          "limit": str(limite)})
    dati = r.get("data") if isinstance(r, dict) else r
    return [[int(x[0]) / 1000.0, float(x[1]), float(x[2]), float(x[3]),
             float(x[4]), float(x[5])] for x in (dati or [])]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config")
    ap.add_argument("--health-dir", default="")
    a = ap.parse_args()
    cfg = yaml.safe_load(pathlib.Path(a.config).read_text(encoding="utf-8"))
    bots = [b for b in (cfg.get("bots") or [])
            if b.get("enabled", True) and b.get("strategy") == "trend"]
    if not bots:
        print("nessun bot trend nel config"); return 1

    ex = ccxt.okx({"enableRateLimit": True, "hostname": "eea.okx.com",
                   "options": {"defaultType": "spot"}})
    ex.load_markets()

    print("%-11s %10s %10s %10s %7s %9s %8s %s"
          % ("ASSET", "chiusura", "canale", "media100", "ATR%", "al canale", "segnale", "stato live"))
    print("-" * 104)
    for b in bots:
        sym = b["symbol"]
        par = TrendParams(
            canale=int(b.get("canale", 40)),
            atr_period=int(b.get("atr_period", 14)),
            trail_mult=float(b.get("trail_mult", 3.0)),
            stop_atr_mult=float(b.get("stop_atr_mult", 2.0)),
            trend_ema=int(b.get("trend_ema", 100)),
            risk_pct=float(b.get("risk_pct", 0.02)),
        )
        try:
            righe = candele(ex, sym)
        except Exception as e:
            print("%-11s errore candele: %s" % (sym.split("/")[0], str(e)[:50])); continue
        if len(righe) < max(par.canale, par.atr_period, par.trend_ema) + 5:
            print("%-11s storico insufficiente (%d barre)" % (sym.split("/")[0], len(righe))); continue
        pol = TrendPolicy(par)
        pol.precarica_barre(righe)
        chiusura = righe[0][4]          # OKX ritorna dalla piu' recente
        atr_pct = 100.0 * pol.atr / chiusura if chiusura else 0.0
        dist = 100.0 * (pol.donchian - chiusura) / chiusura if chiusura else 0.0
        segnale = "ATTIVO" if pol.segnale_breakout() else "-"
        # stato live dal file health
        stato = ""
        hp = b.get("health_path") or ""
        hd = a.health_dir
        if hd:
            hp = os.path.join(hd, os.path.basename(hp))
        if hp and os.path.exists(hp):
            try:
                h = json.load(open(hp))
                stato = "eq=%.2f buys=%s sells=%s%s" % (
                    h.get("total_equity") or 0, h.get("buys"), h.get("sells"),
                    " ERR=%s" % h["error"][:25] if h.get("error") else "")
            except Exception:
                stato = "health illeggibile"
        print("%-11s %10.4f %10.4f %10.4f %6.2f%% %8.2f%% %8s %s"
              % (sym.split("/")[0], chiusura, pol.donchian, pol.ema, atr_pct,
                 dist, segnale, stato))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
