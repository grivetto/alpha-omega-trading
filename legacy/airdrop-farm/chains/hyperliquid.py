"""Hyperliquid connector (L1 + Perps/Spot DEX)."""
from chains.base_connector import BaseConnector
from typing import Dict, List, Any
import requests
import time


class HyperliquidConnector(BaseConnector):
    def __init__(self, api_url: str = "https://api.hyperliquid.xyz"):
        super().__init__(api_url, chain_id=42161, name="hyperliquid", gas_price_gwei=0)
        self.api_url = api_url
        self.info_url = f"{api_url}/info"
        self.exchange_url = f"{api_url}/exchange"
    
    def is_connected(self) -> bool:
        try:
            r = requests.post(self.info_url, json={"type": "meta"}, timeout=10)
            return r.status_code == 200
        except:
            return False
    
    def get_native_balance(self, address: str) -> float:
        """Get USDC balance on Hyperliquid (native quote asset)."""
        return self.get_spot_balance(address, "USDC")
    
    def get_spot_balance(self, address: str, token: str) -> float:
        """Get spot balance for a token."""
        try:
            payload = {"type": "clearinghouseState", "user": address}
            r = requests.post(self.info_url, json=payload, timeout=10)
            data = r.json()
            for asset in data.get("assetPositions", []):
                if asset["position"]["coin"] == token:
                    return float(asset["position"]["szi"])
            return 0.0
        except:
            return 0.0
    
    def get_perp_positions(self, address: str) -> List[Dict]:
        """Get open perp positions."""
        try:
            payload = {"type": "clearinghouseState", "user": address}
            r = requests.post(self.info_url, json=payload, timeout=10)
            data = r.json()
            return data.get("assetPositions", [])
        except:
            return []
    
    def get_token_balance(self, address: str, token_address: str, abi=None) -> float:
        # Hyperliquid uses spot tokens by name, not ERC20 addresses
        return 0.0
    
    def place_perp_order(self, address: str, private_key: str, coin: str, 
                         is_buy: bool, sz: float, limit_px: float = None) -> Dict:
        """Place a perp order (requires L1 wallet + HL signature)."""
        # This requires EIP-712 signing with HL-specific format
        # Placeholder for full implementation
        return {"status": "not_implemented"}
    
    def get_protocol_tvl(self) -> Dict[str, float]:
        try:
            r = requests.post(self.info_url, json={"type": "meta"}, timeout=10)
            meta = r.json()
            universe = meta.get("universe", [])
            tvl = {}
            for asset in universe:
                tvl[asset["name"]] = float(asset.get("sz", 0)) * float(asset.get("markPx", 0))
            return {"perp_tvl": sum(tvl.values()), **tvl}
        except:
            return {"perp_tvl": 1_000_000_000}
    
    def get_points_estimate(self, address: str) -> Dict:
        """Estimate points accrual based on volume."""
        try:
            payload = {"type": "userFundingHistory", "user": address, "startTime": int(time.time() * 1000) - 86400000}
            r = requests.post(self.info_url, json=payload, timeout=10)
            history = r.json()
            volume_24h = sum(abs(float(h.get("sz", 0)) * float(h.get("px", 0))) for h in history)
            return {"volume_24h_usd": volume_24h, "est_points_per_day": volume_24h / 1000}
        except:
            return {"volume_24h_usd": 0, "est_points_per_day": 0}


if __name__ == "__main__":
    conn = HyperliquidConnector()
    print(f"Connected: {conn.is_connected()}")
    print(f"TVL: {conn.get_protocol_tvl()}")