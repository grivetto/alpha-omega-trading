#!/usr/bin/env python3
"""Vale la pena allargare l'universo oltre i 17 asset? (round 30, 2026-09-17)

L'edge del trend e' EPISODICO: il rendimento si concentra in pochi blocchi
(docs/18). Con 17 asset il campione di trend e' la fortuna di un trimestre; la
cura teorica sono PIU' scommesse indipendenti. Ma il capitale e' fisso e
CONDIVISO fra i bot dello stesso conto: piu' asset = piu' occasioni, ma anche
piu' concorrenza sulla stessa cassa.

Protocollo, senza selezione in-sample:
  - gli insiemi sono definiti dalla LIQUIDITA' a 24h (esogena, la stessa che usa
    fetch_universe.py), non dai risultati: primi N per volume;
  - i 3 conti hanno i capitali VERI (42.12 / 24.83 / 42.04) e gli asset
    distribuiti a rotazione in ordine di liquidita';
  - il confronto e' su TUTTA la storia e su 4 finestre recenti: un
    miglioramento che vive in una sola finestra non si adotta (regola della
    sessione).

Per ogni asset il tool stampa anche il rendimento per finestra: serve a vedere
se l'allargamento aggiunge edge o solo rumore correlato.

Uso: python3 tools/trend_universo_largo.py
"""
from __future__ import annotations

import importlib.util
import math
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, "/home/sergio/alpha-omega-trading")
from denaro.research import eval as E  # noqa: E402

BASE_T = Path("/home/sergio/alpha-omega-trading/tools")
spec = importlib.util.spec_from_file_location("cap", str(BASE_T / "trend_capacita.py"))
cap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cap)

DATI = Path("/home/sergio/alpha-omega-trading/backtest_data")

# Parametri DEPLOYATI (trail 2.5 dal round 22, barre giornaliere allineate 16:00)
PAR = dict(canale=40, atr_period=14, trail_mult=2.5, stop_atr_mult=2.0,
           trend_ema=100, entry_slip=0.0005, max_exposure=1.0, risk_pct=0.02)

# Flotta in produzione oggi
FLOTTA = ["BTC", "ETH", "SOL", "XRP", "DOGE", "TRX", "CRV",
          "LINK", "AVAX", "DOT", "UNI", "SUI", "MINA",
          "ADA", "ARB", "XLM", "ALGO"]

CAPITALI = {"mc2": 42.12, "nuvola": 24.83, "MARCODG1": 42.04}
FINESTRE = (("storia", 0), ("540b", 540), ("365b", 365), ("270b", 270),
            ("180b", 180))


def ordine_liquidita(simboli):
    """Ordina per volume in EUR a 24h. Se manca la rete, ordine alfabetico."""
    try:
        import ccxt
        ex = ccxt.okx({"enableRateLimit": True, "hostname": "eea.okx.com",
                       "options": {"defaultType": "spot"}})
        ex.load_markets()
        pairs = [s for s in simboli if (s + "/EUR") in ex.markets]
        tks = ex.fetch_tickers([s + "/EUR" for s in pairs])
        return sorted(pairs, key=lambda s: float(
            (tks.get(s + "/EUR") or {}).get("quoteVolume") or 0), reverse=True)
    except Exception as e:  # noqa: BLE001
        print("  (liquidita' non leggibile: %s — ordine alfabetico)" % str(e)[:60])
        return sorted(simboli)


def carica():
    serie = {}
    for p in sorted(DATI.glob("dl_*_1D.csv")):
        base = p.name[3:-7]
        try:
            c = E.load_csv(p)
        except Exception:
            continue
        if len(c) > 250:
            serie[base] = c
    n = min(len(c) for c in serie.values())
    return {s: c[-n:] for s, c in serie.items()}, n


def conti_per(asset_ordinati):
    nomi = list(CAPITALI)
    conti = {k: [] for k in nomi}
    for i, s in enumerate(asset_ordinati):
        conti[nomi[i % len(nomi)]].append(s)
    return conti


def prova(dati, conti, risk=0.02):
    curve, rif, tr = [], 0, 0
    for nome, simboli in conti.items():
        if not simboli:
            continue
        assets = [(s, dati[s]) for s in simboli]
        r = cap.simula(assets, CAPITALI[nome], risk, cap.FEE, cap.SLIP, **PAR)
        curve.append([e / CAPITALI[nome] for e in r["curva"]])
        rif += r["rifiutati"]
        tr += r["trade"]
    n = min(len(c) for c in curve)
    port = [sum(c[i] for c in curve) / len(curve) for i in range(n)]
    picco, mdd = -1e18, 0.0
    for e in port:
        picco = max(picco, e)
        if picco > 0:
            mdd = max(mdd, 1.0 - e / picco)
    rr = [port[i] / port[i - 1] - 1.0 for i in range(1, n) if port[i - 1] > 0]
    sd = st.stdev(rr) if len(rr) > 10 else 0.0
    sharpe = (st.mean(rr) / sd * math.sqrt(365)) if sd > 0 else 0.0
    return dict(rend=port[-1] - 1.0, mdd=mdd, sharpe=sharpe, rif=rif, tr=tr,
                barre=n)


def per_asset(dati, ordinati):
    print()
    print("RENDIMENTO PER ASSET, parametri deployati (trail 2.5), capitale pieno")
    print("  %-7s %8s %8s %8s %8s %8s %5s %6s" %
          ("asset", "storia", "540b", "365b", "270b", "180b", "pos", "trade"))
    fuori = []
    for s in ordinati:
        riga = []
        trade = 0
        for _, w in FINESTRE:
            c = dati[s] if w == 0 else dati[s][-w:]
            try:
                r = E.backtest_trend(c, dict(PAR, fee_buffer=0.01), 1.0, cap.FEE)
                riga.append(r.ritorno if not r.errore else 0.0)
                trade = r.trade
            except Exception:
                riga.append(0.0)
        pos = sum(1 for x in riga if x > 0)
        in_flotta = s in FLOTTA
        if not in_flotta:
            fuori.append((pos, riga[0], s))
        print("  %-7s %7.1f%% %7.1f%% %7.1f%% %7.1f%% %7.1f%% %4d/5 %6s%s" %
              (s, riga[0] * 100, riga[1] * 100, riga[2] * 100, riga[3] * 100,
               riga[4] * 100, pos, trade, "" if in_flotta else " *fuori*"))
    fuori.sort(reverse=True)
    print()
    print("  candidate fuori flotta con piu' finestre positive: %s" %
          [s for pos, r, s in fuori[:10]])


def main():
    dati, n = carica()
    ordinati = ordine_liquidita(list(dati))
    print("asset con dati: %d | barre comuni: %d | fee %.2f%%/lato | rischio 2%%"
          % (len(dati), n, cap.FEE * 100))
    print("capitali: %s" % CAPITALI)
    print("ordine per liquidita': %s" % " ".join(ordinati[:24]))

    per_asset(dati, ordinati)

    print()
    print("PORTAFOGLIO a capitale condiviso (media dei 3 conti normalizzati)")
    print("  %-18s %-7s %10s %8s %8s %8s %9s %7s" %
          ("universo", "finestra", "rend.", "maxDD", "Sharpe", "trades",
           "rifiutati", "barre"))
    insiemi = [("flotta (17)", FLOTTA)]
    for k in (17, 26, 35, 44, 52):
        if k <= len(ordinati):
            insiemi.append(("top %d" % k, ordinati[:k]))
    for etichetta, simboli in insiemi:
        conti = conti_per(simboli)
        for nome_fin, w in FINESTRE:
            sotto = {s: (c if w == 0 else c[-w:]) for s, c in dati.items()
                     if s in simboli}
            m = prova(sotto, conti)
            print("  %-18s %-7s %9.2f%% %7.2f%% %8.2f %8d %9d %7d" %
                  (etichetta, nome_fin, m["rend"] * 100, m["mdd"] * 100,
                   m["sharpe"], m["tr"], m["rif"], m["barre"]))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
