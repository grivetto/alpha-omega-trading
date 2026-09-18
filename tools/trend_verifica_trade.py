#!/usr/bin/env python3
"""Verifica il PRIMO trade contro cio' che la strategia misurata prevede.

Per ogni bot live del config:
  - legge le candele reali e ricostruisce canale/EMA/ATR con la STESSA policy di
    produzione;
  - dice se l'ultima barra chiusa era un breakout (ingresso atteso);
  - legge stato e journal del bot (posizione aperta, ordini, fill);
  - se c'e' un ingresso, confronta amount, nozionale e stop con quelli attesi dal
    modello di rischio e misura lo slittamento rispetto alla chiusura.

Non piazza e non modifica nulla. Risponde a "il primo ordine e' quello che il
backtest avrebbe fatto?" con numeri.

Uso: python3 tools/trend_verifica_trade.py config/node_nuvola_trade.yaml
"""
from __future__ import annotations

import argparse
import datetime
import glob
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import ccxt  # noqa: E402
import yaml  # noqa: E402

from denaro.domain.trend import TrendParams, TrendPolicy  # noqa: E402

GIORNO = 86_400.0
TABELLA = "  %-7s %-9s %11s %11s %7s %-9s %s"


def candele(ex, simbolo, limite=300):
    m = ex.market(simbolo)
    r = ex.publicGetMarketHistoryCandles({"instId": m["id"], "bar": "1D",
                                          "limit": str(limite)})
    dati = r.get("data") or []
    return [[int(x[0]) / 1000.0, float(x[1]), float(x[2]), float(x[3]),
             float(x[4]), float(x[5])] for x in dati]


def stato_del_bot(simbolo, data_dir):
    base = simbolo.split("/")[0]
    stato, journal = None, []
    for p in glob.glob(str(pathlib.Path(data_dir) / ("*_%s_EUR_state.json" % base))):
        try:
            stato = json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
        except Exception:
            stato = None
    for p in glob.glob(str(pathlib.Path(data_dir) / ("*_%s_EUR_trades.jsonl" % base))):
        for riga in pathlib.Path(p).read_text(encoding="utf-8").splitlines():
            try:
                journal.append(json.loads(riga))
            except Exception:
                continue
    return stato, journal


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config")
    ap.add_argument("--data-dir", default="node_data_trade")
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
    adesso = datetime.datetime.now(datetime.timezone.utc)
    print("ora UTC %s" % adesso.isoformat(timespec="seconds"))
    print(TABELLA % ("asset", "ultima barra", "chiusura", "canale", "ATR%",
                     "breakout", "stato / verifica"))
    print("  " + "-" * 96)
    ingressi_attesi, ingressi_presenti, problemi = 0, 0, []
    for b in bots:
        sym = b["symbol"]
        cand = candele(ex, sym)
        if len(cand) < 200:
            print(TABELLA % (sym.split("/")[0], "-", "-", "-", "-", "-",
                             "storico insufficiente"))
            continue
        par = TrendParams(
            canale=int(b.get("canale", 40)),
            atr_period=int(b.get("atr_period", 14)),
            trail_mult=float(b.get("trail_mult", 2.5)),
            stop_atr_mult=float(b.get("stop_atr_mult", 2.0)),
            trend_ema=int(b.get("trend_ema", 100)),
            risk_pct=float(b.get("risk_pct", 0.02)),
            periodo_barre_s=GIORNO)
        pol = TrendPolicy(par)
        pol.precarica_barre(cand, adesso.timestamp())
        ultima = list(pol.barre)[-1]
        chiusura = ultima["c"]
        atr_pct = pol.atr / chiusura if chiusura else 0.0
        breakout = pol.segnale_breakout()
        if breakout:
            ingressi_attesi += 1
        stato, journal = stato_del_bot(sym, a.data_dir)
        pos = (stato or {}).get("posizione_aperta")
        fill = None
        for ev in journal:
            if ev.get("evento") == "buy_filled" or ev.get("event") == "buy_filled":
                fill = ev
        dettagli = []
        if pos:
            ingressi_presenti += 1
            entry = float(pos.get("entry") or 0.0)
            amount = float(pos.get("amount") or 0.0)
            stop = float(pos.get("stop") or 0.0)
            budget = float(b.get("capital", 0) or 0)
            atteso_qty = (budget * par.risk_pct) / (par.stop_atr_mult * pol.atr)
            atteso_qty = min(atteso_qty,
                             budget * par.max_exposure / (entry or 1.0))
            atteso_stop = entry - par.stop_atr_mult * pol.atr
            scarto = (amount / atteso_qty - 1.0) if atteso_qty else 0.0
            dettagli.append("IN POSIZIONE entry %.6f x %.6f (nozionale %.2f EUR)"
                            % (entry, amount, entry * amount))
            dettagli.append("atteso qty %.6f (scarto %+.2f%%) | stop %.6f (atteso %.6f)"
                            % (atteso_qty, scarto * 100, stop, atteso_stop))
            if abs(scarto) > 0.05:
                problemi.append("%s: quantita' fuori dal 5%% dall'atteso" % sym)
            if stop > 0 and abs(stop - atteso_stop) / atteso_stop > 0.02:
                problemi.append("%s: stop lontano dal 2 ATR atteso" % sym)
            if fill:
                prezzo_fill = float(fill.get("entry") or fill.get("price") or 0.0)
                if prezzo_fill and chiusura:
                    dettagli.append("fill vs chiusura: %+.3f%%"
                                    % ((prezzo_fill / chiusura - 1.0) * 100))
        elif breakout:
            problemi.append("%s: breakout sull'ultima barra chiusa ma NESSUN "
                            "ingresso registrato" % sym)
            dettagli.append("BREAKOUT SENZA INGRESSO (verificare ordini e cassa)")
        else:
            dettagli.append("flat, nessun breakout (distanza al canale %.2f%%)"
                            % (100.0 * (pol.donchian - chiusura) / chiusura
                               if chiusura else 0.0))
        print(TABELLA % (sym.split("/")[0],
                         datetime.datetime.fromtimestamp(
                             ultima["ts"], datetime.timezone.utc).strftime("%m-%d %H:%M"),
                         "%.5f" % chiusura, "%.5f" % pol.donchian,
                         "%.2f%%" % (atr_pct * 100),
                         "SI" if breakout else "-", dettagli[0]))
        for d in dettagli[1:]:
            print("  %-7s %s" % ("", d))
    print()
    print("  ingressi attesi (breakout sull'ultima barra chiusa): %d" % ingressi_attesi)
    print("  posizioni registrate dallo stato: %d" % ingressi_presenti)
    if problemi:
        print("  PROBLEMI:")
        for p in problemi:
            print("    - %s" % p)
    else:
        print("  nessuna divergenza rilevata")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
