"""
Dynamic Pair Scanner for Alpha-Omega Trading System.

Scans exchanges for optimal trading pairs based on:
- Volume and liquidity
- Volatility regime (ATR)
- Trend strength (ADX)
- Mean reversion potential (RSI/BB)
- Correlation filtering
- Performance decay scoring

Outputs fleet configuration for deployment.
"""
from __future__ import annotations
import asyncio
import json
import logging
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any

log = logging.getLogger("alpha_omega.scanner.pair_scanner")

try:
    import aiohttp
except ImportError:
    log.critical("aiohttp required for scanner")
    raise

try:
    import numpy as np
except ImportError:
    log.warning("numpy not available, using pure python")
    np = None

from ..core.custom_types import MarketRegime


@dataclass
class PairCandidate:
    """Candidate trading pair with metrics."""
    symbol: str
    exchange: str
    base: str
    quote: str
    volume_24h: float = 0.0
    volume_usd_24h: float = 0.0
    spread_pct: float = 0.0
    atr_pct: float = 0.0
    adx: float = 0.0
    rsi: float = 50.0
    regime: MarketRegime = MarketRegime.UNKNOWN
    suitability: str = "grid"  # grid, scalp, dca, momentum, mean_reversion
    grid_score: float = 0.0
    risk_score: float = 0.0
    
    # Suggested parameters
    suggested_port: int = 0
    suggested_capital: float = 50.0
    suggested_grid_levels: int = 5
    suggested_spread_pct: float = 0.5
    suggested_per_level: float = 0.2


class PairScanner:
    """
    Scans exchanges for optimal trading pairs.
    
    Features:
    - Multi-exchange support (Kraken, OKX)
    - Regime detection (range, trend, transitional, extreme_vol)
    - Correlation matrix filtering
    - Performance decay scoring
    - Auto fleet config generation
    """

    def __init__(
        self,
        kraken_api_key: str = "",
        kraken_api_secret: str = "",
        okx_api_key: str = "",
        okx_api_secret: str = "",
        okx_passphrase: str = "",
        min_volume_usd: float = 1_000_000,  # $1M daily volume
        max_spread_pct: float = 0.5,
        min_atr_pct: float = 0.1,
        max_atr_pct: float = 5.0,
        correlation_threshold: float = 0.7,
    ):
        self.kraken_api_key = kraken_api_key
        self.kraken_api_secret = kraken_api_secret
        self.okx_api_key = okx_api_key
        self.okx_api_secret = okx_api_secret
        self.okx_passphrase = okx_passphrase
        self.min_volume_usd = min_volume_usd
        self.max_spread_pct = max_spread_pct
        self.min_atr_pct = min_atr_pct
        self.max_atr_pct = max_atr_pct
        self.correlation_threshold = correlation_threshold
        
        # HTTP session
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Kraken symbol mapping
        self.kraken_symbols = {
            "BTC/EUR": "XXBTZEUR",
            "ETH/EUR": "XETHZEUR",
            "SOL/EUR": "SOLEUR",
            "DOGE/EUR": "XDGXEUR",
            "XRP/EUR": "XXRPZEUR",
            "ADA/EUR": "ADAEUR",
            "LINK/EUR": "LINKXEUR",
            "AVAX/EUR": "AVAXEUR",
            "MATIC/EUR": "MATICEUR",
            "DOT/EUR": "DOTXEUR",
            "LTC/EUR": "XLTCZEUR",
            "BCH/EUR": "BCHXEUR",
        }
        
        # OKX symbol mapping
        self.okx_symbols = {
            "BTC/USDT": "BTC-USDT",
            "ETH/USDT": "ETH-USDT",
            "SOL/USDT": "SOL-USDT",
            "DOGE/USDT": "DOGE-USDT",
            "XRP/USDT": "XRP-USDT",
            "ADA/USDT": "ADA-USDT",
            "LINK/USDT": "LINK-USDT",
            "AVAX/USDT": "AVAX-USDT",
            "MATIC/USDT": "MATIC-USDT",
            "DOT/USDT": "DOT-USDT",
            "BICO/USDT": "BICO-USDT",
            "GRVT/USDT": "GRVT-USDT",
        }

    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=30)
        self._session = aiohttp.ClientSession(timeout=timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            await self._session.close()

    async def scan_kraken(self) -> List[PairCandidate]:
        """Scan Kraken for EUR pairs."""
        candidates = []
        
        try:
            # Get ticker data for all pairs
            url = "https://api.kraken.com/0/public/Ticker"
            pairs = ",".join(self.kraken_symbols.values())
            async with self._session.get(url, params={"pair": pairs}) as resp:
                data = await resp.json()
            
            result = data.get("result", {})
            
            for symbol, kraken_symbol in self.kraken_symbols.items():
                if kraken_symbol not in result:
                    continue
                
                t = result[kraken_symbol]
                bid = float(t["b"][0])
                ask = float(t["a"][0])
                last = float(t["c"][0])
                volume = float(t["v"][1])  # 24h volume
                high = float(t["h"][1])
                low = float(t["l"][1])
                
                spread_pct = ((ask - bid) / last * 100) if last > 0 else 0
                volume_usd = volume * last  # Approximate
                
                # Filter by volume and spread
                if volume_usd < self.min_volume_usd:
                    continue
                if spread_pct > self.max_spread_pct:
                    continue
                
                base, quote = symbol.split("/")
                
                candidate = PairCandidate(
                    symbol=symbol,
                    exchange="kraken",
                    base=base,
                    quote=quote,
                    volume_24h=volume,
                    volume_usd_24h=volume_usd,
                    spread_pct=spread_pct,
                    suggested_port=self._get_port_for_symbol(symbol, "kraken"),
                )
                candidates.append(candidate)
        
        except Exception as e:
            log.error(f"Kraken scan error: {e}")
        
        return candidates

    async def scan_okx(self) -> List[PairCandidate]:
        """Scan OKX for USDT pairs."""
        candidates = []
        
        try:
            url = "https://www.okx.com/api/v5/market/tickers"
            async with self._session.get(url, params={"instType": "SPOT"}) as resp:
                data = await resp.json()
            
            result = data.get("data", [])
            
            for ticker in result:
                inst_id = ticker.get("instId", "")
                if inst_id not in self.okx_symbols.values():
                    continue
                
                # Find our symbol
                symbol = None
                for s, oid in self.okx_symbols.items():
                    if oid == inst_id:
                        symbol = s
                        break
                
                if not symbol:
                    continue
                
                bid = float(ticker.get("bidPx", 0))
                ask = float(ticker.get("askPx", 0))
                last = float(ticker.get("last", 0))
                volume = float(ticker.get("vol24h", 0))
                
                spread_pct = ((ask - bid) / last * 100) if last > 0 else 0
                volume_usd = volume * last
                
                if volume_usd < self.min_volume_usd:
                    continue
                if spread_pct > self.max_spread_pct:
                    continue
                
                base, quote = symbol.split("/")
                
                candidate = PairCandidate(
                    symbol=symbol,
                    exchange="okx",
                    base=base,
                    quote=quote,
                    volume_24h=volume,
                    volume_usd_24h=volume_usd,
                    spread_pct=spread_pct,
                    suggested_port=self._get_port_for_symbol(symbol, "okx"),
                )
                candidates.append(candidate)
        
        except Exception as e:
            log.error(f"OKX scan error: {e}")
        
        return candidates

    def _get_port_for_symbol(self, symbol: str, exchange: str) -> int:
        """Get assigned port for symbol/exchange."""
        # Port assignment logic
        kraken_ports = {
            "SOL/EUR": 8912, "DOGE/EUR": 8913, "XRP/EUR": 8914,
            "ADA/EUR": 8915, "LINK/EUR": 8916, "ETH/EUR": 8917,
            "BTC/EUR": 8920, "AVAX/EUR": 8923,
        }
        okx_ports = {
            "BICO/USDT": 8930, "GRVT/USDT": 8931, "ADA/USDT": 8932,
            "SOL/USDT": 8933, "XRP/USDT": 8934, "DOGE/USDT": 8935,
            "LINK/USDT": 8934, "BTC/USDT": 8930,
        }
        
        if exchange == "kraken":
            return kraken_ports.get(symbol, 8900)
        else:
            return okx_ports.get(symbol, 8930)

    async def enrich_with_indicators(self, candidates: List[PairCandidate]) -> List[PairCandidate]:
        """Fetch OHLCV and compute ATR, ADX, RSI for each candidate."""
        enriched = []
        
        for candidate in candidates:
            try:
                ohlcv = await self._fetch_ohlcv(candidate)
                if not ohlcv or len(ohlcv) < 20:
                    continue
                
                # Compute indicators
                atr_pct = self._compute_atr(ohlcv, 14)
                adx = self._compute_adx(ohlcv, 14)
                rsi = self._compute_rsi(ohlcv, 14)
                
                if atr_pct < self.min_atr_pct or atr_pct > self.max_atr_pct:
                    continue
                
                candidate.atr_pct = atr_pct
                candidate.adx = adx
                candidate.rsi = rsi
                
                # Detect regime
                candidate.regime = self._detect_regime(adx, rsi)
                candidate.suitability = self._determine_suitability(candidate)
                
                # Calculate grid score
                candidate.grid_score = self._calculate_grid_score(candidate)
                candidate.risk_score = self._calculate_risk_score(candidate)
                
                # Suggest parameters
                candidate.suggested_spread_pct = max(0.2, min(2.5, atr_pct * 0.7))
                candidate.suggested_grid_levels = 5 if candidate.regime == MarketRegime.RANGE else 3
                
                enriched.append(candidate)
                
            except Exception as e:
                log.debug(f"Failed to enrich {candidate.symbol}: {e}")
        
        return enriched

    async def _fetch_ohlcv(self, candidate: PairCandidate, timeframe: str = "1h", limit: int = 100) -> List[Dict]:
        """Fetch OHLCV data for candidate."""
        if candidate.exchange == "kraken":
            url = "https://api.kraken.com/0/public/OHLC"
            params = {
                "pair": self.kraken_symbols.get(candidate.symbol, "").replace("/", ""),
                "interval": 60,  # 1 hour
            }
        else:
            url = "https://www.okx.com/api/v5/market/candles"
            tf_map = {"1h": "1H", "4h": "4H", "1d": "1D"}
            params = {
                "instId": self.okx_symbols.get(candidate.symbol, ""),
                "bar": tf_map.get(timeframe, "1H"),
                "limit": str(limit),
            }
        
        try:
            async with self._session.get(url, params=params) as resp:
                data = await resp.json()
            
            if candidate.exchange == "kraken":
                result = data.get("result", {})
                for pair, candles in result.items():
                    return [
                        {
                            "timestamp": int(c[0]),
                            "open": float(c[1]),
                            "high": float(c[2]),
                            "low": float(c[3]),
                            "close": float(c[4]),
                            "volume": float(c[6]),
                        }
                        for c in candles[-limit:]
                    ]
            else:
                result = data.get("data", [])
                return [
                    {
                        "timestamp": int(c[0]),
                        "open": float(c[1]),
                        "high": float(c[2]),
                        "low": float(c[3]),
                        "close": float(c[4]),
                        "volume": float(c[5]),
                    }
                    for c in result[-limit:]
                ]
        except Exception as e:
            log.debug(f"OHLCV fetch failed for {candidate.symbol}: {e}")
        
        return []

    def _compute_atr(self, ohlcv: List[Dict], period: int) -> float:
        """Compute ATR as percentage of price."""
        if len(ohlcv) < period + 1:
            return 0.0
        
        trs = []
        for i in range(1, len(ohlcv)):
            high = ohlcv[i]["high"]
            low = ohlcv[i]["low"]
            prev_close = ohlcv[i-1]["close"]
            
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            trs.append(tr)
        
        atr = sum(trs[-period:]) / period
        current_price = ohlcv[-1]["close"]
        
        return (atr / current_price * 100) if current_price > 0 else 0.0

    def _compute_adx(self, ohlcv: List[Dict], period: int) -> float:
        """Compute ADX (Average Directional Index)."""
        if len(ohlcv) < period * 2:
            return 0.0
        
        # Simplified ADX calculation
        plus_dm = []
        minus_dm = []
        trs = []
        
        for i in range(1, len(ohlcv)):
            high = ohlcv[i]["high"]
            low = ohlcv[i]["low"]
            prev_high = ohlcv[i-1]["high"]
            prev_low = ohlcv[i-1]["low"]
            prev_close = ohlcv[i-1]["close"]
            
            up_move = high - prev_high
            down_move = prev_low - low
            
            plus_dm.append(up_move if up_move > down_move and up_move > 0 else 0)
            minus_dm.append(down_move if down_move > up_move and down_move > 0 else 0)
            
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            trs.append(tr)
        
        # Smooth with Wilder's smoothing
        def wilder_smooth(values, period):
            if len(values) < period:
                return 0
            smoothed = sum(values[:period]) / period
            for v in values[period:]:
                smoothed = smoothed - smoothed / period + v
            return smoothed
        
        plus_di = 100 * wilder_smooth(plus_dm, period) / wilder_smooth(trs, period) if wilder_smooth(trs, period) > 0 else 0
        minus_di = 100 * wilder_smooth(minus_dm, period) / wilder_smooth(trs, period) if wilder_smooth(trs, period) > 0 else 0
        
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di) if (plus_di + minus_di) > 0 else 0
        
        # ADX is smoothed DX
        return dx  # Simplified

    def _compute_rsi(self, ohlcv: List[Dict], period: int) -> float:
        """Compute RSI."""
        if len(ohlcv) < period + 1:
            return 50.0
        
        closes = [c["close"] for c in ohlcv]
        gains = []
        losses = []
        
        for i in range(1, len(closes)):
            diff = closes[i] - closes[i-1]
            gains.append(max(diff, 0))
            losses.append(max(-diff, 0))
        
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def _detect_regime(self, adx: float, rsi: float) -> MarketRegime:
        """Detect market regime."""
        if adx > 30:
            return MarketRegime.TREND
        elif adx < 20:
            return MarketRegime.RANGE
        else:
            return MarketRegime.TRANSITIONAL

    def _determine_suitability(self, candidate: PairCandidate) -> str:
        """Determine best strategy for pair."""
        if candidate.regime == MarketRegime.TREND:
            if candidate.adx > 40:
                return "momentum"
            return "scalp"
        elif candidate.regime == MarketRegime.RANGE:
            if candidate.rsi < 35 or candidate.rsi > 65:
                return "mean_reversion"
            return "grid"
        else:
            return "dca"

    def _calculate_grid_score(self, candidate: PairCandidate) -> float:
        """Calculate suitability score for grid trading."""
        score = 0.0
        
        # Regime bonus
        if candidate.regime == MarketRegime.RANGE:
            score += 40
        elif candidate.regime == MarketRegime.TRANSITIONAL:
            score += 20
        
        # ATR bonus (moderate volatility good for grid)
        if 0.5 <= candidate.atr_pct <= 2.0:
            score += 20
        elif 0.3 <= candidate.atr_pct <= 3.0:
            score += 10
        
        # Spread penalty
        if candidate.spread_pct < 0.1:
            score += 15
        elif candidate.spread_pct < 0.3:
            score += 10
        elif candidate.spread_pct < 0.5:
            score += 5
        
        # Volume bonus
        if candidate.volume_usd_24h > 10_000_000:
            score += 15
        elif candidate.volume_usd_24h > 5_000_000:
            score += 10
        elif candidate.volume_usd_24h > 1_000_000:
            score += 5
        
        # RSI in middle range
        if 40 <= candidate.rsi <= 60:
            score += 10
        
        return min(score, 100.0)

    def _calculate_risk_score(self, candidate: PairCandidate) -> float:
        """Calculate risk score (lower = better)."""
        risk = 0.0
        
        # High ATR = higher risk
        risk += candidate.atr_pct * 5
        
        # Wide spread = higher risk
        risk += candidate.spread_pct * 10
        
        # Extreme RSI = higher risk
        if candidate.rsi < 25 or candidate.rsi > 75:
            risk += 10
        
        # Low volume = higher risk
        if candidate.volume_usd_24h < 2_000_000:
            risk += 15
        
        return risk

    def filter_by_correlation(self, candidates: List[PairCandidate]) -> List[PairCandidate]:
        """Filter candidates to avoid highly correlated pairs."""
        # Group by base currency
        by_base = {}
        for c in candidates:
            by_base.setdefault(c.base, []).append(c)
        
        # For each base, keep only the best candidate
        filtered = []
        for base, group in by_base.items():
            # Sort by grid_score descending
            group.sort(key=lambda x: x.grid_score, reverse=True)
            filtered.append(group[0])  # Keep best
            
            # Optionally keep second if very different quotes
            if len(group) > 1 and group[0].quote != group[1].quote:
                if group[1].grid_score > 60:
                    filtered.append(group[1])
        
        return filtered

    def select_top_pairs(self, candidates: List[PairCandidate], max_pairs: int = 12) -> List[PairCandidate]:
        """Select top N pairs by grid score."""
        candidates.sort(key=lambda x: x.grid_score, reverse=True)
        return candidates[:max_pairs]

    async def generate_fleet_config(
        self,
        total_capital: float = 200.0,
        kraken_allocation: float = 0.5,
        okx_allocation: float = 0.5,
        max_pairs_per_exchange: int = 6,
    ) -> Dict[str, Any]:
        """Generate complete fleet configuration."""
        
        # Scan both exchanges
        kraken_candidates = await self.scan_kraken()
        okx_candidates = await self.scan_okx()
        
        log.info(f"Raw candidates: Kraken={len(kraken_candidates)}, OKX={len(okx_candidates)}")
        
        # Enrich with indicators
        kraken_enriched = await self.enrich_with_indicators(kraken_candidates)
        okx_enriched = await self.enrich_with_indicators(okx_candidates)
        
        log.info(f"Enriched: Kraken={len(kraken_enriched)}, OKX={len(okx_enriched)}")
        
        # Filter by correlation
        kraken_filtered = self.filter_by_correlation(kraken_enriched)
        okx_filtered = self.filter_by_correlation(okx_enriched)
        
        # Select top pairs
        kraken_selected = self.select_top_pairs(kraken_filtered, max_pairs_per_exchange)
        okx_selected = self.select_top_pairs(okx_filtered, max_pairs_per_exchange)
        
        # Build config
        capital_per_kraken = (total_capital * kraken_allocation) / len(kraken_selected) if kraken_selected else 0
        capital_per_okx = (total_capital * okx_allocation) / len(okx_selected) if okx_selected else 0
        
        pairs = []
        for c in kraken_selected:
            pairs.append({
                "symbol": c.symbol,
                "exchange": c.exchange,
                "port": c.suggested_port,
                "capital": round(capital_per_kraken, 2),
                "regime": c.regime.value,
                "suitability": c.suitability,
                "atr_pct": round(c.atr_pct, 2),
                "adx": round(c.adx, 1),
                "rsi": round(c.rsi, 1),
                "grid_levels": c.suggested_grid_levels,
                "spread_pct": round(c.suggested_spread_pct, 2),
                "per_level": c.suggested_per_level,
                "max_drawdown_pct": 0.15,
                "max_daily_loss_pct": 0.05,
                "use_momentum_filter": True,
                "hybrid_mode": True,
                "state_file": f"/tmp/shadowgrid_state_{c.exchange}_{c.symbol.replace('/', '_')}.json",
                "log_file": f"/tmp/shadowgrid_{c.exchange}_{c.symbol.replace('/', '_')}.log",
            })
        
        okx_pairs = []
        for c in okx_selected:
            okx_pairs.append({
                "symbol": c.symbol,
                "exchange": c.exchange,
                "port": c.suggested_port,
                "capital": round(capital_per_okx, 2),
                "regime": c.regime.value,
                "suitability": c.suitability,
                "atr_pct": round(c.atr_pct, 2),
                "adx": round(c.adx, 1),
                "rsi": round(c.rsi, 1),
                "grid_levels": c.suggested_grid_levels,
                "spread_pct": round(c.suggested_spread_pct, 2),
                "per_level": c.suggested_per_level,
                "max_drawdown_pct": 0.15,
                "max_daily_loss_pct": 0.05,
                "use_momentum_filter": True,
                "hybrid_mode": True,
                "state_file": f"/tmp/shadowgrid_state_{c.exchange}_{c.symbol.replace('/', '_')}.json",
                "log_file": f"/tmp/shadowgrid_{c.exchange}_{c.symbol.replace('/', '_')}.log",
            })
        
        return {
            "version": "2.2",
            "total_fleet_capital": total_capital,
            "capital_per_exchange": {
                "kraken": round(total_capital * kraken_allocation, 2),
                "okx": round(total_capital * okx_allocation, 2),
            },
            "pairs": pairs,
            "okx_pairs": okx_pairs,
            "risk_params": {
                "max_portfolio_dd": 0.20,
                "max_daily_loss": 0.05,
                "max_exposure_per_base": 0.30,
                "max_correlation": 0.7,
                "max_positions_per_base": 2,
                "volatility_targeting": True,
            },
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "scan_version": "2.2",
        }

    async def save_fleet_configs(self, config: Dict, nuvola_path: str, marcodg1_path: str) -> None:
        """Save fleet configs for both nodes with appropriate pair distribution."""
        # For Nuvola: Kraken pairs + OKX pairs
        nuvola_config = config.copy()
        
        # For MARCODG1: Different Kraken pairs (diversification)
        marcodg1_config = config.copy()
        
        # Could implement different pair selection per node
        # For now, save same config to both
        with open(nuvola_path, 'w') as f:
            json.dump(nuvola_config, f, indent=2)
        
        with open(marcodg1_path, 'w') as f:
            json.dump(marcodg1_config, f, indent=2)
        
        log.info(f"Fleet configs saved: {nuvola_path}, {marcodg1_path}")


async def main() -> None:
    """Main entry point for pair scanner."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Alpha-Omega Pair Scanner")
    parser.add_argument("--capital", type=float, default=200.0)
    parser.add_argument("--kraken-allocation", type=float, default=0.5)
    parser.add_argument("--okx-allocation", type=float, default=0.5)
    parser.add_argument("--max-pairs", type=int, default=6)
    parser.add_argument("--output-nuvola", default="fleet_config_nuvola.json")
    parser.add_argument("--output-marcodg1", default="fleet_config_marcodg1.json")
    args = parser.parse_args()
    
    # Get API keys from env
    scanner = PairScanner(
        kraken_api_key=os.getenv("KRAKEN_API_KEY", ""),
        kraken_api_secret=os.getenv("KRAKEN_API_SECRET", ""),
        okx_api_key=os.getenv("OKX_API_KEY", ""),
        okx_api_secret=os.getenv("OKX_API_SECRET", ""),
        okx_passphrase=os.getenv("OKX_PASSPHRASE", ""),
    )
    
    async with scanner:
        config = await scanner.generate_fleet_config(
            total_capital=args.capital,
            kraken_allocation=args.kraken_allocation,
            okx_allocation=args.okx_allocation,
            max_pairs_per_exchange=args.max_pairs,
        )
        
        await scanner.save_fleet_configs(config, args.output_nuvola, args.output_marcodg1)
        
        print(json.dumps(config, indent=2))


if __name__ == "__main__":
    import os
    asyncio.run(main())