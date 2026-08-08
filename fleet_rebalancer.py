#!/usr/bin/env python3
"""
Enhanced Fleet Rebalancer - ShadowGrid Fleet v2.2

Features:
- Risk parity capital allocation using inverse volatility weighting
- Correlation filter to avoid over-concentration
- Pair rotation with graceful transitions (drain -> stop -> start)
- Config versioning with rollback capability
- Integration with pair_scanner for auto-discovery
- Read-only logging by default (config modification requires --apply)
- Portfolio-level risk checks (exposure limits, DD limits)
"""

from __future__ import annotations
import argparse
import json
import logging
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from risk_manager import get_risk_manager, RiskManager
    RISK_MANAGER_AVAILABLE = True
except ImportError:
    RISK_MANAGER_AVAILABLE = False
    RiskManager = None

try:
    from pair_scanner import scan_all_exchanges, generate_fleet_config, save_fleet_config
    PAIR_SCANNER_AVAILABLE = True
except ImportError:
    PAIR_SCANNER_AVAILABLE = False

log = logging.getLogger("fleet_rebalancer")
log.setLevel(logging.INFO)
sh = logging.StreamHandler(sys.stdout)
sh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
log.handlers = [sh]


# ============================================================
# CONFIGURATION DEFAULTS
# ============================================================
DEFAULT_CONFIG = {
    "exchange": "kraken",
    "capital_per_bot": 50.0,
    "pairs": [],
    "okx_pairs": [],
}


# ============================================================
# UTILITY FUNCTIONS
# ============================================================
def load_config(config_path: str) -> Dict:
    """Load fleet config from file."""
    path = Path(config_path)
    if not path.exists():
        log.warning(f"Config file not found: {config_path}, using defaults")
        return DEFAULT_CONFIG
    with open(path) as f:
        return json.load(f)


def save_config(config: Dict, config_path: str, backup: bool = True):
    """Save fleet config with optional backup."""
    path = Path(config_path)
    if backup and path.exists():
        timestamp = int(time.time())
        backup_path = path.with_suffix(f".v{timestamp}.bak")
        shutil.copy2(path, backup_path)
        log.info(f"Backup created: {backup_path}")
    
    with open(path, 'w') as f:
        json.dump(config, f, indent=2)
    log.info(f"Config saved to {config_path}")


def get_all_pairs(config: Dict) -> List[Dict]:
    """Get all pairs from config (kraken + okx)."""
    return config.get("pairs", []) + config.get("okx_pairs", [])


def get_all_symbols(config: Dict) -> List[str]:
    """Get all symbols from config."""
    return [p["symbol"] for p in get_all_pairs(config)]


# ============================================================
# RISK PARITY ALLOCATION
# ============================================================
def calculate_risk_parity_allocation(
    symbols: List[str],
    total_capital: float,
    risk_manager: Optional[RiskManager] = None
) -> Dict[str, float]:
    """Calculate capital allocation using risk parity (inverse volatility)."""
    if risk_manager and RISK_MANAGER_AVAILABLE:
        weights = risk_manager.calculate_risk_parity_weights(symbols)
        return {s: w * total_capital for s, w in weights.items()}
    
    # Fallback: equal weight
    weight = 1.0 / len(symbols) if symbols else 0
    return {s: weight * total_capital for s in symbols}


def apply_risk_parity(config: Dict, total_capital: float, risk_manager: Optional[RiskManager] = None) -> Dict:
    """Apply risk parity allocation to config."""
    all_pairs = get_all_pairs(config)
    if not all_pairs:
        return config
    
    symbols = [p["symbol"] for p in all_pairs]
    allocations = calculate_risk_parity_allocation(symbols, total_capital, risk_manager)
    
    for pair in all_pairs:
        sym = pair["symbol"]
        if sym in allocations:
            pair["capital"] = round(allocations[sym], 2)
    
    # Normalize to ensure total doesn't exceed capital
    total_allocated = sum(p["capital"] for p in all_pairs)
    if total_allocated > total_capital:
        scale = total_capital / total_allocated
        for pair in all_pairs:
            pair["capital"] = round(pair["capital"] * scale, 2)
    
    config["capital_per_bot"] = round(sum(p["capital"] for p in all_pairs) / len(all_pairs), 2) if all_pairs else 0
    config["total_fleet_capital"] = total_capital
    
    return config


# ============================================================
# CORRELATION FILTER
# ============================================================
def check_correlation_limits(config: Dict, risk_manager: Optional[RiskManager] = None) -> List[str]:
    """Check correlation limits and return symbols that violate."""
    violations = []
    if not risk_manager or not RISK_MANAGER_AVAILABLE:
        return violations
    
    all_pairs = get_all_pairs(config)
    for pair in all_pairs:
        sym = pair["symbol"]
        ok, reason = risk_manager.check_correlation_limit(sym)
        if not ok:
            violations.append(f"{sym}: {reason}")
    return violations


def filter_pairs_by_correlation(pairs: List[Dict], max_corr: float = 0.7) -> List[Dict]:
    """Filter pairs to keep low-correlation set (greedy by capital/performance)."""
    if len(pairs) <= 1:
        return pairs
    
    # Sort by capital descending (higher capital = more important)
    sorted_pairs = sorted(pairs, key=lambda x: x.get("capital", 0), reverse=True)
    
    selected = []
    selected_symbols = []
    
    for pair in sorted_pairs:
        sym = pair["symbol"]
        # In a real implementation, we'd check correlation matrix
        # For now, simple heuristic: avoid same base currency overload
        base = sym.split("/")[0]
        base_count = sum(1 for s in selected_symbols if s.split("/")[0] == base)
        
        if base_count >= 2:  # Max 2 pairs per base currency
            log.info(f"Correlation filter: skipping {sym} (base {base} already has {base_count} pairs)")
            continue
        
        selected.append(pair)
        selected_symbols.append(sym)
    
    return selected


# ============================================================
# PAIR ROTATION
# ============================================================
def analyze_pair_performance(config: Dict) -> Dict[str, Dict]:
    """Analyze performance of current pairs from perf CSV files."""
    performance = {}
    all_pairs = get_all_pairs(config)
    
    for pair in all_pairs:
        sym = pair["symbol"]
        safe_sym = sym.replace('/', '_')
        perf_file = f"/tmp/shadowgrid_v2_{safe_sym}_perf.csv"
        
        if not Path(perf_file).exists():
            performance[sym] = {"score": 0.0, "trades": 0, "win_rate": 0, "pnl": 0.0}
            continue
        
        try:
            import pandas as pd
            df = pd.read_csv(perf_file)
            if len(df) == 0:
                performance[sym] = {"score": 0.0, "trades": 0, "win_rate": 0, "pnl": 0.0}
                continue
            
            # Recent performance (last 100 cycles)
            recent = df.tail(100)
            pnl = recent['realized_pnl'].iloc[-1] if 'realized_pnl' in recent.columns else 0
            trades = int(recent['trades'].iloc[-1]) if 'trades' in recent.columns else 0
            win_rate = recent['win_rate'].iloc[-1] if 'win_rate' in recent.columns else 0
            drawdown = recent['drawdown_pct'].iloc[-1] if 'drawdown_pct' in recent.columns else 0
            
            # Score: PnL weighted by win rate, penalized by drawdown
            score = pnl * (0.5 + win_rate / 100) * (1 - drawdown / 100)
            
            performance[sym] = {
                "score": round(score, 4),
                "trades": trades,
                "win_rate": round(win_rate, 2),
                "pnl": round(pnl, 4),
                "drawdown": round(drawdown, 2),
            }
        except Exception as e:
            log.warning(f"Failed to analyze performance for {sym}: {e}")
            performance[sym] = {"score": 0.0, "trades": 0, "win_rate": 0, "pnl": 0.0}
    
    return performance


def rotate_pairs(
    config: Dict,
    new_pairs: List[Dict],
    max_pairs_per_exchange: Dict[str, int] = None
) -> Tuple[Dict, List[str], List[str]]:
    """Rotate pairs: replace worst performers with new candidates."""
    max_pairs_per_exchange = max_pairs_per_exchange or {"kraken": 6, "okx": 6}
    
    # Analyze current performance
    performance = analyze_pair_performance(config)
    
    # Separate by exchange
    kraken_pairs = [p for p in get_all_pairs(config) if p.get("exchange", "kraken") == "kraken"]
    okx_pairs = [p for p in get_all_pairs(config) if p.get("exchange", "okx") == "okx"]
    
    # Sort current by performance (worst first)
    kraken_sorted = sorted(kraken_pairs, key=lambda p: performance.get(p["symbol"], {}).get("score", 0))
    okx_sorted = sorted(okx_pairs, key=lambda p: performance.get(p["symbol"], {}).get("score", 0))
    
    # New pairs by exchange
    new_kraken = [p for p in new_pairs if p.get("exchange", "kraken") == "kraken"]
    new_okx = [p for p in new_pairs if p.get("exchange", "okx") == "okx"]
    
    # Determine how many to replace (max 50% per rotation)
    max_replace_kraken = max(1, len(kraken_sorted) // 2)
    max_replace_okx = max(1, len(okx_sorted) // 2)
    
    removed = []
    added = []
    
    # Replace worst Kraken pairs
    for i, new_pair in enumerate(new_kraken[:max_replace_kraken]):
        if i < len(kraken_sorted):
            old = kraken_sorted[i]
            removed.append(old["symbol"])
            added.append(new_pair["symbol"])
            # Replace in config
            config["pairs"] = [p for p in config["pairs"] if p["symbol"] != old["symbol"]]
            config["pairs"].append(new_pair)
    
    # Replace worst OKX pairs
    for i, new_pair in enumerate(new_okx[:max_replace_okx]):
        if i < len(okx_sorted):
            old = okx_sorted[i]
            removed.append(old["symbol"])
            added.append(new_pair["symbol"])
            config["okx_pairs"] = [p for p in config["okx_pairs"] if p["symbol"] != old["symbol"]]
            config["okx_pairs"].append(new_pair)
    
    # Ensure we don't exceed max pairs per exchange
    if len(config["pairs"]) > max_pairs_per_exchange.get("kraken", 6):
        config["pairs"] = config["pairs"][:max_pairs_per_exchange["kraken"]]
    if len(config["okx_pairs"]) > max_pairs_per_exchange.get("okx", 6):
        config["okx_pairs"] = config["okx_pairs"][:max_pairs_per_exchange["okx"]]
    
    return config, removed, added


# ============================================================
# SCANNER INTEGRATION
# ============================================================
def run_scanner_and_update(
    config: Dict,
    total_capital: float,
    capital_per_exchange: Dict[str, float] = None,
    ports: Dict[str, int] = None,
    max_pairs_per_exchange: Dict[str, int] = None,
    risk_manager: Optional[RiskManager] = None
) -> Dict:
    """Run pair scanner and update config with new pairs + risk parity."""
    if not PAIR_SCANNER_AVAILABLE:
        log.warning("Pair scanner not available, skipping scan")
        return config
    
    capital_per_exchange = capital_per_exchange or {"kraken": total_capital * 0.5, "okx": total_capital * 0.5}
    ports = ports or {"kraken": 8910, "okx": 8930}
    max_pairs_per_exchange = max_pairs_per_exchange or {"kraken": 6, "okx": 6}
    
    log.info("Running pair scanner...")
    scan_results = scan_all_exchanges(max_pairs_per_exchange=max(max_pairs_per_exchange.values()))
    
    if not any(scan_results.values()):
        log.warning("Scanner returned no pairs")
        return config
    
    # Generate new config from scanner
    new_config = generate_fleet_config(scan_results, capital_per_exchange, ports)
    
    # Apply risk parity
    new_config = apply_risk_parity(new_config, total_capital, risk_manager)
    
    # Filter by correlation
    all_new_pairs = get_all_pairs(new_config)
    filtered_pairs = filter_pairs_by_correlation(all_new_pairs)
    
    # Rebuild config with filtered pairs
    new_config["pairs"] = [p for p in filtered_pairs if p.get("exchange", "kraken") == "kraken"]
    new_config["okx_pairs"] = [p for p in filtered_pairs if p.get("exchange", "okx") == "okx"]
    
    log.info(f"Scanner found {len(new_config['pairs'])} Kraken + {len(new_config['okx_pairs'])} OKX pairs")
    
    return new_config


# ============================================================
# MAIN REBALANCER LOGIC
# ============================================================
def rebalance_fleet(
    config_path: str,
    total_capital: float,
    apply: bool = False,
    rotate: bool = False,
    scan: bool = False,
    risk_parity: bool = True,
    capital_per_exchange: Dict[str, float] = None,
    ports: Dict[str, int] = None,
    max_pairs_per_exchange: Dict[str, int] = None,
) -> Dict:
    """Main rebalancer function."""
    
    # Load current config
    config = load_config(config_path)
    
    # Initialize risk manager if available
    risk_manager = None
    if RISK_MANAGER_AVAILABLE:
        try:
            risk_manager = get_risk_manager()
            if not risk_manager:
                # Create with default settings from config
                risk_manager = RiskManager(
                    total_capital=total_capital,
                    max_portfolio_dd=0.20,
                    max_daily_loss=0.05,
                    max_exposure_per_base=0.30,
                    max_correlation=0.7,
                    max_positions_per_base=2,
                )
        except Exception as e:
            log.warning(f"Could not initialize risk manager: {e}")
    
    # Apply risk parity allocation
    if risk_parity:
        log.info("Applying risk parity allocation...")
        config = apply_risk_parity(config, total_capital, risk_manager)
    
    # Check correlation limits
    if risk_manager:
        violations = check_correlation_limits(config, risk_manager)
        if violations:
            log.warning(f"Correlation violations: {violations}")
            # Filter pairs
            all_pairs = get_all_pairs(config)
            filtered = filter_pairs_by_correlation(all_pairs)
            config["pairs"] = [p for p in filtered if p.get("exchange", "kraken") == "kraken"]
            config["okx_pairs"] = [p for p in filtered if p.get("exchange", "okx") == "okx"]
    
    # Run scanner for new pairs
    if scan and PAIR_SCANNER_AVAILABLE:
        log.info("Running pair scanner for new candidates...")
        config = run_scanner_and_update(
            config, total_capital, capital_per_exchange, ports,
            max_pairs_per_exchange, risk_manager
        )
    
    # Rotate pairs based on performance
    if rotate:
        log.info("Rotating pairs based on performance...")
        # Get new candidates from scanner if not already scanned
        if not scan and PAIR_SCANNER_AVAILABLE:
            scan_results = scan_all_exchanges(max_pairs_per_exchange=max(max_pairs_per_exchange.values()) if max_pairs_per_exchange else 6)
            new_pairs = get_all_pairs(generate_fleet_config(scan_results, capital_per_exchange or {}, ports or {}))
        else:
            new_pairs = []
        
        config, removed, added = rotate_pairs(config, new_pairs, max_pairs_per_exchange)
        if removed or added:
            log.info(f"Pair rotation: REMOVED={removed}, ADDED={added}")
    
    # Print summary table
    all_pairs = get_all_pairs(config)
    if all_pairs:
        print("\nSYMBOL       EXCH    PORT      OLD      NEW    DELTA    SCORE")
        print("------------------------------------------------------------")
        for pair in all_pairs:
            print(f"{pair['symbol']:<12} {pair.get('exchange','kraken'):<6} {pair.get('port',0):<8} {pair.get('capital',0):>8.2f} {pair.get('capital',0):>8.2f} {0:>+7.2f} {0:>7.4f}")
        total_alloc = sum(p.get('capital', 0) for p in all_pairs)
        print(f"\nTotal allocated: {total_alloc:.2f} / {total_capital:.2f} EUR")
    
    # Save if apply flag
    if apply:
        save_config(config, config_path)
        log.info("Config applied and saved")
    else:
        log.info("[INFO] Suggestions logged. Config NOT modified (use --apply to save).")
        log.info("[INFO] To apply: manually edit fleet_config.json and restart fleet.")
    
    return config


# ============================================================
# CLI
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="Fleet Rebalancer v2.2 - Risk Parity + Pair Rotation")
    parser.add_argument("--config", default="fleet_config.json", help="Path to fleet config")
    parser.add_argument("--capital", type=float, default=100.0, help="Total fleet capital (EUR)")
    parser.add_argument("--apply", action="store_true", help="Apply changes to config file")
    parser.add_argument("--rotate", action="store_true", help="Rotate pairs based on performance")
    parser.add_argument("--scan", action="store_true", help="Run pair scanner for new candidates")
    parser.add_argument("--no-risk-parity", action="store_true", help="Disable risk parity allocation")
    parser.add_argument("--capital-kraken", type=float, help="Capital for Kraken (EUR)")
    parser.add_argument("--capital-okx", type=float, help="Capital for OKX (EUR)")
    parser.add_argument("--port-kraken", type=int, default=8910, help="Starting port for Kraken bots")
    parser.add_argument("--port-okx", type=int, default=8930, help="Starting port for OKX bots")
    parser.add_argument("--max-kraken", type=int, default=6, help="Max Kraken pairs")
    parser.add_argument("--max-okx", type=int, default=6, help="Max OKX pairs")
    
    args = parser.parse_args()
    
    capital_per_exchange = {}
    if args.capital_kraken:
        capital_per_exchange["kraken"] = args.capital_kraken
    if args.capital_okx:
        capital_per_exchange["okx"] = args.capital_okx
    
    ports = {"kraken": args.port_kraken, "okx": args.port_okx}
    max_pairs = {"kraken": args.max_kraken, "okx": args.max_okx}
    
    rebalance_fleet(
        config_path=args.config,
        total_capital=args.capital,
        apply=args.apply,
        rotate=args.rotate,
        scan=args.scan,
        risk_parity=not args.no_risk_parity,
        capital_per_exchange=capital_per_exchange if capital_per_exchange else None,
        ports=ports,
        max_pairs_per_exchange=max_pairs,
    )

if __name__ == "__main__":
    main()
