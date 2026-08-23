#!/usr/bin/env python3
"""
Migration script: v1 legacy state (free_cash/coins/equity_peak) → v2 state (equity/grid_anchor)

Usage: python migrate_v1_to_v2.py <v1_state_file.json> <v2_state_file.json> [capital]
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def migrate_v1_to_v2(v1_state: dict, capital: float = 100.0) -> dict:
    """Convert v1 legacy state to v2 format."""
    
    # Calculate equity from v1 fields
    free_cash = v1_state.get("free_cash", capital)
    locked_cash = v1_state.get("locked_cash", 0.0)
    coins = v1_state.get("coins", 0.0)
    
    # We need current price to calculate equity from coins
    # Since we don't have it, approximate equity as free_cash + locked_cash
    # (coins value unknown without current price)
    equity = free_cash + locked_cash
    
    # If equity is 0 or negative, use capital
    if equity <= 0:
        equity = capital
    
    # Extract realized PnL
    realized_pnl = v1_state.get("realized_pnl", 0.0)
    
    # Trade counts
    total_trades = v1_state.get("total_trades", 0)
    winning_trades = v1_state.get("winning_trades", 0)
    losses = total_trades - winning_trades
    
    # Convert orders list to open_orders dict
    # v1 orders are historical fills, not open orders
    # v2 open_orders expects: {order_id: {side, price, amount, cost, timestamp}}
    open_orders = {}
    v1_orders = v1_state.get("orders", [])
    
    # For migration, we don't have open orders from v1 (only historical fills)
    # So open_orders starts empty - bot will rebuild grid from grid_anchor
    
    # Calculate grid_anchor from last buy/sell if available
    grid_anchor = None
    grid_levels = []
    
    if v1_orders:
        # Find most recent buy order to estimate grid anchor
        buy_orders = [o for o in v1_orders if o.get("side") == "buy"]
        if buy_orders:
            last_buy = buy_orders[-1]
            grid_anchor = last_buy.get("price", 0)
        else:
            # Use first sell as reference
            grid_anchor = v1_orders[0].get("price", 0)
    
    # Build v2 state
    v2_state = {
        "equity": round(equity, 4),
        "realized_pnl": round(realized_pnl, 4),
        "trades_count": total_trades,
        "wins": winning_trades,
        "losses": max(0, losses),
        "open_orders": open_orders,
        "grid_anchor": grid_anchor,
        "grid_levels": grid_levels,
        "daily_loss": 0.0,
        "day_start_equity": round(equity, 4),
        "last_day": datetime.now(timezone.utc).date().isoformat(),
        # v2.2 additions
        "peak_equity": round(v1_state.get("equity_peak", equity), 4),
        "volatility_regime": "normal",
        "kill_switch_triggered": False,
    }
    
    return v2_state


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    
    v1_path = Path(sys.argv[1])
    v2_path = Path(sys.argv[2])
    capital = float(sys.argv[3]) if len(sys.argv) > 3 else 100.0
    
    if not v1_path.exists():
        print(f"ERROR: v1 state file not found: {v1_path}")
        sys.exit(1)
    
    with open(v1_path, "r") as f:
        v1_state = json.load(f)
    
    v2_state = migrate_v1_to_v2(v1_state, capital)
    
    # Backup original v1 file
    backup_path = v1_path.with_suffix(f".v1_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    v1_path.rename(backup_path)
    print(f"Backed up v1 state to: {backup_path}")
    
    with open(v2_path, "w") as f:
        json.dump(v2_state, f, indent=2)
    
    print(f"Migrated v1 → v2 state saved to: {v2_path}")
    print(f"Equity: {v2_state['equity']}, Grid anchor: {v2_state['grid_anchor']}")
    print(f"Trades: {v2_state['trades_count']} (W: {v2_state['wins']}, L: {v2_state['losses']})")
    print(f"Peak equity: {v2_state['peak_equity']}")


if __name__ == "__main__":
    main()
