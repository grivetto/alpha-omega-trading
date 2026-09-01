#!/usr/bin/env python3
"""Denaro — domain momentum policy (puro Python, zero I/O).

Strategia TREND-FOLLOWING per il Node:
- segnale bullish: EMA fast > EMA slow E RSI non overbought (filtro conferma)
- segnale bearish/neutro: cancella i buy non fillati (niente posizioni contro trend)
- al massimo UNA posizione aperta alla volta (levels non si applica)
- uscita: TP fisso (sell_target) oppure stop-loss del BotTask

Nota di design: il ticker `last` non fornisce OHLC → niente ADX/ATR da candle.
Il segnale usa EMA su prezzi last + RSI su serie storica (AdvancedIndicators).
"""
from __future__ import annotations

from collections import deque
from typing import Callable, Dict, List, Optional

from .grid import GridDecision, GridLevel
from .indicators import AdvancedIndicators
from .policy import Policy


class MomentumParams:
    def __init__(self, fast_period: int = 8, slow_period: int = 21,
                 history: int = 60, profit_target: float = 0.02,
                 entry_slip: float = 0.002,
                 rsi_confirm: float = 50.0,
                 min_history: int = 21) -> None:
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.history = history
        self.profit_target = profit_target
        self.entry_slip = entry_slip          # sconto entry vs mercato (limit)
        self.rsi_confirm = rsi_confirm        # RSI minimo per confermare il trend
        self.min_history = min_history        # prezzi minimi per un segnale valido


def _ema(values: List[float], period: int) -> float:
    if not values:
        return 0.0
    multiplier = 2 / (period + 1)
    ema = values[0]
    for v in values[1:]:
        ema = (v - ema) * multiplier + ema
    return ema


class MomentumPolicy(Policy):
    """Trend-following: compra il trend confermato, mai contro trend."""

    def __init__(self, params: Optional[MomentumParams] = None,
                 round_price: Optional[Callable[[float], float]] = None,
                 round_amount: Optional[Callable[[float], float]] = None,
                 min_amount: float = 0.0) -> None:
        self.params = params or MomentumParams()
        self.round_price = round_price or (lambda p: round(p, 6))
        self.round_amount = round_amount or (lambda a: round(a, 8))
        self.min_amount = min_amount
        self.history: deque = deque(maxlen=self.params.history)

    # --- memoria --------------------------------------------------------------

    def on_price(self, price: float) -> None:
        if price > 0:
            self.history.append(float(price))

    def _signal(self) -> str:
        """bullish | bearish | neutral (richiede min_history prezzi)."""
        prices = list(self.history)
        if len(prices) < self.params.min_history:
            return "neutral"
        fast = _ema(prices, self.params.fast_period)
        slow = _ema(prices, self.params.slow_period)
        rsi = AdvancedIndicators.rsi(prices, 14)
        # bullish: EMA fast > slow E RSI > 50 (momentum confermato, non solo
        # incrocio; RSI > 70 resta valido: il trend forte non viene escluso)
        if fast > slow and rsi.value > 50.0:
            return "bullish"
        if fast < slow:
            return "bearish"
        return "neutral"

    # --- contratto Policy -----------------------------------------------------

    def sell_target(self, entry_price: float) -> float:
        return self.round_price(entry_price * (1 + self.params.profit_target))

    def decide(self, price: float, open_buys: Dict[str, dict],
               open_sells: Dict[str, dict], cash: float,
               capital_config: float, free_balance: float,
               now: float) -> GridDecision:
        decision = self._decision(reason="momentum")
        if price <= 0:
            decision.reason = "prezzo non valido"
            return decision

        signal = self._signal()
        if signal == "neutral":
            decision.reason = f"momentum: segnale neutro ({len(self.history)} prezzi)"
            return decision

        # bearish → cancella i buy non fillati (mai contro trend)
        if signal == "bearish":
            decision.to_cancel = list(open_buys.keys())
            decision.reason = "momentum: bearish, cancello i buy"
            return decision

        # bullish → una sola posizione; se c'e' gia' un buy, aspetta il fill
        if open_buys:
            decision.reason = f"momentum: bullish, gia' {len(open_buys)} buy aperti"
            return decision

        available = self._available(free_balance, capital_config)
        if available <= 0:
            decision.reason = "momentum: saldo insufficiente"
            return decision

        entry = self.round_price(price * (1 - self.params.entry_slip))
        if entry <= 0:
            decision.reason = "momentum: entry non valida"
            return decision
        amount = self.round_amount(available / entry)
        if amount <= 0 or (self.min_amount and amount < self.min_amount):
            decision.reason = f"momentum: amount {amount} sotto minimo"
            return decision

        decision.to_place = [GridLevel(buy_price=entry, amount=amount, level=0)]
        decision.reason = (f"momentum: bullish (ema fast>slow, rsi "
                           f"{AdvancedIndicators.rsi(list(self.history), 14).value:.0f}), "
                           f"buy {amount} @ {entry}")
        return decision
