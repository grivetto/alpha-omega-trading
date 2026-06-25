import hmac
import hashlib
import time
import requests
import json
from typing import Dict, Optional, Tuple
from urllib.parse import urlencode


class BinanceEngine:
    def __init__(self, config_path: str = "config/war_config.json"):
        with open(config_path, "r") as f:
            self.config = json.load(f)
        
        binance_cfg = self.config["binance"]
        self.base_url = binance_cfg["base_url"]
        self.api_key = binance_cfg.get("api_key", "")
        self.api_secret = binance_cfg.get("api_secret", "").encode()
        
        self.session = requests.Session()
        self.session.headers.update({"X-MBX-APIKEY": self.api_key})

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
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def _post(self, endpoint: str, params: Dict, signed: bool = True) -> Dict:
        url = f"{self.base_url}{endpoint}"
        if signed:
            params = self._sign_params(params)
        response = self.session.post(url, data=params)
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
        return self._post("/api/v3/order", params)


if __name__ == "__main__":
    engine = BinanceEngine()
    print("Price SOLUSDC:", engine.price("SOLUSDC"))
    print("USDC Balance:", engine.balance("USDC"))
    bid, ask, imb = engine.order_book_imbalance("SOLUSDC", 20)
    print(f"Order book - Bid: {bid:.2f}, Ask: {ask:.2f}, Imbalance: {imb:.2f}")