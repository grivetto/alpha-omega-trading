#!/usr/bin/env python3
"""Denaro — tassonomia condivisa degli errori di exchange.

Prima di questo modulo ogni adapter definiva le proprie classi
(`OKXPermanentError`, `KrakenPermanentError`) e il layer application doveva
conoscerle *entrambe*. L'orchestrator ne referenziava una senza importarla
(`NameError` a runtime sul ramo di cancel), quindi un cancel fallito per
ordine inesistente faceva crashare l'intero tick.

Qui la gerarchia comune:

    ExchangeError
    ├── PermanentExchangeError   → MAI ritentare (ordine invalido, saldo
    │                              insufficiente, ordine inesistente, ...)
    └── TransientExchangeError   → ritentato N volte, poi arreso

Le classi storiche restano come alias, cosi' import esistenti e test
continuano a funzionare.
"""
from __future__ import annotations


class ExchangeError(Exception):
    """Errore generico di un adapter di exchange."""


class PermanentExchangeError(ExchangeError):
    """Errore NON ritentabile: il retry non puo' cambiare l'esito.

    Esempi: InvalidOrder, InsufficientFunds, OrderNotFound, bad API key.
    """


class TransientExchangeError(ExchangeError):
    """Errore transitorio esaurito dopo i tentativi previsti.

    Esempi: rate limit, timeout di rete, 5xx, exchange in manutenzione.
    """


# Alias storici: il codice che cattura questi nomi continua a funzionare
# (sono la stessa classe, non due gerarchie parallele).
PermanentOrderError = PermanentExchangeError
TransientOrderError = TransientExchangeError
