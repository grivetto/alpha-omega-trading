# Denaro B.L.A.S.T. Project Plan
**Created:** 2026-05-02 | **Status:** ACTIVE
**North Star:** Self-Healing Infrastructure + Unified Dashboard + Grid Bot v4 + 3% Drawdown Kill-Switch

---

## PHASE 1: B - Blueprint ✅ (Discovery Complete)

### Discovery Answers:
- **North Star:** Self-healing grid infrastructure + unified real-time dashboard + Grid Bot v4 with ATR-dynamic spacing + intelligent kill-switch
- **Integrations:** Binance API (existing), Telegram (existing)  
- **Source of Truth:** trades.db local (unchanged)
- **Delivery Payload:** Telegram + Web Dashboard
- **Behavioral Rules:** Drawdown > 3% = Kill Switch (chiudi i rubinetti)

---

## PHASE 2: L - Link (Connectivity)

- [x] Verify SSH connectivity mc2 → nuvola ✅
- [x] Verify SSH connectivity mc2 → MARCODG1 ✅
- [x] Test trades.db schema ✅ (trades, bot_state tables confirmed)
- [x] Read existing grid_bot_v3.py and denaro_core.py ✅
- [ ] Verify Binance API on nuvola (Key_Sergio)
- [ ] Verify Binance API on MARCODG1 (Key_Marco)
- [ ] Verify Telegram bot token

---

## PHASE 3: A - Architect (3-Layer Build)

### Layer 1: Architecture (architecture/)
- [ ] `SOP_BOT_HEALTH_MONITOR.md` — How to check bot health per node
- [ ] `SOP_GRID_RECOVERY.md` — Step-by-step bot recovery procedure
- [ ] `SOP_DRAWDOWN_KILLSWITCH.md` — 3% drawdown detection and kill logic
- [ ] `SOP_DASHBOARD_AGGREGATOR.md` — How to pull data from all nodes
- [ ] `SOP_ATR_GRID_SPACING.md` — ATR-based dynamic spacing algorithm

### Layer 2: Navigation (Decision Logic)
- [ ] `denaro_navigator.py` — Main orchestrator that routes health checks, recovery, kill-switch
- [ ] `node_heartbeat_monitor.py` — Polls all 3 nodes every 60s
- [ ] `drawdown_watcher.py` — Real-time P&L monitoring with 3% threshold

### Layer 3: Tools (tools/)
- [ ] `tools/check_node_health.py` — Atomic health check per node (returns JSON)
- [ ] `tools/recover_grid.py` — Recovers grid bot on target node
- [ ] `tools/kill_switch.py` — Emergency stop all orders and bot
- [ ] `tools/fetch_node_balances.py` — Gets balances from Binance API
- [ ] `tools/atr_calculator.py` — Calculates ATR for dynamic spacing

---

## PHASE 4: S - Stylize (UI)

- [ ] Dashboard: Real-time grid status for all 3 nodes
- [ ] Dashboard: P&L per node + total
- [ ] Dashboard: Drawdown meter with 3% threshold alert
- [ ] Dashboard: Bot activity timeline
- [ ] Telegram: Hourly health report (06:00-23:00)
- [ ] Telegram: Kill-switch alert when drawdown > 3%

---

## PHASE 5: T - Trigger (Deployment)

- [ ] Deploy denaro_navigator.py as systemd service on mc2
- [ ] Configure cron for hourly reports
- [ ] Configure webhook/trigger for drawdown watcher
- [ ] Update INVENTORY.md with new architecture

---

## Milestones

| # | Milestone | Status |
|---|-----------|--------|
| 1 | Fork bomb fixed (watchdog) | ✅ DONE |
| 2 | Project structure created | 🔄 NOW |
| 3 | Data schema defined (gemini.md) | ⬜ |
| 4 | API links verified | ⬜ |
| 5 | Grid Bot v4 with ATR spacing | ⬜ |
| 6 | Self-healing layer deployed | ⬜ |
| 7 | Unified dashboard live | ⬜ |
| 8 | Kill-switch operational | ⬜ |
| 9 | Documentation finalized | ⬜ |

---

## Behavioral Rules (gemini.md law)

1. **Kill-Switch Trigger:** Total drawdown > 3% across all nodes → close ALL positions, stop ALL bots, alert Telegram
2. **Recovery Timeout:** If node doesn't respond within 120s → auto-recover grid bot
3. **Health Check Interval:** Every 60 seconds per node
4. **Report Window:** Telegram reports 06:00-23:00 only
5. **Min Order Size:** Never less than 5€ per order
6. **No Market Orders:** Only limit orders allowed
