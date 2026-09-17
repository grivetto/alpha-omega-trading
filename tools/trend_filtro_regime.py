#!/usr/bin/env python3
"""Il filtro di regime migliora la strategia? (validato prima di misurarlo)"""
from __future__ import annotations
import math
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, "/home/sergio/alpha-omega-trading/tools")
sys.path.insert(0, "/home/sergio/alpha-omega-trading")
import trend_sim_filtro as sf
import trend_capacita as cap
from denaro.research import eval as E

DATI = Path("/home/sergio/alpha-omega-trading/backtest_data")
FEE = 0.0035
RISK = 0.02
CONTI = [("mc2", 42.12), ("nuvola", 24.83), ("MARCODG1", 42.04)]
FLOTTA = {"mc2": ["BTC", "ETH", "SOL", "XRP", "DOGE", "TRX", "CRV"],
          "nuvola": ["LINK", "AVAX", "DOT", "UNI", "SUI", "MINA"],
          "MARCODG1": ["ADA", "ARB", "XLM", "ALGO"]}
BASE = dict(canale=40, atr_period=14, trail_mult=2.5, stop_atr_mult=2.0,
            trend_ema=100, entry_slip=0.0005, fee_buffer=0.01, max_barre=400,
            max_exposure=1.0)
_cache = {}


def serie(nome):
    if nome not in _cache:
        aa = [(a, E.load_csv(DATI / ("dl_%s_1D.csv" % a))) for a in FLOTTA[nome]]
        n = min(len(c) for _, c in aa)
        _cache[nome] = [(a, c[-n:]) for a, c in aa], n
    return _cache[nome]


def filtro_btc(tipo):
    """Serie booleana allineata alla coda comune: True = si puo' entrare."""
    c = E.load_csv(DATI / "dl_BTC_1D.csv")
    closes = [x["c"] for x in c]
    if tipo == "nessuno":
        return None
    if tipo.startswith("ema"):
        n = int(tipo[3:])
        ema = E.ema(closes, n)
        return [closes[i] > ema[i] for i in range(len(closes))]
    if tipo.startswith("mom"):
        n = int(tipo[3:])
        return [i >= n and closes[i] > closes[i - n] for i in range(len(closes))]
    raise ValueError(tipo)


def misura(tipo_filtro, barre=None):
    curve = []
    for nome, capitale in CONTI:
        aa, _ = serie(nome)
        if barre:
            aa = [(a, c[-barre:]) for a, c in aa]
        n = min(len(c) for _, c in aa)
        aa2 = [(a, c[-n:]) for a, c in aa]
        f = filtro_btc(tipo_filtro)
        f = f[-n:] if f is not None else None
        r = sf.simula_filtrata(aa2, capitale, RISK, FEE, sf.SLIP, filtro=f, **BASE)
        curve.append([e / capitale for e in r["curva"]])
    m = min(len(c) for c in curve)
    port = [sum(c[i] for c in curve) / len(curve) for i in range(m)]
    picco, mdd = -1e18, 0.0
    for e in port:
        picco = max(picco, e)
        if picco > 0:
            mdd = max(mdd, 1.0 - e / picco)
    rr = [port[i]/port[i-1] - 1.0 for i in range(1, m) if port[i-1] > 0]
    sd = st.stdev(rr) if len(rr) > 10 else 0.0
    sharpe = (st.mean(rr)/sd*math.sqrt(365)) if sd > 0 else 0.0
    return port[-1] - 1.0, mdd, sharpe


def main():
    # validazione: senza filtro deve coincidere
    aa, _ = serie("mc2")
    n = min(len(c) for _, c in aa)
    aa2 = [(a, c[-n:]) for a, c in aa]
    r1 = cap.simula(aa2, 42.12, RISK, FEE, cap.SLIP, **BASE)
    r2 = sf.simula_filtrata(aa2, 42.12, RISK, FEE, sf.SLIP, filtro=None, **BASE)
    d = (r2["curva"][-1] - r1["curva"][-1]) / 42.12
    print("VALIDAZIONE filtro=None contro cap.simula: delta %+.2e  trade %d/%d  %s"
          % (d, r1["trade"], r2["trade"], "OK" if abs(d) < 1e-12 else "DIVERGE"))
    if abs(d) > 1e-12:
        return 1
    print()
    print("  %-10s %10s %8s %8s %9s %9s" %
          ("filtro", "storia", "maxDD", "Sharpe", "12 mesi", "6 mesi"))
    for tipo in ("nessuno", "ema50", "ema100", "ema200", "mom30", "mom60"):
        r, dd, sh = misura(tipo)
        r12, _, _ = misura(tipo, 365)
        r6, _, _ = misura(tipo, 180)
        print("  %-10s %+9.2f%% %7.2f%% %8.2f %+8.2f%% %+8.2f%%"
              % (tipo, r * 100, dd * 100, sh, r12 * 100, r6 * 100))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
