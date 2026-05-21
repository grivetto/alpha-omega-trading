#!/usr/bin/env python3
"""
DENARO V2 - Market Scanner
Real-time multi-pair scanning for trading opportunities.
"""
import asyncio
import logging
import time
from typing import Optional

logger = logging.getLogger("Denaro.Scanner")


class MarketScanner:
    """Scans multiple pairs for trading opportunities."""

    def __init__(self, exchange, symbols: list = None):
        self.exchange = exchange
        self.symbols = symbols or [
            'SOL/EUR', 'ETH/EUR', 'BTC/EUR', 'ADA/EUR', 'XRP/EUR',
            'BNB/EUR', 'AVAX/EUR', 'DOT/EUR', 'MATIC/EUR', 'LINK/EUR',
        ]
        self.tickers = {}
        self.orderbooks = {}
        self.ohlcv_cache = {}
        self._last_scan = 0
        self._scan_interval = 2  # seconds

    async def scan(self) -> dict:
        """Perform a full market scan."""
        now = time.time()
        if now - self._last_scan < self._scan_interval:
            return self._build_opportunity_map()

        self._last_scan = now
        await asyncio.gather(
            self._fetch_all_tickers(),
            self._fetch_all_orderbooks(),
            return_exceptions=True,
        )
        return self._build_opportunity_map()

    async def _fetch_all_tickers(self):
        """Fetch tickers for all symbols."""
        tasks = {}
        for symbol in self.symbols:
            try:
                tasks[symbol] = self.exchange.fetch_ticker(symbol)
            except Exception as e:
                logger.debug(f"Ticker fetch failed {symbol}: {e}")

        if tasks:
            results = await asyncio.gather(*tasks.values(), return_exceptions=True)
            for symbol, result in zip(tasks.keys(), results):
                if isinstance(result, dict):
                    self.tickers[symbol] = result

    async def _fetch_all_orderbooks(self):
        """Fetch order books for active symbols."""
        tasks = {}
        for symbol in self.symbols[:5]:  # Limit to top 5 for performance
            try:
                tasks[symbol] = self.exchange.fetch_order_book(symbol, limit=10)
            except Exception as e:
                logger.debug(f"Orderbook fetch failed {symbol}: {e}")

        if tasks:
            results = await asyncio.gather(*tasks.values(), return_exceptions=True)
            for symbol, result in zip(tasks.keys(), results):
                if isinstance(result, dict):
                    self.orderbooks[symbol] = result

    async def fetch_ohlcv(self, symbol: str, timeframe: str = '1m', limit: int = 100) -> list:
        """Fetch OHLCV with caching."""
        cache_key = f"{symbol}_{timeframe}_{limit}"
        now = time.time()

        if cache_key in self.ohlcv_cache:
            cached = self.ohlcv_cache[cache_key]
            if now - cached['timestamp'] < 30:  # 30s cache
                return cached['data']

        try:
            data = await self.exchange.fetch_ohlcv(symbol, timeframe, limit)
            self.ohlcv_cache[cache_key] = {'data': data, 'timestamp': now}
            return data
        except Exception as e:
            logger.debug(f"OHLCV fetch failed {symbol}: {e}")
            return []

    def _build_opportunity_map(self) -> dict:
        """Build opportunity map from scanned data."""
        opportunities = {}

        for symbol, ticker in self.tickers.items():
            if not ticker or ticker.get('last', 0) <= 0:
                continue

            vol_24h = ticker.get('quote_volume', 0)
            if vol_24h < 100000:  # Skip low volume pairs
                continue

            spread = 0
            if ticker.get('ask', 0) > 0 and ticker.get('bid', 0) > 0:
                spread = (ticker['ask'] - ticker['bid']) / ticker['bid'] * 100

            price_change = 0
            if ticker.get('high', 0) > 0 and ticker.get('low', 0) > 0:
                price_change = (ticker['high'] - ticker['low']) / ticker['low'] * 100

            opportunities[symbol] = {
                'price': ticker['last'],
                'bid': ticker.get('bid', 0),
                'ask': ticker.get('ask', 0),
                'spread_pct': spread,
                'volatility_24h': price_change,
                'volume_24h': vol_24h,
                'high_24h': ticker.get('high', 0),
                'low_24h': ticker.get('low', 0),
            }

        return opportunities

    def get_best_pairs(self, min_volume: float = 500000, max_spread: float = 0.1) -> list:
        """Get best trading pairs by volume and spread."""
        best = []
        for symbol, data in self.tickers.items():
            if not data:
                continue
            vol = data.get('quote_volume', 0)
            spread = 0
            if data.get('ask', 0) > 0:
                spread = (data['ask'] - data.get('bid', 0)) / data['ask'] * 100

            if vol >= min_volume and spread <= max_spread:
                best.append({
                    'symbol': symbol,
                    'price': data.get('last', 0),
                    'volume': vol,
                    'spread': spread,
                })

        best.sort(key=lambda x: x['volume'], reverse=True)
        return best
