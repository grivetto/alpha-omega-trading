# SOP-001: Trade Execution Flow (Legion Manager PROD)

## Scopo
Esecuzione deterministica di trades su Binance Spot (EUR pairs).

## Trigger
Bot avviato come long-running process con loop heartbeat (~60s).

## Flusso

1. **Market Data (1m OHLCV)**
   - Fetch candele per ogni symbol attivo
   - Calcola RSI(14), EMA(9/21), ATR(14)

2. **Signal Generation**
   - DIP_BUY: RSI < 30 e price near 24h low (<1%)
   - MOMENTUM: price > EMA(9) e volume > 1.5x media
   - MEAN_REVERSION: RSI < 35 + price near support
   - SCALP: Micro-movimenti su ticker

3. **Risk Check**
   - Exposure attuale < max_positions * 30€
   - Symbol non bloccato da AutoAdaptiveEngine
   - Trading hours: 06:00-22:00 UTC
   - Volume filter: MIN_VOLUME_MULT=1.5

4. **Entry Execution**
   - Order type: `create_market_buy_order_with_cost(quoteOrderQty=position_size)`
   - Position size: Kelly sizing × boost multiplier
   - TP = entry + ATR × 1.5
   - SL = entry - ATR × 0.8

5. **Position Management**
   - Ogni tick: check trailing (1.5× ATR)
   - Ogni tick: check breakeven (0.4% profit)
   - Ogni tick: check TP/SL

6. **Exit**
   - Su TP: market sell, log, add to vault (20% profitto)
   - Su SL: market sell, log, increment loss count
   - Su trailing: market sell when stop hit

## Vault
- 20% del profitto di ogni trade → vault_balance
- Usato per coprire perdite future

## Error Recovery
- Rate limit (429): backoff 5s, retry 3x
- Network error: reconnect WebSocket, retry fetch
- Order rejected: log reason, disable symbol temporaneamente
