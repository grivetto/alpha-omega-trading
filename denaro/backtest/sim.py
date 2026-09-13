#!/usr/bin/env python3
"""Denaro — exchange simulato deterministico (puro Python, zero rete).

Modella il minimo indispensabile per valutare le policy REALI in modo onesto:

- **limit order**: un buy si riempie quando il prezzo scende al suo livello, un
  sell quando il prezzo sale al suo livello. Il fill avviene AL PREZZO LIMITE
  (nessun miglioramento di prezzo: conservativo).
- **path intrabar**: open→low→high→close se la barra chiude in rialzo,
  open→high→low→close altrimenti. Gli ordini attraversati si riempiono
  nell'ordine in cui il prezzo li incontra.
- **fee per lato** sul quote (default 0.1%): il costo e' addebitato al fill.
- **min_amount / min_notional / precisioni**: un ordine sotto soglia viene
  RIFIUTATO (`SimRejection`), come farebbe l'exchange reale.
- **locked vs free**: il quote impegnato nei buy aperti non e' disponibile per
  nuovi buy (e' esattamente il campo `free` di OKX/Kraken). Questo rende
  visibile il classico deadlock "capitale frammentato" del progetto.
- **mai saldi negativi**.

NON modella: latenza, partial fill, depth del book, funding, outage.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

_EPS = 1e-12


class SimRejection(Exception):
    """Ordine rifiutato dall'exchange simulato (minimi, fondi, amount nullo)."""


@dataclass
class SimOrder:
    id: str
    side: str
    price: float
    amount: float
    ts: float = 0.0
    status: str = "open"           # open | closed | canceled | rejected
    filled_price: float = 0.0
    filled_amount: float = 0.0
    fee_paid: float = 0.0
    kind: str = "grid"             # grid | tp | ladder | stop_loss
    reason: str = ""

    def to_ccxt(self, symbol: str = "") -> dict:
        return {
            "id": self.id, "symbol": symbol, "side": self.side, "price": self.price,
            "amount": self.amount, "status": self.status,
            "filled": self.filled_amount,
            "fee": {"cost": self.fee_paid},
            "datetime": None, "timestamp": int(self.ts * 1000) if self.ts else None,
        }


@dataclass
class SimFill:
    order_id: str
    side: str
    price: float
    amount: float
    fee: float
    ts: float
    kind: str = "grid"


class SimExchange:
    """Exchange simulato che espone la stessa superficie usata da BotTask."""

    def __init__(self, symbol: str, cash: float, asset: float = 0.0,
                 fee: float = 0.001, min_amount: float = 0.0,
                 min_notional: float = 0.0, amount_precision: float = 1e-8,
                 price_precision: float = 1e-8, slippage: float = 0.0005,
                 quote: Optional[str] = None, base: Optional[str] = None,
                 reject_on_violation: bool = True) -> None:
        self.symbol = symbol
        parts = symbol.split("/")
        self.base = base or parts[0]
        self.quote = quote or (parts[1] if len(parts) > 1 else "EUR")
        self.cash = float(cash)
        self.asset = float(asset)
        self.fee = float(fee)
        self.min_amount = float(min_amount)
        self.min_notional = float(min_notional)
        self.amount_precision = float(amount_precision or 1e-8)
        self.price_precision = float(price_precision or 1e-8)
        self.slippage = float(slippage)
        self.reject_on_violation = reject_on_violation

        self.price = 0.0
        self.orders: Dict[str, SimOrder] = {}
        self.fills: List[SimFill] = []
        self.fees_paid = 0.0
        self.rejections: List[str] = []
        self._seq = 0
        self._ts = 0.0
        # statistiche per-bot
        self.stats = {"placed": 0, "filled": 0, "canceled": 0, "rejected": 0,
                      "market_sells": 0}

    # --- utility ------------------------------------------------------------

    def _next_id(self) -> str:
        self._seq += 1
        return f"sim{self._seq}"

    def round_amount(self, amount: float) -> float:
        """Floor alla precisione dell'exchange (come engine v3.3 / adapters)."""
        prec = self.amount_precision
        if prec and prec < 1:
            return round(math.floor(amount / prec + _EPS) * prec, 12)
        return round(amount, 8)

    def round_price(self, price: float) -> float:
        prec = self.price_precision
        if prec and prec < 1:
            return round(math.floor(price / prec + _EPS) * prec, 12)
        return round(price, 6)

    # --- superficie ExchangePort -------------------------------------------

    def min_amount_for(self, symbol: str) -> float:
        return self.min_amount

    def min_notional_for(self, symbol: str) -> float:
        return self.min_notional

    # nome usato da BotTask._min_notional (attributo callable)
    def min_notional_fn(self, symbol: str) -> float:  # pragma: no cover - alias
        return self.min_notional

    def _locked_quote(self) -> float:
        return sum(o.amount * o.price for o in self.orders.values()
                   if o.status == "open" and o.side == "buy")

    def _locked_base(self) -> float:
        return sum(o.amount for o in self.orders.values()
                   if o.status == "open" and o.side == "sell")

    def free_quote(self) -> float:
        return max(0.0, self.cash - self._locked_quote())

    def free_base(self) -> float:
        return max(0.0, self.asset - self._locked_base())

    def fetch_balance(self) -> dict:
        locked_q = self._locked_quote()
        locked_b = self._locked_base()
        return {
            "free": {self.quote: self.cash - locked_q, self.base: self.asset - locked_b},
            "used": {self.quote: locked_q, self.base: locked_b},
            "total": {self.quote: self.cash, self.base: self.asset},
            self.quote: {"free": self.cash - locked_q, "used": locked_q,
                         "total": self.cash},
            self.base: {"free": self.asset - locked_b, "used": locked_b,
                        "total": self.asset},
        }

    def fetch_open_orders(self, symbol: str) -> List[dict]:
        return [o.to_ccxt(symbol) for o in self.orders.values() if o.status == "open"]

    def fetch_order(self, order_id: str, symbol: str) -> dict:
        o = self.orders.get(order_id)
        if o is None:
            raise SimRejection(f"ordine sconosciuto {order_id}")
        return o.to_ccxt(symbol)

    def fetch_ticker(self, symbol: str) -> dict:
        return {"last": self.price, "bid": self.price * (1 - self.slippage),
                "ask": self.price * (1 + self.slippage)}

    def equity(self, price: Optional[float] = None) -> float:
        p = self.price if price is None else price
        return self.cash + self.asset * p

    def fetch_total_equity(self) -> float:
        return self.equity()

    # --- creazione / cancellazione ordini ----------------------------------

    def create_limit_order(self, symbol: str, side: str, amount: float,
                           price: float, kind: str = "grid") -> dict:
        # l'exchange reale applica il proprio tick size (ccxt amount_to_precision):
        # qui si arrotonda PER DIFETTO come farebbe la coppia exchange/ccxt
        amount = self.round_amount(float(amount))
        price = self.round_price(float(price))
        if amount <= 0 or price <= 0:
            raise SimRejection(f"amount/price non validi ({amount} @ {price})")
        if self.min_amount and amount < self.min_amount * (1 - 1e-9):
            raise SimRejection(f"amount {amount} < min {self.min_amount}")
        notional = amount * price
        if self.min_notional and notional < self.min_notional * (1 - 1e-9):
            raise SimRejection(f"notional {notional:.4f} < min {self.min_notional}")
        if side == "buy":
            need = notional * (1 + self.fee)
            if need > self.free_quote() + 1e-9:
                raise SimRejection(
                    f"fondi insufficienti: serve {need:.4f}, free {self.free_quote():.4f}")
        else:
            if amount > self.free_base() + 1e-9:
                raise SimRejection(
                    f"asset insufficiente: serve {amount}, free {self.free_base()}")
        o = SimOrder(id=self._next_id(), side=side, price=price, amount=amount,
                     ts=self._ts, kind=kind)
        self.orders[o.id] = o
        self.stats["placed"] += 1
        return o.to_ccxt(symbol)

    def cancel_order(self, order_id: str, symbol: str) -> dict:
        o = self.orders.get(order_id)
        if o is None:
            raise SimRejection(f"ordine sconosciuto {order_id}")
        if o.status == "open":
            o.status = "canceled"
            self.stats["canceled"] += 1
        return o.to_ccxt(symbol)

    def cancel_all(self, symbol: str) -> int:
        n = 0
        for o in self.orders.values():
            if o.status == "open":
                o.status = "canceled"
                self.stats["canceled"] += 1
                n += 1
        return n

    def sell_market(self, symbol: str, amount: float) -> dict:
        """Market sell con slippage: usato dallo stop-loss."""
        amount = float(amount)
        if amount <= 0:
            raise SimRejection("market sell con amount 0")
        if amount > self.asset + 1e-9:
            amount = self.asset
        price = self.price * (1 - self.slippage)
        o = SimOrder(id=self._next_id(), side="sell", price=price, amount=amount,
                     ts=self._ts, kind="stop_loss")
        self.orders[o.id] = o
        self._fill(o, price)
        self.stats["market_sells"] += 1
        return o.to_ccxt(symbol)

    # --- motore di fill -----------------------------------------------------

    def _fill(self, o: SimOrder, price: float) -> Optional[SimFill]:
        if o.status != "open":
            return None
        amount = o.amount
        if o.side == "buy":
            cost = amount * price
            fee = cost * self.fee
            if cost + fee > self.cash + 1e-9:
                return None
            self.cash -= (cost + fee)
            self.asset += amount
        else:
            if amount > self.asset + 1e-9:
                return None
            proceeds = amount * price
            fee = proceeds * self.fee
            self.cash += (proceeds - fee)
            self.asset -= amount
        o.status = "closed"
        o.filled_price = price
        o.filled_amount = amount
        o.fee_paid = fee
        self.fees_paid += fee
        self.stats["filled"] += 1
        fill = SimFill(order_id=o.id, side=o.side, price=price, amount=amount,
                       fee=fee, ts=self._ts, kind=o.kind)
        self.fills.append(fill)
        return fill

    def advance_bar(self, bar: Sequence[float], ts: float = 0.0) -> List[SimFill]:
        """Fa scorrere una barra OHLC e riempie gli ordini attraversati.

        Ritorna i fill NELL'ORDINE in cui il prezzo li ha incontrati.
        Gli ordini creati DOPO questa chiamata non possono riempirsi nella
        stessa barra (evita round-trip intrabar gratuiti).
        """
        self._ts = float(ts or bar[0] / 1000.0)
        o, h, l, c = float(bar[1]), float(bar[2]), float(bar[3]), float(bar[4])
        path = [o, l, h, c] if c >= o else [o, h, l, c]
        out: List[SimFill] = []
        cur = path[0]
        for nxt in path[1:]:
            if nxt < cur:
                cands = sorted(
                    (x for x in self.orders.values()
                     if x.status == "open" and x.side == "buy"
                     and nxt - 1e-12 <= x.price <= cur + 1e-12),
                    key=lambda x: -x.price)
                for x in cands:
                    f = self._fill(x, x.price)
                    if f:
                        out.append(f)
            elif nxt > cur:
                cands = sorted(
                    (x for x in self.orders.values()
                     if x.status == "open" and x.side == "sell"
                     and cur - 1e-12 <= x.price <= nxt + 1e-12),
                    key=lambda x: x.price)
                for x in cands:
                    f = self._fill(x, x.price)
                    if f:
                        out.append(f)
            else:  # segmento piatto: tocca il prezzo, fill a parita' di livello
                for x in sorted(self.orders.values(), key=lambda z: z.side):
                    if x.status == "open" and abs(x.price - cur) <= 1e-12:
                        f = self._fill(x, x.price)
                        if f:
                            out.append(f)
            cur = nxt
        self.price = c
        return out
