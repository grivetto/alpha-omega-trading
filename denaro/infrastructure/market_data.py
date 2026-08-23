#!/usr/bin/env python3
"""Denaro — MarketDataHub (M3/D2 del blueprint).

Un hub per nodo: multiplexa i flussi di mercato di TUTTI i bot su UN
WebSocket per exchange (ccxt.pro), con cache condivisa e fallback REST.

- `subscribe(symbol, handler)`: handler asincrono riceve (symbol, price)
- `price(symbol)`: ultimo prezzo in cache (senza attese)
- canale WS con riconnessione backoff; fallback REST se il WS e' giu'
- `ws_enabled=False` → solo polling REST con TTL (degradazione controllata)

I canali di dati sono iniettabili (`ex_pro` / `ex_rest`), quindi l'intera
logica di broadcast/cache/fallback e' testabile con fake (nessuna rete).
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from typing import Awaitable, Callable, Dict, List, Optional, Set

log = logging.getLogger("denaro.market_data")

PriceHandler = Callable[[str, float], Awaitable[None]]

WS_MAX_RETRIES = 5
WS_RETRY_BASE_S = 2.0


class MarketDataHub:
    """Hub condiviso: 1 canale per exchange, N consumatori."""

    def __init__(self, ex_rest: object, ex_pro: Optional[object] = None,
                 ws_enabled: bool = True,
                 poll_interval: float = 10.0,
                 price_ttl: float = 30.0,
                 ws_max_retries: int = WS_MAX_RETRIES,
                 ws_retry_base_s: float = WS_RETRY_BASE_S,
                 now: Optional[Callable[[], float]] = None) -> None:
        self._rest = ex_rest
        self._pro = ex_pro
        self.ws_enabled = ws_enabled and ex_pro is not None
        self.poll_interval = poll_interval
        self.price_ttl = price_ttl
        self.ws_max_retries = max(1, ws_max_retries)
        self.ws_retry_base_s = max(0.0, ws_retry_base_s)
        self._now = now or time.time

        self._handlers: Dict[str, Set[PriceHandler]] = defaultdict(set)
        self._cache: Dict[str, tuple] = {}        # symbol -> (price, ts)
        self._tasks: Dict[str, asyncio.Task] = {}  # symbol -> canale attivo
        self._running = False

    # --- lifecycle -----------------------------------------------------------

    async def start(self) -> None:
        self._running = True
        # ccxt.pro richiede i markets caricati prima di watch_ticker
        if self.ws_enabled and self._pro is not None:
            load = getattr(self._pro, "load_markets", None)
            if load:
                try:
                    if asyncio.iscoroutinefunction(load):
                        await load()
                    else:
                        load()
                except Exception as e:  # noqa: BLE001
                    log.warning("load_markets ws fallito: %s", e)
        # i canali vanno avviati anche per i simboli sottoscritti PRIMA di start()
        for symbol in list(self._handlers):
            self._ensure_channel(symbol)

    async def stop(self) -> None:
        self._running = False
        tasks = list(self._tasks.values())
        self._tasks.clear()
        for t in tasks:
            t.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    # --- subscription --------------------------------------------------------

    def subscribe(self, symbol: str, handler: PriceHandler) -> None:
        first = symbol not in self._handlers or not self._handlers[symbol]
        self._handlers[symbol].add(handler)
        if first and self._running:
            self._ensure_channel(symbol)

    def unsubscribe(self, symbol: str, handler: PriceHandler) -> None:
        self._handlers[symbol].discard(handler)
        if not self._handlers[symbol]:
            self._handlers.pop(symbol, None)
            task = self._tasks.pop(symbol, None)
            if task:
                task.cancel()

    def _ensure_channel(self, symbol: str) -> None:
        if symbol in self._tasks:
            return
        if self.ws_enabled:
            self._tasks[symbol] = asyncio.create_task(self._ws_loop(symbol))
        else:
            self._tasks[symbol] = asyncio.create_task(self._rest_loop(symbol))

    # --- cache ---------------------------------------------------------------

    def price(self, symbol: str) -> Optional[float]:
        cached = self._cache.get(symbol)
        if not cached:
            return None
        price, ts = cached
        if self._now() - ts > self.price_ttl:
            return None
        return price

    async def get_price(self, symbol: str) -> Optional[float]:
        """Prezzo di cache se fresco, altrimenti fetch REST one-shot."""
        p = self.price(symbol)
        if p is not None:
            return p
        try:
            t = await asyncio.to_thread(self._rest.fetch_ticker, symbol)
            last = float(t["last"])
            self._cache[symbol] = (last, self._now())
            return last
        except Exception as e:  # noqa: BLE001 - fallback silenzioso
            log.warning("get_price(%s) fallito: %s", symbol, e)
            return None

    # --- canali --------------------------------------------------------------

    async def _broadcast(self, symbol: str, price: float) -> None:
        self._cache[symbol] = (price, self._now())
        for handler in list(self._handlers.get(symbol, ())):
            try:
                await handler(symbol, price)
            except Exception as e:  # noqa: BLE001 - un handler non deve uccidere il canale
                log.warning("handler %s per %s fallito: %s", handler, symbol, e)

    async def _ws_loop(self, symbol: str) -> None:
        """Ciclo WebSocket con riconnessione backoff (ccxt.pro watch_ticker).

        In ccxt.pro `watch_ticker` e' una coroutine che si risolve a ogni
        update del ticker: va chiamata in loop (non e' un async generator).
        """
        retries = 0
        while self._running:
            try:
                ticker = await self._pro.watch_ticker(symbol)
                await self._broadcast(symbol, float(ticker["last"]))
                retries = 0
            except asyncio.CancelledError:
                return
            except Exception as e:  # noqa: BLE001 - riconnessione
                retries += 1
                log.warning("ws %s disconnesso (%s), retry %d/%d",
                            symbol, type(e).__name__, retries, self.ws_max_retries)
                if retries >= self.ws_max_retries:
                    log.error("ws %s: passo al fallback REST", symbol)
                    await self._rest_loop(symbol)
                    return
                await asyncio.sleep(self.ws_retry_base_s * (2 ** (retries - 1)))

    async def _rest_loop(self, symbol: str) -> None:
        """Polling REST con TTL: serve finche' il WS non torna (o sempre)."""
        while self._running:
            try:
                t = await asyncio.to_thread(self._rest.fetch_ticker, symbol)
                await self._broadcast(symbol, float(t["last"]))
            except asyncio.CancelledError:
                return
            except Exception as e:  # noqa: BLE001
                log.warning("rest %s fallito: %s", symbol, e)
            await asyncio.sleep(self.poll_interval)
