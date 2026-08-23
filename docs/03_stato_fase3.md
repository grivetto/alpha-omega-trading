# DENARO — Stato Fase 3 e Runbook Cutover (aggiornato round 7)

> La Fase 3 (implementazione modulare) e' in corso. Questo documento traccia
> lo stato di ogni modulo, l'evidenza di verifica e il runbook del cutover live.

---

## 1. Stato dei moduli (blueprint `docs/02_blueprint_fase2.md`)

| Modulo | Stato | Evidenza |
|--------|-------|----------|
| M0 — package 3-layer + test parita' | ✅ | `denaro/domain|application|infrastructure`, 71 test verdi |
| M1 — domain (types, indicators, risk, grid con fix C7) | ✅ | `test_domain.py` 24 test: invarianti re-grid, CB, Kelly |
| M2 — rate limiter + adapter OKX EEA | ✅ | `test_rate_limiter.py` 7 test; live path read-only OK (eea.okx.com, saldi corretti) |
| M3 — MarketDataHub (WS multiplexing + fallback REST) | ✅ | `test_market_data.py` 8 test; **WS ccxt.pro attivo su OKX EEA in produzione** |
| M4 — Supervisor (zero OOM) + Orchestrator (BotTask) | ✅ | `test_supervisor.py` 8 test; `test_orchestrator.py` 6 test (ciclo completo con FakeExchange) |
| M5 — Storage (journal fsync + stato atomico) | ✅ | `test_storage.py` 9 test; crash-recovery testato |
| M6 — Paper sul Node in parallelo ai live | ✅ | Node su MARCODG1: ADA/SOL/XRP 300/100/100, WS reali |
| M7 — **Cutover live** | ⏳ GATING | Parita' 48h in corso (vedi §2); live path read-only OK; adapter Kraken pronto; config `node_live.json` pronto |
| M8 — Benchmark densita' | ✅ | 20 bot = 22.8 MB, 50 bot = 23.3 MB (0.02 MB/bot vs 117 MB v3.3) |

**Bug reali trovati e corretti dai test/deploy**: re-grid sovraesposizione (C7),
Journal falsy a 0 record, mismatch unita' CPU, WS coroutine vs async generator,
canali hub non avviati dopo start, PnL senza fee.

---

## 2. Parita' M7 (Node vs paper live su MARCODG1, prezzi reali WS)

| Symbol | Node pnl / trades | Paper live pnl / trades | Esito |
|--------|-------------------|--------------------------|-------|
| ADA/EUR | 3.5962 / 2 | 3.5945 / 2 | ✅ allineati |
| SOL/EUR | 0.8657 / 2 | 0.8656 / 2 | ✅ identici |
| XRP/EUR | 0.8657 / 2 | 2.1641 / 5 | ✅ meccanica; piu' cicli nel live (griglia piazzata prima) |

Monitoraggio: host Zabbix `alpha-omega-node-paper` (18 item, 3 trigger OFFLINE,
auto-heal via azione "Denaro Auto-Heal"). RAM: Node 3 bot ≈ 71-187 MB vs
3 processi v3.3 ≈ 369 MB.

**Gating per il cutover**: 48h senza divergenze di meccanica (differenze
temporali di piazzamento griglia ammesse; divergenze di PnL > 1% a parita' di
fill NO).

---

## 3. Runbook Cutover live (M7) — da eseguire SOLO dopo approvazione

Principio: **mai due motori sullo stesso conto** (lezione del doppio bot Kraken).

### 3.1 Preparazione (fatta)
- `config/node_live.json`: ADA (OKX marcosub1, 20€, dist 0.1%, TP 2%),
  SOL (OKX main, 5€), SOL (Kraken nuvola, 25€) — parametri identici ai v3.3.
- Le chiavi live arrivano da EnvironmentFile (`.env`), mai dal config.
- Adapter OKX EEA + Kraken pronti, live path read-only verificato.

### 3.2 Sequenza per MARCODG1 (OKX ADA + SOL)
1. `git pull` / sync del repo su `/home/marco/denaro_node_app` (o rsync).
2. Installare `denaro-node-live.service` (stessa unit, config `node_live.json`,
   EnvironmentFile=/home/marco/denaro/.env e alpha-omega-trading/.env per ADA).
   - Nota: ADA usa le chiavi di marcosub1 (`.env` in `/home/marco/alpha-omega-trading`),
     SOL usa main (`.env` in `/home/marco/denaro`). Un solo EnvironmentFile per
     unit: o si unificano le chiavi in un file, o due unit (una per conto).
3. **Prima di avviare il Node live**: fermare `denaro-solo-ada-marcodg1` e
   `denaro-solo-sol-marcodg1` (i v3.3) — MAI contemporanei sullo stesso conto.
4. Avviare `denaro-node-live`; il Node ricostruisce lo stato dagli ordini aperti
   dell'exchange (journal + fetch_open_orders) → nessuna perdita di posizioni.
5. Verificare: health verdi, equity coerente con i saldi reali, ordini invariati.
6. Se qualcosa non torna: fermare il Node, riavviare i v3.3 (rollback < 2 min).

### 3.3 Sequenza per nuvola (Kraken SOL)
1. Sync repo + `pip install ccxtpro` nel venv di nuvola (WS).
2. Fermare `denaro-kraken-sol` (v3.3) e avviare il Node live con il bot Kraken.
3. Rollback simmetrico.

### 3.4 Post-cutover
- Disabilitare/rimuovere le unit v3.3 (`denaro-solo-*`, `denaro-kraken-sol`).
- Aggiornare Zabbix: gli item `bot.sol/ada/kraken.*` ora vengono alimentati dal
  Node (push_metrics legge i nuovi health); trigger invariati.
- Monitorare 24h: equity, ordini orfani, latenza ordini (WS vs polling).

---

## 4. Decisioni pendenti (richiedono approvazione)
1. **Cutover live ora o dopo il gating 48h?**
2. **Zabbix**: cambiare la password `Admin/zabbix` (default) — coordinato con
   `push_metrics.py` (leggerebbe le credenziali da file/env, non hardcoded).
3. **Capitale**: il Node live rispetta `min(capital, free)` come il v3.3 —
   nessun cambio di strategia al cutover.
