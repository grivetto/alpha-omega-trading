import hmac
import hashlib
import time
import requests
import json
import os
from typing import Dict, Optional, Tuple
from urllib.parse import urlencode


class BinanceEngine:
    def __init__(self, config_path: str = "config/war_config.json"):
        with open(config_path, "r") as f:
            self.config = json.load(f)
        
        # Load API keys from env FIRST, then config fallback
        self._load_env_file()
        
        binance_cfg = self.config.get("binance", {}) or self.config.get("exchanges", {}).get("binance", {})
        self.base_url = binance_cfg.get("base_url", "https://api.binance.com")
        self.api_key = os.environ.get("BINANCE_API_KEY", "") or binance_cfg.get("api_key", "")
        self.api_secret = (os.environ.get("BINANCE_API_SECRET", "") or binance_cfg.get("api_secret", "")).encode()
        
        self.session = requests.Session()
        self.session.headers.update({"X-MBX-APIKEY": self.api_key})
        # Default timeout for all requests (connect=5s, read=10s)
        self._timeout = (5, 10)

    def _load_env_file(self):
        """Load .env file into os.environ (systemd EnvironmentFile fallback)."""
        import os as _os
        env_path = _os.path.join(_os.path.dirname(__file__), "..", ".env")
        if _os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        _os.environ.setdefault(k.strip(), v.strip())

    def _sign_params(self, params: Dict) -> Dict:
        """Add timestamp and signature to params"""
        params["timestamp"] = int(time.time() * 1000)
        query_string = urlencode(params)
        signature = hmac.new(
            self.api_secret,
            query_string.encode(),
            hashlib.sha256
        ).hexdigest()
        params["signature"] = signature
        return params

    def _get(self, endpoint: str, params: Dict = None, signed: bool = False) -> Dict:
        url = f"{self.base_url}{endpoint}"
        params = params or {}
        if signed:
            params = self._sign_params(params)
        response = self.session.get(url, params=params, timeout=self._timeout)
        response.raise_for_status()
        return response.json()

    def _post(self, endpoint: str, params: Dict, signed: bool = True) -> Dict:
        url = f"{self.base_url}{endpoint}"
        if signed:
            params = self._sign_params(params)
        response = self.session.post(url, data=params, timeout=self._timeout)
        response.raise_for_status()
        return response.json()

    def _delete(self, endpoint: str, params: Dict, signed: bool = True) -> Dict:
        url = f"{self.base_url}{endpoint}"
        if signed:
            params = self._sign_params(params)
        response = self.session.delete(url, params=params, timeout=self._timeout)
        response.raise_for_status()
        return response.json()

    def price(self, symbol: str) -> float:
        """Get current price for symbol"""
        data = self._get("/api/v3/ticker/price", {"symbol": symbol})
        return float(data["price"])

    def balance(self, asset: str) -> float:
        """Get free balance for asset"""
        data = self._get("/api/v3/account", signed=True)
        for item in data["balances"]:
            if item["asset"] == asset:
                return float(item["free"])
        return 0.0

    def order_book_imbalance(self, symbol: str, limit: int = 20) -> Tuple[float, float, float]:
        """
        Returns (bid_qty, ask_qty, imbalance_ratio)
        imbalance_ratio = bid_qty / ask_qty
        """
        params = {"symbol": symbol, "limit": limit}
        data = self._get("/api/v3/depth", params)
        
        bid_qty = sum(float(b[1]) for b in data["bids"])
        ask_qty = sum(float(a[1]) for a in data["asks"])
        
        imbalance = bid_qty / ask_qty if ask_qty > 0 else float('inf')
        return bid_qty, ask_qty, imbalance

    def market_buy(self, symbol: str, quantity: float) -> Dict:
        """Place market buy order"""
        params = {
            "symbol": symbol,
            "side": "BUY",
            "type": "MARKET",
            "quantity": f"{quantity:.6f}"
        }
        return self._post("/api/v3/order", params)

    def market_sell(self, symbol: str, quantity: float) -> Dict:
        """Place market sell order"""
        params = {
            "symbol": symbol,
            "side": "SELL",
            "type": "MARKET",
            "quantity": f"{quantity:.6f}"
        }
        return self._post("/api/v3/order", params)

    def limit_sell(self, symbol: str, quantity: float, price: float) -> Dict:
        """Place limit sell order"""
        params = {
            "symbol": symbol,
            "side": "SELL",
            "type": "LIMIT",
            "timeInForce": "GTC",
            "quantity": f"{quantity:.6f}",
            "price": f"{price:.6f}"
        }
        return self._post("/api/v3/order", params)

    def get_open_orders(self, symbol: str) -> list:
        """Get open orders for symbol"""
        return self._get("/api/v3/openOrders", {"symbol": symbol}, signed=True)

    def cancel_order(self, symbol: str, order_id: int) -> Dict:
        """Cancel order by ID"""
        params = {"symbol": symbol, "orderId": order_id}
        return self._delete("/api/v3/order", params)

    # --- Adapter methods for WAR strategies ---
    def imbalance(self, symbol: str) -> float:
        _, _, imb = self.order_book_imbalance(symbol, 20)
        return imb

    def open_orders(self, symbol: str) -> list:
        return self.get_open_orders(symbol)

    def cancel_all(self, symbol: str):
        for o in self.open_orders(symbol):
            self.cancel_order(symbol, o["orderId"])

    def ohlcv(self, symbol: str, interval: str = "5m", limit: int = 30) -> list:
        data = self._get("/api/v3/klines", {"symbol": symbol, "interval": interval, "limit": limit})
        return data

    def atr(self, symbol: str, period: int = 14) -> float:
        klines = self.ohlcv(symbol, "5m", limit=period + 1)
        if not klines: return 0.0
        trs = []
        for i in range(1, len(klines)):
            h, l = float(klines[i][2]), float(klines[i][3])
            pc = float(klines[i-1][4])
            trs.append(max(h-l, abs(h-pc), abs(l-pc)))
        return sum(trs) / len(trs) if trs else 0.0

    def balance_usdc(self) -> float:
        return self.balance("USDC")

    def balance_sol(self) -> float:
        return self.balance("SOL")

    def market_buy_quote(self, symbol: str, quote_amount: float) -> dict:
        """Buy using quote amount (USDC) instead of base quantity."""
        p = self.price(symbol)
        qty = round(quote_amount / p, 4) if p else 0
        return self.market_buy(symbol, qty)


if __name__ == "__main__":
    engine = BinanceEngine()
    print("Price SOLUSDC:", engine.price("SOLUSDC"))
    print("USDC Balance:", engine.balance("USDC"))
    bid, ask, imb = engine.order_book_imbalance("SOLUSDC", 20)
    print(f"Order book - Bid: {bid:.2f}, Ask: {ask:.2f}, Imbalance: {imb:.2f}")