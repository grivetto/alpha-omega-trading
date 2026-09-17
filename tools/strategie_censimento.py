#!/usr/bin/env python3
"""Censimento delle strategie: quali hanno alpha, quali no (round 31, 2026-09-17).

Il repo contiene 13 policy ma solo 5 hanno un motore di backtest in
denaro/research/eval.py. Il mandato e' "eliminare o riprogettare le strategie con
alpha negativo": per farlo servono numeri sulla STESSA finestra, sugli STESSI
asset, alla STESSA fee reale.

Metodo, senza tuning:
  - 17 asset della flotta in produzione, capitale 1.0 per asset (rendimento
    percentuale puro), fee taker reale 0.35%/lato per i motori a mercato;
  - backtest_pullback gira con i SUOI default (fee maker 0.20% + taker 0.35% per
    lo stop): e' il motivo per cui esiste;
  - 5 finestre: storia intera, 540, 365, 270, 180 barre.
Regola dichiarata: alpha positivo se il rendimento medio e' positivo in almeno
4 finestre su 5; negativo se positivo in al massimo 2.

Uso: python3 tools/strategie_censimento.py
"""
from __future__ import annotations

import importlib
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, "/home/sergio/alpha-omega-trading")
from denaro.research import eval as E  # noqa: E402

DATI = Path("/home/sergio/alpha-omega-trading/backtest_data")
FEE = 0.0035
FLOTTA = ["BTC", "ETH", "SOL", "XRP", "DOGE", "TRX", "CRV",
          "LINK", "AVAX", "DOT", "UNI", "SUI", "MINA",
          "ADA", "ARB", "XLM", "ALGO"]
FINESTRE = (("storia", 0), ("540b", 540), ("365b", 365), ("270b", 270),
            ("180b", 180))

# motore -> (funzione, kwargs extra)
MOTORI = (
    ("trend", "backtest_trend", {}),
    ("grid", "backtest_grid", {}),
    ("momentum", "backtest_momentum", {}),
    ("meanrev", "backtest_meanrev", {}),
    ("pullback", "backtest_pullback", {"usare_default_fee": True}),
)

# Policy presenti nel dominio: motore di ricerca associato (o None)
POLICY_SENZA_MOTORE = ("adaptive", "adaptive_vol_grid", "irmr", "vagr",
                       "mincapture_grid", "flowgate_grid", "cycle_phase_grid",
                       "asymvol_anchor", "circular")


def carica():
    serie = {}
    for s in FLOTTA:
        p = DATI / ("dl_%s_1D.csv" % s)
        if p.is_file():
            c = E.load_csv(p)
            if len(c) > 400:
                serie[s] = c
    n = min(len(c) for c in serie.values())
    return {s: c[-n:] for s, c in serie.items()}, n


def main():
    dati, n = carica()
    print("flotta %d asset, %d barre comuni, capitale 1.0 per asset, fee taker %.2f%%"
          % (len(dati), n, FEE * 100))
    print()
    print("  %-10s %-7s %10s %10s %6s %7s %8s" %
          ("motore", "finestra", "media", "mediana", "pos/17", "trades", "errore"))
    print("  " + "-" * 66)
    esito = {}
    for nome, fn_name, kw in MOTORI:
        fn = getattr(E, fn_name)
        esiti_fin = []
        for nome_fin, w in FINESTRE:
            rend, trade, err = [], 0, 0
            for s, c in dati.items():
                serie = c if w == 0 else c[-w:]
                try:
                    if kw.get("usare_default_fee"):
                        r = fn(serie, {}, 1.0)
                    else:
                        r = fn(serie, {}, 1.0, FEE)
                    if r.errore:
                        err += 1
                        continue
                    rend.append(r.ritorno)
                    trade += r.trade
                except Exception:
                    err += 1
            media = st.mean(rend) if rend else 0.0
            med = st.median(rend) if rend else 0.0
            pos = sum(1 for x in rend if x > 0)
            esiti_fin.append(media)
            print("  %-10s %-7s %9.2f%% %9.2f%% %5d/%d %7d %8d" %
                  (nome, nome_fin, media * 100, med * 100, pos, len(dati),
                   trade, err))
        esito[nome] = esiti_fin
        print()
    print("  DECISIONE (media positiva in >= 4 finestre su 5)")
    print("  " + "-" * 66)
    for nome, _, _ in MOTORI:
        pos = sum(1 for x in esito[nome] if x > 0)
        if pos >= 4:
            verdetto = "ALPHA POSITIVO - candidata al deploy"
        elif pos <= 2:
            verdetto = "ALPHA NEGATIVO - eliminare o riprogettare"
        else:
            verdetto = "MISTO - non deployabile senza una ragione nuova"
        print("  %-10s %d/5 finestre positive -> %s" % (nome, pos, verdetto))
    print()
    print("  POLICY SENZA MOTORE DI BACKTEST (nessun alpha misurabile):")
    for p in POLICY_SENZA_MOTORE:
        f = Path("/home/sergio/alpha-omega-trading/denaro/domain") / (p + ".py")
        print("    %-20s %s" % (p, "presente" if f.is_file() else "-"))
    print("  -> non sono deployabili: non esiste una misura che le giustifichi.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
