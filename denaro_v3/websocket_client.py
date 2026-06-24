"""Denaro v4 WebSocket Client — Real-time Binance streams.

Replaces REST polling with live WebSocket feeds:
  - Ticker: real-time price updates (<100ms latency)
  - User Data: execution reports, balance updates (instant fill detection)

Architecture:
  WebSocketClient
  ├── TickerStream — 1 stream per pair (price updates)
  ├── UserDataStream — 1 stream per API key (fills, balance)
  └── EventQueue — thread-safe queue consumed by main loop

Usage:
  ws = WebSocketClient(exchange, pairs=["SOL/USDC"])
  await ws.start()
  # Main loop consumes ws.events
  event = await ws.get_event()
"""

from __future__ import annotations

import asyncio
import json
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from loguru import logger


# ═══════════════════════════════════════════════════════════════════
# Events
# ═══════════════════════════════════════════════════════════════════

class EventType(str, Enum):
    TICKER = "ticker"
    FILL = "fill"
    BALANCE = "balance"
    ORDER_UPDATE = "order_update"
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
    """Live ticker stream via Binance WebSocket.

    Stream: wss://stream.binance.com:9443/ws/<symbol>@ticker
    Updates: every ~100ms (real-time)
    """

    def __init__(self, symbol: str, queue: asyncio.Queue):
        self._symbol = symbol.lower().replace("/", "")
        self._queue = queue
        self._ws: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._running = False

    @property
    def url(self) -> str:
        return f"wss://stream.binance.com:9443/ws/{self._symbol}@ticker"

    async def start(self):
        self._running = True
        while self._running:
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection("stream.binance.com", 9443, ssl=True),
                    timeout=10,
                )
                self._reader = reader
                self._writer = writer

                # Send subscribe message
                subscribe = json.dumps({
                    "method": "SUBSCRIBE",
                    "params": [f"{self._symbol}@ticker"],
                    "id": 1,
                })
                writer.write(subscribe.encode() + b"\n")
                await writer.drain()

                logger.info(f"Ticker stream connected: {self._symbol}")

                # Read messages
                while self._running:
                    line = await reader.readline()
                    if not line:
                        break
                    try:
                        data = json.loads(line)
                        if "e" in data and data["e"] == "24hrTicker":
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

            except (asyncio.TimeoutError, ConnectionError, OSError) as e:
                logger.warning(f"Ticker stream {self._symbol} disconnected: {e}")
            finally:
                if self._writer:
                    self._writer.close()
                    try:
                        await self._writer.wait_closed()
                    except Exception:
                        pass

            if self._running:
                logger.info(f"Reconnecting ticker stream {self._symbol} in 5s...")
                await asyncio.sleep(5)

    async def stop(self):
        self._running = False
        if self._writer:
            self._writer.close()


# ═══════════════════════════════════════════════════════════════════
# User Data Stream (fills + balance)
# ═══════════════════════════════════════════════════════════════════

class UserDataStream:
    """Binance User Data Stream for execution reports and balance updates.

    Flow:
      1. POST /api/v3/userDataStream → listenKey
      2. Connect to wss://stream.binance.com:9443/ws/<listenKey>
      3. Receive executionReport and outboundAccountPosition events
      4. Keep-alive: PUT /api/v3/userDataStream every 30min

    Events produced:
      - FILL: order executed (partial or full)
      - BALANCE: account balance changed
    """

    def __init__(self, exchange, queue: asyncio.Queue):
        self._exchange = exchange
        self._queue = queue
        self._listen_key: Optional[str] = None
        self._running = False
        self._keepalive_task: Optional[asyncio.Task] = None

    async def _get_listen_key(self) -> str:
        """Create a new listen key via REST API."""
        # Use direct REST call (most reliable across ccxt versions)
        try:
            import requests
            resp = requests.post(
                "https://api.binance.com/api/v3/userDataStream",
                headers={"X-MBX-APIKEY": self._exchange.apiKey},
                timeout=10,
            )
            result = resp.json()
            return result["listenKey"]
        except Exception as e:
            logger.error(f"Failed to get listen key: {e}")
            return ""

    async def _keepalive(self):
        """Keep the listen key alive (PUT every 30 minutes)."""
        while self._running and self._listen_key:
            await asyncio.sleep(1800)  # 30 minutes
            if not self._running:
                break
            try:
                import requests
                requests.put(
                    "https://api.binance.com/api/v3/userDataStream",
                    headers={
                        "X-MBX-APIKEY": self._exchange.apiKey,
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                    data=f"listenKey={self._listen_key}",
                    timeout=10,
                )
                logger.debug("User data stream keepalive sent")
            except Exception as e:
                logger.warning(f"Keepalive failed: {e}")

    async def start(self):
        self._running = True
        while self._running:
            try:
                self._listen_key = await self._get_listen_key()
                if not self._listen_key:
                    logger.error("Failed to get listen key, retrying in 30s...")
                    await asyncio.sleep(30)
                    continue

                logger.info("User data stream listenKey obtained")
                self._keepalive_task = asyncio.create_task(self._keepalive())

                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection("stream.binance.com", 9443, ssl=True),
                    timeout=10,
                )

                logger.info("User data stream connected")

                while self._running:
                    line = await reader.readline()
                    if not line:
                        break
                    try:
                        data = json.loads(line)
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

                writer.close()

            except (asyncio.TimeoutError, ConnectionError, OSError) as e:
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
    Events are consumed via get_event() in the main loop.
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
        self.last_balance: dict[str, dict] = {}
        self.fill_events: deque[WsEvent] = deque(maxlen=1000)

    @property
    def connected(self) -> bool:
        return self._running

    async def start(self):
        """Start all WebSocket streams."""
        self._running = True

        # Start ticker streams (1 per pair)
        for pair in self._pairs:
            stream = TickerStream(pair, self._queue)
            self._ticker_streams.append(stream)
            self._tasks.append(asyncio.create_task(stream.start()))

        # Start user data stream (fills + balance)
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
        """Get next WebSocket event with timeout. Non-blocking for main loop."""
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    async def drain_events(self) -> list[WsEvent]:
        """Drain all pending events from the queue. Call once per loop cycle."""
        events = []
        while True:
            event = await self.get_event(timeout=0.01)
            if event is None:
                break
            events.append(event)

        # Process events into state
        for event in events:
            if event.type == EventType.TICKER:
                symbol = event.data.get("symbol", "")
                self.last_ticker[symbol] = event.data
            elif event.type == EventType.BALANCE:
                self.last_balance = event.data.get("balances", {})
            elif event.type == EventType.FILL:
                self.fill_events.append(event)

        return events

    @property
    def latest_ticker(self) -> dict:
        """Latest ticker data, indexed by exchange symbol (e.g. SOLUSDC)."""
        return self.last_ticker

    def get_price(self, pair: str) -> float:
        """Get latest price for a pair. Falls back to 0 if no data."""
        symbol = pair.replace("/", "")
        return self.last_ticker.get(symbol, {}).get("last", 0.0)
