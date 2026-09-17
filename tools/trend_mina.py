#!/usr/bin/env python3
"""MINA regge? Finestre scorrevoli, storia intera e collocazione fra i conti.

Un solo candidato su 19 migliora tutte le finestre recenti. Prima di aggiungerlo
a produzione: 10 finestre scorrevoli, la storia intera, e su QUALE conto conviene.

Uso: python3 tools/trend_mina.py
"""
from __future__ import annotations
import importlib.util
import statistics as st
import sys
from pathlib import Path

BASE_T = Path("/home/sergio/alpha-omega-trading/tools")
sp = importlib.util.spec_from_file_location("ag", str(BASE_T / "trend_aggiunta.py"))
ag = importlib.util.module_from_spec(sp)
sp.loader.exec_module(ag)

FIN = [900, 810, 720, 630, 540, 450, 365, 300, 270, 220, 180, 150]


def con_mina(conto):
    c = {k: list(v) for k, v in ag.ATTUALE.items()}
    c[conto] = c[conto] + ["MINA"]
    return c


def main():
    print("=== A) 12 finestre scorrevoli: base vs base+MINA (su nuvola) ===")
    print("  %-8s %10s %10s %8s" % ("barre", "BASE", "+MINA", "delta"))
    vinte = 0
    for b in FIN:
        rb = ag.misura(ag.ATTUALE, b)
        rm = ag.misura(con_mina("nuvola"), b)
        d = rm[0] - rb[0]
        if d > 0:
            vinte += 1
        print("  %-8d %+9.2f%% %+9.2f%% %+7.2fpp" % (b, rb[0] * 100, rm[0] * 100, d * 100))
    print("  --> MINA migliora in %d finestre su %d" % (vinte, len(FIN)))

    print()
    print("=== B) storia intera e drawdown/Sharpe ===")
    for nome, conti in (("BASE", ag.ATTUALE), ("+MINA", con_mina("nuvola"))):
        rb = ag.misura(conti, None)
        print("  %-8s rend %+7.2f%%  maxDD %6.2f%%  Sharpe %5.2f"
              % (nome, rb[0] * 100, rb[1] * 100, rb[2]))

    print()
    print("=== C) su quale conto conviene? ===")
    print("  %-10s %10s %10s %10s" % ("conto", "storia", "12m", "6m"))
    for conto in ("mc2", "nuvola", "MARCODG1"):
        r0 = ag.misura(con_mina(conto), None)[0]
        r12 = ag.misura(con_mina(conto), 365)[0]
        r6 = ag.misura(con_mina(conto), 180)[0]
        print("  %-10s %+9.2f%% %+9.2f%% %+9.2f%%" % (conto, r0 * 100, r12 * 100, r6 * 100))
    r0 = ag.misura(ag.ATTUALE, None)[0]
    r12 = ag.misura(ag.ATTUALE, 365)[0]
    r6 = ag.misura(ag.ATTUALE, 180)[0]
    print("  %-10s %+9.2f%% %+9.2f%% %+9.2f%%" % ("(BASE)", r0 * 100, r12 * 100, r6 * 100))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
