#!/usr/bin/env python3
"""Quante posizioni sono aperte INSIEME? Serve per dimensionare il capitale.

Con 25 EUR per conto e cinque bot, se in media sono aperte 4-5 posizioni il
capitale non basta (il tetto di cassa libera riduce o scarta gli ordini). Se
sono 1-2, il tetto non morde.
"""
import collections, pathlib, statistics as st, sys
sys.path.insert(0, "/home/sergio/alpha-omega-trading")
from denaro.research import eval as E

DATA = pathlib.Path("/home/sergio/alpha-omega-trading/backtest_data")
CONTI = {
    "mc2": ["BTC", "ETH", "SOL", "XRP", "DOGE"],
    "nuvola": ["LINK", "AVAX", "DOT", "LTC", "UNI"],
    "MARCODG1": ["ADA", "ATOM", "AAVE", "ARB", "XLM"],
}
PAR = {"strategy": "trend", "canale": 40, "atr_period": 14, "trail_mult": 3.0,
       "stop_atr_mult": 2.0, "trend_ema": 100, "risk_pct": 0.02,
       "max_exposure": 1.0}

print("=== quante posizioni aperte CONTEMPORANEAMENTE ===")
print("  (daily, parametri di produzione, fee 0.20%/lato)")
print()
for conto, asset in CONTI.items():
    per_barra = collections.Counter()
    esposizioni = []
    for a in asset:
        f = DATA / ("dl_%s_1D.csv" % a)
        if not f.exists():
            print("  %s: %s dati assenti" % (conto, a)); continue
        c = E.load_csv(f)
        r = E.backtest_trend(c, PAR, capitale=100.0, fee=0.002)
        esposizioni.append(100.0 * r.esposizione_pct)
        for ts in r.ts_in_pos:
            per_barra[ts] += 1
    if not per_barra:
        continue
    conteggi = list(per_barra.values())
    tot = len(per_barra)
    dist = collections.Counter(conteggi)
    print("  %-9s esposizione media per asset: %.0f%%" % (conto, st.mean(esposizioni)))
    print("             barre con posizioni aperte: %d" % tot)
    print("             distribuzione: %s"
          % ", ".join("%d pos:%.0f%%" % (k, 100.0 * v / tot) for k, v in sorted(dist.items())))
    print("             MEDIA SIMULTANEA: %.2f   MASSIMA: %d"
          % (st.mean(conteggi), max(conteggi)))
    print()
print("=== interpretazione ===")
print("  media simultanea <= 2  -> il capitale attuale basta")
print("  media simultanea >= 3  -> servono meno bot per conto, o piu' capitale")
