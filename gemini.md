# gemini.md — Denaro Data Schema & Behavioral Rules
**Law of this project. All code must conform. Update only when schema/rule changes.**

---

## 1. tr

Schema

### trades Table
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key, auto-increment |
| bot_name | TEXT | Bot instance name (e.g., "GridBotPro", "mc2", "MARCODG1") |
| symbol | TEXT | Trading pair (e.g., "SOL/EUR") |
| side | TEXT | "buy" or "sell" |
| entry_price | REAL | Price at which order was filled |
| exit_price | REAL | Price at which position closed (0 if still open) |
| quantity | REAL | Amount of base asset |
| entry_time | DATETIME | When buy was filled (ISO 8601) |
| exit_time | DATETIME | When sell was filled (0 if still open) |
| gross_pnl | REAL | Gross profit/loss in EUR |
| fees | REAL | Total fees paid in EUR |
| net_pnl | REAL | Net profit after fees |
| exit_reason | TEXT | "grid_profit", "trailing_stop", "kill_switch", "manual" |

### bot_state Table
| Column | Type | Description |
|--------|------|-------------|
| bot_name | TEXT | Primary key |
| is_in_position | BOOLEAN | True if currently holding asset |
| entry_price | REAL | Avg entry price of current position |
| quantity | REAL | Amount held |
| last_heartbeat | DATETIME | Last alive signal |

---

## 2. Node Health Response (JSON)

Each node returns this from `check_node_health.py`:

```json
{
  "node": "MARCODG1",
  "timestamp": "2026-05-02T02:10:00Z",
  "status": "ALIVE",           // ALIVE | DEGRADED | DEAD
  "uptime_hours": 240.0,
  "load_avg": [0.11, 0.14, 0.10],
  "memory_free_mb": 460,
  "memory_available_mb": 1700,
  "disk_free_gb": 100,
  "grid_bot": {
    "pid": 599632,
    "running": true,
    "symbol": "SOL/EUR",
    "invested_eur": 119.0,
    "profit_eur": 0.15,
    "open_orders": 3,
    "last_log_age_s": 120
  },
  "at

r": 1.42,                      // Current ATR value
  "current_price_eur": 71.2,
  "drawdown_pct": 0.0,         // Portfolio drawdown from peak
  "binance_balance_eur": 39.02,
  "binance_balance_sol": 0.0
}
```

### Status Values
- **ALIVE:** Bot running, health metrics nominal
- **DEGRADED:** Bot running but memory >80% OR load >5 OR last_log >300s OR drawdown >1%
- **DEAD:** SSH unreachable OR bot process gone OR disk <10%

---

## 3. Aggregated Fleet Status (Dashboard API)

```
/api/v1/fleet/status
```

```json
{
  "timestamp": "2026-05-02T02:10:00Z",
  "reference_capital_eur": 300.0,
  "total_drawdown_pct": 0.5,
  "kill_switch_armed": true,
  "kill_switch_triggered": false,
  "kill_switch_threshold_pct": 3.0,
  "nodes": {
    "mc2": { ...Node Health Response... },
    "nuvola": { ...Node Health Response... },
    "MARCODG1": { ...Node Health Response... }
  },
  "totals": {
    "open_orders": 6,
    "invested_eur": 238.0,
    "profit_eur": 0.15,
    "balance_eur": 78.04
  },
  "events": [
    {
      "node": "MARCODG1",
      "type": "BOT_RESTARTED",
      "timestamp": "2026-05-02T01:30:00Z",
      "details": "Auto-recovery after crash"
    }
  ]
}
```

---

## 4. Kill Switch Payload

```json
{
  "event": "KILL_SWITCH_TRIGGERED",
  "timestamp": "2026-05-02T02:10:00Z",
  "trigger_reason": "DRAWDOWN_EXCEEDED_3PCT",
  "drawdown_pct": 3.2,
  "reference_capital_eur": 300.0,
  "current_capital_eur": 290.4,
  "actions_taken": [
    "CANCELLED_ALL_ORDERS",
    "STOPPED_GRID_BOT_MARCODG1",
    "STOPPED_GRID_BOT_NUVOLA"
  ],
  "nodes_affected": ["MARCODG1", "nuvola"],
  "alert_sent": true,
  "telegram_message": "🚨 KILL SWITCH ACTIVATED\nDrawdown: 3.2%\nCapital: €290.40\nAll bots stopped. Manual intervention required."
}
```

---

## 5. Behavioral Rules (GOLDEN LAW)

| Rule ID | Description | Trigger | Action |
|---------|-------------|---------|--------|
| BR-01 | Kill Switch | `total_drawdown_pct > 3.0` | Cancel ALL orders, STOP all bots, Telegram alert |
| BR-02 | Node Dead | Node status = DEAD for >120s | Auto-recover via `recover_denaro_node.sh` |
| BR-03 | Bot Zombie | Bot PID exists but no log activity >300s | Restart bot process |
| BR-04 | Memory Pressure | `memory_available_mb < 200` | Alert, consider restart |
| BR-05 | Disk Low | `disk_free_gb < 10` | Alert immediately |
| BR-06 | High Load | `load_avg[0] > 8.0` | Alert, throttle non-critical processes |
| BR-07 | Drawdown Warning | `total_drawdown_pct > 2.0` | Telegram warning (not kill-switch yet) |
| BR-08 | Report Window | Outside 06:00-23:00 Europe/Rome | Suppress routine alerts |
| BR-09 | No Market Orders | Any code path attempting market order | REJECT — log error |
| BR-10 | Min Order Size | `ORDER_SIZE_EUR < 5.0` | REJECT — enforce minimum |

---

## 6. API Endpoints (Dashboard)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | HTML Dashboard |
| `/api/v1/fleet/status` | GET | Aggregated JSON status of all nodes |
| `/api/v1/node/<nodename>` | GET | Single node health details |
| `/api/v1/kill-switch/status` | GET | Kill switch state |
| `POST /api/v1/kill-switch/trigger` | POST | Manually trigger kill switch |
| `POST /api/v1/node/<nodename>/recover` | POST | Trigger node recovery |

---

## 7. Tool Inputs/Outputs

### tools/check_node_health.py
- **Input:** `node_name` (str), `ssh_alias` (str)
- **Output:** JSON Node Health Response (see section 2)
- **Failsafe:** Returns `status: DEAD` if SSH or bot check fails

### tools/recover_grid.py
- **Input:** `node_name` (str), `ssh_alias` (str), `bot_script` (str)
- **Output:** JSON `{"recovered": bool, "pid": int or None, "error": str or None}`
- **Behavior:** SSH → pkill grid → screen/script restart

### tools/kill_switch.py
- **Input:** `nodes` (list of ssh_alias), `reason` (str)
- **Output:** JSON Kill Switch Payload (see section 4)
- **Behavior:** Cancel orders → stop bots → alert Telegram

### tools/fetch_node_balances.py
- **Input:** `binance_api_key`, `binance_api_secret`
- **Output:** `{"eur": float, "sol": float, "bnb": float}`

### tools/atr_calculator.py
- **Input:** `symbol` (str), `timeframe` (str), `lookback` (int)
- **Output:** `{"atr": float, "atr_pct": float, "current_price": float}`

---

## 8. Architecture SOP Reference

| SOP | File | Purpose |
|-----|------|---------|
| Bot Health Monitor | `architecture/SOP_BOT_HEALTH_MONITOR.md` | How to check node/bot health |
| Grid Recovery | `architecture/SOP_GRID_RECOVERY.md` | Step-by-step recovery procedure |
| Drawdown Kill Switch | `architecture/SOP_DRAWDOWN_KILLSWITCH.md` | 3% drawdown logic |
| Dashboard Aggregator | `architecture/SOP_DASHBOARD_AGGREGATOR.md` | How to aggregate node data |
| ATR Grid Spacing | `architecture/SOP_ATR_GRID_SPACING.md` | ATR-based spacing algorithm |

---

*gemini.md is law. Update this file first if schema, rule, or architecture changes.*
