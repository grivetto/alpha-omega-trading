#!/usr/bin/env python3
"""
DENARO STRATEGIES v5 — Adaptive Strategy Engine for Grid Bot
Implements: AdaptiveTrendFilter, VolatilityAdaptiveGrid, MartingaleLite,
            IntelligentRebalancer, ProfitOptimizer

Changes from v4:
- TrendFilter: Continuous risk factor (0.0-1.0) instead of binary pause
- Grid operates in ALL market conditions with adaptive sizing
- ProfitOptimizer persists adjustments to config file
"""
import time
import logging
import json
from pathlib import Path

logger = logging.getLogger("GridStrategy")


class AdaptiveTrendFilter:
    """
    EMA-200 + RSI-14 trend filter with CONTINUOUS risk factor.
    Returns a float [0.0..1.0] indicating how aggressively to trade:
      1.0 = full aggression (strong uptrend)
      0.5 = reduced grid (ranging/mild downtrend)
      0.6 = reduced grid (downtrend — but still trade!)
    The grid bot NEVER fully pauses based on trend alone.
    """

    def __init__(self, config):
        self.ema_period = config.get('trend_ema_period', 200)
        self.rsi_period = config.get('trend_rsi_period', 14)
        self.cache = {}
        self.cache_ttl = 60

    def get_risk_factor(self, client, symbol, current_price):
        """
        Returns float [0.0..1.0]:
          1.0 = strong buy conditions
          0.8 = uptrend
          0.6 = neutral
          0.4 = mild downtrend
          0.6 = reduced (still trade!)
          0.0 = extreme conditions (use as circuit breaker only)
        """
        now = time.time()
        cache_key = 'risk_factor'
        if cache_key in self.cache and now - self.cache.get('cache_ts', 0) < self.cache_ttl:
            return self.cache[cache_key]

        try:
            ohlcv = client.fetch_ohlcv(symbol, timeframe='1h', limit=max(self.ema_period + 1, self.rsi_period + 1))
            closes = [c[4] for c in ohlcv]
            if len(closes) < max(self.ema_period, self.rsi_period):
                return 0.6  # Neutral when insufficient data

            # EMA-200
            ema = self._ema(closes, self.ema_period)
            ema_current = ema[-1] if ema else current_price

            # RSI-14
            rsi = self._rsi(closes, self.rsi_period)

            ema_dist = (current_price - ema_current) / ema_current * 100

            # Risk factor calculation (continuous, not binary)
            # EMA component: price above EMA = bullish, below = bearish
            # EMA dist range: typically -5% to +10%
            ema_component = max(0.0, min(1.0, (ema_dist + 5.0) / 15.0))
            # Maps: ema_dist=-5% -> 0.0, ema_dist=0% -> 0.33, ema_dist=+10% -> 1.0

            # RSI component: oversold = bullish, overbought = bearish
            rsi_component = max(0.0, min(1.0, (rsi - 20.0) / 60.0))
            # Maps: RSI=20 -> 0.0, RSI=50 -> 0.5, RSI=80 -> 1.0

            # Weighted combination (EMA more important for trend)
            risk = ema_component * 0.6 + rsi_component * 0.4
            risk = max(0.6, min(1.0, risk))  # Floor at 0.6 — ALWAYS trade at least 60%

            # Floor for extreme oversold (buying opportunity)
            if rsi < 25 and ema_dist < -3.0:
                risk = max(risk, 0.4)  # Boost grid activity in potential capitulation

            self.cache = {cache_key: risk, 'cache_ts': now, 'ema': ema_current, 'rsi': rsi,
                         'ema_dist': ema_dist}
            logger.info(f"📊 Trend: risk_factor={risk:.2f} | EMA dist: {ema_dist:.2f}% | RSI: {rsi:.1f}")
            return risk
        except Exception as e:
            logger.error(f"AdaptiveTrendFilter error: {e}")
            return 0.6  # Default to neutral on error

    def get_trend_label(self, risk_factor):
        """Convert numeric risk factor to human-readable label"""
        if risk_factor >= 0.8:
            return "STRONG_UP"
        elif risk_factor >= 0.6:
            return "UP"
        elif risk_factor >= 0.4:
            return "NEUTRAL"
        elif risk_factor >= 0.25:
            return "DOWN"
        else:
            return "STRONG_DOWN"

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


class IntelligentRebalancer:
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
    """
    Real-time performance tracking and risk adjustment.
    v5: PERSISTS adjustments to config file and applies them on next load.
    """

    def __init__(self, config, config_path=None):
        self.trades_file = Path(".tmp") / "profit_optimizer_trades.json"
        self.config_path = config_path  # Path to grid_config.json for persistence
        self.trades = self._load_trades()
        self.last_adjustment = 0
        self.adjustment_interval = 3600  # Check hourly
        self.current_multiplier = 1.0
        self._load_persisted_adjustment()

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

    def _load_persisted_adjustment(self):
        """Load previously saved adjustment from config"""
        if self.config_path:
            try:
                with open(self.config_path, 'r') as f:
                    cfg = json.load(f)
                self.current_multiplier = cfg.get('optimizer_multiplier', 1.0)
                logger.info(f"📊 ProfitOptimizer: Loaded persisted multiplier: {self.current_multiplier:.2f}x")
            except Exception:
                self.current_multiplier = 1.0

    def _persist_adjustment(self):
        """Save adjustment multiplier to config file"""
        if self.config_path:
            try:
                with open(self.config_path, 'r') as f:
                    cfg = json.load(f)
                cfg['optimizer_multiplier'] = round(self.current_multiplier, 4)
                cfg['last_optimization'] = time.strftime('%Y-%m-%d %H:%M:%S')
                with open(self.config_path, 'w') as f:
                    json.dump(cfg, f, indent=4)
                logger.info(f"💾 ProfitOptimizer: Persisted multiplier {self.current_multiplier:.2f}x to config")
            except Exception as e:
                logger.error(f"Failed to persist optimizer adjustment: {e}")

    def add_trade(self, profit):
        self.trades.append({'profit': profit, 'time': time.time()})
        # Keep last 50 trades
        if len(self.trades) > 50:
            self.trades = self.trades[-50:]
        self._save_trades()

    def get_metrics(self):
        if not self.trades:
            return None
        wins = [t for t in self.trades if t['profit'] > 0]
        losses = [t for t in self.trades if t['profit'] <= 0]

        total_profit = sum(t['profit'] for t in self.trades)
        win_rate = len(wins) / len(self.trades) * 100 if self.trades else 0
        avg_profit = total_profit / len(self.trades) if self.trades else 0
        profit_factor = abs(sum(t['profit'] for t in wins) / max(abs(sum(t['profit'] for t in losses)), 0.001)) if losses else 99

        return {
            'total_trades': len(self.trades),
            'win_rate': win_rate,
            'avg_profit': avg_profit,
            'profit_factor': profit_factor,
            'total_profit': total_profit
        }

    def get_adjustment(self, current_base_order):
        """
        Returns (multiplier, adjusted_base_order).
        Now ACTUALLY applies the adjustment and persists it.
        """
        # Apply any previously persisted multiplier
        adjusted = current_base_order * self.current_multiplier

        now = time.time()
        if now - self.last_adjustment < self.adjustment_interval:
            return 1.0, adjusted

        metrics = self.get_metrics()
        if not metrics or metrics['total_trades'] < 5:
            return 1.0, adjusted

        self.last_adjustment = now
        new_multiplier = 1.0

        if metrics['total_trades'] >= 10 and metrics['win_rate'] > 60 and metrics['profit_factor'] > 1.5:
            new_multiplier = 1.15  # +15%
            logger.info(f"📈 ProfitOptimizer: Increasing risk (WR={metrics['win_rate']:.0f}% PF={metrics['profit_factor']:.2f})")
        elif metrics['total_trades'] >= 5 and (metrics['win_rate'] < 40 or metrics['profit_factor'] < 0.8):
            new_multiplier = 0.75  # -25%
            logger.info(f"📉 ProfitOptimizer: Reducing risk (WR={metrics['win_rate']:.0f}% PF={metrics['profit_factor']:.2f})")

        if new_multiplier != 1.0:
            self.current_multiplier *= new_multiplier
            self.current_multiplier = max(0.25, min(3.0, self.current_multiplier))  # Bound: 25% to 300%
            self._persist_adjustment()
            adjusted = current_base_order * self.current_multiplier
            logger.info(f"💰 ProfitOptimizer: base_order adjusted to {adjusted:.2f}€ (multiplier: {self.current_multiplier:.2f}x)")

        return new_multiplier, adjusted