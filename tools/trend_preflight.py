#!/usr/bin/env python3
"""Pre-flight di un ingresso: quanto verrebbe comprato al prossimo confine.

Non piazza nulla: legge le candele reali, costruisce la STESSA policy del Node,
forza il confine di barra e chiede alla policy la decisione, come farebbe il
bot. Serve a sapere PRIMA cosa succede al primo segnale: quantita', nozionale,
minimo dell'exchange, stop iniziale e rischio in euro.

Uso: python3 tools/trend_preflight.py config/node_nuvola_trade.yaml
     python3 tools/trend_preflight.py config/node_nuvola_trade.yaml --forza
"""
from __future__ import annotations

import argparse
import datetime
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import ccxt  # noqa: E402
import yaml  # noqa: E402

from denaro.domain.trend import TrendParams, TrendPolicy  # noqa: E402

GIORNO = 86_400.0
OFFSET_OKX = 57_600.0                    # 16:00 UTC: confine delle candele OKX


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config")
    ap.add_argument("--forza", action="store_true",
                    help="valuta come se il prezzo fosse sopra il canale")
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
    adesso = time.time()
    conf = int((adesso - OFFSET_OKX) // GIORNO) * GIORNO + OFFSET_OKX
    prossimo = conf + GIORNO
    print("ora UTC %s — prossimo confine %s"
          % (datetime.datetime.fromtimestamp(adesso, datetime.timezone.utc)
             .strftime("%m-%d %H:%M"),
             datetime.datetime.fromtimestamp(prossimo, datetime.timezone.utc)
             .strftime("%m-%d %H:%M")))
    print("%-8s %9s %9s %5s %9s %12s %9s %7s %7s %s"
          % ("ASSET", "prezzo", "canale", "sopra", "entry", "amount",
             "nozionale", "stop", "rischio", "esito"))
    print("-" * 104)
    for b in bots:
        sym = b["symbol"]
        m = ex.market(sym)
        r = ex.publicGetMarketHistoryCandles(
            {"instId": m["id"], "bar": "1D", "limit": "300"})
        dati = r.get("data") or []
        candele = [[int(x[0]) / 1000.0, float(x[1]), float(x[2]), float(x[3]),
                    float(x[4]), float(x[5])] for x in dati]
        t = ex.publicGetMarketTicker({"instId": m["id"]})["data"][0]
        prezzo = float(t["last"])
        minimo = float((m.get("limits", {}).get("amount") or {}).get("min") or 0)
        attivo = float(b.get("taker_fee", 0))  # non usato: fee nel buffer
        par = TrendParams(
            canale=int(b.get("canale", 40)),
            atr_period=int(b.get("atr_period", 14)),
            trail_mult=float(b.get("trail_mult", 2.5)),
            stop_atr_mult=float(b.get("stop_atr_mult", 2.0)),
            trend_ema=int(b.get("trend_ema", 100)),
            risk_pct=float(b.get("risk_pct", 0.02)),
            periodo_barre_s=GIORNO)
        pol = TrendPolicy(par, min_amount=minimo)
        pol.precarica_barre(candele, conf + 3_600.0)
        canale = pol.donchian
        sopra = prezzo > canale
        prezzo_uso = canale * 1.01 if (a.forza and not sopra) else prezzo
        capitale = float(b.get("capital", 0) or 0)
        libero = capitale
        # primo giro: inizializza il periodo corrente (nessun segnale)
        pol.decide(prezzo_uso, {}, {}, capitale, capitale, libero, conf + 3_600.0)
        # secondo giro: il prezzo attraversa il confine -> valuta il breakout
        d = pol.decide(prezzo_uso, {}, {}, capitale, capitale, libero,
                       prossimo + 60.0)
        riga = [sym.split("/")[0], "%.5f" % prezzo, "%.5f" % canale,
                "SI" if prezzo > canale else "-"]
        if d.to_place:
            lv = d.to_place[0]
            q = lv.amount
            noz = q * lv.buy_price
            stop = lv.buy_price - par.stop_atr_mult * pol.atr
            rischio = q * (lv.buy_price - stop)
            esito = "OK" if noz >= 1.0 and (not minimo or q >= minimo) else "TROPPO PICCOLO"
            riga += ["%.6f" % lv.buy_price, "%.6f" % q, "%.2f" % noz,
                     "%.5f" % stop, "%.3f" % rischio,
                     "%s (min %.6f, rischio %.2f%% del capitale)"
                     % (esito, minimo, 100.0 * rischio / capitale if capitale else 0)]
        else:
            riga += ["-", "-", "-", "-", "-", d.reason]
        print("%-8s %9s %9s %5s %9s %12s %9s %7s %7s %s"
              % tuple(riga[:9] + [riga[9] if len(riga) > 9 else ""]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
