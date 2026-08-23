#!/usr/bin/env python3
"""
Enhanced Pair Scanner for Dynamic Pair Selection - ShadowGrid Fleet v2.2

Features:
- Multi-exchange scanning (Kraken EUR + OKX USDT)
- Regime detection: Range (ADX<25) vs Trend (ADX>25)
- Performance decay scoring: recent PnL weighted with historical
- Correlation matrix to avoid correlated positions
- Volatility regime detection (ATR-based)
- Auto-config output for fleet_rebalancer
- Liquidity and spread filters
- Risk parity weight suggestions
"""

from __future__ import annotations
import json
import sys
import os
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import ccxt
import numpy as np

# ============================================================
# CONFIGURATION
# ============================================================
DEFAULT_EXCHANGES = {
    "kraken": {"base": "EUR", "quote": "EUR"},
    "okx": {"base": "USDT", "quote": "USDT"},
}

SCAN_CONFIG = {
    "min_volume_24h": 50000,           # Min $50k 24h volume
    "max_spread_pct": 0.2,             # Max 0.2% spread
    "min_atr_pct": 0.3,                # Min 0.3% ATR for grid profit
    "max_atr_pct": 5.0,                # Max 5% ATR (too volatile)
    "adx_range_threshold": 25,         # ADX < 25 = range-bound
    "adx_trend_threshold": 30,         # ADX > 30 = strong trend
    "correlation_limit": 0.7,          # Max correlation between pairs
    "top_candidates_per_exchange": 20, # Evaluate top N by volume
    "max_pairs_per_exchange": 6,       # Return top N per exchange
    "performance_lookback_days": 7,    # Recent PnL lookback
    "performance_decay_factor": 0.7,   # Weight: recent=0.7, historical=0.3
}

# Performance cache file
PERF_CACHE_FILE = Path("/tmp/shadowgrid_pair_performance.json")
PERF_CACHE_TTL = 3600  # 1 hour

log_info = lambda msg: print(f"[PairScanner] {msg}", file=sys.stderr)
log_warn = lambda msg: print(f"[PairScanner WARN] {msg}", file=sys.stderr)
log_error = lambda msg: print(f"[PairScanner ERROR] {msg}", file=sys.stderr)


# ============================================================
# PERFORMANCE CACHE
# ============================================================
class PerformanceCache:
    """Cache for pair performance history with decay weighting."""
    
    def __init__(self, cache_file: Path = PERF_CACHE_FILE, ttl: int = PERF_CACHE_TTL):
        self.cache_file = cache_file
        self.ttl = ttl
        self.cache: Dict = {}
        self.lock = threading.Lock()
        self._load()
    
    def _load(self):
        with self.lock:
            if self.cache_file.exists():
                try:
                    with open(self.cache_file, 'r') as f:
                        data = json.load(f)
                    # Check TTL
                    if time.time() - data.get("timestamp", 0) < self.ttl:
                        self.cache = data.get("pairs", {})
                    else:
                        self.cache = {}
                except Exception as e:
                    log_warn(f"Failed to load performance cache: {e}")
                    self.cache = {}
            else:
                self.cache = {}
    
    def save(self):
        with self.lock:
            try:
                data = {
                    "timestamp": time.time(),
                    "pairs": self.cache
                }
                with open(self.cache_file, 'w') as f:
                    json.dump(data, f, indent=2)
            except Exception as e:
                log_error(f"Failed to save performance cache: {e}")
    
    def get_pair_performance(self, symbol: str) -> Dict:
        """Get performance metrics for a pair."""
        with self.lock:
            return self.cache.get(symbol, {
                "recent_pnl": 0.0,
                "historical_pnl": 0.0,
                "trades": 0,
                "win_rate": 0.0,
                "avg_hold_time": 0.0,
                "last_update": 0,
            })
    
    def update_pair_performance(self, symbol: str, pnl: float, is_win: bool, hold_time: float):
        """Update performance metrics for a pair with decay."""
        with self.lock:
            if symbol not in self.cache:
                self.cache[symbol] = {
                    "recent_pnl": 0.0,
                    "historical_pnl": 0.0,
                    "trades": 0,
                    "wins": 0,
                    "total_pnl": 0.0,
                    "avg_hold_time": 0.0,
                    "last_update": time.time(),
                }
            
            entry = self.cache[symbol]
            # Apply decay to historical
            entry["historical_pnl"] = entry["historical_pnl"] * 0.9 + entry["recent_pnl"] * 0.1
            # Update recent
            entry["recent_pnl"] = pnl
            entry["trades"] += 1
            if is_win:
                entry["wins"] += 1
            entry["total_pnl"] += pnl
            entry["avg_hold_time"] = (entry["avg_hold_time"] * (entry["trades"] - 1) + hold_time) / entry["trades"]
            entry["win_rate"] = entry["wins"] / entry["trades"]
            entry["last_update"] = time.time()
            
            self.save()
    
    def calculate_score(self, symbol: str) -> float:
        """Calculate decay-weighted performance score."""
        perf = self.get_pair_performance(symbol)
        recent = perf.get("recent_pnl", 0.0)
        historical = perf.get("historical_pnl", 0.0)
        win_rate = perf.get("win_rate", 0.0)
        
        # Decay weighted score
        decay = SCAN_CONFIG["performance_decay_factor"]
        score = recent * decay + historical * (1 - decay)
        
        # Boost for high win rate
        score *= (0.5 + win_rate)
        
        return score


# ============================================================
# TECHNICAL ANALYSIS
# ============================================================
def compute_atr_adx_rsi(ohlcv: List[List[float]]) -> Tuple[float, float, float]:
    """Compute ATR(14)%, ADX(14), RSI(14) from OHLCV."""
    if len(ohlcv) < 15:
        return 0.0, 0.0, 50.0
    
    closes = np.array([c[4] for c in ohlcv])
    highs = np.array([c[2] for c in ohlcv])
    lows = np.array([c[3] for c in ohlcv])
    
    # True Range
    tr = np.maximum.reduce([
        highs[1:] - lows[1:],
        np.abs(highs[1:] - closes[:-1]),
        np.abs(lows[1:] - closes[:-1])
    ])
    atr14 = np.mean(tr[-14:])
    atr_pct = (atr14 / closes[-1]) * 100 if closes[-1] > 0 else 0.0
    
    # RSI(14)
    diffs = np.diff(closes[-15:])
    gains = np.where(diffs > 0, diffs, 0)
    losses = np.where(diffs < 0, -diffs, 0)
    avg_gain = np.mean(gains) if len(gains) > 0 else 0
    avg_loss = np.mean(losses) if len(losses) > 0 else 0
    rs = avg_gain / avg_loss if avg_loss > 0 else 100
    rsi = 100 - (100 / (1 + rs))
    
    # ADX(14) - simplified
    up_move = highs[1:] - highs[:-1]
    down_move = lows[:-1] - lows[1:]
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
    
    tr14 = np.mean(tr[-14:])
    if tr14 > 0:
        pdi = np.mean(plus_dm[-14:]) / tr14 * 100
        mdi = np.mean(minus_dm[-14:]) / tr14 * 100
        dx = abs(pdi - mdi) / (pdi + mdi) * 100 if (pdi + mdi) > 0 else 0
    else:
        dx = 0
    adx = dx
    
    return atr_pct, adx, rsi


def detect_regime(adx: float, rsi: float) -> Dict:
    """Detect market regime based on ADX and RSI."""
    if adx < SCAN_CONFIG["adx_range_threshold"]:
        regime = "range"
        suitability = "grid"
    elif adx > SCAN_CONFIG["adx_trend_threshold"]:
        regime = "trend"
        suitability = "scalper" if HYBRID_MODE_AVAILABLE else "avoid"
    else:
        regime = "transitional"
        suitability = "caution"
    
    # Trend direction
    if rsi > 55:
        trend = "bullish"
    elif rsi < 45:
        trend = "bearish"
    else:
        trend = "neutral"
    
    return {
        "regime": regime,
        "suitability": suitability,
        "trend": trend,
        "adx": adx,
        "rsi": rsi,
    }


def detect_volatility_regime(atr_pct: float, atr_history: List[float]) -> Dict:
    """Detect volatility regime from ATR history."""
    if len(atr_history) < 20:
        return {"regime": "unknown", "ratio": 1.0, "action": "normal"}
    
    median_atr = np.median(atr_history)
    ratio = atr_pct / median_atr if median_atr > 0 else 1.0
    
    if ratio >= 3.0:
        regime = "extreme"
        action = "pause"
    elif ratio >= 2.0:
        regime = "high"
        action = "reduce"
    elif ratio <= 0.5:
        regime = "low"
        action = "expand"
    else:
        regime = "normal"
        action = "normal"
    
    return {
        "regime": regime,
        "ratio": ratio,
        "current_atr": atr_pct,
        "median_atr": median_atr,
        "action": action,
    }


# ============================================================
# CORRELATION ANALYSIS
# ============================================================
def calculate_correlation_matrix(symbols: List[str], exchange: ccxt.Exchange,
                                  timeframe: str = '1h', lookback: int = 168) -> np.ndarray:
    """Calculate correlation matrix for symbols using close prices."""
    price_data = {}
    
    for sym in symbols:
        try:
            ohlcv = exchange.fetch_ohlcv(sym, timeframe=timeframe, limit=lookback)
            if len(ohlcv) >= 50:
                closes = np.array([c[4] for c in ohlcv])
                returns = np.diff(closes) / closes[:-1]
                price_data[sym] = returns
        except Exception:
            continue
    
    if len(price_data) < 2:
        return np.eye(len(symbols))
    
    # Align lengths
    min_len = min(len(v) for v in price_data.values())
    returns_matrix = np.array([price_data[s][-min_len:] for s in symbols if s in price_data])
    
    if returns_matrix.shape[0] < 2:
        return np.eye(len(symbols))
    
    corr = np.corrcoef(returns_matrix)
    return corr


def filter_by_correlation(candidates: List[Dict], corr_matrix: np.ndarray,
                           max_corr: float = 0.7) -> List[Dict]:
    """Filter candidates to keep low-correlation set (greedy by grid_score)."""
    if len(candidates) <= 1:
        return candidates
    
    # Sort by grid_score descending
    sorted_candidates = sorted(candidates, key=lambda x: x.get("grid_score", 0), reverse=True)
    
    selected = []
    selected_indices = []
    
    for i, cand in enumerate(sorted_candidates):
        sym = cand["symbol"]
        orig_idx = next((j for j, c in enumerate(candidates) if c["symbol"] == sym), None)
        if orig_idx is None:
            continue
        
        # Check correlation with already selected
        ok = True
        for sel_idx in selected_indices:
            if corr_matrix[orig_idx, sel_idx] > max_corr:
                ok = False
                break
        
        if ok:
            selected.append(cand)
            selected_indices.append(orig_idx)
    
    return selected


# ============================================================
# MAIN SCANNER
# ============================================================
HYBRID_MODE_AVAILABLE = True  # Will be checked from env

def scan_exchange(
    exchange_id: str,
    base_currency: str,
    perf_cache: PerformanceCache,
    max_pairs: int = None,
    atr_history: Dict[str, List[float]] = None
) -> List[Dict]:
    """Scan single exchange for best grid/trend pairs."""
    max_pairs = max_pairs or SCAN_CONFIG["max_pairs_per_exchange"]
    atr_history = atr_history or {}
    
    try:
        ex_cls = getattr(ccxt, exchange_id.lower())
        ex = ex_cls({"enableRateLimit": True})
        
        log_info(f"Fetching tickers for {base_currency} pairs on {exchange_id}...")
        tickers = ex.fetch_tickers()
        
        # Filter by base currency and basic criteria
        candidates = []
        for symbol, t in tickers.items():
            if not symbol.endswith(f"/{base_currency}"):
                continue
            
            last = t.get("last") or t.get("close")
            quote_vol = t.get("quoteVolume") or (t.get("baseVolume", 0) * (last or 0))
            bid = t.get("bid")
            ask = t.get("ask")
            
            if not last or not bid or not ask:
                continue
            if quote_vol < SCAN_CONFIG["min_volume_24h"]:
                continue
            
            spread_pct = ((ask - bid) / last) * 100.0
            if spread_pct > SCAN_CONFIG["max_spread_pct"]:
                continue
            
            candidates.append({
                "symbol": symbol,
                "price": last,
                "volume_24h": quote_vol,
                "spread_pct": round(spread_pct, 3),
            })
        
        # Sort by volume, take top N for indicator evaluation
        candidates.sort(key=lambda x: -x["volume_24h"])
        top_candidates = candidates[:SCAN_CONFIG["top_candidates_per_exchange"]]
        
        log_info(f"Evaluating {len(top_candidates)} candidates for indicators on {exchange_id}...")
        
        # Compute indicators for each candidate
        scored_pairs = []
        for cand in top_candidates:
            sym = cand["symbol"]
            try:
                ohlcv = ex.fetch_ohlcv(sym, timeframe='15m', limit=50)
                if len(ohlcv) < 30:
                    continue
                
                atr_pct, adx, rsi = compute_atr_adx_rsi(ohlcv)
                
                # Filter by ATR range
                if atr_pct < SCAN_CONFIG["min_atr_pct"] or atr_pct > SCAN_CONFIG["max_atr_pct"]:
                    continue
                
                # Detect regime
                regime_info = detect_regime(adx, rsi)
                
                # Detect volatility regime
                vol_regime = detect_volatility_regime(atr_pct, atr_history.get(sym, []))
                
                # Performance score
                perf_score = perf_cache.calculate_score(sym)
                
                # Grid score: ATR * (1 if range else 0.4) * performance multiplier
                grid_multiplier = 1.0 if regime_info["regime"] == "range" else 0.4
                grid_score = atr_pct * grid_multiplier * (1 + perf_score * 0.1)
                
                scored_pairs.append({
                    "symbol": sym,
                    "price": cand["price"],
                    "volume_24h": round(cand["volume_24h"], 2),
                    "spread_pct": cand["spread_pct"],
                    "atr_pct": round(atr_pct, 2),
                    "adx": round(adx, 1),
                    "rsi": round(rsi, 1),
                    "grid_score": round(grid_score, 3),
                    "regime": regime_info["regime"],
                    "suitability": regime_info["suitability"],
                    "trend": regime_info["trend"],
                    "vol_regime": vol_regime["regime"],
                    "vol_action": vol_regime["action"],
                    "perf_score": round(perf_score, 3),
                    "exchange": exchange_id,
                })
            except Exception as e:
                log_warn(f"Error evaluating {sym}: {e}")
                continue
        
        # Sort by grid_score
        scored_pairs.sort(key=lambda x: -x["grid_score"])
        
        # Filter by correlation if we have enough candidates
        if len(scored_pairs) > 2:
            symbols = [p["symbol"] for p in scored_pairs]
            corr_matrix = calculate_correlation_matrix(symbols, ex)
            scored_pairs = filter_by_correlation(scored_pairs, corr_matrix, 
                                                  SCAN_CONFIG["correlation_limit"])
        
        return scored_pairs[:max_pairs]
        
    except Exception as e:
        log_error(f"Scan error on {exchange_id}: {e}")
        return []


def scan_all_exchanges(exchanges: Dict = None, max_pairs_per_exchange: int = None) -> Dict[str, List[Dict]]:
    """Scan all configured exchanges."""
    exchanges = exchanges or DEFAULT_EXCHANGES
    perf_cache = PerformanceCache()
    atr_history = {}  # Could be loaded from file
    
    results = {}
    for ex_id, config in exchanges.items():
        base = config["base"]
        results[ex_id] = scan_exchange(ex_id, base, perf_cache, max_pairs_per_exchange, atr_history)
        log_info(f"{ex_id.upper()}: Found {len(results[ex_id])} pairs")
    
    return results


def generate_fleet_config(scan_results: Dict[str, List[Dict]],
                           capital_per_exchange: Dict[str, float] = None,
                           ports: Dict[str, int] = None) -> Dict:
    """Generate fleet_config.json from scan results."""
    capital_per_exchange = capital_per_exchange or {"kraken": 50.0, "okx": 50.0}
    ports = ports or {"kraken": 8910, "okx": 8930}
    
    config = {
        "exchange": "kraken",  # default
        "capital_per_bot": 8.33,
        "total_fleet_capital": sum(capital_per_exchange.values()),
        "pairs": [],
        "okx_pairs": [],
        "generated_at": datetime.now().isoformat(),
        "scan_version": "2.2",
    }
    
    for ex_id, pairs in scan_results.items():
        ex_capital = capital_per_exchange.get(ex_id, 0)
        ex_port_start = ports.get(ex_id, 8910)
        
        if not pairs:
            continue
        
        capital_per_bot = ex_capital / len(pairs) if pairs else 0
        
        for i, pair in enumerate(pairs):
            port = ex_port_start + i
            pair_config = {
                "symbol": pair["symbol"],
                "port": port,
                "capital": round(capital_per_bot, 2),
                "exchange": ex_id,
                "regime": pair.get("regime", "unknown"),
                "suitability": pair.get("suitability", "grid"),
                "atr_pct": pair.get("atr_pct", 0),
                "adx": pair.get("adx", 0),
            }
            
            if ex_id == "okx":
                config["okx_pairs"].append(pair_config)
            else:
                config["pairs"].append(pair_config)
    
    return config


def save_fleet_config(config: Dict, filepath: str = "fleet_config.json"):
    """Save fleet config with versioning."""
    # Backup existing
    if Path(filepath).exists():
        backup = f"{filepath}.v{int(time.time())}"
        Path(filepath).rename(backup)
    
    with open(filepath, 'w') as f:
        json.dump(config, f, indent=2)
    log_info(f"Fleet config saved to {filepath}")


# ============================================================
# CLI
# ============================================================
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Enhanced Pair Scanner for ShadowGrid Fleet")
    parser.add_argument("--exchange", default="all", help="Exchange to scan (kraken, okx, all)")
    parser.add_argument("--base", default="EUR", help="Base currency for Kraken")
    parser.add_argument("--max-pairs", type=int, default=6, help="Max pairs per exchange")
    parser.add_argument("--output-config", help="Generate fleet_config.json at path")
    parser.add_argument("--capital-kraken", type=float, default=50.0)
    parser.add_argument("--capital-okx", type=float, default=50.0)
    parser.add_argument("--port-kraken", type=int, default=8910)
    parser.add_argument("--port-okx", type=int, default=8930)
    
    args = parser.parse_args()
    
    if args.exchange == "all":
        results = scan_all_exchanges(max_pairs_per_exchange=args.max_pairs)
    else:
        perf_cache = PerformanceCache()
        base = "USDT" if args.exchange == "okx" else args.base
        results = {args.exchange: scan_exchange(args.exchange, base, perf_cache, args.max_pairs)}
    
    print(json.dumps(results, indent=2))
    
    if args.output_config:
        capital = {"kraken": args.capital_kraken, "okx": args.capital_okx}
        ports = {"kraken": args.port_kraken, "okx": args.port_okx}
        config = generate_fleet_config(results, capital, ports)
        save_fleet_config(config, args.output_config)
        print(f"\nFleet config generated at {args.output_config}")
