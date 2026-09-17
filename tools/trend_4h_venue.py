#!/usr/bin/env python3
"""trend_4h_venue.py — l'ultima verifica che puo' giustificare una migrazione.

DOMANDA. Meglio OKX EEA o Bybit EU? Le fee MISURATE sull'account vero sono:
    OKX EEA    maker 0.200%  taker 0.350%
    Bybit EU   maker 0.100%  taker 0.250%
Alle spalle c'e' anche lo spread mediano misurato sugli alt (OKX 0.0778%,
Bybit 0.1183%): Bybit costa ~2 bps/lato in piu'. Il confronto onesto e' quindi
0.25%+0.02% = 0.27%/lato Bybit contro 0.35%/lato OKX.

PERCHE' CONTA. Docs/20: sul 4H il verdetto della griglia cambia RADICALMENTE
cambiando solo la fee (3/24 configurazioni robuste a fee spot, 20/24 a fee swap).
Se il 4H fosse robusto a 0.25%/lato, migrare avrebbe senso; a 0.35% no.

DUE CORREZIONI METODOLOGICHE (2026-09-18) — senza queste la tabella mente:

1. CONFIGURAZIONI NON TESTABILI. trend_ls parte dopo max(canale, atr, EMA) barre.
   In un blocco piu' corto del warm-up la configurazione non fa NESSUN trade e
   la vecchia griglia le contava come "composto 0.00%" e "0 finestre positive":
   8 delle 24 configurazioni (tutte quelle con EMA 200) sparivano dal conteggio
   e la mediana crollava a 0.00% per un artefatto, non per un risultato. Qui le
   configurazioni non testabili sono ESCLUSE dal denominatore e dichiarate.

2. BLOCCHI ADEGUATI AL DATO. Il daily ha ~910 barre: 5 blocchi da 182 barre non
   possono contenere un'EMA 200. Il daily si misura su 3 blocchi. Il taglio
   "largo ma corto" (>=1000 barre su 4H = 1030) e' dichiarato NON testabile:
   blocchi da 206 barre con EMA fino a 200 non dicono niente.

Come si legge: "robuste" = configurazioni positive in >= (blocchi-1) blocchi.
Poi "pieno" = rendimento sull'intera serie con la configurazione deployata
(canale 40, EMA 100, long-only): e' il numero che si confronta con docs/18.

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

UNIVERSO_19 = ["AAVE", "ADA", "ALGO", "ARB", "ATOM", "AVAX", "BTC", "CRV", "DOGE",
               "DOT", "ETH", "LINK", "LTC", "SOL", "SUI", "TRX", "UNI", "XLM", "XRP"]

# fee per lato: valori MISURATI sull'account, non listini pubblici.
LIVELLI = [
    ("OKX spot taker 0.35% [deployato]", 0.0035),
    ("OKX spot maker 0.20%", 0.0020),
    ("Bybit EU taker 0.25%", 0.0025),
    ("Bybit EU taker +spread 0.27% [reale]", 0.0027),
    ("Bybit EU maker 0.10% [non ottenibile]", 0.0010),
    ("OKX swap taker 0.05% [acctLv2, assente]", 0.0005),
]


def carica(prefisso, suffisso, minimo, nomi=None):
    """CSV con >= minimo barre, allineati alla coda della serie PIU' CORTA.

    L'allineamento e' obbligatorio: i blocchi devono cadere sulle stesse date
    per tutti i simboli, altrimenti la media cross-sezionale non confronta nulla.
    """
    serie = {}
    for p in sorted(DATI.glob(prefisso + "*_" + suffisso + ".csv")):
        base = p.name[len(prefisso):-len("_" + suffisso + ".csv")]
        if not base or (nomi is not None and base not in nomi):
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


def griglia(serie, n, fee, blocchi=5):
    """24 configurazioni su blocchi uguali. Ritorna (righe, non_testabili)."""
    passo = n // blocchi
    confini = []
    for k in range(blocchi):
        da = k * passo
        a = (k + 1) * passo if k < blocchi - 1 else n
        confini.append((da, a))
    righe = []
    non_test = 0
    for canale in (20, 40, 60, 80):
        for ema_n in (50, 100, 200):
            for short in (False, True):
                # warm-up piu' lungo del blocco => nessun trade possibile
                if max(canale, 14, ema_n) + 1 >= passo:
                    non_test += 1
                    continue
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
    return righe, non_test


def pieno(serie, fee, canale=40, ema_n=100):
    """Rendimento sull'intera serie, configurazione deployata, long-only."""
    p = dict(BASE, canale=canale, trend_ema=ema_n, atr_period=14)
    rend = []
    for s, c in serie.items():
        r = trend_ls(c, p, 1.0, fee, 0.02, permetti_short=False)
        if r.equity and r.trade >= 1:
            rend.append(r.ritorno)
    if not rend:
        return None, None, 0
    return st.mean(rend), st.median(rend), len(rend)


def mostra(serie, n, titolo, blocchi):
    passo = n // blocchi
    print()
    print("=" * 104)
    print("%s — %d simboli, %d barre, %d blocchi da %d barre"
          % (titolo, len(serie), n, blocchi, passo))
    print("=" * 104)
    print("  %-40s %9s %10s %6s %11s %11s"
          % ("fee per lato", "robuste", "comp.med", "pos.", "pieno media", "pieno med."))
    for nome, fee in LIVELLI:
        righe, non_test = griglia(serie, n, fee, blocchi)
        tot = len(righe)
        robusti = sum(1 for r in righe if r["pos"] >= blocchi - 1)
        fin_pos = sum(1 for r in righe if r["comp"] > 0)
        med = st.median([r["comp"] for r in righe]) if righe else 0.0
        pm, pmd, k = pieno(serie, fee)
        print("  %-40s %4d/%-3d %9.2f%% %4d/%-2d %10s %10s"
              % (nome, robusti, tot, med * 100, fin_pos, tot,
                 ("%+.2f%%" % (pm * 100)) if pm is not None else "n/d",
                 ("%+.2f%%" % (pmd * 100)) if pmd is not None else "n/d"))
    if non_test:
        print("  (%d configurazioni su 24 NON testabili: warm-up EMA piu' lungo del blocco)"
              % non_test)


def per_blocco(serie, n, fee, etichetta, blocchi):
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


# Tagli. Il 4H ha 2.8 anni (blocchi da ~1000 barre: 5 blocchi regge). Il daily
# ha ~910 barre: 5 blocchi da 182 non contengono un'EMA 200, quindi 3 blocchi.
# Il taglio "largo ma corto" NON e' incluso: non e' misurabile, non e' un no.
TAGLI = [
    ("uni_", "4H", 5, [
        ("LE 19 DEL DOCUMENTO 20", 4000, set(UNIVERSO_19)),
        ("LARGO PROFONDO (>=4000 barre)", 4000, None),
    ]),
    ("dl_", "1D", 3, [
        ("LE 19 DEL DOCUMENTO 20", 900, set(UNIVERSO_19)),
        ("LARGO PROFONDO (>=900 barre)", 900, None),
    ]),
]


def main():
    fatto = False
    for prefisso, suffisso, blocchi, tagli in TAGLI:
        for nome_taglio, minimo, nomi in tagli:
            serie, n = carica(prefisso, suffisso, minimo, nomi)
            if not serie:
                print("(%s: nessun file con >= %d barre)" % (nome_taglio, minimo))
                continue
            fatto = True
            mostra(serie, n, "%s — %s" % (suffisso, nome_taglio), blocchi)
        serie, n = carica(prefisso, suffisso, tagli[0][1], None)
        if serie:
            per_blocco(serie, n, 0.0035,
                       "%s, OKX taker deployato 0.35%%" % suffisso, blocchi)
            per_blocco(serie, n, 0.0027,
                       "%s, Bybit EU taker reale 0.27%%" % suffisso, blocchi)
    if not fatto:
        print("Nessun dato: lancia prima tools/fetch_universe.py")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
