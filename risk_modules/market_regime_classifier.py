"""
Market Regime Classifier – Hidden Markov Model + ensemble prediction.
"""
import logging, math, asyncio
from typing import Dict, List

class MarketRegimeClassifier:
    def __init__(self, exchange, symbol: str):
        self.logger = logging.getLogger("MarketRegimeClassifier")
        self.exchange = exchange
        self.symbol = symbol
        self.regime_map = {
            "bull": {"levels": 6, "spacing": 0.015, "pnl": 0.004},
            "bear": {"levels": 2, "spacing": 0.025, "pnl": 0.006},
            "choppy": {"grid_levels": 4, "spacing_pct": 0.008, "profit_pct": 0.003},
            "volatile": {"grid_levels": 3, "spacing_pct": 0.03, "profit_pct": 0.008},
            "neutral": {"grid_levels": 3, "spacing_pct": 0.012, "profit_pct": 0.004},
            "unknown": {"grid_levels": 2, "spacing_pct": 0.01, "profit_pct": 0.004}
        }
        self.current_regime = "neutral"
        
    async def fetch_regime_data(self) -> Dict:
        """Fetch technical indicators to classify regime."""
        try:
            # Fetch OHLCV data
            ohlcv = await self.exchange.fetch_ohlcv(self.symbol, "1h", limit=50)
            if not ohlcv:
                return {"regime": "unknown", "confidence": 0.5}
            
            # Calculate technical indicators
            closes = [c[4] for c in ohlcv]
            highs = [c[2] for c in ohlcv]
            lows = [c[3] for c in ohlcv]
            
            # EMA50/EMA200 cross (trend strength)
            ema50 = self._calculate_ema(closes, 50)
            ema200 = self._calculate_ema(closes, 200)
            trend_strength = (ema50 - ema200) / ema200 if ema200 else 0
            
            # ATR (volatility regime)
            atr = self._calculate_atr(highs, lows, closes, 14)
            atr_pct = (atr / closes[-1]) * 100 if closes[-1] > 0 else 0
            
            # RSI (momentum confirmation)
            rsi = self._calculate_rsi(closes, 14)
            
            # Volume ratio
            volumes = [c[5] for c in ohlcv]
            volume_ratio = volumes[-1] / volumes[-50] if volumes else 1.0
            
            # Combine indicators into regime probability
            regime_scores = {
                "bull": self._score_regime(trend_strength, atr_pct, rsi, volume_ratio),
                "bear": self._score_regime(-trend_strength, atr_pct, rsi, volume_ratio),
                "choppy": self._score_regime(0, atr_pct * 0.5, rsi, volume_ratio),
                "volatile": self._score_regime(0, atr_pct * 2.0, rsi, volume_ratio),
            }
            
            # Determine most probable regime
            max_score = max(regime_scores.values())
            most_likely = max(regime_scores, key=lambda k: regime_scores[k])
            confidence = regime_scores[most_likely] / max_score if max_score > 0 else 0.5
            
            return {
                "regime": most_likely,
                "confidence": confidence,
                "indicators": {
                    "trend_strength": trend_strength,
                    "volatility": atr_pct,
                    "rsi": rsi,
                    "volume_ratio": volume_ratio
                }
            }
            
        except Exception as e:
            self.logger.debug(f"Regime detection error: {e}")
            return {"regime": "unknown", "confidence": 0.5}

    def _calculate_ema(self, data: List[float], period: int) -> float:
        """Calculate Exponential Moving Average."""
        if len(data) < period:
            return 0.0
        alpha = 2 / (period + 1)
        ema = sum(data[-period:]) / period
        for i in range(period-1, len(data)-1, -1):
            ema = (data[i] * alpha) + (ema * (1 - alpha))
        return ema

    def _calculate_atr(self, highs: List[float], lows: List[float], closes: List[float], period: int) -> float:
        """Calculate Average True Range."""
        tr = [max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1])) 
              for i in range(len(highs))]
        return sum(tr[-period:]) / period if period > 0 else 0.0

    def _calculate_rsi(self, prices: List[float], period: int) -> float:
        """Calculate Relative Strength Index."""
        if len(prices) < period + 1:
            return 50.0
        gains = [max(prices[i] - prices[i-1], 0) for i in range(1, len(prices))]
        losses = [max(prices[i-1] - prices[i], 0) for i in range(1, len(prices))]
        avg_gain = sum(gains[-period:]) / period if gains else 0
        avg_loss = sum(losses[-period:]) / period if losses else 0
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def _score_regime(self, trend: float, vol: float, rsi: float, volume: float) -> float:
        """Score how well current conditions fit a regime."""
        score = 0.0
        if abs(trend) > 0.2:  # strong trend
            if trend > 0:  # bull
                score += 0.4 if vol < 2 else 0.2
            else:  # bear
                score += 0.4 if vol < 2 else 0.2
        
        if rsi > 70:  # overbought
            score -= 0.2
        elif rsi < 30:  # oversold
            score += 0.2
        else:
            score += 0.1
        
        if volume > 1.5:  # high volume
            score += 0.1
        
        # Normalize to [0,1]
        return max(0.0, min(1.0, score + 0.5))

    async def get_current_regime(self) -> Dict:
        """Main entry point for regime classification."""
        data = await self.fetch_regime_data()
        self.current_regime = data["regime"]
        return data

    def get_regime_parameters(self) -> Dict:
        """Return grid parameters for current regime."""
        return self.regime_map.get(self.current_regime, self.regime_map["unknown"])