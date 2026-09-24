#!/usr/bin/env python3
"""Denaro — cap di esposizione A LIVELLO DI CONTO (docs/55, Q6).

Perche' esiste: il cap di esposizione del motore e' **per bot**
(`domain/trend.py:493`, `max_exposure`, default 1.0 = spento). Con piu' bot sullo
stesso sub-account — la configurazione che `docs/54` pianifica per i 1000 EUR —
**nessuno di loro vede la somma**. Il massimo teorico misurato e' 258 EUR su 1.000
(26%), ma e' un risultato, non un vincolo.

Questo registro e' l'unico posto dove la somma esiste. E' puro e deterministico:
non fa I/O, non conosce gli exchange, e si testa senza rete.

Contratto:
- il cap e' sul **totale nozionale impegnato**, non sul numero di bot;
- `cap <= 0` significa "nessun cap" (comportamento storico, invariato);
- il rilascio e' idempotente: rilasciare un bot che non ha nulla non e' un errore;
- la decisione e' conservativa: se il nuovo impegno porterebbe il totale OLTRE il
  cap, si rifiuta. Pari al cap e' ammesso.
"""
from __future__ import annotations

from typing import Dict


class AccountExposure:
    """Somma degli impegni dei bot che condividono un conto, con un tetto."""

    def __init__(self, cap_notional: float = 0.0) -> None:
        self.cap = max(0.0, float(cap_notional))
        self._impegnato: Dict[str, float] = {}

    # --- lettura ------------------------------------------------------------

    @property
    def capped(self) -> bool:
        """True se un cap e' configurato."""
        return self.cap > 0.0

    def total(self) -> float:
        return sum(self._impegnato.values())

    def headroom(self) -> float:
        """Quanto resta prima del cap. Senza cap, convenzionalmente infinito."""
        if not self.capped:
            return float("inf")
        return max(0.0, self.cap - self.total())

    def impegnato(self, bot_key: str) -> float:
        return float(self._impegnato.get(bot_key, 0.0))

    # --- decisione ----------------------------------------------------------

    def can_open(self, bot_key: str, notional: float) -> bool:
        """True se aggiungere `notional` per questo bot resta entro il cap.

        Il valore gia' impegnato DALLO STESSO bot viene sostituito, non sommato:
        un bot che apre di nuovo sta dimensionando la sua posizione, non
        raddoppiandola.
        """
        if not self.capped:
            return True
        n = float(notional)
        if n <= 0.0:
            return True
        altri = self.total() - self.impegnato(bot_key)
        return (altri + n) <= self.cap

    def commit(self, bot_key: str, notional: float) -> None:
        """Registra (o sostituisce) l'impegno di un bot."""
        self._impegnato[bot_key] = max(0.0, float(notional))

    def release(self, bot_key: str) -> None:
        """Il bot e' flat: il suo impegno esce dal totale. Idempotente."""
        self._impegnato.pop(bot_key, None)

    def snapshot(self) -> dict:
        """Vista per health/diagnostica."""
        return {
            "cap_notional": round(self.cap, 4),
            "impegnato_totale": round(self.total(), 4),
            "headroom": (None if not self.capped
                         else round(self.headroom(), 4)),
            "bot": {k: round(v, 4) for k, v in self._impegnato.items()},
        }
