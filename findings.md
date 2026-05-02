# Denaro B.L.A.S.T. Findings
**Created:** 2026-05-02

---

## Infrastructure State (as of 2026-05-02 02:00 UTC)

### Node Inventory (CORRECTED)
| Node | IP | SSH alias | Grid Bot PID | Status | Balance |
|------|----|-----------|--------------|--------|---------|
| mc2 | local | mc2 | N/A (controller) | ✅ HIGH LOAD (6.78) | N/A |
| nuvola | 87.106.3.15 | nuvola | PID 286517 | ✅ ACTIVE | ~39€ |
| MARCODG1 | 87.106.222.123 | MARCODG1 | PID 599632 | ✅ ACTIVE | ~39€ |

### Issues Found
1. **MARCODG1 FORK BOMB:** ~40+ watchdog.py child processes (FIXED: killed to 1)
2. **nuvola marked offline in INVENTORY.md:** Actually ONLINE and running grid since May 1
3. **denaro-grid.service:** INACTIVE on MARCODG1 — bot runs directly via shell/screen

### Existing Code Assets
- `grid_bot_v3.py` — Main grid bot (golden source on mc2)
- `grid_bot_v3.py.golden` — Clean reference copy
- `denaro_ultimate.py` — Legacy orchestrator (not in use)
- `denaro_core.py` — Core engine
- `trades.db` — SQLite trade database (schema TBD)
- `dashboard_server.py` — Web dashboard (mc2:8080)
- `mc2_telegram_notifier.py` — Telegram bot
- `health_check.py` — Health monitor

### Bots Running (per node)
**nuvola:**
- grid_bot_v3.py (PID 286517)
- simple_sniper.py (PID 288201)
- simple_grid.py (PID 288526)
- dca_bot.py (PID 296883)
- funding_paper_bot.py (screen)

**MARCODG1:**
- grid_bot_v3.py (PID 599632) — PRIMARY GRID
- denaro_ultimate.py (PID 599754)
- watchdog.py (1 instance only — FIXED)
- simple_sniper.py, simple_grid.py (secondary)
- faucet_farmer.py (faucet)

**mc2:**
- legion_manager_production.py (HIGH CPU)
- dashboard_server.py (:8080)
- mc2_telegram_notifier.py
- eur_usdt_micro_scalper.py

---

## Research Notes

### ATR Dynamic Spacing Algorithm
```
grid_spacing = max(0.005, min(0.03, ATR_14 * multiplier))
multiplier = 0.5 (conservative) to 1.5 (aggressive)
Use ATR_14 (14-period Average True Range)
Recalculate every 5 minutes or on significant price move (>1%)
```

### Drawdown Kill-Switch Logic
```
total_portfolio_value = sum(balance across all nodes)
initial_capital = 300€ (reference)
drawdown_pct = (initial_capital - current_value) / initial_capital * 100

if drawdown_pct > 3%:
    → CANCEL all open orders (Binance API)
    → STOP all grid bots
    → SEND Telegram alert with details
    → LOG event to trades.db
```

### Self-Healing Recovery SOP
```
1. Ping node via SSH
2. If no response in 10s → retry 3x
3. If still down → wait 60s (network transient)
4. If still down → execute recover_denaro_node.sh <nodename>
5. Log recovery attempt
6. Alert on Telegram if recovery fails after 3 attempts
```

---

## API Credentials (per node)
- **mc2:** Uses local .env (Binance Key_Marco?)
- **nuvola:** Key_Sergio (Binance)
- **MARCODG1:** Key_Marco (Binance)
- **Telegram:** mc2_telegram_notifier.py (bot token in .env.telegram)

---

## Data Schema (to be defined in gemini.md)
- trades.db tables: trades, orders, balance_snapshots
- Node status JSON structure
- Dashboard API response format
