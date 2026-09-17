#!/usr/bin/env python3
"""fetch_universe.py — scarica l'universo spot EUR da OKX EEA per la ricerca.

Perche' esiste, due ragioni concrete:

1. I dati in backtest_data/ erano spariti: senza di essi la misura chiave della
   ricerca (3/24 -> 20/24 configurazioni robuste cambiando solo la fee) NON e'
   riproducibile. Una decisione basata su un numero che non si puo' rigenerare
   non e' una decisione.

2. Per il cambio di strategia serve un universo molto piu' largo dei 19 asset
   usati finora. L'edge del trend e' EPISODICO (docs/18 18.2: tutto il rendimento
   in un blocco su cinque). La cura per un edge episodico sono PIU' scommesse
   indipendenti: con 19 asset e 5 posizioni per conto il campione e' la fortuna
   di un trimestre. Con 60-80 asset e' una media.

Scrive CSV con header ts,o,h,l,c,v — il formato che denaro/research/eval.py si
aspetta — con i nomi dl_<BASE>_1D.csv e uni_<BASE>_4H.csv.

Uso:
  python3 tools/fetch_universe.py --top 80 --timeframe 1D
  python3 tools/fetch_universe.py --top 80 --timeframe 4H

Solo lettura sugli exchange: nessun ordine, nessuna chiave richiesta.
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, "/home/sergio/alpha-omega-trading")
import ccxt  # noqa: E402

DATI = Path("/home/sergio/alpha-omega-trading/backtest_data")

# stablecoin e valute: non sono asset da trend
ESCLUSI = {"USDC", "USDT", "DAI", "TUSD", "PYUSD", "EURT", "EURC", "AUSD",
           "EURQ", "EURR", "USDE", "FDUSD", "USDG", "EUR"}


def mercato():
    ex = ccxt.okx({"enableRateLimit": True, "hostname": "eea.okx.com",
                   "options": {"defaultType": "spot"}})
    ex.load_markets()
    return ex


def universo(ex):
    out = []
    for m in ex.markets.values():
        if not m.get("spot") or not m.get("active"):
            continue
        if m.get("quote") != "EUR":
            continue
        base = m.get("base") or ""
        if base in ESCLUSI or not base.isalnum():
            continue
        out.append(m["symbol"])
    return out


def scarica(ex, sym, timeframe, massimo=2000):
    """Pagina all'indietro con 'after' e restituisce le barre in ordine crescente."""
    raccolte = {}
    cursor = None
    for _ in range(60):
        params = {"after": str(cursor)} if cursor is not None else {}
        try:
            batch = ex.fetch_ohlcv(sym, timeframe, limit=100, params=params)
        except Exception as exc:
            print("    %s: stop (%s)" % (sym, str(exc)[:70]), flush=True)
            break
        if not batch:
            break
        for c in batch:
            raccolte[int(c[0])] = c
        piu_vecchio = min(int(c[0]) for c in batch)
        if len(raccolte) >= massimo:
            break
        if cursor is not None and piu_vecchio >= cursor:
            break
        cursor = piu_vecchio
        time.sleep(max(0.05, ex.rateLimit / 1000.0))
    return [raccolte[k] for k in sorted(raccolte)]


def scrivi(path, candele):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["ts", "o", "h", "l", "c", "v"])
        for c in candele:
            w.writerow([int(c[0]), c[1], c[2], c[3], c[4], c[5]])
    tmp.replace(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=80)
    ap.add_argument("--timeframe", default="1D", choices=["1D", "4H"])
    ap.add_argument("--bars", type=int, default=2000)
    args = ap.parse_args()
    prefisso = "dl" if args.timeframe == "1D" else "uni"

    ex = mercato()
    syms = universo(ex)
    print("coppie XXX/EUR candidate: %d" % len(syms), flush=True)

    try:
        tks = ex.fetch_tickers(syms)
    except Exception:
        tks = {}

    def vol(s):
        t = tks.get(s) or {}
        return float(t.get("quoteVolume") or 0)

    syms = sorted(syms, key=vol, reverse=True)[:args.top]
    print("selezionate le %d piu' liquide" % len(syms), flush=True)

    ok = 0
    for i, sym in enumerate(syms, 1):
        base = sym.split("/")[0]
        path = DATI / ("%s_%s_%s.csv" % (prefisso, base, args.timeframe))
        if path.is_file():
            print("[%d/%d] %s gia' presente" % (i, len(syms), sym), flush=True)
            ok += 1
            continue
        cand = scarica(ex, sym, args.timeframe, args.bars)
        if len(cand) < 250:
            print("[%d/%d] %s: %d barre, salto" % (i, len(syms), sym, len(cand)), flush=True)
            continue
        scrivi(path, cand)
        ok += 1
        print("[%d/%d] %s: %d barre" % (i, len(syms), sym, len(cand)), flush=True)
    print("FATTO: %d file in %s" % (ok, DATI), flush=True)


if __name__ == "__main__":
    main()
