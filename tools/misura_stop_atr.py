#!/usr/bin/env python3
"""misura_stop_atr.py - distanza di stop REALE per dimensionare il capitale.

Perche' esiste: il dimensionamento "prepara il sistema per 1000 EUR" dipende da
quanto e' larga la distanza di stop, perche' la size della posizione e'
`rischio_eur / distanza_stop`. Con `risk_pct` al 2% e stop a 2 ATR, la size e'
tutta una conseguenza dell'ATR: senza misurarlo, ogni numero e' un'ipotesi.

Cosa misura: prende le candle locali in `backtest_data/`, le aggrega a
GIORNALIERO (la strategia opera su 1D) e calcola l'ATR di Wilder con la STESSA
funzione che usa la produzione (`denaro.domain.indicators.atr_wilder`), poi
`ATR% = ATR / close`.

Limite dichiarato, non nascosto: i dati locali sono a 5m e coprono ~90 giorni,
per 5 simboli. La strategia e' misurata su 1D e 2,5 anni su 19 asset. Questo e'
quindi un campione indicativo per la SCALA delle size, non una misura di
backtest. Per gli altri simboli servono le candle 1D da OKX.

Uso:
    python tools/misura_stop_atr.py
    python tools/misura_stop_atr.py --capitale 1000 --bot 17
"""
from __future__ import annotations

import argparse
import csv
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from denaro.domain.indicators import atr_wilder  # noqa: E402

GIORNO_MS = 86_400_000


def leggi_5m(path: Path) -> list[list[float]]:
    """Legge il CSV (ts,open,high,low,close,volume) e ritorna barre grezze."""
    barre: list[list[float]] = []
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                barre.append([float(row["ts"]), float(row["open"]),
                              float(row["high"]), float(row["low"]),
                              float(row["close"])])
            except (KeyError, TypeError, ValueError):
                continue
    barre.sort(key=lambda b: b[0])
    return barre


def aggrega_giorno(barre: list[list[float]]) -> list[list[float]]:
    """5m -> 1D bucketizzando su giorni UTC. Ritorna [ts, open, high, low, close]."""
    if not barre:
        return []
    giorni: dict[int, list[list[float]]] = {}
    for b in barre:
        giorni.setdefault(int(b[0] // GIORNO_MS), []).append(b)
    out = []
    for g in sorted(giorni):
        candele = giorni[g]
        out.append([g * GIORNO_MS,
                    candele[0][1],
                    max(c[2] for c in candele),
                    min(c[3] for c in candele),
                    candele[-1][4]])
    return out


def atr_pct_giornaliero(giornaliere: list[list[float]], periodo: int = 14) -> list[float]:
    """ATR% per ogni giorno con dati sufficienti (ATR / close)."""
    if len(giornaliere) <= periodo + 1:
        return []
    highs = [b[2] for b in giornaliere]
    lows = [b[3] for b in giornaliere]
    closes = [b[4] for b in giornaliere]
    atr = atr_wilder(highs, lows, closes, periodo)
    out = []
    for i, a in enumerate(atr):
        if a > 0 and closes[i] > 0:
            out.append(a / closes[i])
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--capitale", type=float, default=1000.0,
                    help="capitale totale del portafoglio (default 1000)")
    ap.add_argument("--bot", type=int, default=17, help="numero di bot (default 17)")
    ap.add_argument("--risk-pct", type=float, default=0.02, help="rischio per trade")
    ap.add_argument("--stop-atr", type=float, default=2.0, help="stop in multipli di ATR")
    ap.add_argument("--min-notional", type=float, default=1.0,
                    help="minimo nozionale per ordine dal config (default 1.0 EUR)")
    ap.add_argument("--data-dir", default=str(ROOT / "backtest_data"))
    args = ap.parse_args()

    ddir = Path(args.data_dir)
    files = sorted(ddir.glob("okx_*_5m.csv"))
    if not files:
        print(f"nessun okx_*_5m.csv in {ddir}", file=sys.stderr)
        return 1

    capitale_bot = args.capitale / args.bot
    rischio_eur = capitale_bot * args.risk_pct

    print(f"capitale {args.capitale:.2f} EUR su {args.bot} bot "
          f"-> {capitale_bot:.2f} EUR per bot")
    print(f"rischio per trade {args.risk_pct:.1%} di {capitale_bot:.2f} "
          f"= {rischio_eur:.2f} EUR")
    print(f"stop = {args.stop_atr} x ATR   |   min_notional = "
          f"{args.min_notional:.2f} EUR\n")

    print(f"{'simbolo':<12}{'giorni':>7}{'ATR% med':>10}{'ATR% p25':>10}"
          f"{'ATR% p75':>10}{'stop':>8}{'size EUR':>10}{'x minimo':>10}")
    print("-" * 77)

    righe = []
    for p in files:
        # nome: okx_SOL-EUR_5m.csv -> SOL/EUR
        parti = p.stem.split("_")
        simbolo = parti[1].replace("-", "/") if len(parti) > 1 else p.stem
        g = aggrega_giorno(leggi_5m(p))
        valori = atr_pct_giornaliero(g)
        if not valori:
            print(f"{simbolo:<12}{len(g):>7}{'dati insufficienti':>30}")
            continue
        med = statistics.median(valori)
        p25 = statistics.quantiles(valori, n=4)[0] if len(valori) > 3 else med
        p75 = statistics.quantiles(valori, n=4)[2] if len(valori) > 3 else med
        stop = args.stop_atr * med
        size = rischio_eur / stop if stop > 0 else 0.0
        righe.append({"simbolo": simbolo, "stop": stop, "size": size,
                      "atr_pct": med, "giorni": len(g)})
        print(f"{simbolo:<12}{len(g):>7}{med * 100:>9.2f}%{p25 * 100:>9.2f}%"
              f"{p75 * 100:>9.2f}%{stop * 100:>7.2f}%{size:>10.2f}"
              f"{size / args.min_notional:>9.1f}x")

    if not righe:
        return 1

    size_med = statistics.median(r["size"] for r in righe)
    stop_med = statistics.median(r["stop"] for r in righe)
    print("\n" + "-" * 77)
    print(f"distanza di stop mediana: {stop_med:.2%}   |   "
          f"size mediana: {size_med:.2f} EUR "
          f"({size_med / args.min_notional:.1f}x il minimo)")
    print(f"se TUTTI i {args.bot} bot fossero in posizione: "
          f"{args.bot * size_med:.0f} EUR impegnati "
          f"({args.bot * size_med / args.capitale:.0%} del capitale), "
          f"rischio aggregato {args.bot * rischio_eur:.2f} EUR "
          f"({args.bot * rischio_eur / args.capitale:.1%} del capitale)")
    print("\nlimite: campione locale a 5m (~90 giorni, "
          f"{len(righe)} simboli) aggregato a 1D; la strategia e' misurata su 1D "
          "e 2,5 anni su 19 asset. Serve per la SCALA delle size, non e' un backtest.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
