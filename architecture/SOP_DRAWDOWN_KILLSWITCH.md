# SOP: Drawdown Kill Switch
**Layer 1 — Architecture**

## Purpose
Detect portfolio drawdown >3% and execute emergency shutdown of all trading bots.

## Kill Switch Threshold
```
DRAWDOWN_THRESHOLD = 3.0%  (HARD CODED — NEVER CHANGE WITHOUT EXPLICIT APPROVAL)
REFERENCE_CAPITAL = 300.0 EUR  (initial capital — adjust in gemini.md only)
```

## Calculation
```
current_capital = sum(binance_balance_eur across all nodes)
               + sum(invested_eur across all nodes)  ← open positions at cost
               + sum(open_sell_order_value_eur)       ← pending sells

drawdown_pct = (REFERENCE_CAPITAL - current_capital) / REFERENCE_CAPITAL * 100
```

## Trigger Logic (drawdown_watcher.py runs every 60s)
```
IF drawdown_pct > 3.0:
    → KILL_SWITCH_TRIGGERED

IF drawdown_pct > 2.0 AND < 3.0:
    → WARNING (Telegram: "Drawdown warning: X.X% — not yet at kill threshold")
```

## Kill Switch Execution Sequence

### 1. CANCEL all open orders (all nodes)
```
For each node:
    SSH → cancel_all_open_orders via Binance API
```
- Timeout per node: 30s
- Log: cancelled order IDs

### 2. STOP all grid bots (all nodes)
```
For each node:
    SSH → pkill -f 'grid_bot_v3.py'
    SSH → pkill -f 'denaro_ultimate.py'
```
- Also stop: simple_grid.py, dca_bot.py, funding_paper_bot.py

### 3. LOG to trades.db
```sql
INSERT INTO trades (bot_name, symbol, side, exit_reason, net_pnl)
VALUES ('KILL_SWITCH', 'SYSTEM', 'EMERGENCY_STOP', 'kill_switch', <drawdown_pct>)
```

### 4. SEND Telegram Alert
```
🚨 KILL SWITCH ACTIVATED
Node: ALL
Drawdown: X.X%
Capital: €XXX.XX / €300.00
Capital Lost: €XXX.XX
Actions: All orders cancelled, all bots stopped
Time: <timestamp>
```

### 5. Set kill_switch_flag
```
echo "TRIGGERED|2026-05-02TXX:XX:XXZ|drawdown_pct|<drawdown_pct>" > ~/denaro/.tmp/kill_switch_flag.txt
```
- Flag file prevents re-trigger for 5 minutes
- Manual reset required after kill switch

## Manual Reset Procedure
```
rm ~/denaro/.tmp/kill_switch_flag.txt
# Then manually review and restart bots
```

## Behavioral Rules (from gemini.md)
- BR-01: Kill Switch triggers at >3% drawdown
- BR-07: Warning at >2% drawdown  
- BR-09: NO MARKET ORDERS — only limit orders cancelled
