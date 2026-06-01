# Denaro – task_plan.md
# Progetto: Alpha-Omega Trading Machine — Self-Healing Automation
# Protocollo: B.L.A.S.T. (Blueprint, Link, Architect, Stylize, Trigger)
# Data kick-off: 2026-05-29

## NORTH STAR
Costruire una macchina di trading auto-chealing che protegga e faccia crescere
i ~200€ di capitale residuo su 3 nodi (mc2, Nuvola, MARCODG1), con drawdown
max 10%, zero OOM risk, zero EUR libero < 5€, e report Telegram real-time.

## INTEGRAZIONI
- Binance API (sub-account per nodo, chiavi in ~/denaro/.env)
- Telegram (token fornito, canale/report)
- SQLite (dati al posto di JSON)
- systemd (gestione processi)

## DATA SCHEMA (da gemini.json)
Vedi gemini.md

## FASI
- [x] Fase 0 — Initialization (file creati)
- [x] Fase 1 — Blueprint (Discovery completata, questo file approvato)
- [ ] Fase 2 — Link (verifica API + credenziali)
- [ ] Fase 3 — Architect (SOP + Python tool deterministici)
  - [ ] 3A: Self-Healing Guardian (OOM guard, auto-restart, drawdown kill)
  - [ ] 3B: DenaroOrchestrator in systemd (orchestratore unico per nodo)
  - [ ] 3C: SQLite persistence layer (trades.db, bot_state, exposure, vault)
  - [ ] 3D: Capital Protection Engine (max 10% drawdown, min 5€ EUR libero)
  - [ ] 3E: Telegram Reporter (notifiche real-time)
- [ ] Fase 4 — Stylize (formattazione report Telegram, dashboard)
- [ ] Fase 5 — Trigger (deploy sui 3 nodi, cron/systemd)

## DISCOVERY ANSWERS
1. North Star: Macchina che genera denaro con 200€, auto-healing serio
2. Integrations: Binance sub-account + Telegram (token dato)
3. Source of Truth: SQLite (trades.db)
4. Delivery: Telegram real-time
5. Behavioural: Drawdown 10% max, no OOM, EUR libero >= 5€, bot in systemd

## ASSET ALLOCATION (da FLEET_TOPOLOGY)
- Nuvola: Ammiraglia, ~80% capitale (SOL/EUR grid + scalper)
- MC2: HFT isolato (~49€ coperto in precedenza, momentum/scalper)
- MARCODG1: Grid + squadra (~80€)

## REPO
- https://github.com/grivetto/alpha-omega-trading (codice principale)
- https://github.com/grivetto/dollari (stesso identico)

## CRITICAL NOTES
- SU MARCODG1: /home/marco/denaro NON /home/sergio (user marco)
- SU mc2: hermes-gateway.service + openclaw-gateway.service attivi (possibile
  causa dei .disabled — DA NON TOCCARE)
