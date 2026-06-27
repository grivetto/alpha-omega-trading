"""WebSocket-powered engine — sub-millisecond price reads, zero API rate burn."""
import json
import time
import threading
from typing import Dict, Optional, Tuple

try:
    import websocket
except ImportError:
    websocket = None

from engine import BinanceEngine


class WSEngine(BinanceEngine):
    """BinanceEngine with WebSocket price + order-book cache.

    Prices and order books update in real-time via a background thread.
    REST calls are used only for orders and balances (authenticated endpoints).
    """

    def __init__(self, config_path: str = "config/war_config.json"):
        super().__init__(config_path)

        # Real-time caches (updated by WS thread)
        self._prices: Dict[str, float] = {}         # symbol -> last price
        self._order_books: Dict[str, dict] = {}      # symbol -> {"bids": [...], "asks": [...]}
        self._ws_connected = False
        self._ws_thread: Optional[threading.Thread] = None
        self._ws_running = False
        self._ws_lock = threading.Lock()

        # Symbols to track
        self._symbols = self.config.get("symbols", ["SOLUSDC"])
        self._streams_connected: Dict[str, bool] = {}

        # Start WS in background if websocket library available
        if websocket:
            self._start_ws()

    # ── WebSocket background thread ────────────────────────
    def _start_ws(self):
        """Launch WebSocket connection in a daemon thread."""
        self._ws_running = True
        self._ws_thread = threading.Thread(target=self._ws_loop, daemon=True)
        self._ws_thread.start()

    def _ws_loop(self):
        """Connect to Binance combined streams and process messages."""
        # Combined stream: tickers (price) + depth@100ms (order book) for all symbols
        streams = []
        for sym in self._symbols:
            streams.append(f"{sym.lower()}@ticker")
            streams.append(f"{sym.lower()}@depth20@100ms")

        stream_url = f"wss://stream.binance.com:9443/stream?streams={'/'.join(streams)}"
        base_url = self.config.get("exchanges", {}).get("binance", {}).get("ws_url",
                        "wss://stream.binance.com:9443/ws")

        # Build URL using configured WS base
        if base_url.endswith("/ws"):
            stream_url = f"{base_url[:-3]}/stream?streams={'/'.join(streams)}"

        while self._ws_running:
            try:
                ws = websocket.WebSocketApp(
                    stream_url,
                    on_message=self._on_ws_message,
                    on_error=self._on_ws_error,
                    on_close=self._on_ws_close,
                    on_open=self._on_ws_open,
                )
                # Run with ping interval to keep alive
                ws.run_forever(ping_interval=30, ping_timeout=10)
            except Exception as e:
                print(f"  ⚠️ WS connection error: {e} — retrying in 5s")
                time.sleep(5)

    def _on_ws_open(self, ws):
        with self._ws_lock:
            self._ws_connected = True
        print(f"  🔗 WebSocket connected | {len(self._symbols)} symbols")

    def _on_ws_close(self, ws, close_status_code, close_msg):
        with self._ws_lock:
            self._ws_connected = False
        print(f"  🔌 WebSocket disconnected ({close_status_code}) — reconnecting...")

    def _on_ws_error(self, ws, error):
        print(f"  ⚠️ WS error: {str(error)[:100]}")

    def _on_ws_message(self, ws, message):
        """Parse incoming WS message and update caches."""
        try:
            data = json.loads(message)
            stream = data.get("stream", "")
            event = data.get("data", {})

            if "@ticker" in stream:
                sym = event.get("s", "")
                price = float(event.get("c", 0))
                if sym and price > 0:
                    with self._ws_lock:
                        self._prices[sym] = price

            elif "@depth" in stream:
                sym = event.get("s", "")
                if sym:
                    with self._ws_lock:
                        self._order_books[sym] = {
                            "bids": event.get("bids", []),
                            "asks": event.get("asks", []),
                            "ts": time.time()
                        }
        except Exception:
            pass  # Ignore malformed messages

    def stop(self):
        """Stop WebSocket thread."""
        self._ws_running = False

    # ── Overridden methods (WS-first, REST fallback) ──────
    def price(self, symbol: str) -> float:
        """Get price from WS cache (instant) or REST fallback."""
        with self._ws_lock:
            p = self._prices.get(symbol, 0)
        if p > 0:
            return p
        # REST fallback
        return super().price(symbol)

    def order_book_imbalance(self, symbol: str, limit: int = 20) -> Tuple[float, float, float]:
        """Get order book imbalance from WS cache (instant) or REST fallback."""
        with self._ws_lock:
            ob = self._order_books.get(symbol)
        if ob and ob.get("bids") and time.time() - ob.get("ts", 0) < 5:
            bids = ob["bids"][:limit]
            asks = ob["asks"][:limit]
            bid_qty = sum(float(b[1]) for b in bids)
            ask_qty = sum(float(a[1]) for a in asks)
            imbalance = bid_qty / ask_qty if ask_qty > 0 else float('inf')
            return bid_qty, ask_qty, imbalance
        # REST fallback
        return super().order_book_imbalance(symbol, limit)

    # ── WS status ──────────────────────────────────────────
    @property
    def ws_alive(self) -> bool:
        with self._ws_lock:
            return self._ws_connected

    @property
    def ws_prices(self) -> Dict[str, float]:
        with self._ws_lock:
            return dict(self._prices)
