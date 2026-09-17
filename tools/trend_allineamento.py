#!/usr/bin/env python3
"""Verifica che le barre live si chiudano sullo STESSO confine delle candele.

Per ogni bot trend del config scarica lo storico reale, lo inietta nella policy
di produzione e stampa il confine ricavato, la prossima chiusura di barra e la
distanza al canale. Serve a garantire che il live valuti il segnale misurato nel
backtest: OKX allinea le candele giornaliere alle 16:00 UTC (mezzanotte UTC+8),
non a mezzanotte UTC.

Uso: python3 tools/trend_allineamento.py config/node_mc2.yaml
"""
from __future__ import annotations

import argparse
import datetime
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import ccxt  # noqa: E402
import yaml  # noqa: E402

from denaro.domain.trend import TrendParams, TrendPolicy  # noqa: E402

GIORNO = 86_400.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config")
    a = ap.parse_args()
    cfg = yaml.safe_load(pathlib.Path(a.config).read_text(encoding="utf-8"))
    bots = [b for b in (cfg.get("bots") or [])
            if b.get("enabled", True) and b.get("strategy") == "trend"]
    if not bots:
        print("nessun bot trend nel config")
        return 1
    ex = ccxt.okx({"enableRateLimit": True, "hostname": "eea.okx.com",
                   "options": {"defaultType": "spot"}})
    ex.load_markets()
    now = datetime.datetime.now(datetime.timezone.utc).timestamp()
    print("ora UTC %s" % datetime.datetime.now(
        datetime.timezone.utc).isoformat(timespec="seconds"))
    print("%-9s %8s %6s %-14s %-14s %6s %8s"
          % ("ASSET", "offset", "barre", "ultima chiusa", "pross. chiusura",
             "ore", "al canale"))
    print("-" * 82)
    for b in bots:
        m = ex.market(b["symbol"])
        r = ex.publicGetMarketHistoryCandles(
            {"instId": m["id"], "bar": "1D", "limit": "300"})
        dati = r.get("data") or []
        righe = [[int(x[0]) / 1000.0, float(x[1]), float(x[2]), float(x[3]),
                  float(x[4]), float(x[5])] for x in dati]
        par = TrendParams(
            canale=int(b.get("canale", 40)),
            atr_period=int(b.get("atr_period", 14)),
            trail_mult=float(b.get("trail_mult", 2.5)),
            stop_atr_mult=float(b.get("stop_atr_mult", 2.0)),
            trend_ema=int(b.get("trend_ema", 100)),
            risk_pct=float(b.get("risk_pct", 0.02)),
            periodo_barre_s=GIORNO)
        pol = TrendPolicy(par)
        n = pol.precarica_barre(righe, now)
        off = pol.params.offset_barre_s
        ultima = list(pol.barre)[-1]["ts"]
        chiusura = list(pol.barre)[-1]["c"]
        prossima = int((now - off) // GIORNO) * GIORNO + off + GIORNO
        dist = 100.0 * (pol.donchian - chiusura) / chiusura if chiusura else 0.0
        print("%-9s %8.0f %6d %-14s %-14s %6.1f %7.2f%%"
              % (b["symbol"].split("/")[0], off, n,
                 datetime.datetime.fromtimestamp(
                     ultima, datetime.timezone.utc).strftime("%m-%d %H:%M"),
                 datetime.datetime.fromtimestamp(
                     prossima, datetime.timezone.utc).strftime("%m-%d %H:%M"),
                 (prossima - now) / 3600.0, dist))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
