#!/usr/bin/env python3
"""
KRAKEN ENGINE — CCXT adapter for Kraken exchange.
Handles DOGE/EUR pair only. No Binance code, no USDC references.
"""

import os
import time
from typing import List, Dict, Optional
import ccxt


SYMBOL = "DOGE/EUR"


def _fix_base64_secret(s: str) -> str:
    """Ensure valid base64 padding for Kraken API secret."""
    s = s.strip()
    missing = len(s) % 4
    if missing:
        s += "=" * (4 - missing)
    return s


class KrakenEngine:
    """CCXT-based Kraken adapter with Denaro-compatible interface."""

    def __init__(self, api_key: str, api_secret: str):
        secret = _fix_base64_secret(api_secret)
        self.ex = ccxt.kraken({
            "apiKey": api_key,
            "secret": secret,
            "enableRateLimit": True,
            "options": {"defaultType": "spot"},
        })
        self.ex.load_markets()
        self._last_request: float = 0.0

    # -- internal helpers ------------------------------------------------

    def _rate_limit(self):
        """Simple request throttle (~6 req/s max)."""
        now = time.time()
        wait = 0.15 - (now - self._last_request)
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.time()

    # -- public methods --------------------------------------------------

    def fetch_ticker(self, symbol: str = SYMBOL) -> float:
        """Return current last price."""
        self._rate_limit()
        ticker = self.ex.fetch_ticker(symbol)
        return float(ticker["last"])

    def fetch_balance(self, currency: str = "EUR") -> float:
        """Return free+locked balance for a given currency."""
        self._rate_limit()
        bal = self.ex.fetch_balance()
        return float(bal.get("total", {}).get(currency, 0) or 0)

    def create_limit_buy_order(self, symbol: str, amount: float, price: float) -> dict:
        """635850074499424512"""
        self._rate_limit()
        return self.ex.create_limit_buy_order(symbol, amount, price)

    def create_limit_sell_order(self, symbol: str, amount: float, price: float) -> dict:
        """Place a limit sell order on Kraken."""
        self._rate_limit()
        return self.ex.create_limit_sell_order(symbol, amount, price)

    def cancel_all_orders(self, symbol: str = SYMBOL) -> List[dict]:                                 
        """Cancel every open order for the given symbol."""
        self._rate_limit()
        try:
            orders = self.ex.fetch_open_orders(symbol)
            for o in orders:
                try:
                    self.ex.cancel_order(o["id"], symbol)
                except Exception:
                    pass
            return orders
        except Exception:
            return []

    def fetch_open_orders(self, symbol: str = SYMBOL) -> List[dict]:
        """Return list of open order dicts."""
        self._rate_limit()
        return self.ex.fetch_open_orders(symbol) or []

    def round_amount(self, qty: float, symbol: str = SYMBOL) -> float:
        """Round quantity to exchange precision."""
        return float(self.ex.amount_to_precision(symbol, qty))

    def round_price(self, price: float, symbol: str = SYMBOL) -> float:
        """Round price to exchange precision."""
        return float(self.ex.price_to_precision(symbol, price))
