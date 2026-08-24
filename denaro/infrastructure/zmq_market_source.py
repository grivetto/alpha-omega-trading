#!/usr/bin/env python3
"""zmq_market_source.py — subscriber ZeroMQ lato nodi (requisito 1 ATLAS v6).

Su MARCODG1 e nuvola: si collega al feeder centralizzato di MC2
(tcp://<mc2>:5557 ticker, tcp://<mc2>:5558 ohlcv) e inietta i prezzi nel
MarketDataHub locale. Se il feeder e' irraggiungibile (heartbeat stale),
il nodo degrada al proprio canale WS/REST (nessuna perdita di dati).

Il subscriber e' un PriceHandler: `handler(symbol, price)` chiamato da un
task asyncio dedicato; si integra con hub.subscribe(symbol, handler).
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Awaitable, Callable, Dict, Optional

log = logging.getLogger("denaro.zmq_source")

try:
    import zmq
    import zmq.asyncio as zmq_async
except Exception:  # noqa: BLE001
    zmq = None
    zmq_async = None

TICKER_PORT = 5557
OHLCV_PORT = 5558
HEARTBEAT_TTL_S = 15.0      # nessun dato dal feeder per 15s → fallback locale
RECONNECT_S = 5.0

Handler = Callable[[str, float], Awaitable[None]]
OhlcvHandler = Callable[[str, list], Awaitable[None]]


class ZMQMarketSource:
    """Sorgente prezzi ZeroMQ con degradazione automatica.

    - `start()`: avvia i task SUB ticker e OHLCV
    - `subscribe(symbol, handler)`: handler prezzi (stesso contratto hub)
    - `on_ohlcv(handler)`: handler candle (per il regime filter ADX/ATR)
    - `healthy()`: True se il feeder sta pubblicando dati freschi
    """

    __slots__ = ("host", "ctx", "sub_ticker", "sub_ohlcv", "handlers",
                 "ohlcv_handlers", "_last_seen", "_running", "_tasks")

    def __init__(self, host: str = "127.0.0.1") -> None:
        if zmq is None:
            raise RuntimeError("pyzmq non installato: pip install pyzmq")
        self.host = host
        self.ctx = zmq_async.Context()
        self.sub_ticker = self.ctx.socket(zmq.SUB)
        self.sub_ticker.setsockopt(zmq.SUBSCRIBE, b"ticker.")
        self.sub_ticker.setsockopt(zmq.LINGER, 0)
        self.sub_ticker.connect(f"tcp://{host}:{TICKER_PORT}")
        self.sub_ohlcv = self.ctx.socket(zmq.SUB)
        self.sub_ohlcv.setsockopt(zmq.SUBSCRIBE, b"ohlcv.")
        self.sub_ohlcv.setsockopt(zmq.LINGER, 0)
        self.sub_ohlcv.connect(f"tcp://{host}:{OHLCV_PORT}")
        self.handlers: Dict[str, list] = {}
        self.ohlcv_handlers: list = []
        self._last_seen: Dict[str, float] = {}
        self._running = False
        self._tasks = []

    # --- lifecycle ------------------------------------------------------------

    async def start(self) -> None:
        self._running = True
        self._tasks = [
            asyncio.create_task(self._ticker_loop()),
            asyncio.create_task(self._ohlcv_loop()),
        ]
        log.info("ZMQ subscriber verso %s attivo (:5557 ticker, :5558 ohlcv)",
                 self.host)

    async def stop(self) -> None:
        self._running = False
        for t in self._tasks:
            t.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        self.sub_ticker.close()
        self.sub_ohlcv.close()
        self.ctx.term()

    # --- API ------------------------------------------------------------------

    def subscribe(self, symbol: str, handler: Handler) -> None:
        self.handlers.setdefault(symbol, []).append(handler)

    def on_ohlcv(self, handler: OhlcvHandler) -> None:
        self.ohlcv_handlers.append(handler)

    def healthy(self) -> bool:
        """Feeder vivo? (dati recenti su almeno un simbolo o ohlcv)."""
        if not self._last_seen:
            return False
        latest = max(self._last_seen.values())
        return (time.time() - latest) < HEARTBEAT_TTL_S

    # --- loop -----------------------------------------------------------------

    async def _ticker_loop(self) -> None:
        while self._running:
            try:
                topic, body = await self.sub_ticker.recv_multipart()
                msg = json.loads(body)
                symbol = msg.get("symbol", "")
                price = msg.get("last")
                if not symbol or not price:
                    continue
                self._last_seen[f"ticker:{symbol}"] = time.time()
                for h in list(self.handlers.get(symbol, ())):
                    try:
                        await h(symbol, float(price))
                    except Exception as e:  # noqa: BLE001
                        log.warning("handler %s fallito: %s", symbol, e)
            except asyncio.CancelledError:
                return
            except Exception as e:  # noqa: BLE001
                log.warning("zmq ticker: %s — retry tra %ds", e, RECONNECT_S)
                await asyncio.sleep(RECONNECT_S)

    async def _ohlcv_loop(self) -> None:
        while self._running:
            try:
                topic, body = await self.sub_ohlcv.recv_multipart()
                msg = json.loads(body)
                symbol = msg.get("symbol", "")
                ohlcv = msg.get("ohlcv", [])
                if not symbol or not ohlcv:
                    continue
                self._last_seen[f"ohlcv:{symbol}"] = time.time()
                for h in list(self.ohlcv_handlers):
                    try:
                        await h(symbol, ohlcv)
                    except Exception as e:  # noqa: BLE001
                        log.warning("ohlcv handler %s fallito: %s", symbol, e)
            except asyncio.CancelledError:
                return
            except Exception as e:  # noqa: BLE001
                log.warning("zmq ohlcv: %s — retry tra %ds", e, RECONNECT_S)
                await asyncio.sleep(RECONNECT_S)
