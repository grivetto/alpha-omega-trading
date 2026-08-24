#!/usr/bin/env python3
"""Denaro — PaperExchange (simulatore di mercato per il Node).

Implementa il contratto `ExchangePort` con la SEMANTICA del motore paper v1
(`engine_paper.py`, già validata sui 500€ virtuali):
- FEE 0.1% per lato (0.001): cost = amount×price×(1+fee) sul buy,
  proceeds = amount×price×(1-fee) sul sell
- fill quando il prezzo tocca il livello (buy: price <= level; sell: price >= target)
- `update_price(price)` simula il movimento del mercato e riempie gli ordini

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

    def __init__(self, symbol: str, capital: float, quote: str = "EUR",
                 fee: float = FEE) -> None:
        self.symbol = symbol
        self.quote = quote
        self.fee = fee
        self.cash = float(capital)
        self.asset = 0.0
        self.price = 0.0
        self.orders: Dict[str, dict] = {}
        self.fill_events: List[dict] = []   # storia dei fill (per i test/parita')

    # --- ricostruzione dal journal (ripristino dopo restart) -----------------

    def rebuild(self, records: List[dict], capital: float) -> None:
        """Ricostruisce cash/asset dal journal immutabile (M5/D5).

        Semantica 1:1 del grid: ogni buy_filled genera un asset, ogni
        sell_filled lo chiude; cash = capital + Σ profit (gia' fee-aware).
        """
        self.cash = float(capital)
        self.asset = 0.0
        for r in records:
            if r.get("symbol") != self.symbol:
                continue
            ev = r.get("event")
            if ev == "buy_filled":
                self.asset += float(r.get("amount", 0.0))
            elif ev == "sell_filled":
                self.asset -= float(r.get("amount", 0.0))
                self.cash += float(r.get("profit", 0.0))

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
        """Il paper non impone notional minimi (0 = nessun vincolo)."""
        return 0.0

    # --- ExchangePort --------------------------------------------------------

    def fetch_ticker(self, symbol: str) -> dict:
        return {"last": self.price}

    def fetch_balance(self) -> dict:
        total = self.equity()
        return {"free": {self.quote: self.cash},
                "total": {self.quote: total}}

    def create_limit_order(self, symbol: str, side: str, amount: float,
                           price: float) -> dict:
        oid = f"paper-{uuid.uuid4().hex[:10]}"
        order = {"id": oid, "symbol": symbol, "side": side,
                 "amount": float(amount), "price": float(price), "status": "open"}
        self.orders[oid] = order
        return order

    def sell_market(self, symbol: str, amount: float) -> dict:
        """Vendita immediata (stop-loss): vende `amount` asset al prezzo corrente."""
        amount = float(amount)
        if amount <= 0 or self.price <= 0:
            return {"id": "", "status": "rejected"}
        proceeds = amount * self.price * (1 - self.fee)
        self.cash += proceeds
        self.asset -= amount
        self.fill_events.append(
            {"side": "sell", "amount": amount, "price": self.price,
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
