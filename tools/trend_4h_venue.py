#!/usr/bin/env python3
"""trend_4h_venue.py — l'ultima verifica che puo' giustificare una migrazione.

DOMANDA. Meglio OKX EEA o Bybit EU? Le fee MISURATE sull'account vero sono:
    OKX EEA    maker 0.200%  taker 0.350%
    Bybit EU   maker 0.100%  taker 0.250%
Alle spalle c'e' un'altra differenza, lo spread mediano misurato sugli alt:
    OKX 0.0778%   Bybit 0.1183%
cioe' Bybit costa ~2 bps/lato in piu' di spread. Il confronto onesto e' quindi
0.25%+0.02% = 0.27%/lato Bybit contro 0.35%/lato OKX.

PERCHE' CONTA. Docs/20: sul 4H il verdetto della griglia cambia RADICALMENTE
cambiando solo la fee (3/24 configurazioni robuste a fee spot, 20/24 a fee swap).
Se il 4H fosse robusto a 0.25%/lato, migrare avrebbe senso; a 0.35% no. Quindi il
numero da produrre non e' "quanto rende", e' "quante configurazioni su 24 sono
positive in almeno 4 finestre su 5" a ciascun livello di fee.

CRITERIO (identico a tools/trend_4h_griglia.py, per confrontabilita'):
  4 canali (20/40/60/80) x 3 EMA (50/100/200) x 2 (long-only, long/short) = 24
  configurazioni; serie divisa in 5 blocchi uguali; "robusta" = composta positiva
  in >= 4 blocchi su 5.

Uso: python3 tools/trend_4h_venue.py
"""
from __future__ import annotations

import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, "/home/sergio/alpha-omega-trading")
from denaro.research import eval as E  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
from trend_longshort import trend_ls, BASE  # noqa: E402

DATI = Path("/home/sergio/alpha-omega-trading/backtest_data")

# Le 19 del documento 20 (per confrontare i numeri 3/24 e 20/24 gia' pubblicati).
UNIVERSO_19 = ["AAVE", "ADA", "ALGO", "ARB", "ATOM", "AVAX", "BTC", "CRV", "DOGE",
               "DOT", "ETH", "LINK", "LTC", "SOL", "SUI", "TRX", "UNI", "XLM", "XRP"]

# fee per lato: valori MISURATI sull'account, non listini pubblici.
LIVELLI = [
    ("OKX spot taker 0.35%  [deployato oggi]", 0.0035),
    ("OKX spot maker 0.20%", 0.0020),
    ("Bybit EU taker 0.25%", 0.0025),
    ("Bybit EU taker +spread 0.27%  [reale]", 0.0027),
    ("Bybit EU maker 0.10%", 0.0010),
    ("OKX swap taker 0.05%  [NON ottenibile: acctLv1]", 0.0005),
]


def carica(prefisso, suffisso, minimo):
    """Tutti i CSV del prefisso con almeno `minimo` barre, allineati alla coda."""
    serie = {}
    for p in sorted(DATI.glob(prefisso + "*_" + suffisso + ".csv")):
        base = p.name[len(prefisso):-len("_" + suffisso + ".csv")]
        if not base:
            continue
        try:
            c = E.load_csv(p)
        except Exception:
            continue
        if len(c) >= minimo:
            serie[base] = c
    if not serie:
        return {}, 0
    n = min(len(c) for c in serie.values())
    return {s: c[-n:] for s, c in serie.items()}, n


def seleziona(serie, nomi):
    return {s: c for s, c in serie.items() if s in nomi}


def griglia(serie, n, fee, blocchi=5):
    passo = n // blocchi
    confini = []
    for k in range(blocchi):
        da = k * passo
        a = (k + 1) * passo if k < blocchi - 1 else n
        confini.append((da, a))
    righe = []
    for canale in (20, 40, 60, 80):
        for ema_n in (50, 100, 200):
            for short in (False, True):
                p = dict(BASE, canale=canale, trend_ema=ema_n, atr_period=14)
                vals = []
                for da, a in confini:
                    rend = []
                    for s, c in serie.items():
                        r = trend_ls(c[da:a], p, 1.0, fee, 0.02, permetti_short=short)
                        if r.equity and r.trade >= 1:
                            rend.append(r.ritorno)
                    vals.append(st.mean(rend) if rend else 0.0)
                comp = 1.0
                for v in vals:
                    comp *= (1.0 + v)
                righe.append({"canale": canale, "ema": ema_n, "short": short,
                              "vals": vals, "comp": comp - 1.0,
                              "pos": sum(1 for v in vals if v > 0)})
    return righe


def mostra(serie, n, titolo, blocchi=5):
    print()
    print("=" * 96)
    print("%s — %d simboli, %d barre" % (titolo, len(serie), n))
    print("=" * 96)
    print("  %-46s %9s %10s %10s" % ("fee per lato", "robuste", "comp.med", "pos./24"))
    for nome, fee in LIVELLI:
        righe = griglia(serie, n, fee, blocchi)
        tot = len(righe)
        robusti = sum(1 for r in righe if r["pos"] >= blocchi - 1)
        fin_pos = sum(1 for r in righe if r["comp"] > 0)
        med = st.median([r["comp"] for r in righe])
        print("  %-46s %5d/%d %9.2f%% %10d" % (nome, robusti, tot, med * 100, fin_pos))


def per_blocco(serie, n, fee, etichetta, blocchi=5):
    """Dove sta il rendimento: episodico o distribuito? (docs/18 18.2)"""
    passo = n // blocchi
    p = dict(BASE, canale=40, trend_ema=100, atr_period=14)
    print()
    print("%s (canale 40, EMA 100, long-only, fee %.2f%%/lato)" % (etichetta, fee * 100))
    for k in range(blocchi):
        da = k * passo
        a = (k + 1) * passo if k < blocchi - 1 else n
        rend = []
        for s, c in serie.items():
            r = trend_ls(c[da:a], p, 1.0, fee, 0.02, permetti_short=False)
            if r.equity and r.trade >= 1:
                rend.append(r.ritorno)
        if rend:
            print("   blocco %d: media %+7.2f%%  mediana %+7.2f%%  positivi %2d/%d"
                  % (k + 1, st.mean(rend) * 100, st.median(rend) * 100,
                     sum(1 for x in rend if x > 0), len(rend)))


def main():
    fatto = False
    for prefisso, suffisso, minimo, titolo_tf in (
            ("uni_", "4H", 4000, "4H"), ("dl_", "1D", 900, "1D")):
        serie, n = carica(prefisso, suffisso, minimo)
        if not serie:
            print("(nessun file %s*_%s.csv con >= %d barre)" % (prefisso, suffisso, minimo))
            continue
        fatto = True
        s19 = seleziona(serie, set(UNIVERSO_19))
        if len(s19) >= 10:
            n19 = min(len(c) for c in s19.values())
            mostra({s: c[-n19:] for s, c in s19.items()}, n19,
                   "%s — LE 19 DEL DOCUMENTO 20" % titolo_tf)
        mostra(serie, n, "%s — UNIVERSO LARGO" % titolo_tf)
        per_blocco(serie, n, 0.0027,
                   "%s universo largo, Bybit EU taker reale" % titolo_tf)
        per_blocco(serie, n, 0.0035,
                   "%s universo largo, OKX taker deployato" % titolo_tf)
    if not fatto:
        print("Nessun dato: lancia prima tools/fetch_universe.py")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
