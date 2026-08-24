#!/usr/bin/env python3
"""Denaro — Kraken adapter (REST, CCXT).

Adattatore minimale con la stessa architettura di OKXAdapter:
- retry/backoff su errori transitori, classificazione errori
- rate limiting via TokenBucket condiviso del nodo
Nessuna particolarita' di hostname (a differenza di OKX EEA).
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import ccxt

from ..rate_limiter import TokenBucket

log = logging.getLogger("denaro.kraken")

DEFAULT_CAPACITY = 10.0
DEFAULT_REFILL_RATE = 5.0

MAX_RETRIES = 3
RETRY_BASE_S = 1.0

# Caching rigido dei bilanci (requisito 4 ATLAS v6)
BALANCE_CACHE_TTL = 15.0


class KrakenPermanentError(Exception):
    """Errore non ritentabile."""


class KrakenTransientError(Exception):
    """Errore transitorio — ritentabile."""


class KrakenAdapter:
    """Adapter REST Kraken con rate limit + retry."""

    def __init__(self, api_key: str, secret: str,
                 bucket: Optional[TokenBucket] = None) -> None:
        self.ex = ccxt.kraken({
            "apiKey": api_key,
            "secret": secret,
            "enableRateLimit": True,
            "options": {"defaultType": "spot"},
        })
        self.bucket = bucket or TokenBucket(DEFAULT_CAPACITY, DEFAULT_REFILL_RATE)
        self._balance_cache: Optional[tuple] = None  # (value, ts)

    @staticmethod
    def _classify(exc: Exception) -> bool:
        if isinstance(exc, (ccxt.RateLimitExceeded, ccxt.NetworkError,
                            ccxt.ExchangeNotAvailable, ccxt.OperationFailed)):
            return True
        if isinstance(exc, ccxt.ExchangeError):
            msg = str(exc).lower()
            return ("rate limit" in msg or "too many" in msg
                    or any(c in msg for c in ("eorder:", "egeneral:timedout")))
        return False

    def _call(self, fn, *args, retries: int = MAX_RETRIES, **kwargs):
        last: Optional[Exception] = None
        for attempt in range(retries):
            if not self.bucket.try_acquire():
                time.sleep(min(self.bucket.wait_time(), 5.0))
            try:
                return fn(*args, **kwargs)
            except Exception as e:  # noqa: BLE001
                if not self._classify(e):
                    raise KrakenPermanentError(f"{type(e).__name__}: {e}") from e
                last = e
                sleep_s = RETRY_BASE_S * (2 ** attempt)
                log.warning("kraken transitorio (%s), retry %d tra %.1fs",
                            type(e).__name__, attempt + 1, sleep_s)
                time.sleep(sleep_s)
        raise KrakenTransientError(f"kraken non raggiungibile dopo {retries} tentativi: {last}")

    # market
    def fetch_ticker(self, symbol: str) -> dict:
        return self._call(self.ex.fetch_ticker, symbol)

    def fetch_ohlcv(self, symbol: str, timeframe: str = "1h", limit: int = 100) -> list:
        return self._call(self.ex.fetch_ohlcv, symbol, timeframe, limit)

    # account
    def fetch_balance(self) -> dict:
        """Bilancio con cache TTL 15s (requisito 4: niente refresh ridondanti)."""
        import time as _t
        now = _t.time()
        if self._balance_cache and (now - self._balance_cache[1]) < BALANCE_CACHE_TTL:
            return self._balance_cache[0]
        bal = self._call(self.ex.fetch_balance)
        self._balance_cache = (bal, now)
        return bal

    def invalidate_balance(self) -> None:
        """Forza il refresh al prossimo fetch (dopo un ordine/fill)."""
        self._balance_cache = None

    def fetch_free_quote(self, quote: str = "EUR") -> float:
        bal = self.fetch_balance()
        free = bal.get("free", {})
        for qc in (quote, "USDT", "USD", "GBP"):
            if free.get(qc):
                return float(free[qc])
        return 0.0

    def fetch_total_equity(self, base_quote: str = "EUR") -> float:
        bal = self.fetch_balance()
        total = bal.get("total", {})
        equity = 0.0
        for asset, amount in total.items():
            if not amount or float(amount) <= 0:
                continue
            if asset == base_quote:
                equity += float(amount)
            else:
                try:
                    t = self.fetch_ticker(f"{asset}/{base_quote}")
                    equity += float(amount) * float(t["last"])
                except Exception:
                    continue
        return equity

    def available_trading_capital(self, quote: str = "EUR") -> float:
        """Capitale usabile = free + locked in buy limit cancellabili (equity dinamica)."""
        bal = self.fetch_balance()
        capital = float(bal.get("free", {}).get(quote, 0.0) or 0.0)
        try:
            for o in self.fetch_open_orders(None):
                if o.get("side") != "buy" or not o.get("symbol", "").endswith(f"/{quote}"):
                    continue
                capital += float(o.get("amount", 0.0)) * float(o.get("price", 0.0))
        except Exception as e:  # noqa: BLE001
            log.warning("available_trading_capital: open orders falliti (%s)", e)
        return capital

    def min_notional(self, symbol: str) -> float:
        """Size minima (notional) richiesta da Kraken per un ordine."""
        try:
            m = self.ex.market(symbol)
            return float((m.get("limits", {}).get("cost", {}).get("min") or 0.0))
        except Exception:
            return 0.0

    # orders
    def create_limit_order(self, symbol: str, side: str, amount: float,
                           price: float) -> dict:
        if side == "buy":
            return self._call(self.ex.create_limit_buy_order, symbol, amount, price)
        return self._call(self.ex.create_limit_sell_order, symbol, amount, price)

    def sell_market(self, symbol: str, amount: float) -> dict:
        """Vendita immediata (stop-loss): market sell di `amount` asset."""
        return self._call(self.ex.create_market_sell_order, symbol, amount)

    @property
    def min_amount(self) -> float:
        """Amount minimo di default per gli ordini (filtro conservative)."""
        return 0.0

    def min_amount_for(self, symbol: str) -> float:
        """Amount minimo dell'exchange per un symbol (limits.amount.min)."""
        try:
            m = self.ex.market(symbol)
            return float((m.get("limits", {}).get("amount", {}).get("min") or 0.0))
        except Exception:
            return 0.0

    def cancel_order(self, order_id: str, symbol: str) -> dict:
        return self._call(self.ex.cancel_order, order_id, symbol)

    def fetch_open_orders(self, symbol: str) -> List[dict]:
        return self._call(self.ex.fetch_open_orders, symbol)

    def fetch_order(self, order_id: str, symbol: str) -> dict:
        return self._call(self.ex.fetch_order, order_id, symbol)

    def cancel_all(self, symbol: str) -> List[dict]:
        return self._call(self.ex.cancel_all_orders, symbol)
