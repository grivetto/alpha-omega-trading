#!/usr/bin/env python3
"""
DENARO V2 - Core Exchange Abstraction
Professional-grade exchange interface with connection pooling, rate limiting,
and error recovery.
"""
import asyncio
import logging
import time
import os
from typing import Optional

logger = logging.getLogger("Denaro.Exchange")


class ExchangeClient:
    """Unified exchange client with connection management."""

    def __init__(self, api_key: str, api_secret: str, testnet: bool = False):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self._exchange = None
        self._last_request = 0
        self._request_count = 0
        self._rate_limit_reset = 0

    async def connect(self):
        """Initialize exchange connection."""
        import ccxt.async_support as ccxt
        self._exchange = ccxt.binance({
            'apiKey': self.api_key,
            'secret': self.api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot',
                'adjustForTimeDifference': True,
            },
        })
        if self.testnet:
            self._exchange.set_sandbox_mode(True)
        logger.info(f"Exchange connected (testnet={self.testnet})")

    async def close(self):
        """Close exchange connection."""
        if self._exchange:
            try:
                await self._exchange.close()
            except Exception:
                pass
            self._exchange = None
            logger.info("Exchange connection closed")

    @property
    def exchange(self):
        if not self._exchange:
            raise RuntimeError("Exchange not connected. Call connect() first.")
        return self._exchange

    async def fetch_balance(self) -> dict:
        """Fetch account balance."""
        raw = await self.exchange.fetch_balance()
        balance = {}
        for symbol, data in raw.items():
            if isinstance(data, dict) and 'total' in data:
                total = data.get('total') or 0
                free = data.get('free') or 0
                used = data.get('used') or 0
                if total > 0:
                    balance[symbol] = {'total': total, 'free': free, 'used': used}
        return balance

    async def fetch_ticker(self, symbol: str) -> dict:
        """Fetch ticker data."""
        raw = await self.exchange.fetch_ticker(symbol)
        return {
            'symbol': symbol,
            'last': raw.get('last', 0),
            'bid': raw.get('bid', 0),
            'ask': raw.get('ask', 0),
            'high': raw.get('high', 0),
            'low': raw.get('low', 0),
            'volume': raw.get('baseVolume', 0),
            'quote_volume': raw.get('quoteVolume', 0),
            'timestamp': raw.get('timestamp', 0),
        }

    async def fetch_ohlcv(self, symbol: str, timeframe: str = '1m', limit: int = 100) -> list:
        """Fetch OHLCV candles."""
        raw = await self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        return raw

    async def fetch_order_book(self, symbol: str, limit: int = 20) -> dict:
        """Fetch order book."""
        raw = await self.exchange.fetch_order_book(symbol, limit)
        return {
            'bids': raw.get('bids', []),
            'asks': raw.get('asks', []),
            'timestamp': raw.get('timestamp', 0),
        }

    async def create_limit_buy(self, symbol: str, amount: float, price: float,
                                params: Optional[dict] = None) -> Optional[dict]:
        """Place limit buy order."""
        try:
            # Get market precision
            market = self._exchange.markets.get(symbol) if self._exchange else None
            if market:
                amt_prec = market.get('precision', {}).get('amount')
                price_prec = market.get('precision', {}).get('price')
                if isinstance(amt_prec, (int, float)) and amt_prec:
                    if isinstance(amt_prec, int):
                        amount = round(amount, amt_prec)
                    else:
                        decimals = len(str(amt_prec).split('.')[1]) if '.' in str(amt_prec) else 0
                        amount = round(amount, decimals)
                if isinstance(price_prec, (int, float)) and price_prec:
                    if isinstance(price_prec, int):
                        price = round(price, price_prec)
                    else:
                        decimals = len(str(price_prec).split('.')[1]) if '.' in str(price_prec) else 0
                        price = round(price, decimals)

            if amount <= 0 or price <= 0:
                logger.warning(f"Invalid order params: amount={amount} price={price}")
                return None

            order = await self.exchange.create_order(symbol, 'limit', 'buy', amount, price, params)
            return self._normalize_order(order)
        except Exception as e:
            logger.error(f"Limit buy failed {symbol}: {e}")
            return None

    async def create_limit_sell(self, symbol: str, amount: float, price: float,
                                 params: Optional[dict] = None) -> Optional[dict]:
        """Place limit sell order."""
        try:
            market = self._exchange.markets.get(symbol) if self._exchange else None
            if market:
                amt_prec = market.get('precision', {}).get('amount')
                price_prec = market.get('precision', {}).get('price')
                if isinstance(amt_prec, (int, float)) and amt_prec:
                    if isinstance(amt_prec, int):
                        amount = round(amount, amt_prec)
                    else:
                        decimals = len(str(amt_prec).split('.')[1]) if '.' in str(amt_prec) else 0
                        amount = round(amount, decimals)
                if isinstance(price_prec, (int, float)) and price_prec:
                    if isinstance(price_prec, int):
                        price = round(price, price_prec)
                    else:
                        decimals = len(str(price_prec).split('.')[1]) if '.' in str(price_prec) else 0
                        price = round(price, decimals)

            if amount <= 0 or price <= 0:
                logger.warning(f"Invalid order params: amount={amount} price={price}")
                return None

            order = await self.exchange.create_order(symbol, 'limit', 'sell', amount, price, params)
            return self._normalize_order(order)
        except Exception as e:
            logger.error(f"Limit sell failed {symbol}: {e}")
            return None

    async def create_market_buy(self, symbol: str, amount: float) -> Optional[dict]:
        """Place market buy order."""
        try:
            amount = round(amount, 5)
            if amount <= 0:
                return None
            order = await self.exchange.create_order(symbol, 'market', 'buy', amount)
            return self._normalize_order(order)
        except Exception as e:
            logger.error(f"Market buy failed {symbol}: {e}")
            return None

    async def create_market_sell(self, symbol: str, amount: float) -> Optional[dict]:
        """Place market sell order."""
        try:
            amount = round(amount, 5)
            if amount <= 0:
                return None
            order = await self.exchange.create_order(symbol, 'market', 'sell', amount)
            return self._normalize_order(order)
        except Exception as e:
            logger.error(f"Market sell failed {symbol}: {e}")
            return None

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel an order."""
        try:
            await self.exchange.cancel_order(order_id, symbol)
            return True
        except Exception as e:
            logger.error(f"Cancel order failed {symbol}/{order_id}: {e}")
            return False

    async def fetch_open_orders(self, symbol: Optional[str] = None) -> list:
        """Fetch open orders."""
        try:
            if symbol:
                raw = await self.exchange.fetch_open_orders(symbol)
            else:
                raw = await self.exchange.fetch_open_orders()
            return [self._normalize_order(o) for o in raw]
        except Exception as e:
            logger.error(f"Fetch open orders failed: {e}")
            return []

    async def fetch_order(self, order_id: str, symbol: str) -> Optional[dict]:
        """Fetch order status."""
        try:
            raw = await self.exchange.fetch_order(order_id, symbol)
            return self._normalize_order(raw)
        except Exception as e:
            logger.error(f"Fetch order failed {symbol}/{order_id}: {e}")
            return None

    async def fetch_my_trades(self, symbol: str, limit: int = 10) -> list:
        """Fetch recent trades."""
        try:
            raw = await self.exchange.fetch_my_trades(symbol, limit=limit)
            return [self._normalize_trade(t) for t in raw]
        except Exception as e:
            logger.error(f"Fetch trades failed {symbol}: {e}")
            return []

    def _normalize_order(self, order: dict) -> dict:
        """Normalize order format."""
        return {
            'id': order.get('id', ''),
            'symbol': order.get('symbol', ''),
            'side': order.get('side', ''),
            'type': order.get('type', ''),
            'amount': order.get('amount', 0) or 0,
            'price': order.get('price', 0) or 0,
            'average': order.get('average', 0) or 0,
            'filled': order.get('filled', 0) or 0,
            'remaining': order.get('remaining', 0) or 0,
            'status': order.get('status', 'open'),
            'fee': order.get('fee', {}),
            'timestamp': order.get('timestamp', 0),
        }

    def _normalize_trade(self, trade: dict) -> dict:
        """Normalize trade format."""
        return {
            'id': trade.get('id', ''),
            'symbol': trade.get('symbol', ''),
            'side': trade.get('side', ''),
            'amount': trade.get('amount', 0) or 0,
            'price': trade.get('price', 0) or 0,
            'cost': trade.get('cost', 0) or 0,
            'fee': trade.get('fee', {}),
            'timestamp': trade.get('timestamp', 0),
            'datetime': trade.get('datetime', ''),
        }

    def _round_amount(self, symbol: str, amount: float) -> float:
        """Round amount to exchange precision."""
        if not self._exchange:
            return amount
        try:
            market = self._exchange.markets.get(symbol)
            if market and 'precision' in market:
                precision = market['precision'].get('amount')
                if precision is not None:
                    if isinstance(precision, int):
                        return round(amount, precision)
                    else:
                        # Decimal precision
                        decimals = len(str(precision).split('.')[1]) if '.' in str(precision) else 0
                        return round(amount, decimals)
        except Exception:
            pass
        return round(amount, 5)

    def _round_price(self, symbol: str, price: float) -> float:
        """Round price to exchange precision."""
        if not self._exchange:
            return price
        try:
            market = self._exchange.markets.get(symbol)
            if market and 'precision' in market:
                precision = market['precision'].get('price')
                if precision is not None:
                    if isinstance(precision, int):
                        return round(price, precision)
                    else:
                        decimals = len(str(precision).split('.')[1]) if '.' in str(precision) else 0
                        return round(price, decimals)
        except Exception:
            pass
        return round(price, 2)

    async def get_market_info(self, symbol: str) -> dict:
        """Get market info including limits and precision."""
        if not self._exchange:
            return {}
        try:
            market = self._exchange.markets.get(symbol)
            if not market:
                market = await self.exchange.load_market(symbol)
            return {
                'symbol': symbol,
                'base': market.get('base', ''),
                'quote': market.get('quote', ''),
                'precision': market.get('precision', {}),
                'limits': market.get('limits', {}),
                'active': market.get('active', False),
            }
        except Exception as e:
            logger.error(f"Get market info failed {symbol}: {e}")
            return {}
