#!/usr/bin/env python3
"""Denaro — domain trend policy (puro Python, zero I/O).

Trend following GIORNALIERO: breakout del massimo delle ultime N barre, trailing
stop a k*ATR, posizione dimensionata sul RISCHIO.

E' la versione di produzione di denaro/research/eval.py:backtest_trend, con gli
stessi parametri e la STESSA implementazione di ATR (importata da
denaro/domain/indicators.py): l'equivalenza backtest/live e' verificata dai test,
non sperata.

Perche' esiste (misurato il 2026-09-17): su barre 4H il trend ha un segnale
reale (alpha +34.98% con t=+4.51 a fee zero) ma paga 0.70% di round trip a ogni
passaggio, e il costo lo azzera. Su barre GIORNALIERE ogni trade cattura
movimenti molto piu' grandi del costo — circa 10 trade per asset in 2.5 anni
invece di centinaia. Con parametri FISSI, su 19 asset, l'alpha e' positivo in
36 set su 36 (mediano +19.99%, t mediano +2.24) e sopravvive alla fee taker.

Costruisce da sola le barre giornaliere dai tick, quindi il dominio resta puro
(zero I/O) e non serve un feed OHLCV: le barre si costruiscono in decide(), dove
il timestamp e' disponibile.
"""
from __future__ import annotations

from collections import deque
from typing import Callable, Dict, Optional

from .grid import GridDecision, GridLevel
from .indicators import atr_wilder, ema_series
from .policy import Policy
from .sizing import FEE_BUFFER

GIORNO_S = 86_400.0


class TrendParams:
    """Parametri del trend giornaliero. Default = set fisso misurato buono."""

    __slots__ = ("canale", "atr_period", "trail_mult", "stop_atr_mult",
                 "trend_ema", "risk_pct", "max_exposure", "entry_slip",
                 "fee_buffer", "max_barre")

    def __init__(self, canale: int = 40, atr_period: int = 14,
                 trail_mult: float = 3.0, stop_atr_mult: float = 2.0,
                 trend_ema: int = 100, risk_pct: float = 0.02,
                 max_exposure: float = 1.0, entry_slip: float = 0.0005,
                 fee_buffer: float = FEE_BUFFER,
                 max_barre: int = 400) -> None:
        self.canale = canale
        self.atr_period = atr_period
        self.trail_mult = trail_mult
        self.stop_atr_mult = stop_atr_mult
        self.trend_ema = trend_ema
        self.risk_pct = risk_pct
        self.max_exposure = max_exposure
        self.entry_slip = entry_slip
        self.fee_buffer = fee_buffer
        self.max_barre = max_barre


class TrendPolicy(Policy):
    """Breakout + trailing stop ATR + size sul rischio, su barre giornaliere."""

    FEE_BUFFER = FEE_BUFFER

    def __init__(self, params: Optional[TrendParams] = None,
                 round_price: Optional[Callable[[float], float]] = None,
                 round_amount: Optional[Callable[[float], float]] = None,
                 min_amount: float = 0.0) -> None:
        self.params = params or TrendParams()
        self.round_price = round_price or (lambda p: round(p, 8))
        self.round_amount = round_amount or (lambda a: round(a, 8))
        self.min_amount = min_amount
        self.barre: deque = deque(maxlen=self.params.max_barre)
        self._giorno = None
        self._ap = self._ma = self._mi = self._ch = 0.0
        self.atr = 0.0
        self.ema = 0.0
        self.donchian = 0.0
        self.in_posizione = False
        self.entrata = 0.0
        self.stop = 0.0

    # --- costruzione delle barre giornaliere dai tick -------------------------

    def _aggiorna(self, price: float, now: float) -> bool:
        """Accumula il tick nella barra del giorno corrente.

        Ritorna True quando una barra e' stata APPENA CHIUSA, cioe' quando il
        giorno e' cambiato: e' l'unico momento in cui si valuta il segnale, cosi'
        la strategia resta giornaliera anche con tick ogni 30 secondi.
        """
        if price <= 0 or now is None:
            return False
        giorno = int(now // GIORNO_S)
        if self._giorno is None:
            self._giorno = giorno
            self._ap = self._ma = self._mi = self._ch = price
            return False
        if giorno == self._giorno:
            if price > self._ma:
                self._ma = price
            if price < self._mi or self._mi <= 0:
                self._mi = price
            self._ch = price
            return False
        self.barre.append({"ts": self._giorno * GIORNO_S, "o": self._ap,
                           "h": self._ma, "l": self._mi, "c": self._ch})
        self._giorno = giorno
        self._ap = self._ma = self._mi = self._ch = price
        return True

    def _aggiorna_indicatori(self) -> None:
        """Ricalcola ATR, media lunga e canale dalle barre CHIUSE."""
        barre = list(self.barre)
        if len(barre) > self.params.atr_period:
            highs = [b["h"] for b in barre]
            lows = [b["l"] for b in barre]
            closes = [b["c"] for b in barre]
            self.atr = atr_wilder(highs, lows, closes, self.params.atr_period)[-1]
        else:
            self.atr = 0.0
        if self.params.trend_ema and len(barre) >= 2:
            serie = ema_series([b["c"] for b in barre], self.params.trend_ema)
            self.ema = serie[-1] if serie else 0.0
        else:
            self.ema = 0.0
        n = self.params.canale
        if len(barre) > n:
            # massimo degli high delle n barre PRIMA dell'ultima chiusa
            self.donchian = max(b["h"] for b in barre[-(n + 1):-1])
        else:
            self.donchian = 0.0

    # --- segnale -------------------------------------------------------------

    def segnale_breakout(self) -> bool:
        """Rispecchia la condizione di backtest_trend: chiusura sopra il canale
        e, se richiesto, sopra la media lunga."""
        barre = list(self.barre)
        if len(barre) <= self.params.canale or self.atr <= 0:
            return False
        chiusura = barre[-1]["c"]
        if chiusura <= self.donchian:
            return False
        if self.params.trend_ema and self.ema > 0 and chiusura <= self.ema:
            return False
        return True

    def trailing_stop(self, price: float) -> float:
        """Nuovo stop = max(stop attuale, prezzo - trail*ATR). Sale e non scende."""
        if self.atr <= 0:
            return self.stop
        nuovo = price - self.params.trail_mult * self.atr
        return max(self.stop, nuovo)

    # --- contratto Policy ----------------------------------------------------

    def on_price(self, price: float) -> None:
        """No-op: le barre si costruiscono in decide(), dove c'e' il timestamp.

        L'orchestratore chiama on_price(price) e subito dopo decide(..., now):
        accumulare qui senza timestamp significherebbe contare due volte lo
        stesso prezzo.
        """
        return None

    def on_fill(self, order_id: str, side: str, price: float, size: float) -> None:
        """Traccia la posizione: il trailing stop esiste solo mentre si e' long."""
        if side == "buy":
            self.in_posizione = True
            self.entrata = float(price)
            dist = self.params.stop_atr_mult * self.atr
            self.stop = self.entrata - dist if dist > 0 else self.entrata * 0.9
        elif side == "sell":
            self.in_posizione = False
            self.entrata = 0.0
            self.stop = 0.0

    def sell_target(self, entry_price: float) -> float:
        """Stop iniziale, piazzato dall'orchestratore subito dopo il fill del buy.

        Non e' un target di profitto: e' la protezione iniziale. Il trailing la
        alza nel tempo tramite to_cancel_sell + to_sell.
        """
        dist = self.params.stop_atr_mult * self.atr
        if dist <= 0:
            return self.round_price(entry_price * 0.9)
        return self.round_price(entry_price - dist)

    def decide(self, price: float, open_buys: Dict[str, dict],
               open_sells: Dict[str, dict], cash: float,
               capital_config: float, free_balance: float,
               now: float, free_asset: float = 0.0) -> GridDecision:
        d = self._decision(reason="trend")
        if price <= 0:
            d.reason = "trend: prezzo non valido"
            return d

        nuovo_giorno = self._aggiorna(price, now)
        if nuovo_giorno:
            self._aggiorna_indicatori()

        # --- in posizione: alza il trailing stop e riposiziona la vendita ---
        if self.in_posizione or open_sells:
            if self.atr > 0:
                self.stop = self.trailing_stop(price)
            if open_sells:
                oid, info = next(iter(open_sells.items()))
                attuale = float(info.get("target_price") or info.get("price") or 0.0)
                amount = float(info.get("amount", 0.0))
                if (self.stop > 0 and attuale > 0 and amount > 0
                        and abs(self.stop - attuale) / attuale > 0.002):
                    d.to_cancel_sell = [oid]
                    d.to_sell = [(amount, self.round_price(self.stop))]
                    d.reason = ("trend: trailing stop %.6f (era %.6f)"
                                % (self.stop, attuale))
                else:
                    d.reason = "trend: stop %.6f invariato" % self.stop
            else:
                d.reason = "trend: in posizione senza vendita a mercato"
            return d

        # --- flat: valuta il breakout SOLO alla chiusura di una barra ---
        if not nuovo_giorno:
            d.reason = "trend: attesa chiusura giornaliera (atr %.4f)" % self.atr
            return d
        if not self.segnale_breakout():
            d.reason = ("trend: nessun breakout (chiusura %.6f, canale %.6f, "
                        "ema %.6f)" % (list(self.barre)[-1]["c"], self.donchian, self.ema))
            return d
        if open_buys:
            d.reason = "trend: buy gia' in attesa"
            return d

        entry = self.round_price(price * (1.0 + self.params.entry_slip))
        budget = self._available(free_balance, capital_config)
        if budget <= 0 or entry <= 0:
            d.reason = "trend: budget non disponibile"
            return d
        dist = self.params.stop_atr_mult * self.atr
        qty = (budget * self.params.risk_pct) / dist if dist > 0 else 0.0
        qty = min(qty, (budget * self.params.max_exposure) / entry)
        amount = self.round_amount(qty * (1.0 - self.params.fee_buffer))
        if amount <= 0 or (self.min_amount and amount < self.min_amount):
            d.reason = "trend: amount %s sotto il minimo" % amount
            return d
        d.to_place = [GridLevel(buy_price=entry, amount=amount, level=0)]
        d.reason = ("trend: breakout (chiusura %.6f > canale %.6f, atr %.6f) "
                    "buy %s @ %s" % (list(self.barre)[-1]["c"], self.donchian,
                                     self.atr, amount, entry))
        return d
