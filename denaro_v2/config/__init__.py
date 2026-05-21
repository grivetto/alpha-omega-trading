#!/usr/bin/env python3
"""
DENARO V2 - System Configuration
"""
import json

DEFAULT_CONFIG = {
    "system": {
        "name": "Denaro V2",
        "version": "2.0.0",
        "mode": "live",  # live or test
        "log_level": "INFO",
        "heartbeat_sec": 60,
    },

    "exchange": {
        "name": "binance",
        "testnet": False,
    },

    "risk": {
        "max_portfolio_risk": 0.05,
        "max_position_size": 0.15,
        "max_drawdown": 0.10,
        "max_daily_trades": 50,
        "max_daily_loss": 0.03,
    },

    "strategies": {
        "grid_mm": {
            "enabled": True,
            "symbols": ["SOL/EUR", "ADA/EUR"],
            "grid_levels": 7,
            "grid_spacing_pct": 0.005,
            "base_order_eur": 5.0,
            "max_total_invested": 40.0,
            "profit_per_grid": 0.004,
        },
        "momentum": {
            "enabled": True,
            "symbols": ["SOL/EUR", "ETH/EUR"],
            "timeframe": "1m",
            "base_order_eur": 5.0,
            "tp_pct": 0.008,
            "sl_pct": 0.005,
            "min_vol_ratio": 1.5,
            "min_score": 0.3,
        },
        "mean_reversion": {
            "enabled": True,
            "symbols": ["ETH/EUR", "BTC/EUR"],
            "timeframe": "5m",
            "base_order_eur": 5.0,
            "rsi_oversold": 25,
            "rsi_overbought": 75,
            "tp_pct": 0.01,
            "sl_pct": 0.008,
        },
    },

    "monitoring": {
        "status_file": ".tmp/denaro_v2_status.json",
        "trade_log": ".tmp/denaro_v2_trades.json",
    },
}


def load_config(path: str = None) -> dict:
    """Load configuration from file or use defaults."""
    import os
    if path and os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return DEFAULT_CONFIG


def save_config(config: dict, path: str):
    """Save configuration to file."""
    import os
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(config, f, indent=4)
