#!/usr/bin/env python3
"""Denaro — domain mean-reversion policy (puro Python, zero I/O).

Strategia RANGE per il Node:
- segnale buy: RSI < oversold (ipervenduto) → il prezzo e' "caduto troppo"
- il buy si piazza al prezzo corrente con un piccolo sconto
- uscita: ritorno alla media → TP = entry × (1 + profit_target)
- al massimo UNA posizione; nessun buy se il mercato e' in trend forte
  (RSI estremo puo' essere momentum, non reversion → filtro distanza dalla media)

Nota di design: stesso limite OHLC della momentum policy — RSI + SMA sul prezzo.
"""
from __future__ import annotations

from collections import deque
from typing import Callable, Dict, List, Optional

from .grid import GridDecision, GridLevel
from .indicators import AdvancedIndicators
from .policy import Policy


class MeanReversionParams:
    def __init__(self, rsi_period: int = 14,
                 rsi_oversold: float = 30.0,
                 rsi_exit: float = 55.0,      # uscita anticipata se RSI torna sopra
                 history: int = 60,
                 profit_target: float = 0.015,
                 entry_slip: float = 0.001,
                 max_dev_from_mean: float = 0.05,  # max distanza dalla SMA (frazione)
                 min_history: int = 21) -> None:
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_exit = rsi_exit
        self.history = history
        self.profit_target = profit_target
        self.entry_slip = entry_slip
        self.max_dev_from_mean = max_dev_from_mean
        self.min_history = min_history


class MeanReversionPolicy(Policy):
    """Compra l'ipervenduto, vende il ritorno alla media."""

    def __init__(self, params: Optional[MeanReversionParams] = None,
                 round_price: Optional[Callable[[float], float]] = None,
                 round_amount: Optional[Callable[[float], float]] = None,
                 min_amount: float = 0.0) -> None:
        self.params = params or MeanReversionParams()
        self.round_price = round_price or (lambda p: round(p, 6))
        self.round_amount = round_amount or (lambda a: round(a, 8))
        self.min_amount = min_amount
        self.history: deque = deque(maxlen=self.params.history)

    def on_price(self, price: float) -> None:
        if price > 0:
            self.history.append(float(price))

    def _mean(self, prices: List[float]) -> float:
        return sum(prices) / len(prices) if prices else 0.0

    def sell_target(self, entry_price: float) -> float:
        return self.round_price(entry_price * (1 + self.params.profit_target))

    def decide(self, price: float, open_buys: Dict[str, dict],
               open_sells: Dict[str, dict], cash: float,
               capital_config: float, free_balance: float,
               now: float) -> GridDecision:
        decision = self._decision(reason="meanrev")
        if price <= 0:
            decision.reason = "prezzo non valido"
            return decision

        prices = list(self.history)
        if len(prices) < self.params.min_history:
            decision.reason = f"meanrev: storico insufficiente ({len(prices)})"
            return decision

        rsi = AdvancedIndicators.rsi(prices, self.params.rsi_period)
        mean = self._mean(prices)
        dev = (mean - price) / mean if mean > 0 else 0.0  # >0 se sotto la media

        # gia' una posizione → aspetta il fill (o uscita anticipata via TP)
        if open_buys:
            decision.reason = f"meanrev: posizione aperta ({len(open_buys)})"
            return decision

        # segnale: RSI oversold E prezzo sotto la media (dev > 0)
        if rsi.value >= self.params.rsi_oversold or dev <= 0:
            decision.reason = (f"meanrev: rsi {rsi.value:.0f} dev {dev * 100:.1f}% "
                               f"— nessun setup")
            return decision
        if dev > self.params.max_dev_from_mean:
            # caduta estrema: puo' essere trend, non reversion → skip
            decision.reason = f"meanrev: dev {dev * 100:.1f}% oltre soglia — skip"
            return decision

        available = self._available(free_balance, capital_config)
        if available <= 0:
            decision.reason = "meanrev: saldo insufficiente"
            return decision

        entry = self.round_price(price * (1 - self.params.entry_slip))
        amount = self.round_amount(available / entry)
        if amount <= 0 or (self.min_amount and amount < self.min_amount):
            decision.reason = f"meanrev: amount {amount} sotto minimo"
            return decision

        decision.to_place = [GridLevel(buy_price=entry, amount=amount, level=0)]
        decision.reason = (f"meanrev: rsi {rsi.value:.0f} oversold, "
                           f"dev {dev * 100:.1f}% sotto media, buy {amount} @ {entry}")
        return decision
