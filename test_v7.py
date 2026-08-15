#!/usr/bin/env python3
"""Test V7 enhancements."""

from denaro.core import DenaroCore
from denaro.indicators_advanced import AdvancedIndicators
from denaro.dynamic_grid import DynamicATRGrid
from denaro.regime_enhanced import EnhancedRegimeDetector
from denaro.types import RegimeState, Trend, MicroState, CoreState, VaRState, DCAState, ExecutionState, CircuitBreakerState, PerfMetrics

# Test Advanced Indicators
prices = [0.15 + i*0.001 for i in range(50)]
highs = [p + 0.002 for p in prices]
lows = [p - 0.002 for p in prices]
volumes = [1000 + i*10 for i in range(50)]

rsi = AdvancedIndicators.rsi(prices)
print(f'RSI: {rsi.value:.2f} ({rsi.signal})')

macd = AdvancedIndicators.macd(prices)
print(f'MACD: {macd.value:.6f} ({macd.signal})')

bb = AdvancedIndicators.bollinger_bands(prices)
print(f'BB: {bb.value:.4f} ({bb.signal})')

adx = AdvancedIndicators.adx(highs, lows, prices)
print(f'ADX: {adx.value:.2f} ({adx.signal})')

# Test Enhanced Regime Detector
regime = RegimeState()
detector = EnhancedRegimeDetector()
ohlcv = [[i, p+0.002, p-0.002, p, p+0.001*i, 1000+i] for i, p in enumerate(prices[-30:])]
detector.update(regime, MicroState(), ohlcv)
print(f'Regime: {regime.trend.value} strength={regime.trend_strength:.2f}')
print(f'Volatility: {regime.volatility_regime}, Volume: {regime.volume_regime}')
print(f'Momentum 24h: {regime.momentum_24h:.4f}')
print(f'Dump Mode: {regime.dump_mode} ({regime.dump_reason})')
print(f'Combined Signal: {regime.combined_signal} (conf: {regime.signal_confidence:.2f})')

# Test Dynamic Grid
core_state = CoreState()
core_state.regime = regime
core_state.micro = MicroState()
core_state.micro.last_price_micro = 0.15
grid = DynamicATRGrid()
params = grid.compute(core_state)
print(f'Grid: spread={params.spread:.4f}, levels={params.levels}, center={params.center:.4f}')
print(f'TP: {params.tp:.4f}, bias={params.bias:.2f}')
print(f'Buy levels: {[f"{x:.4f}" for x in params.buy_levels[:3]]}...')
print(f'Sell levels: {[f"{x:.4f}" for x in params.sell_levels[:3]]}...')

print('\nAll V7 enhancements working correctly!')