#!/usr/bin/env python3
"""Denaro — capitale minimo perche' il trend funzioni davvero.

Perche' esiste: il 2026-09-17 il live check ha scoperto che con capital 5.0 per
bot e rischio 2% sei bot su quindici non avrebbero MAI piazzato un ordine,
perche' il sizing sul rischio produceva posizioni sotto il minimo
dell'exchange (BTC 6.67 EUR, ARB 1.51, ADA 1.76, XLM 1.62...).

Questo strumento calcola, per ogni asset, il capitale necessario perche' la
posizione calcolata superi il minimo reale, e per ogni conto:
  - il minimo perche' OGNI bot possa piazzare (il massimo fra i suoi asset)
  - il minimo perche' TUTTI i bot possano essere in posizione insieme (la somma)

Uso: python3 tools/trend_capital.py config/node_mc2.yaml [--rendimento 0.07]
"""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import ccxt  # noqa: E402
import yaml  # noqa: E402

from denaro.domain.trend import TrendParams, TrendPolicy  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config")
    ap.add_argument("--rendimento", type=float, default=0.07,
                    help="rendimento annuo atteso dell'edge misurato")
    a = ap.parse_args()
    cfg = yaml.safe_load(pathlib.Path(a.config).read_text(encoding="utf-8"))
    bots = [b for b in (cfg.get("bots") or [])
            if b.get("enabled", True) and b.get("strategy") == "trend"]
    if not bots:
        print("nessun bot trend"); return 1

    ex = ccxt.okx({"enableRateLimit": True, "hostname": "eea.okx.com",
                   "options": {"defaultType": "spot"}})
    ex.load_markets()

    print("%-9s %10s %10s %9s %9s %12s" %
          ("ASSET", "prezzo", "min EUR", "ATR%", "stop%", "capitale min"))
    print("-" * 68)
    righe = []
    for b in bots:
        sym = b["symbol"]
        par = TrendParams(canale=int(b.get("canale", 40)),
                          atr_period=int(b.get("atr_period", 14)),
                          stop_atr_mult=float(b.get("stop_atr_mult", 2.0)),
                          trend_ema=int(b.get("trend_ema", 100)),
                          risk_pct=float(b.get("risk_pct", 0.02)))
        try:
            m = ex.market(sym)
            r0 = ex.publicGetMarketHistoryCandles({"instId": m["id"], "bar": "1D",
                                                   "limit": "300"})
            dati = r0.get("data") or []
            min_amt = m["limits"]["amount"]["min"]
            prezzo = ex.fetch_ticker(sym).get("last") or 0.0
        except Exception as e:
            print("%-9s errore: %s" % (sym.split("/")[0], str(e)[:40])); continue
        righe_c = [[int(x[0]) / 1000.0, float(x[1]), float(x[2]), float(x[3]),
                    float(x[4]), float(x[5])] for x in dati]
        pol = TrendPolicy(par)
        pol.precarica_barre(righe_c[1:])
        if pol.atr <= 0 or prezzo <= 0:
            continue
        atr_frac = pol.atr / prezzo
        stop = par.stop_atr_mult * atr_frac
        min_eur = min_amt * prezzo
        # notional = capitale * risk / stop  >=  min_eur
        cap_min = (min_eur * stop / par.risk_pct) if par.risk_pct > 0 else 0.0
        righe.append((sym.split("/")[0], prezzo, min_eur, atr_frac, stop, cap_min))
        print("%-9s %10.4f %10.4f %8.2f%% %8.2f%% %12.2f" %
              (sym.split("/")[0], prezzo, min_eur, 100 * atr_frac, 100 * stop, cap_min))

    if not righe:
        return 1
    peggiore = max(righe, key=lambda z: z[5])
    totale = sum(z[5] for z in righe)
    print()
    print("=== conclusioni ===")
    print("  perche' OGNI bot possa piazzare serve almeno : %.2f EUR  (limitato da %s)"
          % (peggiore[5], peggiore[0]))
    print("  perche' TUTTI siano in posizione insieme   : %.2f EUR" % totale)
    print("  attuale nel config: %.2f EUR per bot" % float(bots[0].get("capital", 0.0)))
    print()
    print("=== capitale e rendimento atteso (edge misurato ~%.0f%%/anno) ==="
          % (100 * a.rendimento))
    for cap in (25, 100, 250, 500, 1000, 5000, 10000):
        print("  %6d EUR  ->  %8.2f EUR/anno   (%.2f EUR/mese)"
              % (cap, cap * a.rendimento, cap * a.rendimento / 12))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
