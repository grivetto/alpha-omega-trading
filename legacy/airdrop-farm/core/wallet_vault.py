import os
import json
from pathlib import Path
from cryptography.fernet import Fernet
from eth_account import Account

# Abilita feature HD Wallet
Account.enable_unaudited_hdwallet_features()


class WalletVault:
    def __init__(self, vault_path="data/vault.json", key_env_var="FERNET_KEY"):
        self.vault_path = Path(vault_path)
        key = os.getenv(key_env_var)
        if not key:
            key = Fernet.generate_key().decode()
            print(f"⚠️ FERNET_KEY non trovata in .env. Generata nuova chiave (salvala):\n{key}\n")
        self.fernet = Fernet(key.encode())

    def create_vault_from_mnemonic(self, mnemonic: str, num_wallets=20, derivation_path="m/44'/60'/0'/0/"):
        """Crea vault crittografato da seed BIP39."""
        vault_data = []
        for i in range(num_wallets):
            path = f"{derivation_path}{i}"
            acc = Account.from_mnemonic(mnemonic, account_path=path)
            enc_priv = self.fernet.encrypt(acc.key.hex().encode()).decode()
            vault_data.append({
                "index": i,
                "address": acc.address,
                "encrypted_private_key": enc_priv,
                "derivation_path": path
            })

        self.vault_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.vault_path, "w") as f:
            json.dump(vault_data, f, indent=2)
        print(f"✅ Vault creato: {self.vault_path} ({num_wallets} wallet)")
        return vault_data

    def load_wallets(self):
        """Carica e decripta tutti i wallet dal vault."""
        if not self.vault_path.exists():
            raise FileNotFoundError(f"Vault non trovato: {self.vault_path}. Esegui create_vault_from_mnemonic() prima.")

        with open(self.vault_path, "r") as f:
            vault_data = json.load(f)

        wallets = []
        for item in vault_data:
            dec_priv = self.fernet.decrypt(item["encrypted_private_key"].encode()).decode()
            wallets.append({
                "index": item["index"],
                "address": item["address"],
                "private_key": dec_priv,
                "derivation_path": item.get("derivation_path", "")
            })
        return wallets

    def get_wallet(self, index: int):
        """Ottiene un singolo wallet per indice."""
        wallets = self.load_wallets()
        for w in wallets:
            if w["index"] == index:
                return w
        return None


if __name__ == "__main__":
    # Test CLI: python3 -m core.wallet_vault "seed phrase here"
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 -m core.wallet_vault \"mnemonic phrase\" [num_wallets]")
        sys.exit(1)
    
    mnemonic = sys.argv[1]
    num = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    
    vault = WalletVault()
    vault.create_vault_from_mnemonic(mnemonic, num)