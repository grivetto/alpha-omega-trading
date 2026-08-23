"""Base connector for EVM-compatible chains."""
from web3 import Web3
from typing import Dict, Any, Optional
import time
import random

# web3 v7+ middleware location
try:
    from web3.middleware import geth_poa_middleware
except ImportError:
    try:
        from web3.middleware.proof_of_authority import geth_poa_middleware
    except ImportError:
        geth_poa_middleware = None


class BaseConnector:
    def __init__(self, rpc_url: str, chain_id: int, name: str, gas_price_gwei: int = 0):
        self.name = name
        self.chain_id = chain_id
        self.rpc_url = rpc_url
        self.gas_price_gwei = gas_price_gwei
        
        self.w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 30}))
        
        # Add PoA middleware for chains that need it (BSC, Polygon, etc.)
        if geth_poa_middleware and chain_id in [56, 137, 100, 42161, 42220, 250, 59144, 534352, 10143]:
            self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        
        if not self.w3.is_connected():
            raise ConnectionError(f"Failed to connect to {name} at {rpc_url}")
    
    def get_gas_price(self) -> int:
        if self.gas_price_gwei > 0:
            return self.w3.to_wei(self.gas_price_gwei, "gwei")
        return self.w3.eth.gas_price
    
    def get_native_balance(self, address: str) -> float:
        balance = self.w3.eth.get_balance(address)
        return self.w3.from_wei(balance, "ether")
    
    def get_token_balance(self, address: str, token_address: str, abi: list = None) -> float:
        if abi is None:
            abi = [{"inputs":[{"name":"account","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"type":"function"},{"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"type":"function"}]
        token = self.w3.eth.contract(address=self.w3.to_checksum_address(token_address), abi=abi)
        decimals = token.functions.decimals().call()
        balance = token.functions.balanceOf(self.w3.to_checksum_address(address)).call()
        return balance / (10 ** decimals)
    
    def get_protocol_tvl(self) -> Dict[str, float]:
        """Override in subclass to return protocol TVLs."""
        return {}
    
    def send_transaction(self, signed_tx: Any) -> str:
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        return tx_hash.hex()
    
    def wait_for_receipt(self, tx_hash: str, timeout: int = 120) -> Dict:
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)
        return dict(receipt)
    
    def estimate_gas(self, tx_params: Dict) -> int:
        try:
            return self.w3.eth.estimate_gas(tx_params)
        except Exception:
            return 21000  # fallback
    
    def get_nonce(self, address: str) -> int:
        return self.w3.eth.get_transaction_count(address)
    
    def get_block_number(self) -> int:
        return self.w3.eth.block_number
    
    def is_connected(self) -> bool:
        return self.w3.is_connected()


if __name__ == "__main__":
    import os
    rpc = os.getenv("BASE_RPC", "https://mainnet.base.org")
    conn = BaseConnector(rpc, chain_id=8453, name="base")
    print(f"Chain: {conn.name}, ID: {conn.chain_id}")
    print(f"Connected: {conn.is_connected()}")
    print(f"Block: {conn.get_block_number()}")
    print(f"Gas price: {conn.get_gas_price()} wei")