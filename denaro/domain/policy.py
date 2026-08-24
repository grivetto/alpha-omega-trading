#!/usr/bin/env python3
"""Denaro — domain policy base (puro Python, zero I/O).

Contratto comune di TUTTE le strategie di trading del Node:
- `decide(...)`: decisione pura per il tick corrente (nessuna I/O)
- `sell_target(entry)`: prezzo obiettivo di vendita per una posizione
- `on_price(price)`: opzionale, aggiorna lo storico interno della strategia

Le implementazioni concrete:
- `GridPolicy` (grid.py) — griglia statica idempotente
- `MomentumPolicy` (momentum.py) — segue il trend con conferma (EMA/ADX)
- `MeanReversionPolicy` (meanrev.py) — compra l'oversold, vende il ritorno

`GridDecision` e' il DTO condiviso: i campi non usati da una strategia restano
vuoti (lista vuota = nessuna azione).
"""
from __future__ import annotations

from typing import Dict, List, Optional

from .grid import GridDecision, GridLevel


class Policy:
    """Contratto base di una strategia (duck typing, nessuna classe astratta).

    Una strategia DEVE implementare `decide` e `sell_target`; `on_price` e'
    opzionale (usato dalle strategie con memoria storica).
    """

    def decide(self, price: float, open_buys: Dict[str, dict],
               open_sells: Dict[str, dict], cash: float,
               capital_config: float, free_balance: float,
               now: float) -> GridDecision:
        raise NotImplementedError

    def sell_target(self, entry_price: float) -> float:
        raise NotImplementedError

    def on_price(self, price: float) -> None:
        """Aggiorna lo storico interno (default: no-op)."""
        return None

    # --- helper condivisi -----------------------------------------------------

    @staticmethod
    def _available(free_balance: float, capital_config: float) -> float:
        return max(0.0, min(capital_config, free_balance))

    @staticmethod
    def _decision(to_cancel: Optional[List[str]] = None,
                  to_place: Optional[List[GridLevel]] = None,
                  reason: str = "") -> GridDecision:
        return GridDecision(to_cancel=list(to_cancel or []),
                            to_place=list(to_place or []),
                            reason=reason)
