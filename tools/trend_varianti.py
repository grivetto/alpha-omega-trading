#!/usr/bin/env python3
"""Esiste un ritocco CONSERVATIVO che migliora sia la storia sia il presente?

Il set aggressivo (canale 20) vince nella storia intera ma perde in ogni finestra
recente: cattura meglio il rally 2024 e peggio i mercati normali. Un cambio che
vale la pena deve migliorare ENTRAMBE le cose, non solo il passato.

Si tengono fisso canale 40, stop 2.0 (il cuore del deployato) e si provano solo
trail, stop e media. Vince chi e' positivo in ogni finestra e batte il deployato
sul recente.

Uso: python3 tools/trend_varianti.py
"""
from __future__ import annotations
import importlib.util
import math
import statistics as st
import sys
from pathlib import Path

BASE_T = Path("/home/sergio/alpha-omega-trading/tools")
spec = importlib.util.spec_from_file_location("cap", str(BASE_T / "trend_capacita.py"))
cap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cap)
spec2 = importlib.util.spec_from_file_location("vs", str(BASE_T / "trend_verifica_set.py"))
vs = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(vs)
sys.path.insert(0, "/home/sergio/alpha-omega-trading")
from denaro.research import eval as E  # noqa: E402

FINESTRE = [(None, "storia"), (540, "18m"), (365, "12m"), (270, "9m"), (180, "6m")]
VARIANTI = {
    "DEPLOY 40/3.0/2.0/100": dict(vs.BASE, canale=40, trail_mult=3.0, stop_atr_mult=2.0, trend_ema=100),
    "40/2.5/2.0/100": dict(vs.BASE, canale=40, trail_mult=2.5, stop_atr_mult=2.0, trend_ema=100),
    "40/3.0/2.5/100": dict(vs.BASE, canale=40, trail_mult=3.0, stop_atr_mult=2.5, trend_ema=100),
    "40/3.0/2.0/200": dict(vs.BASE, canale=40, trail_mult=3.0, stop_atr_mult=2.0, trend_ema=200),
    "40/2.5/2.0/200": dict(vs.BASE, canale=40, trail_mult=2.5, stop_atr_mult=2.0, trend_ema=200),
    "40/3.5/2.0/100": dict(vs.BASE, canale=40, trail_mult=3.5, stop_atr_mult=2.0, trend_ema=100),
    "30/3.0/2.0/100": dict(vs.BASE, canale=30, trail_mult=3.0, stop_atr_mult=2.0, trend_ema=100),
    "50/3.0/2.0/100": dict(vs.BASE, canale=50, trail_mult=3.0, stop_atr_mult=2.0, trend_ema=100),
}


def main():
    cache = {}
    print("capitale condiviso reale, fee %.2f%%, rischio %.0f%%" % (vs.FEE * 100, vs.RISK * 100))
    intest = "  %-22s" % "variante"
    for _, nome in FINESTRE:
        intest += " %8s" % nome
    intest += " %8s %8s" % ("b3", "b4")
    print(intest)
    esiti = {}
    for nome, p in VARIANTI.items():
        riga = "  %-22s" % nome
        vals = []
        for barre, _ in FINESTRE:
            if barre not in cache:
                cache[barre] = vs.serie_per_conto(barre)
            # una finestra troppo corta per scaldare media e canale produce
            # equity VUOTA: non e' un risultato, e' assenza di dati
            try:
                r, _, _ = vs.condiviso(cache[barre], p)
            except (IndexError, ValueError):
                r = float("nan")
            vals.append(r)
            riga += " %7.2f%%" % (r * 100)
        # gli ultimi due blocchi: e' li' che si vede se soffre i mercati normali
        serie = cache[None]
        lungh = [len(c) for aa in serie.values() for _, c in aa]
        n = min(lungh)
        passo = n // 4
        bvals = []
        for k in (2, 3):
            da = k * passo
            a = (k + 1) * passo if k < 3 else n
            blocco = {conto: [(s, c[da:a]) for s, c in aa] for conto, aa in serie.items()}
            try:
                r, _, _ = vs.condiviso(blocco, p)
            except (IndexError, ValueError):
                r = float("nan")
            bvals.append(r)
            riga += " %7.2f%%" % (r * 100)
        print(riga)
        esiti[nome] = vals + bvals
    print()
    print("  'storia' e' il periodo intero; b3/b4 sono gli ultimi due quarti (mercato normale)")
    print("  Criterio: batte il deployato in TUTTE le finestre recenti (18m,12m,9m,6m,b3,b4)?")
    rif = esiti["DEPLOY 40/3.0/2.0/100"]
    for nome, v in esiti.items():
        if nome.startswith("DEPLOY"):
            continue
        peggio = sum(1 for i in (1, 2, 3, 4, 5, 6) if v[i] < rif[i])
        print("    %-22s rende meno del deployato in %d/6 finestre recenti" % (nome, peggio))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
