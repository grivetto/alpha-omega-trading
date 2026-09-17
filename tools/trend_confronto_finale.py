#!/usr/bin/env python3
"""Aggiunge la misura sul PERIODO INTERO accanto a quella per blocchi.

Il "composto dei blocchi" moltiplica MEDIE per-simbolo: non e' un rendimento di
portafoglio valido se i singoli simboli rendono in modo molto diverso (XLM +135%
in un blocco, altri negativi). Da solo puo' raccontare una storia falsa. Qui si
riportano ENTRAMBE le misure per ogni configurazione, cosi' il confronto e' onesto.
"""
from __future__ import annotations
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, "/home/sergio/alpha-omega-trading")
from denaro.research import eval as E  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
from trend_longshort import trend_ls, BASE  # noqa: E402
from trend_4h_griglia import carica  # noqa: E402

BLOCCHI = 5


def analizza(serie, n, etichetta, fee):
    passo = n // BLOCCHI
    confini = [(k * passo, (k + 1) * passo if k < BLOCCHI - 1 else n)
               for k in range(BLOCCHI)]
    righe = []
    for canale in (20, 40, 60, 80):
        for ema_n in (50, 100, 200):
            for short in (False, True):
                p = dict(BASE, canale=canale, trend_ema=ema_n, atr_period=14)
                # periodo INTERO
                intero = []
                for s, c in serie.items():
                    r = trend_ls(c, p, 1.0, fee, 0.02, permetti_short=short)
                    if r.equity:
                        intero.append(r.ritorno)
                # blocchi
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
                righe.append({"intero": st.mean(intero) if intero else 0.0,
                              "comp": comp - 1.0, "short": short,
                              "pos": sum(1 for v in vals if v > 0)})
    tot = len(righe)
    print()
    print("=== %s  (fee %.2f%%/lato, %d configurazioni)" % (etichetta, fee * 100, tot))
    print("    PERIODO INTERO: mediano %+7.2f%%   positivo %d/%d (%.0f%%)"
          % (st.median([r["intero"] for r in righe]) * 100,
             sum(1 for r in righe if r["intero"] > 0), tot,
             100.0 * sum(1 for r in righe if r["intero"] > 0) / tot))
    print("    PER BLOCCHI  : mediano %+7.2f%%   robusto (>=4/5) %d/%d (%.0f%%)"
          % (st.median([r["comp"] for r in righe]) * 100,
             sum(1 for r in righe if r["pos"] >= 4), tot,
             100.0 * sum(1 for r in righe if r["pos"] >= 4) / tot))
    for short in (False, True):
        sel = [r for r in righe if r["short"] == short]
        print("      %-11s intero mediano %+8.2f%%  (positivo %d/%d)   robusto %d/%d"
              % ("long/short" if short else "long-only",
                 st.median([r["intero"] for r in sel]) * 100,
                 sum(1 for r in sel if r["intero"] > 0), len(sel),
                 sum(1 for r in sel if r["pos"] >= 4), len(sel)))
    return righe


def main():
    s4, n4 = carica("uni_", "4H")
    if s4:
        analizza(s4, n4, "4H a fee SWAP 0.05% (derivati)", 0.0005)
        analizza(s4, n4, "4H a fee SPOT 0.35%", 0.0035)
    sd, nd = carica("dl_", "1D")
    if sd:
        analizza(sd, nd, "GIORNALIERO a fee SPOT (deployato oggi)", 0.0035)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
