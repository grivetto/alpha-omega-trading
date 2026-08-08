#!/usr/bin/env python3
"""
Fleet Capital Rebalancer - Only LOGS suggestions, does NOT modify config.

Usage: python fleet_rebalancer.py --config /path/to/fleet_config.json --capital 100
"""

import json
import argparse
import sys
import os
from datetime import datetime
from pathlib import Path


def load_state_for_bot(bot_name: str, base_dir: str = "/home/sergio/denaro") -> dict:
    """Load shadowgrid state file for a bot."""
    # Try multiple possible state file patterns
    patterns = [
        f"shadowgrid_{bot_name.replace('/', '_')}_state.json",
        f"shadowgrid_{bot_name.replace('/', '_')}.json",
        f"state_{bot_name.replace('/', '_')}.json",
    ]
    for pattern in patterns:
        path = Path(base_dir) / pattern
        if path.exists():
            try:
                with open(path) as f:
                    return json.load(f)
            except Exception:
                pass
    return {}


def compute_performance_score(bot: dict, base_dir: str) -> float:
    """Compute performance score from live state."""
    state = load_state_for_bot(bot["symbol"], base_dir)
    
    realized_pnl = state.get("realized_pnl", 0.0)
    equity = state.get("equity", bot.get("capital", 25.0))
    trades = state.get("trades_count", 0)
    win_rate = state.get("win_rate", 0.0)
    
    # Score formula: PnL% * trades_weight + win_rate * win_weight
    capital = bot.get("capital", 25.0)
    if capital <= 0:
        return 0.0
    
    pnl_pct = (equity - capital) / capital * 100
    
    # Only score if bot has actually traded
    if trades < 3:
        return max(0.1, pnl_pct / 100 + 0.1)
    
    score = (pnl_pct * 0.6) + (win_rate * 0.4)
    return max(0.1, score)


def rebalance_fleet(config_path: str, total_capital: float, base_dir: str = None):
    """Main rebalancing logic - ONLY LOGS suggestions."""
    
    if base_dir is None:
        base_dir = os.path.dirname(config_path)
    
    with open(config_path) as f:
        config = json.load(f)
    
    # Collect ALL pairs from both kraken and okx
    all_bots = []
    for p in config.get("pairs", []):
        p["exchange"] = p.get("exchange", "kraken")
        all_bots.append(p)
    for p in config.get("okx_pairs", []):
        p["exchange"] = p.get("exchange", "okx")
        all_bots.append(p)
    
    if not all_bots:
        
# Normalize allocations to fit within total_fleet_capital
total_allocated = sum(new_allocations.values())
if total_allocated > total_fleet_capital:
    scale = total_fleet_capital / total_allocated
    for sym in new_allocations:
        new_allocations[sym] = round(new_allocations[sym] * scale, 2)


        print(f"[{datetime.now()}] No bots found in config")
        return
    
    # Compute scores
    scored = []
    for bot in all_bots:
        score = compute_performance_score(bot, base_dir)
        scored.append((score, bot))
    
    # Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)
    
    # Calculate new allocations
    min_cap = total_capital * 0.15  # 15% min per bot
    max_cap = total_capital * 0.45  # 45% max per bot
    
    # Weighted allocation based on score
    total_score = sum(s for s, _ in scored)
    
    suggestions = []
    for score, bot in scored:
        weight = score / total_score if total_score > 0 else 1.0 / len(scored)
        new_capital = total_capital * weight
        new_capital = max(min_cap, min(max_cap, new_capital))
        
        old_capital = bot.get("capital", total_capital / len(scored))
        delta = new_capital - old_capital
        
        suggestions.append({
            "symbol": bot["symbol"],
            "exchange": bot["exchange"],
            "old_capital": round(old_capital, 2),
            "new_capital": round(new_capital, 2),
            "delta": round(delta, 2),
            "score": round(score, 4),
            "port": bot.get("port", "?")
        })
    
    # Log results
    print(f"\n=== FLEET REBALANCER [{datetime.now().isoformat()}] ===")
    print(f"Config: {config_path}")
    print(f"Total Capital: {total_capital} EUR")
    print(f"Bots: {len(all_bots)} (Kraken: {len(config.get('pairs', []))}, OKX: {len(config.get('okx_pairs', []))})")
    print(f"Min/Max per bot: {min_cap:.2f} / {max_cap:.2f} EUR")
    print(f"\n{'SYMBOL':<12} {'EXCH':<6} {'PORT':>5} {'OLD':>8} {'NEW':>8} {'DELTA':>8} {'SCORE':>8}")
    print("-" * 60)
    
    for s in suggestions:
        print(f"{s['symbol']:<12} {s['exchange']:<6} {s['port']:>5} {s['old_capital']:>8.2f} {s['new_capital']:>8.2f} {s['delta']:>+8.2f} {s['score']:>8.4f}")
    
    # Summary
    total_new = sum(s["new_capital"] for s in suggestions)
    print(f"\nTotal allocated: {total_new:.2f} / {total_capital:.2f} EUR")
    
    # DO NOT write back to config - bots don't reload it anyway
    print(f"\n[INFO] Suggestions logged. Config NOT modified (bots don't reload at runtime).")
    print(f"[INFO] To apply: manually edit fleet_config.json and restart fleet.")


def main():
    parser = argparse.ArgumentParser(description="Fleet Capital Rebalancer (read-only)")
    parser.add_argument("--config", required=True, help="Path to fleet_config.json")
    parser.add_argument("--capital", type=float, default=100.0, help="Total fleet capital")
    parser.add_argument("--basedir", help="Base directory for state files (default: config dir)")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.config):
        print(f"[ERROR] Config file not found: {args.config}", file=sys.stderr)
        sys.exit(1)
    
    rebalance_fleet(args.config, args.capital, args.basedir)


if __name__ == "__main__":
    main()
