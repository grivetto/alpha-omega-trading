"""Unified Trading Engine — merges REST + WebSocket logic."""
from __future__ import annotations
import hashlib, hmac, requests, time, json
from typing import Optional

class UnifiedEngine:
    """Single engine replacing engine.py (REST) + stella_engine.py (WebSocket).

    Uses direct REST API calls (no ccxt) for maximum compatibility with
    sub-account API keys that lack sapi permissions.
    """

    def __init__(self, api_key: str, api_secret: str, symbol: str = "SOL/USDC"):
        self.api_key = api_key
        self.secret = api_secret
        self.symbol = symbol
        self.sym = symbol.replace("/", "")  # "SOLUSDC"
        self.base = symbol.split("/")[0]    # "SOL"
        self.quote = symbol.split("/")[1]    # "USDC"

    def _sign(self, qs: str) -> str:
        return hmac.new(self.secret.encode(), qs.encode(), hashlib.sha256).hexdigest()

    def _get(self, path: str, params: str = "") -> dict:
        ts = int(time.time() * 1000)
        q = f"timestamp={ts}&recvWindow=30000"
        if params:
            q += "&" + params
        sig = self._sign(q)
        r = requests.get(f"https://api.binance.com{path}?{q}&signature={sig}",
                         headers={"X-MBX-APIKEY": self.api_key}, timeout=15)
        return r.json() if r.status_code == 200 else {"error": r.text[:200]}

    def _post(self, path: str, params: str = "") -> dict:
        ts = int(time.time() * 1000)
        q = f"timestamp={ts}&recvWindow=30000"
        if params:
            q += "&" + params
        sig = self._sign(q)
        r = requests.post(f"https://api.binance.com{path}?{q}&signature={sig}",
                          headers={"X-MBX-APIKEY": self.api_key}, timeout=15)
        return r.json() if r.status_code == 200 else {"error": r.text[:200]}

    def price(self) -> float:
        r = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={self.sym}", timeout=10)
        return float(r.json()["price"]) if r.status_code == 200 else 0.0

    def balance(self) -> dict:
        b = self._get("/api/v3/account")
        if "balances" in b:
            return {x["asset"]: {"free": float(x["free"]), "locked": float(x["locked"])}
                    for x in b["balances"] if float(x["free"]) > 0 or float(x["locked"]) > 0}
        return {}

    def equity(self) -> float:
        b = self.balance()
        val = b.get(self.quote, {}).get("free", 0) + b.get(self.quote, {}).get("locked", 0)
        base_free = b.get(self.base, {}).get("free", 0)
        base_locked = b.get(self.base, {}).get("locked", 0)
        if base_free + base_locked > 0:
            val += (base_free + base_locked) * self.price()
        return val

    def open_orders(self) -> list:
        o = self._get("/api/v3/openOrders", f"symbol={self.sym}")
        return o if isinstance(o, list) else []

    def cancel_all(self):
        for o in self.open_orders():
            self._post("/api/v3/order", f"symbol={self.sym}&orderId={o['orderId']}")

    def market_buy(self, quote_amount: float) -> dict:
        return self._post("/api/v3/order",
                          f"symbol={self.sym}&side=BUY&type=MARKET&quoteOrderQty={quote_amount:.2f}")

    def market_sell(self, quantity: float) -> dict:
        return self._post("/api/v3/order",
                          f"symbol={self.sym}&side=SELL&type=MARKET&quantity={quantity:.4f}")

    def limit_sell(self, quantity: float, price: float) -> dict:
        return self._post("/api/v3/order",
                          f"symbol={self.sym}&side=SELL&type=LIMIT&timeInForce=GTC&quantity={quantity:.4f}&price={price:.2f}")

    def ticker_24h(self) -> dict:
        r = requests.get(f"https://api.binance.com/api/v3/ticker/24hr?symbol={self.sym}", timeout=10)
        return r.json() if r.status_code == 200 else {}

    def order_book_snapshot(self, limit: int = 50) -> dict:
        r = requests.get(f"https://api.binance.com/api/v3/depth?symbol={self.sym}&limit={limit}", timeout=10)
        return r.json() if r.status_code == 200 else {}
