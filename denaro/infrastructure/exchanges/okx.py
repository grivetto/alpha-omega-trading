#!/usr/bin/env python3
"""Denaro — OKX adapter (endpoint EEA obbligatorio).

Vincolo critico dal runtime (audit Fase 1): le chiavi EU funzionano SOLO su
`eea.okx.com` — senza hostname EEA l'API fallisce con 50119 "API key doesn't
exist". Questo adapter rende EEA il default e applica:
- rate limiting centralizzato (TokenBucket condiviso del nodo)
- retry con backoff esponenziale su errori transitori
- classificazione errori: permanente vs transitorio
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import ccxt

from ..rate_limiter import TokenBucket

log = logging.getLogger("denaro.okx")

# OKX EEA: ~20 richieste private / 2s (limite documentato approssimativo).
# Conservativo: 10 token con refill di 5/s per il trading a densita' alta.
DEFAULT_CAPACITY = 10.0
DEFAULT_REFILL_RATE = 5.0

MAX_RETRIES = 3
RETRY_BASE_S = 1.0


class OKXPermanentError(Exception):
    """Errore non ritentabile (ordine invalido, chiave errata, ...)."""


class OKXTransientError(Exception):
    """Errore transitorio (rate limit, rete, 5xx) — ritentabile."""


class OKXAdapter:
    """Adapter REST OKX EEA con rate limit + retry."""

    def __init__(self, api_key: str, secret: str, passphrase: str,
                 bucket: Optional[TokenBucket] = None,
                 sandbox: bool = False) -> None:
        config: Dict[str, Any] = {
            "apiKey": api_key,
            "secret": secret,
            "password": passphrase,
            "enableRateLimit": True,
            "options": {"defaultType": "spot"},
        }
        if not sandbox:
            # CRITICO: chiavi EU solo su eea.okx.com
            config["hostname"] = "eea.okx.com"
        self.sandbox = sandbox
        self.ex = ccxt.okx(config)
        self.bucket = bucket or TokenBucket(DEFAULT_CAPACITY, DEFAULT_REFILL_RATE)

    # --- error classification ------------------------------------------------

    @staticmethod
    def _classify(exc: Exception) -> bool:
        """True se l'errore e' transitorio (ritentabile)."""
        if isinstance(exc, ccxt.RateLimitExceeded):
            return True
        if isinstance(exc, ccxt.NetworkError):
            return True
        if isinstance(exc, ccxt.ExchangeNotAvailable):
            return True
        if isinstance(exc, ccxt.ExchangeError):
            msg = str(exc).lower()
            if "rate limit" in msg or "too many requests" in msg:
                return True
            if any(code in msg for code in ("-1", "500", "502", "503", "504")):
                return True
            return False
        if isinstance(exc, ccxt.OperationFailed):
            return True
        return False

    # --- core guard -----------------------------------------------------------

    def _call(self, fn, *args, retries: int = MAX_RETRIES, **kwargs):
        """Esegue una chiamata API con rate limit + retry backoff."""
        last: Optional[Exception] = None
        for attempt in range(retries):
            if not self.bucket.try_acquire():
                delay = self.bucket.wait_time()
                log.debug("rate limit: attendo %.1fs", delay)
                time.sleep(min(delay, 5.0))
            try:
                return fn(*args, **kwargs)
            except Exception as e:  # noqa: BLE001 - classificazione esplicita
                if not self._classify(e):
                    raise OKXPermanentError(f"{type(e).__name__}: {e}") from e
                last = e
                sleep_s = RETRY_BASE_S * (2 ** attempt)
                log.warning("okx transitorio (%s), retry %d tra %.1fs",
                            type(e).__name__, attempt + 1, sleep_s)
                time.sleep(sleep_s)
        raise OKXTransientError(f"okx non raggiungibile dopo {retries} tentativi: {last}")

    # --- market data ----------------------------------------------------------

    def fetch_ticker(self, symbol: str) -> dict:
        return self._call(self.ex.fetch_ticker, symbol)

    def fetch_ohlcv(self, symbol: str, timeframe: str = "1h", limit: int = 100) -> list:
        return self._call(self.ex.fetch_ohlcv, symbol, timeframe, limit)

    # --- account --------------------------------------------------------------

    def fetch_balance(self) -> dict:
        return self._call(self.ex.fetch_balance)

    def fetch_free_quote(self, quote: str = "EUR") -> float:
        bal = self.fetch_balance()
        free = bal.get("free", {})
        for qc in (quote, "USDT", "USD", "GBP"):
            if free.get(qc):
                return float(free[qc])
        return 0.0

    def fetch_total_equity(self, base_quote: str = "EUR") -> float:
        """Equity totale in quote, valutando gli asset al prezzo corrente."""
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
        """Capitale realmente usabile = free + locked in ordini limit BUY
        cancellabili (TODO punto 1: equity dinamica).

        Il `free` non include il capitale bloccato nei buy limit aperti:
        quelli sono cancellabili, quindi vanno conteggiati come capacita'.
        """
        bal = self.fetch_balance()
        capital = float(bal.get("free", {}).get(quote, 0.0) or 0.0)
        try:
            for o in self.fetch_open_orders(None):
                if o.get("side") != "buy" or not o.get("symbol", "").endswith(f"/{quote}"):
                    continue
                capital += float(o.get("amount", 0.0)) * float(o.get("price", 0.0))
        except Exception as e:  # noqa: BLE001 - degradazione: solo free
            log.warning("available_trading_capital: open orders falliti (%s)", e)
        return capital

    def min_notional(self, symbol: str) -> float:
        """Size minima (notional) richiesta dall'exchange per un ordine."""
        try:
            m = self.ex.market(symbol)
            return float((m.get("limits", {}).get("cost", {}).get("min") or 0.0))
        except Exception:
            return 0.0

    # --- orders ---------------------------------------------------------------

    def create_limit_order(self, symbol: str, side: str, amount: float,
                           price: float) -> dict:
        if side == "buy":
            return self._call(self.ex.create_limit_buy_order, symbol, amount, price)
        return self._call(self.ex.create_limit_sell_order, symbol, amount, price)

    def cancel_order(self, order_id: str, symbol: str) -> dict:
        return self._call(self.ex.cancel_order, order_id, symbol)

    def fetch_open_orders(self, symbol: str) -> List[dict]:
        return self._call(self.ex.fetch_open_orders, symbol)

    def fetch_order(self, order_id: str, symbol: str) -> dict:
        return self._call(self.ex.fetch_order, order_id, symbol)

    def cancel_all(self, symbol: str) -> List[dict]:
        return self._call(self.ex.cancel_all_orders, symbol)
