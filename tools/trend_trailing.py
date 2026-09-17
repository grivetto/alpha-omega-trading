#!/usr/bin/env python3
"""Il trailing 2.5 e' una REGIONE stabile o un punto fortunato?

Due prove:
  A) per-asset: se batte il trailing 3.0 sulla maggioranza dei 19 asset, il
     vantaggio non dipende da un simbolo;
  B) sweep fine del trailing (2.0, 2.25, 2.5, 2.75, 3.0, 3.25) su piu' finestre
     scorrevoli: un punto isolato circondato da valori peggiori e' rumore, una
     regione piatta e' un segnale.

Uso: python3 tools/trend_trailing.py
"""
from __future__ import annotations
import importlib.util
import math
import statistics as st
import sys
from pathlib import Path

BASE_T = Path("/home/sergio/alpha-omega-trading/tools")
for nome_mod, file_mod in (("cap", "trend_capacita.py"), ("vs", "trend_verifica_set.py")):
    sp = importlib.util.spec_from_file_location(nome_mod, str(BASE_T / file_mod))
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    globals()[nome_mod] = m
sys.path.insert(0, "/home/sergio/alpha-omega-trading")
from denaro.research import eval as E  # noqa: E402

DATI = Path("/home/sergio/alpha-omega-trading/backtest_data")
TRAILS = [2.0, 2.25, 2.5, 2.75, 3.0, 3.25]


def p_di(trail):
    return dict(vs.BASE, canale=40, trail_mult=trail, stop_atr_mult=2.0, trend_ema=100)


def main():
    print("A) PER-ASSET — confronto trailing 2.5 contro 3.0 (il deployato)")
    tutti = [(s, E.load_csv(DATI / ("dl_%s_1D.csv" % s)))
             for _, (_, sims) in vs.REALI.items() for s in sims]
    n = min(len(c) for _, c in tutti)
    tutti = [(s, c[-n:]) for s, c in tutti]
    vinte25 = vinte30 = 0
    for s, c in tutti:
        r25 = E.backtest_trend(c, dict(p_di(2.5), risk_pct=vs.RISK), 1.0, vs.FEE, cap.SLIP).ritorno
        r30 = E.backtest_trend(c, dict(p_di(3.0), risk_pct=vs.RISK), 1.0, vs.FEE, cap.SLIP).ritorno
        if r25 > r30:
            vinte25 += 1
        else:
            vinte30 += 1
    print("   trailing 2.5 vince su %d/19 asset   |   trailing 3.0 su %d/19"
          % (vinte25, vinte30))

    print()
    print("B) SWEEP FINO su finestre scorrevoli (capitale condiviso)")
    cache = {}
    for barre in (None, 540, 450, 365, 300, 270, 220, 180):
        if barre not in cache:
            cache[barre] = vs.serie_per_conto(barre)
    n_max = min(len(c) for aa in cache[None].values() for _, c in aa)
    intest = "  %-8s" % "trail"
    for barre in (None, 540, 450, 365, 300, 270, 220, 180):
        intest += " %8s" % ("storia" if barre is None else "%db" % barre)
    intest += " %8s" % "media"
    print(intest)
    for trail in TRAILS:
        riga = "  %-8s" % ("%.2f" % trail)
        vals = []
        for barre in (None, 540, 450, 365, 300, 270, 220, 180):
            try:
                r, _, _ = vs.condiviso(cache[barre], p_di(trail))
            except (IndexError, ValueError):
                r = float("nan")
            vals.append(r)
            riga += " %7.2f%%" % (r * 100)
        # media delle finestre recenti (esclusa la storia intera)
        rec = [v for v in vals[1:] if v == v]
        riga += " %7.2f%%" % (st.mean(rec) * 100 if rec else float("nan"))
        print(riga)
    print()
    print("  Se 2.25-2.75 battono 3.0 in modo uniforme, e' una REGIONE; se solo 2.5")
    print("  spicca ed e' circondato da valori peggiori, e' rumore.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
