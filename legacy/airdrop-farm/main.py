#!/usr/bin/env python3
"""Airdrop Farm - Main entry point."""
import sys
import os
import argparse

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import get_config
from core.wallet_vault import WalletVault
from core.orchestrator import Orchestrator


def main():
    parser = argparse.ArgumentParser(description="Airdrop Farm - Multi-chain airdrop farming bot")
    parser.add_argument("--mnemonic", help="BIP39 mnemonic phrase (or set MNEMONIC env var)")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Run in dry-run mode (default)")
    parser.add_argument("--live", action="store_true", help="Run live (overrides dry-run)")
    parser.add_argument("--init-vault", action="store_true", help="Initialize vault from mnemonic and exit")
    parser.add_argument("--status", action="store_true", help="Print status and exit")
    parser.add_argument("--test-strategies", action="store_true", help="Test all strategies and exit")
    
    args = parser.parse_args()
    
    # Load config
    config = get_config(args.config)
    
    # Override dry_run from CLI
    if args.live:
        config.dry_run = False
    elif args.dry_run:
        config.dry_run = True
    
    # Get mnemonic
    mnemonic = args.mnemonic or os.getenv("MNEMONIC")
    
    if args.init_vault:
        if not mnemonic:
            print("❌ Mnemonic required for --init-vault (--mnemonic or MNEMONIC env)")
            sys.exit(1)
        
        vault = WalletVault()
        vault.create_vault_from_mnemonic(mnemonic, config.budget.max_wallets)
        print("✅ Vault initialized. Save your FERNET_KEY from .env!")
        sys.exit(0)
    
    # Initialize orchestrator
    orch = Orchestrator(args.config)
    
    if args.test_strategies:
        print("🧪 Testing all strategies...")
        from strategies import get_all_strategies
        strategies = get_all_strategies(orch)
        for s in strategies:
            result = s.execute_dry_run(None)
            print(f"  {result['strategy']}: {result['action']} ({result['details']})")
        print("✅ All strategies OK")
        sys.exit(0)
    
    if args.status:
        status = orch.get_status()
        print(f"Status: {'running' if status['running'] else 'stopped'}")
        print(f"Uptime: {status['uptime_hours']:.1f}h")
        print(f"Dry run: {status['config']['dry_run']}")
        print(f"Wallets: {len(status['wallets'])}")
        for w in status['wallets']:
            print(f"  #{w['index']} {w['address']} next={w['next_action_in_min']:.0f}m")
        sys.exit(0)
    
    # Need mnemonic for running
    if not mnemonic:
        print("❌ Mnemonic required (--mnemonic or MNEMONIC env var)")
        print("   Or run with --init-vault to create vault first")
        sys.exit(1)
    
    # Initialize wallets
    orch.initialize_wallets(mnemonic)
    
    # Run main loop
    try:
        orch.run_loop()
    except KeyboardInterrupt:
        print("\n👋 Shutdown requested")
    except Exception as e:
        print(f"💥 Fatal error: {e}")
        if orch.telegram:
            orch.telegram.send_alert("Fatal Error", str(e), "critical")
        sys.exit(1)


if __name__ == "__main__":
    main()