"""ATLAS CCXT Adapter - Exchange connector implementation using ccxt.async_support."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import AsyncIterator, Optional

import ccxt.async_support as ccxt
import ccxt.pro as ccxtpro

from atlas.connector.interface import ExchangeConnector
from atlas.connector.models import Ticker, OrderBook, Balance
from atlas.execution.models import OrderRequest, OrderResponse, CancelResponse, OrderSide, OrderType, OrderStatus, TimeInForce
from atlas.core.resilience import exchange_call

logger = logging.getLogger(__name__)


class CCXTAdapter(ExchangeConnector):
    """CCXT-based exchange adapter with resilience patterns."""

    def __init__(
        self,
        exchange_id: str,
        api_key: str = "",
        api_secret: str = "",
        passphrase: str = "",
        sandbox: bool = False,
        testnet: bool = False,
        rate_limit_rps: float = 5.0,
        rate_limit_burst: int = 10,
        hostname: str = "",
    ):
        self._exchange_id = exchange_id.lower()
        self._api_key = api_key
        self._api_secret = api_secret
        self._passphrase = passphrase
        self._sandbox = sandbox
        self._testnet = testnet
        self._rate_limit_rps = rate_limit_rps
        self._rate_limit_burst = rate_limit_burst
        self._hostname = hostname

        self._exchange: Optional[ccxt.Exchange] = None
        self._ws_exchange: Optional[ccxtpro.Exchange] = None
        self._connected = False

    @property
    def exchange_id(self) -> str:
        return self._exchange_id

    def _create_exchange(self) -> ccxt.Exchange:
        exchange_class = getattr(ccxt, self._exchange_id)
        config = {
            "apiKey": self._api_key,
            "secret": self._api_secret,
            "enableRateLimit": True,
            "rateLimit": int(1000 / self._rate_limit_rps),
        }
        if self._passphrase:
            config["password"] = self._passphrase
        if self._sandbox:
            config["test"] = True
        if self._hostname:
            config["hostname"] = self._hostname
            config["urls"] = {"api": {"public": f"https://{self._hostname}", "private": f"https://{self._hostname}"}}
        return exchange_class(config)

    def _create_ws_exchange(self) -> ccxtpro.Exchange:
        exchange_class = getattr(ccxtpro, self._exchange_id)
        config = {
            "apiKey": self._api_key,
            "secret": self._api_secret,
            "enableRateLimit": True,
        }
        if self._passphrase:
            config["password"] = self._passphrase
        if self._sandbox:
            config["test"] = True
        if self._hostname:
            config["hostname"] = self._hostname
        return exchange_class(config)

    @exchange_call(max_retries=3, cb_failures=5)
    async def connect(self) -> None:
        if self._connected:
            return
        self._exchange = self._create_exchange()
        self._ws_exchange = self._create_ws_exchange()
        await self._exchange.load_markets()
        if self._ws_exchange:
            await self._ws_exchange.load_markets()
        self._connected = True
        logger.info(f"Connected to {self._exchange_id} (sandbox={self._sandbox})")

    @exchange_call(max_retries=2, cb_failures=3)
    async def disconnect(self) -> None:
        if self._exchange:
            await self._exchange.close()
        if self._ws_exchange:
            await self._ws_exchange.close()
        self._connected = False
        logger.info(f"Disconnected from {self._exchange_id}")

    def _normalize_symbol(self, symbol: str) -> str:
        return symbol

    def _safe_timestamp(self, data: dict) -> int:
        """Safely extract timestamp from exchange response."""
        ts = data.get("timestamp")
        if ts is None:
            return int(time.time() * 1000)
        if isinstance(ts, str):
            return int(float(ts))
        return int(ts)

    def _map_order_type(self, order_type: OrderType) -> str:
        return "limit" if order_type == OrderType.LIMIT else "market"

    def _map_side(self, side: OrderSide) -> str:
        return side.value.lower()

    def _map_status(self, status: str) -> OrderStatus:
        if not status:
            return OrderStatus.OPEN
        status = status.lower()
        if status in ("open", "pending"):
            return OrderStatus.OPEN
        elif status == "closed":
            return OrderStatus.FILLED
        elif status == "canceled":
            return OrderStatus.CANCELLED
        elif status == "rejected":
            return OrderStatus.REJECTED
        elif status == "expired":
            return OrderStatus.EXPIRED
        else:
            return OrderStatus.OPEN

    @exchange_call(max_retries=3, timeout_seconds=10.0)
    async def fetch_ticker(self, symbol: str) -> Ticker:
        ex_symbol = self._normalize_symbol(symbol)
        data = await self._exchange.fetch_ticker(ex_symbol)
        return Ticker(
            symbol=symbol,
            exchange=self._exchange_id,
            bid=float(data.get("bid", 0) or 0),
            ask=float(data.get("ask", 0) or 0),
            last=float(data.get("last", 0) or data.get("close", 0) or 0),
            high=float(data.get("high", 0) or 0),
            low=float(data.get("low", 0) or 0),
            open=float(data.get("open", 0) or 0),
            close=float(data.get("close", 0) or 0),
            volume=float(data.get("baseVolume", 0) or data.get("quoteVolume", 0) or 0),
            timestamp=self._safe_timestamp(data),
        )

    @exchange_call(max_retries=3, timeout_seconds=10.0)
    async def fetch_order_book(self, symbol: str, limit: int = 100) -> OrderBook:
        ex_symbol = self._normalize_symbol(symbol)
        data = await self._exchange.fetch_order_book(ex_symbol, limit=limit)
        return OrderBook(
            symbol=symbol,
            exchange=self._exchange_id,
            bids=[(float(b[0]), float(b[1])) for b in data.get("bids", [])[:limit]],
            asks=[(float(a[0]), float(a[1])) for a in data.get("asks", [])[:limit]],
            timestamp=self._safe_timestamp(data),
        )

    @exchange_call(max_retries=3, timeout_seconds=10.0)
    async def fetch_balance(self) -> dict[str, Balance]:
        data = await self._exchange.fetch_balance()
        balances = {}
        for currency, amounts in data.get("total", {}).items():
            if amounts and amounts > 0:
                free = float(data.get("free", {}).get(currency, 0) or 0)
                used = float(data.get("used", {}).get(currency, 0) or 0)
                total = float(amounts)
                if total > 0:
                    balances[currency] = Balance(
                        currency=currency,
                        free=free,
                        used=used,
                        total=total,
                        exchange=self._exchange_id,
                    )
        return balances

    @exchange_call(max_retries=2, timeout_seconds=15.0)
    async def create_order(self, order: OrderRequest) -> OrderResponse:
        ex_symbol = self._normalize_symbol(order.symbol)
        order_type = self._map_order_type(order.type)
        side = self._map_side(order.side)

        params = {}
        if order.time_in_force == TimeInForce.IOC:
            params["timeInForce"] = "IOC"
        elif order.time_in_force == TimeInForce.FOK:
            params["timeInForce"] = "FOK"
        params["clientOrderId"] = order.idempotency_key

        result = await self._exchange.create_order(
            symbol=ex_symbol,
            type=order_type,
            side=side,
            amount=order.amount,
            price=order.price,
            params=params,
        )

        return OrderResponse(
            exchange_order_id=str(result.get("id", "")),
            client_order_id=order.idempotency_key,
            symbol=order.symbol,
            side=order.side,
            type=order.type,
            amount=float(result.get("amount", order.amount)),
            price=float(result.get("price", order.price or 0)),
            filled=float(result.get("filled", 0) or 0),
            status=self._map_status(result.get("status", "open")),
            timestamp=self._safe_timestamp(result),
            exchange=self._exchange_id,
            fee=float((result.get("fee") or {}).get("cost", 0) or 0),
            fee_currency=(result.get("fee") or {}).get("currency", "") or "",
        )

    @exchange_call(max_retries=2, timeout_seconds=10.0)
    async def cancel_order(self, order_id: str, symbol: str) -> CancelResponse:
        ex_symbol = self._normalize_symbol(symbol)
        result = await self._exchange.cancel_order(order_id, ex_symbol)
        return CancelResponse(
            exchange_order_id=order_id,
            client_order_id="",
            success=result.get("status") == "canceled",
            status=self._map_status(result.get("status", "canceled")),
            timestamp=self._safe_timestamp(result),
            exchange=self._exchange_id,
        )

    @exchange_call(max_retries=3, timeout_seconds=10.0)
    async def fetch_order(self, order_id: str, symbol: str) -> OrderResponse:
        ex_symbol = self._normalize_symbol(symbol)
        result = await self._exchange.fetch_order(order_id, ex_symbol)
        return OrderResponse(
            exchange_order_id=str(result.get("id", "")),
            client_order_id=result.get("clientOrderId", ""),
            symbol=symbol,
            side=OrderSide.BUY if result.get("side") == "buy" else OrderSide.SELL,
            type=OrderType.LIMIT if result.get("type") == "limit" else OrderType.MARKET,
            amount=float(result.get("amount", 0)),
            price=float(result.get("price", 0) or 0),
            filled=float(result.get("filled", 0) or 0),
            status=self._map_status(result.get("status", "open")),
            timestamp=self._safe_timestamp(result),
            exchange=self._exchange_id,
            fee=float((result.get("fee") or {}).get("cost", 0) or 0),
            fee_currency=(result.get("fee") or {}).get("currency", "") or "",
        )

    @exchange_call(max_retries=3, timeout_seconds=10.0)
    async def fetch_open_orders(self, symbol: str = "") -> list[OrderResponse]:
        """Fetch open orders, optionally filtered by symbol."""
        ex_symbol = self._normalize_symbol(symbol) if symbol else None
        results = await self._exchange.fetch_open_orders(ex_symbol)
        orders = []
        for result in results:
            orders.append(OrderResponse(
                exchange_order_id=str(result.get("id", "")),
                client_order_id=result.get("clientOrderId") or "",
                symbol=result.get("symbol") or symbol,
                side=OrderSide.BUY if result.get("side") == "buy" else OrderSide.SELL,
                type=OrderType.LIMIT if result.get("type") == "limit" else OrderType.MARKET,
                amount=float(result.get("amount", 0) or 0),
                price=float(result.get("price", 0) or 0),
                filled=float(result.get("filled", 0) or 0),
                status=self._map_status(result.get("status")),
                timestamp=self._safe_timestamp(result),
                exchange=self._exchange_id,
                fee=float((result.get("fee") or {}).get("cost", 0) or 0),
                fee_currency=(result.get("fee") or {}).get("currency", "") or "",
            ))
        return orders

    async def watch_ticker(self, symbol: str) -> AsyncIterator[Ticker]:
        if not self._ws_exchange:
            self._ws_exchange = self._create_ws_exchange()
            await self._ws_exchange.load_markets()

        ex_symbol = self._normalize_symbol(symbol)
        while True:
            try:
                data = await self._ws_exchange.watch_ticker(ex_symbol)
                yield Ticker(
                    symbol=symbol,
                    exchange=self._exchange_id,
                    bid=float(data.get("bid", 0) or 0),
                    ask=float(data.get("ask", 0) or 0),
                    last=float(data.get("last", 0) or data.get("close", 0) or 0),
                    high=float(data.get("high", 0) or 0),
                    low=float(data.get("low", 0) or 0),
                    open=float(data.get("open", 0) or 0),
                    close=float(data.get("close", 0) or 0),
                    volume=float(data.get("baseVolume", 0) or data.get("quoteVolume", 0) or 0),
                    timestamp=self._safe_timestamp(data),
                )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"WS ticker error for {symbol}: {e}")
                await asyncio.sleep(5)

    async def watch_order_book(self, symbol: str) -> AsyncIterator[OrderBook]:
        if not self._ws_exchange:
            self._ws_exchange = self._create_ws_exchange()
            await self._ws_exchange.load_markets()

        ex_symbol = self._normalize_symbol(symbol)
        while True:
            try:
                data = await self._ws_exchange.watch_order_book(ex_symbol)
                yield OrderBook(
                    symbol=symbol,
                    exchange=self._exchange_id,
                    bids=[(float(b[0]), float(b[1])) for b in data.get("bids", [])],
                    asks=[(float(a[0]), float(a[1])) for a in data.get("asks", [])],
                    timestamp=self._safe_timestamp(data),
                )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"WS orderbook error for {symbol}: {e}")
                await asyncio.sleep(5)