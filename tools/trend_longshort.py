#!/usr/bin/env python3
"""Quanto vale poter andare SHORT, e quanto valgono fee 7 volte piu' basse?

Il trend deployato e' LONG-ONLY: nel bear market sta in cash. OKX EEA espone i
derivati (482 swap) con fee maker 0.02% / taker 0.05%, contro lo spot 0.20%/0.35%.
Ma l'account e' acctLv 1 (solo spot): per andare short serve un upgrade.

Qui si misura cosa cambierebbe, PRIMA di chiedere qualsiasi cosa:
  1) long-only vs long/short, alle fee spot reali;
  2) long/short alle fee dei derivati;
  3) la stessa cosa su barre 4H, dove il costo era il motivo del rifiuto.

DISCIPLINA: il percorso long-only di questo motore deve riprodurre ESATTAMENTE
backtest_trend. Senza quella prova il confronto non vale nulla.

Uso: python3 tools/trend_longshort.py
"""
from __future__ import annotations
import math
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, "/home/sergio/alpha-omega-trading")
from denaro.research import eval as E  # noqa: E402

DATI = Path("/home/sergio/alpha-omega-trading/backtest_data")
UNIVERSO = ["AAVE", "ADA", "ALGO", "ARB", "ATOM", "AVAX", "BTC", "CRV", "DOGE",
            "DOT", "ETH", "LINK", "LTC", "SOL", "SUI", "TRX", "UNI", "XLM", "XRP"]
FEE_SPOT = 0.0035   # taker OKX spot, livello Lv1
FEE_SWAP = 0.0005   # taker OKX swap
BASE = dict(canale=40, atr_period=14, trail_mult=3.0, stop_atr_mult=2.0,
            trend_ema=100, max_exposure=1.0, entry_slip=0.0005,
            fee_buffer=0.01, risk_pct=0.02)


def trend_ls(candles, p, capitale=1.0, fee=0.0035, slippage_k=0.02,
             permetti_short=True):
    """Trend following long/short. Con permetti_short=False deve coincidere con
    backtest_trend (stessa disciplina: segnale sul close, ingresso all'open dopo)."""
    canale = int(p.get("canale", 40))
    atr_n = int(p.get("atr_period", 14))
    trail = float(p.get("trail_mult", 3.0))
    rischio = float(p.get("risk_pct", 0.02))
    ema_n = int(p.get("trend_ema", 100))
    esp_max = float(p.get("max_exposure", 1.0))
    stop_mult = float(p.get("stop_atr_mult", 2.0))
    slip_entry = float(p.get("entry_slip", 0.0005))

    closes = [c["c"] for c in candles]
    highs = [c["h"] for c in candles]
    lows = [c["l"] for c in candles]
    atr_l = E.atr_wilder(highs, lows, closes, atr_n)
    ema_l = E.ema(closes, ema_n) if ema_n else []
    inizio = max(canale, atr_n, ema_n) + 1

    r = E.Risultato(nome="trend_ls", capitale=capitale)
    cash = capitale
    qty = 0.0          # >0 long, <0 short (in valore assoluto per lato)
    lato = 0           # +1 long, -1 short, 0 flat
    basis = 0.0
    stop = 0.0
    pending = 0        # +1 / -1 segnale deciso ieri

    for i in range(inizio, len(candles)):
        c = candles[i]
        price, hi, lo = c["c"], c["h"], c["l"]
        vol_med = E._media_volumi(candles, i)

        # ingresso deciso ieri, eseguito all'open di oggi
        if pending and lato == 0:
            a = atr_l[i - 1]
            if a > 0 and c["o"] > 0:
                dist = stop_mult * a
                entry = c["o"] * (1.0 + slip_entry * pending)
                qty_esp = (cash * esp_max) / entry
                q = min((cash * rischio) / dist, qty_esp)
                notional = q * entry
                sl = E.slippage(notional, vol_med, slippage_k)
                costo = notional * (1.0 + fee + sl)
                if costo > cash and costo > 0:
                    q *= cash / costo
                    notional = q * entry
                    sl = E.slippage(notional, vol_med, slippage_k)
                    costo = notional * (1.0 + fee + sl)
                if q > 1e-12 and costo <= cash * (1.0 + 1e-9):
                    if pending > 0:
                        cash -= costo
                        basis = costo / q
                    else:
                        cash += notional * (1.0 - fee - sl)
                        basis = notional * (1.0 - fee - sl) / q
                    qty = q
                    lato = pending
                    stop = entry - dist if pending > 0 else entry + dist
            pending = 0

        # uscita
        if lato != 0:
            colpito = (lo <= stop) if lato > 0 else (hi >= stop)
            if colpito:
                notional = qty * stop
                sl = E.slippage(notional, vol_med, slippage_k)
                if lato > 0:
                    incasso = qty * stop * (1.0 - fee - sl)
                    cash += incasso
                    r.trade_pnls.append(incasso - qty * basis)
                else:
                    esborso = qty * stop * (1.0 + fee + sl)
                    cash -= esborso
                    r.trade_pnls.append(qty * basis - esborso)
                r.fee_pagate += notional * fee
                qty, lato, stop = 0.0, 0, 0.0
            else:
                a = atr_l[i]
                if a > 0:
                    if lato > 0:
                        ns = price - trail * a
                        if ns > stop:
                            stop = ns
                    else:
                        ns = price + trail * a
                        if ns < stop:
                            stop = ns

        # segnale sul close di oggi -> ingresso domani
        if lato == 0 and not pending and i >= canale:
            massimo = max(highs[i - canale:i])
            minimo = min(lows[i - canale:i])
            sopra = (not ema_l) or price > ema_l[i]
            sotto = (not ema_l) or price < ema_l[i]
            if price > massimo and sopra and atr_l[i] > 0:
                pending = 1
            elif permetti_short and price < minimo and sotto and atr_l[i] > 0:
                pending = -1

        # equity mark-to-market
        if lato > 0:
            eq = cash + qty * price
        elif lato < 0:
            eq = cash - qty * price
        else:
            eq = cash
        r.equity.append(eq)
        r.ts.append(c["ts"])
        if lato != 0:
            r.esposizione_bar += 1
            r.ts_in_pos.append(c["ts"])

    r.barre = len(r.equity)
    r.lordo = sum(r.trade_pnls) + r.fee_pagate
    return r


def carica(suffisso="1D", minimo=250):
    serie = {}
    for s in UNIVERSO:
        p = DATI / ("dl_%s_%s.csv" % (s, suffisso))
        if not p.is_file():
            continue
        try:
            c = E.load_csv(p)
        except Exception:
            continue
        if len(c) > minimo:
            serie[s] = c
    if not serie:
        return {}, 0
    n = min(len(c) for c in serie.values())
    return {s: c[-n:] for s, c in serie.items()}, n


def valida(serie):
    print("VALIDAZIONE: il percorso long-only deve coincidere con backtest_trend")
    ok = True
    for s in sorted(serie)[:6]:
        c = serie[s]
        a = trend_ls(c, BASE, 1.0, FEE_SPOT, 0.02, permetti_short=False)
        b = E.backtest_trend(c, BASE, 1.0, FEE_SPOT, 0.02)
        d = a.ritorno - b.ritorno
        if abs(d) > 1e-9:
            ok = False
        print("   %-6s long-only %+9.4f%%  backtest %+9.4f%%  delta %+.2e  trade %d/%d"
              % (s, a.ritorno * 100, b.ritorno * 100, d, a.trade, b.trade))
    print("   --> %s" % ("COINCIDONO" if ok else "DIVERGONO: confronto non credibile"))
    return ok


def misura(serie, fee, short, etichetta, **over):
    p = dict(BASE, **over)
    rend, esp, tr = [], [], 0
    for s, c in serie.items():
        r = trend_ls(c, p, 1.0, fee, 0.02, permetti_short=short)
        if not r.equity:
            continue
        rend.append(r.ritorno)
        esp.append(r.esposizione_pct)
        tr += r.trade
    if not rend:
        return None
    mediare = st.mean(rend)
    anni = len(next(iter(serie.values()))) / 365.0
    return {"rend": mediare, "med": st.median(rend), "esp": st.mean(esp),
            "trade": tr, "cagr": (1 + mediare) ** (1 / anni) - 1 if mediare > -1 else -1,
            "pos": sum(1 for x in rend if x > 0), "n": len(rend), "anni": anni}


def tabella(serie, titolo, fee_spot, **over):
    print()
    print("=" * 84)
    print(titolo)
    print("=" * 84)
    print("  %-34s %10s %9s %8s %8s %8s" %
          ("configurazione", "rend.medio", "CAGR", "espos%", "trades", "positivi"))
    for short, nome in ((False, "long-only"), (True, "LONG/SHORT")):
        for fee, fname in ((fee_spot, "fee spot 0.35%"), (FEE_SWAP, "fee swap 0.05%")):
            m = misura(serie, fee, short, nome, **over)
            if not m:
                continue
            print("  %-34s %9.2f%% %8.2f%% %7.1f%% %8d %6d/%d"
                  % ("%s, %s" % (nome, fname), m["rend"] * 100, m["cagr"] * 100,
                     m["esp"], m["trade"], m["pos"], m["n"]))


def main():
    serie, n = carica("1D")
    print("universo daily: %d simboli, %d barre (%.1f anni)" % (len(serie), n, n / 365.0))
    if not valida(serie):
        return 1
    tabella(serie, "A) BARRE GIORNALIERE", FEE_SPOT)

    serie4, n4 = carica("4H", minimo=500)
    if serie4:
        print()
        print("universo 4H: %d simboli, %d barre (%.1f anni)"
              % (len(serie4), n4, n4 / (6 * 365.0)))
        p4 = dict(BASE, canale=40, trend_ema=100)
        tabella(serie4, "B) BARRE 4H (il costo era il motivo del rifiuto)", FEE_SPOT, **{})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
