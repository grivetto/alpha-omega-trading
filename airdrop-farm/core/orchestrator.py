"""Orchestrator - main loop coordinator with Poisson timing and circuit breaker."""
import time
import random
import signal
import sys
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime

from core.config import get_config
from core.wallet_vault import WalletVault
from chains import get_factory
from strategies.airdrop_strategy import AirdropStrategy
from strategies.hyperliquid_strategy import HyperliquidStrategy
from strategies.yield_strategy import YieldStrategy
from strategies.mexc_strategy import MexcLaunchpadStrategy
from activity.tracker import ActivityTracker
from monitoring.telegram_bot import TelegramBot


@dataclass
class WalletState:
    index: int
    address: str
    private_key: str
    last_action_time: float = 0
    next_action_time: float = 0
    daily_actions: int = 0
    daily_loss_pct: float = 0.0
    consecutive_failures: int = 0
    in_cooldown: bool = False
    cooldown_until: float = 0


class Orchestrator:
    def __init__(self, config_path: str = "config.yaml"):
        self.config = get_config(config_path)
        self.vault = WalletVault()
        self.chain_factory = get_factory(config_path)
        self.tracker = ActivityTracker()
        self.telegram = TelegramBot(self.config.telegram) if self.config.telegram.enabled else None
        
        # Initialize strategies
        self.strategies = {
            "airdrop": AirdropStrategy(self),
            "hyperliquid": HyperliquidStrategy(self),
            "yield": YieldStrategy(self),
            "mexc": MexcLaunchpadStrategy(self),
        }
        
        # Wallet states
        self.wallets: List[WalletState] = []
        self.running = False
        self.start_time = time.time()
        
        # Signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        print(f"\n⚠️ Signal {signum} received, shutting down gracefully...")
        self.running = False
    
    def initialize_wallets(self, mnemonic: str = None, num_wallets: int = None):
        """Initialize wallet states from vault or create new vault."""
        if mnemonic:
            vault_data = self.vault.create_vault_from_mnemonic(
                mnemonic, 
                num_wallets=self.config.budget.max_wallets
            )
        else:
            vault_data = self.vault.load_wallets()
        
        self.wallets = []
        for w in vault_data:
            self.wallets.append(WalletState(
                index=w["index"],
                address=w["address"],
                private_key=w["private_key"],
                next_action_time=time.time()  # Start immediately
            ))
        
        print(f"✅ Initialized {len(self.wallets)} wallets")
        
        # Schedule first actions
        self._schedule_next_actions()
    
    def _schedule_next_actions(self):
        """Schedule next action for each wallet using Poisson timing."""
        now = time.time()
        for ws in self.wallets:
            if ws.in_cooldown and now < ws.cooldown_until:
                continue
            
            min_h = self.config.timing.min_hours
            max_h = self.config.timing.max_hours
            jitter = self.config.timing.jitter_pct
            
            base = random.uniform(min_h, max_h) * 3600
            jitter_amt = base * random.uniform(-jitter, jitter)
            wait = max(0, base + jitter_amt)
            
            ws.next_action_time = now + wait
            ws.in_cooldown = False
    
    def _select_strategy(self, wallet: WalletState) -> Optional[str]:
        """Select strategy based on wallet state and config."""
        # Simple round-robin for now, can be weighted by performance
        strategies = list(self.strategies.keys())
        return random.choice(strategies) if strategies else None
    
    def _execute_strategy(self, wallet: WalletState, strategy_name: str) -> bool:
        """Execute a strategy for a wallet."""
        strategy = self.strategies.get(strategy_name)
        if not strategy:
            return False
        
        try:
            if self.config.dry_run:
                print(f"  [DRY RUN] Wallet {wallet.index} ({wallet.address[:8]}...) → {strategy_name}")
                # Simulate success
                result = strategy.execute_dry_run(wallet)
            else:
                print(f"  [LIVE] Wallet {wallet.index} ({wallet.address[:8]}...) → {strategy_name}")
                result = strategy.execute_live(wallet)
            
            if result.get("success", False):
                wallet.consecutive_failures = 0
                self.tracker.record_action(wallet.index, strategy_name, result)
                if self.telegram:
                    self.telegram.send(f"✅ Wallet {wallet.index}: {strategy_name} - {result.get('details', '')}")
                return True
            else:
                wallet.consecutive_failures += 1
                self.tracker.record_failure(wallet.index, strategy_name, result.get("error", "Unknown"))
                if self.telegram:
                    self.telegram.send(f"❌ Wallet {wallet.index}: {strategy_name} failed - {result.get('error', 'Unknown')}")
                return False
        
        except Exception as e:
            wallet.consecutive_failures += 1
            error_msg = str(e)
            self.tracker.record_failure(wallet.index, strategy_name, error_msg)
            if self.telegram:
                self.telegram.send(f"💥 Wallet {wallet.index}: {strategy_name} exception - {error_msg}")
            return False
    
    def _check_circuit_breakers(self, wallet: WalletState) -> bool:
        """Check if wallet should be paused."""
        cb = self.config.circuit_breaker
        
        if wallet.consecutive_failures >= cb.max_consecutive_failures:
            wallet.in_cooldown = True
            wallet.cooldown_until = time.time() + cb.cooldown_hours * 3600
            if self.telegram:
                self.telegram.send(f"🔴 Wallet {wallet.index} circuit breaker: {cb.cooldown_hours}h cooldown")
            return True
        
        if wallet.daily_loss_pct >= cb.max_daily_loss_pct:
            wallet.in_cooldown = True
            wallet.cooldown_until = time.time() + 86400  # Until next day
            if self.telegram:
                self.telegram.send(f"🔴 Wallet {wallet.index} daily loss limit reached")
            return True
        
        return False
    
    def run_loop(self):
        """Main orchestration loop."""
        self.running = True
        print("🚀 Orchestrator started. Press Ctrl+C to stop.")
        
        if self.telegram:
            self.telegram.send(f"🚀 Airdrop Farm started - {len(self.wallets)} wallets, DRY_RUN={self.config.dry_run}")
        
        while self.running:
            now = time.time()
            
            # Process each wallet
            for wallet in self.wallets:
                if not self.running:
                    break
                
                # Check cooldown
                if wallet.in_cooldown:
                    if now >= wallet.cooldown_until:
                        wallet.in_cooldown = False
                        wallet.consecutive_failures = 0
                        wallet.daily_loss_pct = 0  # Reset daily
                    else:
                        continue
                
                # Check if it's time for action
                if now < wallet.next_action_time:
                    continue
                
                # Check circuit breakers
                if self._check_circuit_breakers(wallet):
                    continue
                
                # Select and execute strategy
                strategy = self._select_strategy(wallet)
                if strategy:
                    success = self._execute_strategy(wallet, strategy)
                    
                    if success:
                        wallet.daily_actions += 1
                    else:
                        wallet.daily_loss_pct += 1.0  # Rough estimate
                
                # Schedule next action
                min_h = self.config.timing.min_hours
                max_h = self.config.timing.max_hours
                jitter = self.config.timing.jitter_pct
                
                base = random.uniform(min_h, max_h) * 3600
                jitter_amt = base * random.uniform(-jitter, jitter)
                wait = max(0, base + jitter_amt)
                wallet.next_action_time = now + wait
            
            # Sleep until next wallet ready
            next_times = [w.next_action_time for w in self.wallets if not w.in_cooldown or now >= w.cooldown_until]
            if next_times:
                sleep_until = min(next_times)
                sleep_time = max(1, min(60, sleep_until - now))  # Cap at 60s for responsiveness
                time.sleep(sleep_time)
            else:
                time.sleep(60)
        
        print("🛑 Orchestrator stopped.")
        if self.telegram:
            self.telegram.send("🛑 Airdrop Farm stopped")
    
    def get_status(self) -> Dict:
        """Get current status for monitoring."""
        return {
            "running": self.running,
            "uptime_hours": (time.time() - self.start_time) / 3600,
            "wallets": [
                {
                    "index": w.index,
                    "address": w.address[:8] + "...",
                    "next_action_in_min": max(0, (w.next_action_time - time.time()) / 60),
                    "daily_actions": w.daily_actions,
                    "consecutive_failures": w.consecutive_failures,
                    "in_cooldown": w.in_cooldown
                }
                for w in self.wallets
            ],
            "config": {
                "dry_run": self.config.dry_run,
                "budget_virtual": self.config.budget.virtual_capital,
                "budget_real": self.config.budget.real_capital
            }
        }


if __name__ == "__main__":
    # Test initialization
    orch = Orchestrator()
    print("Orchestrator initialized")
    print(f"Dry run: {orch.config.dry_run}")
    print(f"Strategies: {list(orch.strategies.keys())}")