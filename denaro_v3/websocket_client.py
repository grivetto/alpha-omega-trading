"""Denaro v4 WebSocket Client — Real-time Binance streams.

Uses the `websockets` library for reliable WebSocket connections.
- TickerStream: 1 stream per pair, ~100ms price updates
- UserDataStream: execution reports + balance updates (instant fill detection)

Usage:
    ws = WebSocketClient(exchange, pairs=["SOL/USDC"])
    await ws.start()
    event = await ws.get_event()  # in main loop
"""

from __future__ import annotations

import asyncio
import json
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import websockets
from loguru import logger


# ═══════════════════════════════════════════════════════════════════
# Events
# ═══════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════
# Ticker Stream
# ═══════════════════════════════════════════════════════════════════

class TickerStream:
    """Live ticker via Binance WebSocket. ~100ms updates.

    Stream URL: wss://stream.binance.com:9443/ws/<symbol>@ticker
    """

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
                    logger.info(f"Ticker stream connected: {self._symbol}")
                    async for message in ws:
                        if not self._running:
                            break
                        try:
                            data = json.loads(message)
                            if data.get("e") == "24hrTicker":
                                await self._queue.put(WsEvent(
                                    type=EventType.TICKER,
                                    data={
                                        "symbol": data["s"],
                                        "last": float(data["c"]),
                                        "bid": float(data["b"]),
                                        "ask": float(data["a"]),
                                        "volume": float(data["v"]),
                                    },
                                ))
                        except (json.JSONDecodeError, KeyError):
                            pass
            except (websockets.ConnectionClosed, ConnectionError, OSError) as e:
                logger.warning(f"Ticker stream {self._symbol} disconnected: {e}")

            if self._running:
                logger.info(f"Reconnecting ticker {self._symbol} in 3s...")
                await asyncio.sleep(3)

    async def stop(self):
        self._running = False


# ═══════════════════════════════════════════════════════════════════
# User Data Stream (fills + balance)
# ═══════════════════════════════════════════════════════════════════

class UserDataStream:
    """Binance User Data Stream for execution reports and balance updates.

    Flow:
      1. POST /api/v3/userDataStream → listenKey
      2. Connect wss://stream.binance.com:9443/ws/<listenKey>
      3. Receive executionReport + outboundAccountPosition events
      4. Keep-alive: PUT every 30min
    """

    def __init__(self, exchange, queue: asyncio.Queue):
        self._exchange = exchange
        self._queue = queue
        self._listen_key: Optional[str] = None
        self._running = False
        self._keepalive_task: Optional[asyncio.Task] = None

    async def _get_listen_key(self) -> str:
        """Create a new listen key via REST API."""
        try:
            import requests
            resp = requests.post(
                "https://api.binance.com/api/v3/userDataStream",
                headers={"X-MBX-APIKEY": self._exchange.apiKey},
                timeout=10,
            )
            return resp.json()["listenKey"]
        except Exception as e:
            logger.error(f"Failed to get listen key: {e}")
            return ""

    async def _keepalive(self):
        """Keep listen key alive (PUT every 30 minutes)."""
        while self._running and self._listen_key:
            await asyncio.sleep(1800)
            if not self._running:
                break
            try:
                import requests
                requests.put(
                    "https://api.binance.com/api/v3/userDataStream",
                    headers={"X-MBX-APIKEY": self._exchange.apiKey},
                    data={"listenKey": self._listen_key},
                    timeout=10,
                )
            except Exception as e:
                logger.warning(f"Keepalive failed: {e}")

    async def start(self):
        self._running = True
        while self._running:
            try:
                self._listen_key = await self._get_listen_key()
                if not self._listen_key:
                    logger.error("No listen key, retrying in 30s...")
                    await asyncio.sleep(30)
                    continue

                logger.info("User data stream connected")
                self._keepalive_task = asyncio.create_task(self._keepalive())

                url = f"wss://stream.binance.com:9443/ws/{self._listen_key}"
                async with websockets.connect(url, ping_interval=20) as ws:
                    async for message in ws:
                        if not self._running:
                            break
                        try:
                            data = json.loads(message)
                            event_type = data.get("e", "")

                            if event_type == "executionReport":
                                status = data.get("X", "")
                                if status in ("FILLED", "PARTIALLY_FILLED"):
                                    await self._queue.put(WsEvent(
                                        type=EventType.FILL,
                                        data={
                                            "symbol": data["s"],
                                            "side": data["S"].lower(),
                                            "amount": float(data["l"]),
                                            "price": float(data["L"]),
                                            "order_id": str(data["i"]),
                                            "status": status,
                                            "filled": float(data["z"]),
                                            "total": float(data["q"]),
                                            "fee": float(data.get("n", 0)),
                                            "fee_asset": data.get("N", ""),
                                            "is_maker": data.get("m", False),
                                        },
                                    ))

                            elif event_type == "outboundAccountPosition":
                                await self._queue.put(WsEvent(
                                    type=EventType.BALANCE,
                                    data={
                                        "balances": {
                                            b["a"]: {
                                                "free": float(b["f"]),
                                                "locked": float(b["l"]),
                                            }
                                            for b in data.get("B", [])
                                        },
                                    },
                                ))
                        except (json.JSONDecodeError, KeyError):
                            pass

            except (websockets.ConnectionClosed, ConnectionError, OSError) as e:
                logger.warning(f"User data stream disconnected: {e}")
            finally:
                if self._keepalive_task:
                    self._keepalive_task.cancel()

            if self._running:
                logger.info("Reconnecting user data stream in 5s...")
                await asyncio.sleep(5)

    async def stop(self):
        self._running = False
        if self._keepalive_task:
            self._keepalive_task.cancel()


# ═══════════════════════════════════════════════════════════════════
# WebSocket Client (unified)
# ═══════════════════════════════════════════════════════════════════

class WebSocketClient:
    """Unified WebSocket manager for Binance.

    Starts ticker streams + user data stream.
    Events consumed via drain_events() in the main loop.
    REST fallback via DataFeeder when WebSocket is disconnected.
    """

    def __init__(self, exchange, pairs: list[str]):
        self._exchange = exchange
        self._pairs = pairs
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        self._ticker_streams: list[TickerStream] = []
        self._user_stream: Optional[UserDataStream] = None
        self._tasks: list[asyncio.Task] = []
        self._running = False

        # Real-time state (updated by WS events, read by main loop)
        self.last_ticker: dict[str, dict] = {}
        self.fill_events: deque[WsEvent] = deque(maxlen=1000)

    async def start(self):
        """Start all WebSocket streams."""
        self._running = True

        for pair in self._pairs:
            stream = TickerStream(pair, self._queue)
            self._ticker_streams.append(stream)
            self._tasks.append(asyncio.create_task(stream.start()))

        self._user_stream = UserDataStream(self._exchange, self._queue)
        self._tasks.append(asyncio.create_task(self._user_stream.start()))

        logger.info(f"WebSocket client started: {len(self._pairs)} pairs")

    async def stop(self):
        """Stop all streams gracefully."""
        self._running = False
        for stream in self._ticker_streams:
            await stream.stop()
        if self._user_stream:
            await self._user_stream.stop()
        for task in self._tasks:
            task.cancel()
        logger.info("WebSocket client stopped")

    async def get_event(self, timeout: float = 1.0) -> Optional[WsEvent]:
        """Get next WebSocket event with timeout."""
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    async def drain_events(self) -> list[WsEvent]:
        """Drain all pending events. Call once per loop cycle."""
        events = []
        while True:
            event = await self.get_event(timeout=0.01)
            if event is None:
                break
            events.append(event)
            if event.type == EventType.TICKER:
                self.last_ticker[event.data.get("symbol", "")] = event.data
            elif event.type == EventType.FILL:
                self.fill_events.append(event)
        return events

    def get_price(self, pair: str) -> float:
        """Latest price for a pair. Falls back to 0."""
        symbol = pair.replace("/", "")
        return self.last_ticker.get(symbol, {}).get("last", 0.0)
