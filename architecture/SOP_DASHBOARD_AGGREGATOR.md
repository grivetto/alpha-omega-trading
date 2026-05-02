# SOP: Dashboard Aggregator
**Layer 1 — Architecture**

## Purpose
Aggregate real-time status from all Denaro nodes into a unified JSON API for the web dashboard.

## Data Flow
```
[MARCODG1] ─┐
[nuvola] ───┼─ SSH ── [mc2: denaro_navigator.py] ── JSON ── [dashboard_server.py] ── HTML
[mc2 local]─┘
```

## Aggregation Steps

### Step 1: Parallel Health Checks
```
For each node (parallel):
    tools/check_node_health.py <node_name> <ssh_alias>
Returns: Node Health Response JSON
```

### Step 2: Parallel Balance Fetch
```
For each node (parallel):
    tools/fetch_node_balances.py
Returns: {eur, sol, bnb}
```

### Step 3: Calculate Totals
```
total_invested = sum(node.grid_bot.invested_eur for node in nodes)
total_profit = sum(node.grid_bot.profit_eur for node in nodes)
total_balance_eur = sum(node.binance_balance_eur for node in nodes)
open_orders = sum(node.grid_bot.open_orders for node in nodes)
```

### Step 4: Calculate Drawdown
```
reference_capital = 300.0  (from gemini.md)
current_capital = total_balance_eur + total_invested
drawdown_pct = (reference_capital - current_capital) / reference_capital * 100
```

### Step 5: Check Kill Switch Flag
```
kill_switch_file = ~/denaro/.tmp/kill_switch_flag.txt
if exists → kill_switch_triggered = true
else → kill_switch_triggered = false
```

## Output: Aggregated Fleet Status
See gemini.md section 3 — Fleet Status JSON schema

## Refresh Rate
- Endpoint `/api/v1/fleet/status`: every 15s (dashboard refreshes every 10s)
- Node health checks cached for 30s to avoid SSH spam

## Dashboard HTML Updates Needed
1. Node-by-node status cards
2. Total P&L display
3. Drawdown meter with 3% threshold line
4. Kill switch armed indicator
5. Event log (last 10 events)
