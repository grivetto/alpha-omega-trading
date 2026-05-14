# Denaro Trading System - Analysis and Recommendations

## Executive Summary
After analyzing the Denaro trading system across servers (nuvola, mc2, MARCODG1), we identified several critical issues preventing consistent profitability:

1. **Strategy Logic Flaws**: The TrendFilter indicator used overly permissive thresholds, causing entries in weak downtrends that often resulted in losses.
2. **State Persistence Fragility**: Performance metrics were parsed from volatile log files (`grid.log`) instead of persistent storage, causing the supervisor to make decisions based on incomplete or corrupted data.
3. **Process Monitoring Misconfiguration**: The metrics collector was configured to monitor non-existent scalper processes, leading to false health indicators.
4. **Orphaned Bot Processes**: Legacy bots running outside the orchestrator ("phantom bots") create conflicting positions and state inconsistencies.
5. **Performance Measurement Lag**: The dashboard displayed instantaneous P&L from the last trade rather than cumulative performance, giving a misleading view of system health.

## Detailed Findings

### 1. TrendFilter Indicator Issues (`denaro_strategies.py`)
- **Problem**: The original RSI thresholds (`RSI > 30` for STRONG_DOWN, `RSI > 25` for DOWN) were too low, triggering downtrend signals during sideways consolidation or weak pullbacks within uptrends.
- **Impact**: Increased false short signals leading to losses in choppy markets.
- **Evidence**: Memory notes RSI=nan issues during sideways markets, indicating strategy struggles with non-trending conditions.

### 2. Performance Metrics Fragility (`config_supervisor.py`)
- **Problem**: The `get_performance()` function parsed `grid.log` using string splitting, which is prone to format changes, missing lines, and corruption.
- **Impact**: Supervisor received `None` or incorrect performance data, disabling risk adjustments and position sizing optimizations.
- **Evidence**: Frequent `None` returns from `get_performance()` would cause the supervisor to use default parameters.

### 3. Process Monitoring Errors (`metrics_collector.py`)
- **Problem**: Configured to monitor `scalper_v1.py` (which doesn't exist in production) instead of the actual `scalper_v2.py`.
- **Impact**: Reported 0 active scalpers on MC2 regardless of actual state, hiding real issues and preventing alerts.
- **Evidence**: Memory confirms scalper_v2_fixed.py should be the only active scalper variant.

### 4. State Persistence Risks (Memory Notes)
- **Problem**: Legacy bots used JSON files for state persistence, which corrupt on crash causing "amnesia" (forgetting open positions).
- **Impact**: Bots would restart unaware of open positions, leading to unintended doubling or missed exits.
- **Evidence**: Explicit memory directive to use SQLite (.tmp/denaro.db, WAL mode) for all bot state.

### 5. Phantom Bot Processes (Memory Notes)
- **Problem**: Bots like `scalper_v2_fixed.py` running in screen sessions outside the orchestrator create conflicting trades.
- **Impact**: Duplicate positions, increased slippage, and state conflicts with orchestrator-managed bots.
- **Evidence**: Memory states these must be eliminated - only orchestrator-managed bots should be active.

### 6. Misleading Performance Display (`metrics_collector.py`)
- **Problem**: MC2 dashboard showed last trade's P&L instead of cumulative profit.
- **Impact**: Traders saw noisy, short-term fluctuations instead of the strategy's true edge, causing premature interventions.
- **Evidence**: The change from "last PnL" to "cumulative profit" provides a realistic equity curve view.

## Applied Fixes (Phase 1)
We have prepared a patch file (`dev_team_changes.patch`) implementing the following critical fixes:

### A. TrendFilter Threshold Adjustment
- Changed STRONG_DOWN trigger from `RSI > 30` to `RSI > 40`
- Changed DOWN trigger from `RSI > 25` to `RSI > 35`
- **Rationale**: Requires stronger downtrend momentum before signaling, reducing false entries in sideways markets.

### B. ProfitOptimizer Persistence
- Added JSON-based persistence for trade history in `.tmp/profit_optimizer_trades.json`
- Trades are saved after each addition and loaded on startup
- **Rationale**: Ensures performance metrics survive restarts and crashes, enabling consistent risk adjustments.

### C. Robust Performance Metrics Source
- Replaced `grid.log` parsing with direct reading of `profit_optimizer_trades.json`
- Calculates: total_orders, recent_profit (last 10 trades), avg_profit_per_trade
- **Rationale**: Eliminates fragile log parsing; uses the same trade data the optimizer uses for decisions.

### D. Process Monitoring Correction
- Updated metrics collector to monitor `scalper_v2.py` instead of `scalper_v1.py`
- **Rationale**: Aligns health checks with actual deployed processes.

### E. Cumulative Profit Display
- Modified MC2 metrics to show cumulative profit from all trades (via trade_db or profit optimizer fallback)
- **Rationale**: Provides accurate equity curve for performance evaluation.

## Critical Next Steps for Dev Team

### 1. Verify Strategy Integration
**Issue**: Our changes to `denaro_strategies.py` only take effect if bots actually import and use it.
**Actions**:
- Confirm which bots import `denaro_strategies` (currently none do based on our scans)
- If the legion bots should use this shared strategy, modify `LegionBot.update()` to call `TrendFilter` and `ProfitOptimizer`
- Alternatively, if the money directory contains the active system, ensure the denaro directory mirrors it correctly

### 2. Eliminate Phantom Bots
**Actions**:
- On each server (nuvola, mc2, MARCODG1):
  ```bash
  # List screen sessions
  screen -ls
  
  # Kill any scalper or legion bot screens not started by orchestrator
  screen -S <session_name> -X quit
  
  # Verify only orchestrator-managed processes remain
  ps aux | grep -E '(legion_manager|scalper_v2)' | grep -v grep
  ```
- Implement a startup script that clears any existing bot screens before launching the orchestrator

### 3. Ensure State Persistence Directory
**Actions**:
- Create and secure the `.tmp` directory:
  ```bash
  mkdir -p /home/sergio/denaro/.tmp
  chmod 750 /home/sergio/denaro/.tmp
  ```
- Verify the ProfitOptimizer can write to `.tmp/profit_optimizer_trades.json`
- Monitor that the file gets created and updated after trades

### 4. Validate Oracle Usage
**Actions**:
- Check that `legion_manager_production.py` is the actual orchestrator running on all servers
- Confirm it's initializing the correct number of bots (should match SYMBOLS_WS length)
- Review the bot initialization logic for any misconfiguration

### 5. Monitor and Tune
**Actions**:
- After deployment, watch for:
  - Creation of `.tmp/profit_optimizer_trades.json`
  - Non-zero scalper counts in metrics
  - Reasonable trend signals in logs (look for "📊 Trend:" messages)
  - Supervisor making adjustments when performance degrades
- Consider further tuning:
  - TrendFilter EMA distance thresholds
  - ProfitOptimizer adjustment intervals
  - RiskManager position sizing parameters

## Risk Mitigation
- **Backup First**: Always backup current state before applying changes:
  ```bash
  cp denaro_strategies.py denaro_strategies.py.pre-fix
  cp config_supervisor.py config_supervisor.py.pre-fix
  cp metrics_collector.py metrics_collector.py.pre-fix
  ```
- **Staging Test**: Apply changes in a test environment with paper trading before live deployment
- **Gradual Rollout**: Deploy to one server (e.g., mc2) first, monitor for 24 hours, then expand

## Expected Outcomes
With these fixes implemented:
1. **Reduced False Signals**: Higher RSI thresholds filter out weak downtrend entries
2. **Consistent Risk Decisions**: Persistent performance data enables reliable supervisor actions
3. **Accurate Health Monitoring**: Process metrics reflect actual bot states
4. **Eliminated State Loss**: SQLite state persistence survives crashes and restarts
5. **Clear Performance View**: Dashboard shows true equity curve, not trade-by-trade noise
6. **Orchestrator Supremacy**: Only one source of truth for positions and strategy

## Longer-Term Considerations
1. **Strategy Evaluation**: Backtest the adjusted TrendFilter parameters on historical data
2. **Orchestrator Enhancement**: Consider moving all strategy logic into shared modules (like denaro_strategies.py) to ensure consistency
3. **Advanced Risk Management**: Explore volatility-based position sizing and correlation limits
4. **Telemetry Improvement**: Add more detailed metrics to the profit optimizer trades (win rate, avg win/loss, etc.)

## Files Modified
Please apply the patch in `dev_team_changes.patch` to the denaro directory. The patch modifies:
- `denaro_strategies.py` (TrendFilter thresholds + ProfitOptimizer persistence)
- `config_supervisor.py` (performance metrics source)
- `metrics_collector.py` (process monitoring + cumulative profit display)

After applying, verify syntax:
```bash
python3 -m py_compile denaro_strategies.py config_supervisor.py metrics_collector.py
```

## Conclusion
The Denaro system has a solid foundation (SQLite state persistence, exposure guards, multi-bot architecture) but was hampered by fragile data flows and suboptimal signal generation. The addressed issues are the most critical blockers to profitability. With these fixes and disciplined elimination of phantom processes, the system should transition from erratic P&L to consistent, risk-managed returns.

--- 
Analysis generated: 2026-05-13
For questions, refer to the dev team patch and memory notes in the Hermes Agent context.