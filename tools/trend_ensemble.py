#!/usr/bin/env python3
"""trend_ensemble.py — l'edge episodico si cura con l'INSIEME, non con la config.

Il fatto misurato (docs/39, docs/40): la configurazione deployata sta quasi tutta
in un blocco su tre, e sul 4H solo 4/24 configurazioni reggono a fee spot. Ma
TUTTE e 24 hanno rendimento composto positivo sull'intero periodo: il problema non
e' che una config sia sbagliata, e' che ognuna e' episodica in momenti diversi.

Domanda di questa misura: l'INSIEME delle configurazioni (equipesato, su un
universo largo) e' robusto anche quando le singole configurazioni non lo sono? E
lo e' anche la sola meta' long-only, cioe' l'unica che possiamo davvero negoziare?

Piu' due schermi economici: stagionalita' settimanale e oraria sul 4H, e drift
delle nuove quotazioni EUR.

Uso: python3 tools/trend_ensemble.py
"""
from __future__ import annotations

import datetime as D
import math
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, "/home/sergio/alpha-omega-trading")
from denaro.research import eval as E  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
from trend_longshort import trend_ls, BASE  # noqa: E402

DATI = Path("/home/sergio/alpha-omega-trading/backtest_data")
CONFIG = [(c, e, s) for c in (20, 40, 60, 80)
          for e in (50, 100, 200) for s in (False, True)]
FEE_OKX = 0.0035      # taker spot OKX EEA, deployato
FEE_BYBIT = 0.0027    # taker Bybit EU + spread reale


def carica(prefisso, suffisso, minimo):
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


def bordi(n, blocchi):
    passo = n // blocchi
    out = []
    for k in range(blocchi):
        da = k * passo
        a = (k + 1) * passo if k < blocchi - 1 else n
        out.append((da, a))
    return passo, out


def per_blocco(serie, n, fee, blocchi, canale, ema, short):
    passo, conf = bordi(n, blocchi)
    if max(canale, 14, ema) + 1 >= passo:
        return None
    vals = []
    for da, a in conf:
        rend = []
        for s, c in serie.items():
            r = trend_ls(c[da:a], dict(BASE, canale=canale, trend_ema=ema,
                                       atr_period=14), 1.0, fee, 0.02,
                          permetti_short=short)
            if r.equity and r.trade >= 1:
                rend.append(r.ritorno)
        vals.append(st.mean(rend) if rend else 0.0)
    return vals


def ensemble(serie, n, fee, blocchi, solo_long=False):
    passo, _ = bordi(n, blocchi)
    righe = {}
    for (c, e, s) in CONFIG:
        if solo_long and s:
            continue
        v = per_blocco(serie, n, fee, blocchi, c, e, s)
        if v is not None:
            righe[(c, e, s)] = v
    if not righe:
        return None, 0
    vals = [st.mean([righe[k][i] for k in righe]) for i in range(blocchi)]
    return vals, len(righe)


def ensemble_pieno(serie, fee, solo_long=False):
    medie = []
    for (c, e, s) in CONFIG:
        if solo_long and s:
            continue
        rend = []
        for sym, cd in serie.items():
            r = trend_ls(cd, dict(BASE, canale=c, trend_ema=e, atr_period=14),
                         1.0, fee, 0.02, permetti_short=s)
            if r.equity and r.trade >= 1:
                rend.append(r.ritorno)
        if rend:
            medie.append(st.mean(rend))
    if not medie:
        return None
    return st.mean(medie), st.median(medie), len(medie)


def composto(vals):
    c = 1.0
    for v in vals:
        c *= (1.0 + v)
    return c - 1.0


def riga(nome, vals):
    pos = sum(1 for v in vals if v > 0)
    print("  %-40s comp %+8.2f%%  positivi %d/%d  blocchi: %s"
          % (nome, composto(vals) * 100, pos, len(vals),
             " ".join("%+.2f%%" % (v * 100) for v in vals)))


def taglio(prefisso, suffisso, minimo, blocchi, titolo):
    serie, n = carica(prefisso, suffisso, minimo)
    if not serie:
        print()
        print("(%s: nessun dato)" % titolo)
        return
    print()
    print("=" * 108)
    print("%s — %d simboli, %d barre, %d blocchi" % (titolo, len(serie), n, blocchi))
    print("=" * 108)
    for fee, fname in ((FEE_OKX, "OKX taker 0.35%"), (FEE_BYBIT, "Bybit taker 0.27%")):
        print("  --- fee %s ---" % fname)
        for nome, sl in (("ensemble 24 config", False), ("ensemble 12 long-only", True)):
            vals, k = ensemble(serie, n, fee, blocchi, sl)
            if vals:
                riga("%s (%d)" % (nome, k), vals)
        dep = per_blocco(serie, n, fee, blocchi, 40, 100, False)
        if dep:
            riga("config deployata", dep)
        pf = ensemble_pieno(serie, fee, True)
        if pf:
            print("  %-40s media %+8.2f%%  mediana %+8.2f%%  su %d config long-only"
                  % ("pieno periodo, ensemble long-only", pf[0] * 100, pf[1] * 100, pf[2]))


def stagionalita(serie):
    print()
    print("=" * 108)
    print("STAGIONALITA' delle barre 4H dell'universo largo (rendimenti del mercato, non della strategia)")
    print("=" * 108)
    giorni = {i: [] for i in range(7)}
    ore = {i: [] for i in range(24)}
    nomi = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"]
    for s, c in serie.items():
        for i in range(1, len(c)):
            p0 = float(c[i - 1]["c"])
            p1 = float(c[i]["c"])
            if p0 <= 0:
                continue
            r = p1 / p0 - 1.0
            dt = D.datetime.fromtimestamp(c[i]["ts"] / 1000, D.timezone.utc)
            giorni[dt.weekday()].append(r)
            ore[dt.hour].append(r)
    print("  %-6s %8s %10s %8s %8s" % ("giorno", "barre", "media bp", "t", "vincente%"))
    for i in range(7):
        v = giorni[i]
        if len(v) < 30:
            continue
        m = st.mean(v)
        sd = st.pstdev(v)
        t = m / (sd / math.sqrt(len(v))) if sd > 0 else 0.0
        print("  %-6s %8d %10.2f %8.2f %8.1f"
              % (nomi[i], len(v), m * 10000, t, 100.0 * sum(1 for x in v if x > 0) / len(v)))
    print("  %-6s %8s %10s %8s %8s" % ("ora", "barre", "media bp", "t", "vincente%"))
    for i in range(24):
        v = ore[i]
        if len(v) < 30:
            continue
        m = st.mean(v)
        sd = st.pstdev(v)
        t = m / (sd / math.sqrt(len(v))) if sd > 0 else 0.0
        if abs(t) >= 1.5:
            print("  %02d:00  %8d %10.2f %8.2f %8.1f"
                  % (i, len(v), m * 10000, t, 100.0 * sum(1 for x in v if x > 0) / len(v)))
    print("  (t calcolato su barre, non su giorni indipendenti: gonfiato, serve solo da setaccio)")


def drift_quotazione(prefisso, suffisso):
    print()
    print("=" * 108)
    print("DRIFT DELLE NUOVE QUOTAZIONI EUR — rendimento dopo la prima barra disponibile")
    print("=" * 108)
    grezza = {}
    for p in sorted(DATI.glob(prefisso + "*_" + suffisso + ".csv")):
        base = p.name[len(prefisso):-len("_" + suffisso + ".csv")]
        if not base:
            continue
        try:
            c = E.load_csv(p)
        except Exception:
            continue
        if len(c) >= 120:
            grezza[base] = c
    if not grezza:
        print("  (nessun dato)")
        return
    print("  %-8s %7s %10s %10s %10s" % ("simbolo", "barre", "30 barre", "60 barre", "120 barre"))
    for soglia, etichetta in ((1500, "corta (<1500 barre)"), (10 ** 9, "tutte")):
        acc = {30: [], 60: [], 120: []}
        for s, c in grezza.items():
            if soglia == 1500 and len(c) >= 1500:
                continue
            for k in (30, 60, 120):
                if len(c) > k:
                    acc[k].append(c[k]["c"] / c[0]["o"] - 1.0)
        if not acc[30]:
            continue
        print("  -- %s: %d simboli --" % (etichetta, len(acc[30])))
        for k in (30, 60, 120):
            v = acc[k]
            if len(v) < 3:
                continue
            m = st.mean(v)
            sd = st.pstdev(v)
            t = m / (sd / math.sqrt(len(v))) if sd > 0 else 0.0
            print("     dopo %3d barre: media %+7.2f%%  mediana %+7.2f%%  t %5.2f  positivi %d/%d"
                  % (k, m * 100, st.median(v) * 100, t, sum(1 for x in v if x > 0), len(v)))


def main():
    taglio("uni_", "4H", 4000, 5, "4H UNIVERSO LARGO")
    serie4, _ = carica("uni_", "4H", 4000)
    if serie4:
        stagionalita(serie4)
    drift_quotazione("uni_", "4H")
    taglio("dl_", "1D", 900, 3, "1D UNIVERSO LARGO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
