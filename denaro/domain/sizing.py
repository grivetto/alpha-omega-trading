#!/usr/bin/env python3
"""Denaro — sizing condiviso (puro Python, zero dipendenze).

UNICA implementazione della riserva fee/slippage del progetto.

Sta in un modulo SENZA import perche' la usano tutte le strategie, anche
quelle che non ereditano \`Policy\` (GridPolicy, StrategyBase, ...):
\`policy\` importa \`grid\`, quindi far importare \`policy\` da \`grid\`
creerebbe un ciclo. \`sizing\` non importa nulla: importarlo e' sempre sicuro.

Perche' esiste: il 2026-09-17 momentum (SOL/EUR) e meanrev (XRP/EUR) hanno
dimensionato l'ordine sull'INTERO saldo disponibile; l'exchange ha rifiutato
l'ordine per la fee (InsufficientFunds). La correzione era rimasta nel
working tree, non committata, ed e' andata persa a un ripristino del repo.
Ora e' codice versionato + test di regressione.
"""
from __future__ import annotations

# Riserva applicata a OGNI ordine dimensionato da un budget disponibile.
FEE_BUFFER: float = 0.01


def size_amount(budget, price, round_amount, fee_buffer=None) -> float:
    """Qty da un budget: budget x (1 - fee_buffer) / price.

    Non usa MAI il 100% del budget: la differenza copre fee e slippage, cosi'
    l'ordine non viene rifiutato quando il saldo e' esattamente il budget.
    """
    try:
        p = float(price)
    except (TypeError, ValueError):
        return 0.0
    if p <= 0.0:
        return 0.0
    buf = FEE_BUFFER if fee_buffer is None else float(fee_buffer)
    buf = min(max(buf, 0.0), 0.5)
    return round_amount(max(0.0, float(budget)) * (1.0 - buf) / p)
