"""Exchange connector wrapping ccxt with async support and error handling."""
from __future__ import annotations
import time
from typing import Optional

import ccxt.async_support as ccxt_async

from core.config import settings
from core.exceptions import ExchangeConnectionError
from core.logger import AgentLogger
from models import MarketSnapshot, MarketRegime

log = AgentLogger.get("exchange")


class ExchangeConnector:
    """Async wrapper around ccxt exchange with resilience logic."""

    def __init__(self, exchange_id: str = "binance"):
        self.exchange_id = exchange_id
        self._exchange: Optional[ccxt_async.Exchange] = None
        self._last_connect_attempt = 0.0

    async def connect(self) -> None:
        """Establish connection to the exchange."""
        now = time.time()
        if now - self._last_connect_attempt < 5.0:
            return  # Throttle reconnection
        self._last_connect_attempt = now

        cfg = settings.exchange
        try:
            exchange_class = getattr(ccxt_async, self.exchange_id)
            self._exchange = exchange_class({
                "apiKey": cfg.api_key,
                "secret": cfg.api_secret,
                "enableRateLimit": cfg.rate_limit,
                "options": {
                    "defaultType": "spot",
                    "recvWindow": cfg.recv_window,
                },
            })
            if cfg.testnet:
                self._exchange.set_sandbox_mode(True)

            await self._exchange.load_markets()
            log.info("Connected to %s (%s)", self.exchange_id,
                     "testnet" if cfg.testnet else "live")

        except Exception as e:
            raise ExchangeConnectionError(self.exchange_id, str(e)) from e

    async def fetch_snapshot(self, symbol: str) -> MarketSnapshot:
        """Fetch a fresh market snapshot for a symbol."""
        if not self._exchange:
            await self.connect()

        ticker = await self._exchange.fetch_ticker(symbol)
        ohlcv_5m = await self._exchange.fetch_ohlcv(symbol, "5m", limit=2)
        ohlcv_1h = await self._exchange.fetch_ohlcv(symbol, "1h", limit=2)

        # Calculate 5m volatility
        vol_5m = 0.0
        if len(ohlcv_5m) >= 2:
            c0, c1 = ohlcv_5m[-2][4], ohlcv_5m[-1][4]
            vol_5m = abs(c1 - c0) / c0 if c0 else 0

        # 1h volatility
        vol_1h = 0.0
        if len(ohlcv_1h) >= 2:
            c0, c1 = ohlcv_1h[-2][4], ohlcv_1h[-1][4]
            vol_1h = abs(c1 - c0) / c0 if c0 else 0

        return MarketSnapshot(
            symbol=symbol,
            price=ticker.get("last"),
            bid=ticker.get("bid"),
            ask=ticker.get("ask"),
            spread_bps=(
                ((ticker["ask"] - ticker["bid"]) / ticker["bid"]) * 10000
                if ticker.get("bid") and ticker.get("ask")
                else None
            ),
            volume_24h=ticker.get("quoteVolume"),
            volatility_5m=vol_5m,
            volatility_1h=vol_1h,
        )

    async def fetch_order_book_imbalance(self, symbol: str, depth: int = 50) -> float:
        """Calculate order book imbalance: (bids - asks) / (bids + asks)."""
        ob = await self._exchange.fetch_order_book(symbol, depth)
        bid_vol = sum(b[1] * b[0] for b in ob["bids"])
        ask_vol = sum(a[1] * a[0] for a in ob["asks"])
        total = bid_vol + ask_vol
        return (bid_vol - ask_vol) / total if total else 0.0

    async def close(self):
        if self._exchange:
            await self._exchange.close()
