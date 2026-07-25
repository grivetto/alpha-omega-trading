"""Base chain connector."""
from chains.base_connector import BaseConnector
from typing import Dict, Any
from web3 import Web3


class BaseConnectorImpl(BaseConnector):
    def __init__(self, rpc_url: str, gas_price_gwei: int = 0):
        super().__init__(rpc_url, chain_id=8453, name="base", gas_price_gwei=gas_price_gwei)
    
    def get_native_balance(self, address: str) -> float:
        balance = self.w3.eth.get_balance(address)
        return Web3.from_wei(balance, "ether")
    
    def get_token_balance(self, address: str, token_address: str) -> float:
        erc20_abi = [{"inputs":[{"name":"account","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"type":"function"},{"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"type":"function"}]
        token = self.w3.eth.contract(address=Web3.to_checksum_address(token_address), abi=erc20_abi)
        decimals = token.functions.decimals().call()
        balance = token.functions.balanceOf(Web3.to_checksum_address(address)).call()
        return balance / (10 ** decimals)
    
    def get_protocol_tvl(self) -> Dict[str, float]:
        """Get TVL for major Base protocols (simplified)."""
        return {
            "aerodrome": 500_000_000,
            "friendtech": 50_000_000,
            "based": 10_000_000
        }


if __name__ == "__main__":
    import os
    rpc = os.getenv("BASE_RPC", "https://mainnet.base.org")
    conn = BaseConnectorImpl(rpc)
    print(f"Chain: {conn.name}, ID: {conn.chain_id}")
    print(f"Connected: {conn.w3.is_connected()}")
    print(f"Gas price: {conn.get_gas_price() / 1e9:.2f} gwei")