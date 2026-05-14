#!/usr/bin/env python3
"""
DENARO STRATEGIES v4 - Modular Strategy Engine for Grid Bot
Implements: TrendFilter, VolatilityAdaptiveGrid, MartingaleLite,
            IntelligentRebalancer, ProfitOptimizer
"""
import time
import logging
import json
from pathlib import Path

logger = logging.getLogger("GridStrategy")

class TrendFilter:
    """EMA-200 + RSI-14 trend filter to pause trading during downtrends"""
    
    def __init__(self, config):
        self.ema_period = config.get('trend_ema_period', 200)
        self.rsi_period = config.get('trend_rsi_period', 14)
        self.cache = {}
        self.cache_ttl = 60
        
    def get_trend(self, client, symbol, current_price):
        """Returns: STRONG_UP, UP, NEUTRAL, DOWN, STRONG_DOWN"""
        now = time.time()
        if 'trend' in self.cache and now - self.cache.get('trend_ts', 0) < self.cache_ttl:
            return self.cache['trend']
        
        try:
            ohlcv = client.fetch_ohlcv(symbol, timeframe='1h', limit=max(self.ema_period + 1, self.rsi_period + 1))
            closes = [c[4] for c in ohlcv]
            if len(closes) < max(self.ema_period, self.rsi_period):
                return "NEUTRAL"
            
            # EMA-200
            ema = self._ema(closes, self.ema_period)
            ema_current = ema[-1] if ema else current_price
            
            # RSI-14
            rsi = self._rsi(closes, self.rsi_period)
            
            ema_dist = (current_price - ema_current) / ema_current * 100
            result = "NEUTRAL"
            
            if ema_dist > 1.0 and rsi < 70:
                result = "STRONG_UP"
            elif ema_dist > 0 and rsi < 75:
                result = "UP"
            elif ema_dist < -1.0 and rsi > 40:
                result = "STRONG_DOWN"
            elif ema_dist < 0 and rsi > 35:
                result = "DOWN"
            
            self.cache = {'trend': result, 'trend_ts': now, 'ema': ema_current, 'rsi': rsi}
            logger.info(f"📊 Trend: {result} | EMA dist: {ema_dist:.2f}% | RSI: {rsi:.1f}")
            return result
        except Exception as e:
            logger.error(f"TrendFilter error: {e}")
            return "NEUTRAL"
    
    def _ema(self, prices, period):
        if len(prices) < period: return []
        multiplier = 2 / (period + 1)
        ema = [sum(prices[:period]) / period]
        for p in prices[period:]:
            ema.append((p - ema[-1]) * multiplier + ema[-1])
        return ema
    
    def _rsi(self, prices, period):
        if len(prices) < period + 1: return 50
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0 for d in deltas[-period:]]
        losses = [-d if d < 0 else 0 for d in deltas[-period:]]
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        if avg_loss == 0: return 100
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))


class VolatilityGrid:
    """Volatility-adaptive grid spacing using ATR"""
    
    def __init__(self, config):
        self.base_range = config.get('grid_range_pct', 0.01)
        self.profit_target = config.get('profit_per_grid', 0.003)
        self.atr_factor = config.get('atr_spacing_factor', 4.0)
        self.multiplier = config.get('volatility_multiplier', 1.0)
        self.cache = {}
        
    def get_spacing(self, atr_value, current_price):
        """Returns (grid_range_pct, profit_per_grid) adjusted for volatility"""
        if atr_value is None or atr_value <= 0 or current_price <= 0:
            return self.base_range * self.multiplier, self.profit_target * self.multiplier
        
        atr_pct = atr_value / current_price
        # Volatility factor: how many times ATR fits in base range
        vol_factor = max(0.5, min(2.0, (atr_pct * self.atr_factor) / max(self.base_range, 0.001)))
        
        grid_range = self.base_range * vol_factor * self.multiplier
        profit = self.profit_target * vol_factor * self.multiplier
        
        return grid_range, profit


class MartingaleLite:
    """Progressive position sizing: larger orders at lower prices"""
    
    def __init__(self, config):
        self.factor = config.get('martingale_factor', 1.12)
        self.base_size = config.get('base_order_eur', 10.0)
    
    def get_size(self, level_index):
        """level_index: 0 = highest price level (first to fill)"""
        return self.base_size * (self.factor ** level_index)
    
    def get_total_for_levels(self, num_levels):
        total = 0
        for i in range(num_levels):
            total += self.get_size(i)
        return total


class Rebalancer:
    """Intelligent grid re-centering"""
    
    def __init__(self, config):
        self.interval = config.get('rebalance_interval_sec', 300)
        self.last_rebalance = 0
        
    def needs_rebalance(self, current_price, grid_buy_levels, config):
        """Check if grid needs re-centering"""
        if not grid_buy_levels:
            return False
        
        now = time.time()
        if now - self.last_rebalance < self.interval:
            return False
        
        center = (max(grid_buy_levels) + min(grid_buy_levels)) / 2
        dist = abs(current_price - center) / max(center, 0.001) * 100
        
        threshold = config.get('out_of_bounds_threshold', 0.02) * 100  # 2%
        if dist > threshold:
            logger.info(f"🔄 Rebalance triggered: price moved {dist:.2f}% from grid center ({center:.2f}€ vs {current_price:.2f}€)")
            return True
        
        return False
    
    def mark_rebalanced(self):
        self.last_rebalance = time.time()


class ProfitOptimizer:
    """Real-time performance tracking and risk adjustment"""
    
    def __init__(self, config):
        self.trades_file = Path(".tmp") / "profit_optimizer_trades.json"
        self.trades = self._load_trades()
        self.last_adjustment = 0
        self.adjustment_interval = 3600  # Check hourly

    def _load_trades(self):
        if self.trades_file.exists():
            try:
                with open(self.trades_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load optimizer trades: {e}")
        return []

    def _save_trades(self):
        try:
            self.trades_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.trades_file, 'w') as f:
                json.dump(self.trades, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save optimizer trades: {e}")
        
    def add_trade(self, profit):
        self.trades.append({'profit': profit, 'time': time.time()})
        # Keep last 50 trades
        if len(self.trades) > 50:
            self.trades = self.trades[-50:]
        self._save_trades()  # Persist after each addition
    
    def get_metrics(self):
        if not self.trades:
            return None
        wins = [t for t in self.trades if t['profit'] > 0]
        losses = [t for t in self.trades if t['profit'] <= 0]
        
        total_profit = sum(t['profit'] for t in self.trades)
        win_rate = len(wins) / len(self.trades) * 100 if self.trades else 0
        avg_profit = total_profit / len(self.trades) if self.trades else 0
        profit_factor = abs(sum(t['profit'] for t in wins) / min(abs(sum(t['profit'] for t in losses)), 0.001)) if losses else 99
        
        return {
            'total_trades': len(self.trades),
            'win_rate': win_rate,
            'avg_profit': avg_profit,
            'profit_factor': profit_factor,
            'total_profit': total_profit
        }
    
    def get_adjustment(self, current_base_order):
        """Returns multiplier to adjust base_order_eur, or 1.0"""
        now = time.time()
        if now - self.last_adjustment < self.adjustment_interval:
            return 1.0
        
        metrics = self.get_metrics()
        if not metrics or metrics['total_trades'] < 5:
            return 1.0
        
        self.last_adjustment = now
        
        if metrics['total_trades'] >= 10 and metrics['win_rate'] > 60 and metrics['profit_factor'] > 1.5:
            logger.info(f"📈 ProfitOptimizer: Increasing risk (WR={metrics['win_rate']:.0f}% PF={metrics['profit_factor']:.2f})")
            return 1.15  # +15%
        elif metrics['total_trades'] >= 5 and (metrics['win_rate'] < 40 or metrics['profit_factor'] < 0.8):
            logger.info(f"📉 ProfitOptimizer: Reducing risk (WR={metrics['win_rate']:.0f}% PF={metrics['profit_factor']:.2f})")
            return 0.75  # -25%
        
        return 1.0
