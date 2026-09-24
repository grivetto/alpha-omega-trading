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
import re
import time
from typing import Any, Dict, List, Optional

import ccxt

from ..rate_limiter import TokenBucket
from .errors import PermanentExchangeError, TransientExchangeError

log = logging.getLogger("denaro.okx")

# OKX EEA: ~20 richieste private / 2s (limite documentato approssimativo).
# Conservativo: 10 token con refill di 5/s per il trading a densita' alta.
DEFAULT_CAPACITY = 10.0
DEFAULT_REFILL_RATE = 5.0

MAX_RETRIES = 3
RETRY_BASE_S = 1.0

# Caching rigido dei bilanci (requisito 4 ATLAS v6): i dati in tempo reale
# arrivano dagli eventi WS (orders/fills), il balance REST e' solo un
# fallback → refresh minimo ogni 15s.
BALANCE_CACHE_TTL = 15.0


# --- R3b (docs/58 §58.3): chiave di idempotenza degli ordini -------------------
# Un ordine inviato SENZA chiave e' irriconoscibile: se il processo muore fra
# l'invio e il salvataggio dello stato, l'ordine resta vivo sull'exchange e il
# bot non sa piu' che e' suo (capitale impegnato che non vede). Con `clOrdId`
# l'ordine e' NOSTRO per costruzione e un riavvio lo riconosce.
# VINCOLO OKX: `clOrdId` e' alfanumerico MINUSCOLO, max 32 caratteri. Non e' un
# dettaglio di stile: un id con un carattere non ammesso fa RIFIUTARE l'ordine,
# cioe' trasforma una protezione in un blocco degli ordini.
CLIENT_ORDER_ID_MAX = 32
# carattere NON ammesso (la classe ammessa e' [a-z0-9]): si sostituisce, non si
# elimina, cosi' due id che differiscono solo per un separatore restano distinti
CLIENT_ORDER_ID_RE = re.compile(r"[^a-z0-9]")


def client_order_id_sicuro(client_order_id: Optional[str],
                           max_len: int = CLIENT_ORDER_ID_MAX) -> str:
    """Rende una chiave d'ordine accettabile da OKX: [a-z0-9], max 32 caratteri.

    Sostituisce ogni carattere non ammesso con `x` (NON lo elimina: eliminandolo
    `a.b` e `ab` colliderebbero, e due ordini diversi finirebbero con la STESSA
    chiave di idempotenza) e tronca a `max_len`. Tutto minuscolo, perche' OKX
    rifiuta le maiuscole.
    """
    if not client_order_id:
        return ""
    out = CLIENT_ORDER_ID_RE.sub("x", str(client_order_id).lower())[:max_len]
    if len(str(client_order_id)) > max_len:
        log.debug("clOrdId troncato a %d caratteri: %r -> %r",
                  max_len, client_order_id, out)
    return out


class OKXPermanentError(PermanentExchangeError):
    """Errore non ritentabile (ordine invalido, chiave errata, ...)."""


class OKXTransientError(TransientExchangeError):
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
        # cache bilanci con TTL (evita chiamate REST ridondanti)
        self._balance_cache: Optional[tuple] = None  # (value, ts)
        # metadati mercati caricati pigramente (SENZA questo i limiti
        # min_amount/min_notional/precision sono invisibili -> 0.0)
        self._markets_loaded = False

    def _ensure_markets(self) -> bool:
        """Carica i metadati dei mercati UNA volta.

        Bug di produzione (2026-09-11): senza load_markets() la chiamata
        ex.market() solleva "markets not loaded" e TUTTI i filtri di minimo
        ordine (min_amount_for, min_notional) restituiscono 0.0. Risultato:
        la policy pianificava ordini dust (9e-08 DOGE) mai accettabili
        dall'exchange, ritentati a ogni tick e loggati come "piazzati".
        """
        if self._markets_loaded:
            return True
        try:
            self._call(self.ex.load_markets)
            self._markets_loaded = True
            log.info("okx: %d mercati caricati (limiti/precision disponibili)",
                     len(getattr(self.ex, "markets", {}) or {}))
        except Exception as e:  # noqa: BLE001
            log.warning("okx load_markets fallito (%s) - minimi ordine NON "
                        "disponibili: i filtri restano disattivati", e)
            return False
        return True

    @property
    def min_amount(self) -> float:
        """Amount minimo di default per gli ordini (filtro conservative)."""
        return 0.0

    def min_amount_for(self, symbol: str) -> float:
        """Amount minimo dell'exchange per un symbol (limits.amount.min)."""
        if not self._ensure_markets():
            return 0.0
        try:
            m = self.ex.market(symbol)
            return float((m.get("limits", {}).get("amount", {}).get("min") or 0.0))
        except Exception:
            return 0.0

    # --- error classification ------------------------------------------------

    @staticmethod
    def _classify(exc: Exception) -> bool:
        """True se l'errore e' transitorio (ritentabile).

        Gli errori di ORDINE sono PERMANENTI (InvalidOrder, InsufficientFunds,
        OrderNotFound...): ritentarli in loop blocca il tick e congela le
        health (bug visto in produzione: stop-loss DOGE appeso 90 min).
        """
        if isinstance(exc, (ccxt.InvalidOrder, ccxt.InsufficientFunds,
                           ccxt.OrderNotFound, ccxt.NotSupported,
                           ccxt.BadRequest)):
            return False
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

    def fetch_ohlcv_raw(self, symbol: str, timeframe: str = "1h",
                        limit: int = 200) -> list:
        """OHLCV via RAW API (bypassa il bug di ccxt 4.5.x su fetch_ohlcv).
        Ritorna [[ts, o, h, l, c, v], ...] con ts in secondi."""
        try:
            m = self.ex.market(symbol)
            inst = m["id"]
        except Exception:
            # markets non caricati → formato OKX BASE-QUOTE
            inst = symbol.replace("/", "-")
        bar = {"1h": "1H", "15m": "15m", "1d": "1D"}.get(timeframe, "1H")
        try:
            r = self._call(self.ex.publicGetMarketHistoryCandles,
                           {"instId": inst, "bar": bar, "limit": str(limit)})
        except Exception:
            return []
        data = r.get("data") if isinstance(r, dict) else r
        return [[int(row[0]) / 1000.0, float(row[1]), float(row[2]),
                 float(row[3]), float(row[4]), float(row[5])]
                for row in (data or [])]

    # --- account --------------------------------------------------------------

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
        if not self._ensure_markets():
            return 0.0
        try:
            m = self.ex.market(symbol)
            return float((m.get("limits", {}).get("cost", {}).get("min") or 0.0))
        except Exception:
            return 0.0

    # --- orders ---------------------------------------------------------------

    def create_limit_order(self, symbol: str, side: str, amount: float,
                           price: float,
                           client_order_id: Optional[str] = None) -> dict:
        """Ordine limite, con chiave di idempotenza opzionale (`clOrdId`).

        R3b (docs/58 §58.3): la chiave viaggia come `params={"clOrdId": ...}` —
        ccxt la mappa sul campo OKX `clOrdId`. Serve a riconoscere al riavvio un
        ordine inviato prima di un crash, invece di contarlo come "unknown".

        Se `client_order_id` e' None il comportamento e' IDENTICO a prima
        (nessun `params` alla chiamata): nessun effetto sui chiamanti storici.
        """
        # i mercati servono a ccxt per applicare tick size / precision
        self._ensure_markets()
        coid = client_order_id_sicuro(client_order_id)
        params: Dict[str, Any] = {"clOrdId": coid} if coid else {}
        create = (self.ex.create_limit_buy_order if side == "buy"
                  else self.ex.create_limit_sell_order)
        if params:
            out = self._call(create, symbol, amount, price, params)
        else:
            out = self._call(create, symbol, amount, price)
        # il free balance cambia subito (fondi bloccati): non riusare la cache
        self.invalidate_balance()
        return out

    def sell_market(self, symbol: str, amount: float,
                    client_order_id: Optional[str] = None) -> dict:
        """Vendita immediata (stop-loss): market sell di `amount` asset.

        Anche qui la chiave e' opzionale (R3b): uno stop inviato e poi perso da
        un crash e' esattamente il caso in cui serve riconoscere l'ordine.
        Senza chiave il comportamento resta quello storico.
        """
        coid = client_order_id_sicuro(client_order_id)
        if coid:
            return self._call(self.ex.create_market_sell_order, symbol, amount,
                              {"clOrdId": coid})
        return self._call(self.ex.create_market_sell_order, symbol, amount)

    def cancel_order(self, order_id: str, symbol: str) -> dict:
        return self._call(self.ex.cancel_order, order_id, symbol)

    def fetch_open_orders(self, symbol: str) -> List[dict]:
        return self._call(self.ex.fetch_open_orders, symbol)

    def fetch_order(self, order_id: str, symbol: str) -> dict:
        return self._call(self.ex.fetch_order, order_id, symbol)

    def cancel_all(self, symbol: str) -> List[dict]:
        return self._call(self.ex.cancel_all_orders, symbol)
