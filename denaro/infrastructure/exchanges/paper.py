#!/usr/bin/env python3
"""Denaro — PaperExchange (simulatore di mercato per il Node).

Implementa il contratto `ExchangePort` con la SEMANTICA del motore paper v1
(`engine_paper.py`, già validata sui 500€ virtuali):
- fee per lato (frazione): cost = amount×price×(1+fee) sul buy,
  proceeds = amount×price×(1-fee) sul sell
- fill quando il prezzo tocca il livello (buy: price <= level; sell: price >= target)
- `update_price(price)` simula il movimento del mercato e riempie gli ordini

REALISMO v2 (parita' col live):
- fee configurabile per bot (non piu' 0.001 fisso)
- min_notional: il paper rifiuta ordini sotto il minimo (come il live)
- slippage: i market order (stop-loss) eseguiti con slippage (come il live)
- precision: amount/price arrotondati ai tick del mercato
- MTM: equity = cash + asset×price (mark-to-market)

Nessuna rete: il prezzo arriva dal MarketDataHub (reale) o da un fake nei test.
"""
from __future__ import annotations

import logging
import uuid
from typing import Dict, List, Optional

log = logging.getLogger("denaro.paper")


class PaperExchange:
    """Exchange in-memory con fill simulati (compatibile con ExchangePort)."""

    FEE = 0.001
    DEFAULT_MIN_NOTIONAL = 1.0   # ~minimo reale OKX/Kraken spot (EUR notional)
    DEFAULT_SLIPPAGE = 0.001     # 0.1% slippage sui market order (stop-loss)

    def __init__(self, symbol: str, capital: float, quote: str = "EUR",
                 fee: float = FEE, min_notional: Optional[float] = None,
                 slippage: Optional[float] = None,
                 amount_precision: float = 1e-8,
                 price_precision: float = 1e-6) -> None:
        self.symbol = symbol
        self.quote = quote
        self.fee = fee
        self._min_notional_val = (float(min_notional) if min_notional is not None
                                  else self.DEFAULT_MIN_NOTIONAL)
        self.slippage = (float(slippage) if slippage is not None
                         else self.DEFAULT_SLIPPAGE)
        self.amount_precision = amount_precision
        self.price_precision = price_precision
        self.cash = float(capital)
        self.asset = 0.0
        self.price = 0.0
        self.orders: Dict[str, dict] = {}
        self.fill_events: List[dict] = []   # storia dei fill (per i test/parita')

    # --- ricostruzione dal journal (ripristino dopo restart) -----------------

    def rebuild(self, records: List[dict], capital: float) -> None:
        """Ricostruisce cash/asset dal journal immutabile (M5/D5).

        Semantica 1:1 del runtime: ogni buy_filled scala il cash del costo
        (amount×entry×(1+fee)) e aggiunge asset; ogni sell_filled incassa
        proceeds (amount×exit×(1-fee)) e scala l'asset. Senza questo, dopo
        un restart il cash NON scala i buy → capitale libero gonfiato
        (free_quote > capitale reale, PnL fittizio).
        """
        self.cash = float(capital)
        self.asset = 0.0
        for r in records:
            if r.get("symbol") != self.symbol:
                continue
            ev = r.get("event")
            if ev == "buy_filled":
                amt = float(r.get("amount", 0.0))
                entry = float(r.get("entry", 0.0))
                self.asset += amt
                self.cash -= amt * entry * (1 + self.fee)
            elif ev == "sell_filled":
                amt = float(r.get("amount", 0.0))
                exit_px = float(r.get("exit", r.get("price", 0.0)))
                self.asset -= amt
                self.cash += amt * exit_px * (1 - self.fee)

    # --- precision -----------------------------------------------------------

    def _round_amount(self, a: float) -> float:
        if self.amount_precision and self.amount_precision < 1:
            return round(a // self.amount_precision * self.amount_precision, 10)
        return round(a, 8)

    def _round_price(self, p: float) -> float:
        if self.price_precision and self.price_precision < 1:
            return round(p // self.price_precision * self.price_precision, 10)
        return round(p, 6)

    # --- market --------------------------------------------------------------

    def update_price(self, price: float) -> None:
        """Aggiorna il prezzo e riempie gli ordini incrociati (fill simulati)."""
        if price <= 0:
            return
        self.price = float(price)
        for o in list(self.orders.values()):
            if o["status"] != "open":
                continue
            if o["side"] == "buy" and price <= o["price"]:
                o["status"] = "filled"
                cost = o["amount"] * o["price"] * (1 + self.fee)
                self.cash -= cost
                self.asset += o["amount"]
                self.fill_events.append(
                    {"side": "buy", "amount": o["amount"], "price": o["price"],
                     "cost": cost, "id": o["id"]})
            elif o["side"] == "sell" and price >= o["price"]:
                o["status"] = "filled"
                proceeds = o["amount"] * o["price"] * (1 - self.fee)
                self.cash += proceeds
                self.asset -= o["amount"]
                self.fill_events.append(
                    {"side": "sell", "amount": o["amount"], "price": o["price"],
                     "proceeds": proceeds, "id": o["id"]})

    def equity(self) -> float:
        return self.cash + self.asset * self.price

    def available_trading_capital(self, quote: str = "EUR") -> float:
        """Capitale usabile = cash (il paper non ha locked)."""
        return self.cash

    def min_notional(self, symbol: str) -> float:
        """Notional minimo: il paper rifiuta ordini sotto il minimo (come live)."""
        return self._min_notional_val

    # --- ExchangePort --------------------------------------------------------

    def fetch_ticker(self, symbol: str) -> dict:
        return {"last": self.price}

    def fetch_balance(self) -> dict:
        total = self.equity()
        return {"free": {self.quote: self.cash},
                "total": {self.quote: total}}

    def create_limit_order(self, symbol: str, side: str, amount: float,
                           price: float) -> dict:
        amount = self._round_amount(float(amount))
        price = self._round_price(float(price))
        notional = amount * price
        if notional < self._min_notional_val:
            return {"id": "", "status": "rejected",
                    "info": {"reason": f"notional {notional:.4f} < min {self._min_notional_val}"}}
        oid = f"paper-{uuid.uuid4().hex[:10]}"
        order = {"id": oid, "symbol": symbol, "side": side,
                 "amount": amount, "price": price, "status": "open"}
        self.orders[oid] = order
        return order

    def sell_market(self, symbol: str, amount: float) -> dict:
        """Vendita immediata (stop-loss): slippage realistico come il live."""
        amount = self._round_amount(float(amount))
        if amount <= 0 or self.price <= 0:
            return {"id": "", "status": "rejected"}
        # slippage: esegue a prezzo peggiore di (1 - slippage) per il venditore
        exec_price = self.price * (1 - self.slippage)
        proceeds = amount * exec_price * (1 - self.fee)
        self.cash += proceeds
        self.asset -= amount
        self.fill_events.append(
            {"side": "sell", "amount": amount, "price": exec_price,
             "proceeds": proceeds, "id": "stop-loss-market"})
        return {"id": "stop-loss-market", "status": "closed"}

    def cancel_order(self, order_id: str, symbol: str) -> dict:
        if order_id in self.orders:
            self.orders[order_id]["status"] = "canceled"
        return {"id": order_id, "status": "canceled"}

    def fetch_order(self, order_id: str, symbol: str) -> dict:
        return self.orders.get(order_id, {"id": order_id, "status": "closed", "filled": 0})

    def fetch_open_orders(self, symbol: str) -> List[dict]:
        return [o for o in self.orders.values() if o["status"] == "open"]
