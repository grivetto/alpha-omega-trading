"""Linea chain connector."""
from chains.base_connector import BaseConnector
from typing import Dict
from web3 import Web3

class LineaConnector(BaseConnector):
    def __init__(self, rpc_url: str, gas_price_gwei: int = 0):
        super().__init__(rpc_url, chain_id=59144, name="linea", gas_price_gwei=gas_price_gwei)
    
    def get_native_balance(self, address: str) -> float:
        balance = self.w3.eth.get_balance(address)
        return self.w3.from_wei(balance, "ether")
    
    def get_token_balance(self, address: str, token_address: str, abi=None) -> float:
        return super().get_token_balance(address, token_address, abi)
    
    def get_protocol_tvl(self) -> Dict[str, float]:
        return {
            "velocore": 100_000_000,
            "syncswap": 50_000_000,
            "lending": 30_000_000,
        }


if __name__ == "__main__":
    import os
    rpc = os.getenv("LINEA_RPC", "https://rpc.linea.build")
    conn = LineaConnector(rpc)
    print(f"Chain: {conn.name}, ID: {conn.chain_id}")
    print(f"Connected: {conn.is_connected()}")