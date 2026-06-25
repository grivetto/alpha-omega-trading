"""Denaro v3 WebSocket Client – Real-time Binance streams with async HTTP.

Fixes:
- sync requests → aiohttp (async, non‑blocking listen‑key keepalive).
- Proper reconnection with backoff.
- In‑memory event queue for main loop consumption.
"""

from __future__ import annotations
import asyncio, json, time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import aiohttp
import websockets
from loguru import logger


# ── Event types ────────────────────────────────────────────────────
class EventType(str, Enum):
    TICKER = "ticker"
    FILL = "fill"
    BALANCE = "balance"
    ERROR = "error"
    DISCONNECTED = "disconnected"


@dataclass
class WsEvent:
    type: EventType
    timestamp: float = field(default_factory=time.time)
    data: dict = field(default_factory=dict)


# ── Ticker stream ────────────────────────────────────────────────────
class TickerStream:
    def __init__(self, symbol: str, queue: asyncio.Queue):
        self._symbol = symbol.lower().replace("/", "")
        self._url = f"wss://stream.binance.com:9443/ws/{self._symbol}@ticker"
        self._queue = queue
        self._running = False

    async def start(self):
        self._running = True
        while self._running:
            try:
                async with websockets.connect(self._url, ping_interval=20) as ws:
                    logger.info(f"Ticker WS connected: {self._symbol}")
                    async for msg in ws:
                        if not self._running:
                            break
                        try:
                            data = json.loads(msg)
                            if data.get("e") == "24hrTicker":
                                await self._queue.put(WsEvent(EventType.TICKER, data={
                                    "symbol": data["s"],
                                    "last": float(data["c"]),
                                    "bid": float(data["b"]),
                                    "ask": float(data["a"]),
                                    "volume": float(data["v"]),
                                }))
                        except (json.JSONDecodeError, KeyError):
                            pass
            except (websockets.ConnectionClosed, ConnectionError, OSError) as exc:
                logger.warning(f"Ticker WS {self._symbol} down: {exc}")
            if self._running:
                await asyncio.sleep(3)

    async def stop(self):
        self._running = False


# ── User data stream (fills + balance) ──────────────────────────────
class UserDataStream:
    def __init__(self, exchange, queue: asyncio.Queue):
        self._exchange = exchange
        self._queue = queue
        self._listen_key: Optional[str] = None
        self._running = False
        self._keepalive_task: Optional[asyncio.Task] = None
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_listen_key(self) -> str:
        try:
            if self._session is None:
                self._session = aiohttp.ClientSession()
            async with self._session.post(
                "https://api.binance.com/api/v3/userDataStream",
                headers={"X-MBX-APIKEY": self._exchange.apiKey},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    js = await resp.json()
                    return js.get("listenKey", "")
                logger.error(f"Listen‑key API returned {resp.status}")
                return ""
        except Exception as exc:
            logger.error(f"Failed to get listen key: {exc}")
            return ""

    async def _keepalive(self):
        while self._running and self._listen_key:
            await asyncio.sleep(1800)
            if not self._running:
                break
            try:
                if self._session is None:
                    self._session = aiohttp.ClientSession()
                async with self._session.put(
                    "https://api.binance.com/api/v3/userDataStream",
                    headers={"X-MBX-APIKEY": self._exchange.apiKey},
                    params={"listenKey": self._listen_key},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        logger.warning(f"Keepalive returned {resp.status}")
            except Exception as exc:
                logger.warning(f"Keepalive failed: {exc}")

    async def start(self):
        self._running = True
        while self._running:
            try:
                self._listen_key = await self._get_listen_key()
                if not self._listen_key:
                    logger.error("No listen key – retry 30s")
                    await asyncio.sleep(30)
                    continue
                logger.info("User data WS connected")
                self._keepalive_task = asyncio.create_task(self._keepalive())
                url = f"wss://stream.binance.com:9443/ws/{self._listen_key}"
                async with websockets.connect(url, ping_interval=20) as ws:
                    async for msg in ws:
                        if not self._running:
                            break
                        try:
                            data = json.loads(msg)
                            etype = data.get("e", "")
                            if etype == "executionReport":
                                status = data.get("X", "")
                                if status in ("FILLED", "PARTIALLY_FILLED"):
                                    await self._queue.put(WsEvent(EventType.FILL, data={
                                        "symbol": data["s"],
                                        "side": data["S"].lower(),
                                        "amount": float(data["l"]),
                                        "price": float(data["L"]),
                                        "order_id": str(data["i"]),
                                        "status": status,
                                        "fee": float(data.get("n", 0)),
                                        "is_maker": data.get("m", False),
                                    }))
                            elif etype == "outboundAccountPosition":
                                await self._queue.put(WsEvent(EventType.BALANCE, data={
                                    "balances": {b["a"]: {"free": float(b["f"]), "locked": float(b["l"])} for b in data.get("B", [])}
                                }))
                        except (json.JSONDecodeError, KeyError):
                            pass
            except (websockets.ConnectionClosed, ConnectionError, OSError) as exc:
                logger.warning(f"User data WS down: {exc}")
            finally:
                if self._keepalive_task:
                    self._keepalive_task.cancel()
                    self._keepalive_task = None
            if self._running:
                await asyncio.sleep(5)

    async def stop(self):
        self._running = False
        if self._keepalive_task:
            self._keepalive_task.cancel()
            self._keepalive_task = None
        if self._session:
            await self._session.close()
            self._session = None


# ── Unified WebSocket manager ──────────────────────────────────────
class WebSocketClient:
    def __init__(self, exchange, pairs: list[str]):
        self._exchange = exchange
        self._pairs = pairs
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        self._ticker_streams: list[TickerStream] = []
        self._user_stream: Optional[UserDataStream] = None
        self._tasks: list[asyncio.Task] = []
        self._running = False
        self.last_ticker: dict[str, dict] = {}
        self.fill_events: deque[WsEvent] = deque(maxlen=1000)

    async def start(self):
        self._running = True
        for pair in self._pairs:
            s = TickerStream(pair, self._queue)
            self._ticker_streams.append(s)
            self._tasks.append(asyncio.create_task(s.start()))
        self._user_stream = UserDataStream(self._exchange, self._queue)
        self._tasks.append(asyncio.create_task(self._user_stream.start()))
        logger.info(f"WS client started: {len(self._pairs)} pairs")

    async def stop(self):
        self._running = False
        for s in self._ticker_streams:
            await s.stop()
        if self._user_stream:
            await self._user_stream.stop()
        for t in self._tasks:
            t.cancel()
        logger.info("WS client stopped")

    async def get_event(self, timeout: float = 1.0) -> Optional[WsEvent]:
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    async def drain_events(self) -> list[WsEvent]:
        events = []
        while True:
            ev = await self.get_event(timeout=0.01)
            if ev is None:
                break
            events.append(ev)
            if ev.type == EventType.TICKER:
                self.last_ticker[ev.data.get("symbol", "")] = ev.data
            elif ev.type == EventType.FILL:
                self.fill_events.append(ev)
        return events

    def get_price(self, pair: str) -> float:
        return self.last_ticker.get(pair.replace("/", ""), {}).get("last", 0.0)