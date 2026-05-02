# SOP: ATR-Based Dynamic Grid Spacing
**Layer 1 — Architecture**

## Purpose
Calculate grid spacing dynamically based on market volatility (ATR), replacing static percentage spacing.

## ATR Configuration
```
SYMBOL: SOL/EUR
TIMEFRAME: 1h (1-hour candles)
LOOKBACK: 14 periods
MULTIPLIER: 1.0 (adjustable via config)
MIN_SPACING: 0.5% (floor — prevents grid being too tight)
MAX_SPACING: 3.0% (ceiling — prevents grid being too wide)
```

## Calculation Algorithm

```
1. Fetch OHLCV data: last 15 candles (1h timeframe)
2. For each candle i (1 to 14):
   TR_i = max(
       high_i - low_i,
       abs(high_i - close_{i-1}),
       abs(low_i - close_{i-1})
   )
3. ATR = sum(TR_1..TR_14) / 14

4. Convert ATR to percentage of current price:
   atr_pct = ATR / current_price

5. Grid range = atr_pct * multiplier
   (Clamped to MIN_SPACING and MAX_SPACING)

6. Per-level spacing = grid_range / grid_levels

7. Buy prices (below current):
   buy_i = round(current_price * (1 - i * per_level_spacing), 2)
   for i in [1, 2, ..., grid_levels]

8. Sell prices (above each buy):
   sell_i = round(buy_i * (1 + profit_per_grid), 2)
```

## Formula
```
grid_spacing_pct = max(0.005, min(0.03, (ATR / current_price) * multiplier))
per_level = grid_spacing_pct / grid_levels
buy_price[i] = round(current_price * (1 - i * per_level), 2)
sell_price[i] = round(buy_price[i] * (1 + profit_per_grid), 2)
```

## Example
```
Current Price: 71.20€
ATR (14h): 1.42€ (2.0% of price)
atr_pct = 0.02
multiplier = 1.0
grid_range = 2.0%
per_level = 2.0% / 6 = 0.33%

Buy prices:
  Level 1: 70.96€ (71.20 * 0.997)
  Level 2: 70.73€ (71.20 * 0.994)
  Level 3: 70.49€ (71.20 * 0.991)
  Level 4: 70.25€ (71.20 * 0.988)
  Level 5: 70.01€ (71.20 * 0.985)
  Level 6: 69.78€ (71.20 * 0.982)

Sell prices: buy + 0.3% profit margin
```

## Config Parameters (in grid_config.json)
| Parameter | Default | Description |
|-----------|---------|-------------|
| atr_spacing_factor | 1.0 | Multiplier (0.5 = conservative, 1.5 = aggressive) |
| min_grid_spacing_pct | 0.005 | Floor (0.5%) |
| max_grid_spacing_pct | 0.03 | Ceiling (3.0%) |
| atr_timeframe | "1h" | Candle timeframe |
| atr_lookback | 14 | Periods for ATR calc |

## Recalculation Trigger
- Every 1 hour (config_reload_sec: 600)
- Immediately if price moves >2% from last grid center
- On bot restart

## Fallback
If ATR fetch fails → use static grid_range_pct from config (default: 1.0%)
