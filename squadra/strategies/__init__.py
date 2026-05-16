"""Squadra Denaro — Strategy Modules.

Ogni modulo e' una funzione pura che prende OHLCV + parametri e restituisce signal.
Le strategie NON toccano exchange, DB o stato dei bot.
"""
from .ares_strategy import ares_signal
from .hermes_strategy import hermes_signal
from .apollo_strategy import apollo_signal
from .artemis_strategy import artemis_signal

__all__ = ["ares_signal", "hermes_signal", "apollo_signal", "artemis_signal"]
