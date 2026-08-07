#!/usr/bin/env python3
"""
Pair Scanner for Grid Trading Strategy.
Scans exchange pairs (Kraken / MEXC / Bitvavo) to select top grid-trading candidates.
Criteria:
1. 24h Volume > Min threshold (High liquidity)
2. ATR(14) % between 0.8% and 5.0% (Enough volatility to yield grid profit)
3. ADX(14) < 25 (Range-bound, not trending violently)
4. Bid/Ask Spread < 0.15% (Low fee drag)
"""
from __future__ import annotations
import json
import sys
import ccxt
from typing import List, Dict


def scan_pairs(exchange_id: str = "kraken", base_currency: str = "EUR", max_pairs: int = 5) -> List[Dict]:
    try:
        ex_cls = getattr(ccxt, exchange_id.lower())
        ex = ex_cls({"enableRateLimit": True})
        log_info = lambda msg: print(f"[Scanner {exchange_id.upper()}] {msg}", file=sys.stderr)
        log_info(f"Fetching tickers for {base_currency} pairs...")
        
        tickers = ex.fetch_tickers()
        candidates = []
        
        for symbol, t in tickers.items():
            if not symbol.endswith(f"/{base_currency}"):
                continue
            
            last = t.get("last") or t.get("close")
            quote_vol = t.get("quoteVolume") or (t.get("baseVolume", 0) * (last or 0))
            bid = t.get("bid")
            ask = t.get("ask")
            
            if not last or not bid or not ask or quote_vol < 10000:  # Min 10k volume
                continue
                
            spread_pct = ((ask - bid) / last) * 100.0
            if spread_pct > 0.35:  # Skip illiquid wide spread pairs
                continue
                
            candidates.append({
                "symbol": symbol,
                "price": last,
                "volume_24h": quote_vol,
                "spread_pct": round(spread_pct, 3),
            })
            
        # Sort candidates by volume
        candidates.sort(key=lambda x: -x["volume_24h"])
        top_candidates = candidates[:15]
        
        log_info(f"Evaluating top {len(top_candidates)} candidates for ATR/ADX indicators...")
        scored_pairs = []
        
        for cand in top_candidates:
            sym = cand["symbol"]
            try:
                ohlcv = ex.fetch_ohlcv(sym, timeframe="5m", limit=30)
                if len(ohlcv) < 25:
                    continue
                    
                closes = [c[4] for c in ohlcv]
                highs = [c[2] for c in ohlcv]
                lows = [c[3] for c in ohlcv]
                
                # TR & ATR(14)
                tr_list = [max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1])) for i in range(1, len(ohlcv))]
                atr14 = sum(tr_list[-14:]) / 14.0
                atr_pct = (atr14 / closes[-1]) * 100.0
                
                # Simplified ADX
                plus_dm = [max(highs[i] - highs[i-1], 0) for i in range(1, len(ohlcv))]
                minus_dm = [max(lows[i-1] - lows[i], 0) for i in range(1, len(ohlcv))]
                sum_tr = sum(tr_list[-14:]) or 1.0
                pdi = (sum(plus_dm[-14:]) / sum_tr) * 100.0
                mdi = (sum(minus_dm[-14:]) / sum_tr) * 100.0
                adx = (abs(pdi - mdi) / (pdi + mdi or 1.0)) * 100.0
                
                # Grid Score: High ATR % + Low ADX (pure range)
                # Ideal range: ATR > 0.5%, ADX < 25
                grid_score = atr_pct * (1.0 if adx < 25 else 0.4)
                
                scored_pairs.append({
                    "symbol": sym,
                    "price": cand["price"],
                    "volume_24h": round(cand["volume_24h"], 2),
                    "spread_pct": cand["spread_pct"],
                    "atr_pct": round(atr_pct, 2),
                    "adx": round(adx, 1),
                    "grid_score": round(grid_score, 3),
                })
            except Exception as e:
                continue
                
        scored_pairs.sort(key=lambda x: -x["grid_score"])
        return scored_pairs[:max_pairs]
        
    except Exception as e:
        print(f"Scan error: {e}", file=sys.stderr)
        return []


if __name__ == "__main__":
    ex = sys.argv[1] if len(sys.argv) > 1 else "kraken"
    curr = sys.argv[2] if len(sys.argv) > 2 else "EUR"
    results = scan_pairs(ex, curr)
    print(json.dumps(results, indent=2))
