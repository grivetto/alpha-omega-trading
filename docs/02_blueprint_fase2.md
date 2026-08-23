# DENARO — Blueprint Architettura Scalabile (Fase 2)

> Deliverable della Fase 2 del piano di riprogettazione enterprise (Audit → Blueprint → Implementazione).
> Base: audit reale della Fase 1 (`docs/01_audit_fase1.md`) + verifica operativa del 23/08/2026.
> Obiettivo cardine: **massima densità di bot per nodo, zero OOM, stabilità e redditività**.
> Questo documento va **approvato** prima della Fase 3 (implementazione).

---

## 1. Sintesi delle decisioni architetturali

| # | Decisione | Motivazione (dall'audit) |
|---|-----------|--------------------------|
| D1 | **1 processo asincrono per nodo** ("Denaro Node"), N bot come task `asyncio` leggeri | Oggi 1 processo ≈ **117 MB RSS** per bot (7 bot ≈ 820 MB su MARCODG1). Con task asincroni: footprint per bot ≈ **1-3 MB** → densità teorica 20-50×. |
| D2 | **Market Data Hub condiviso**: 1 WebSocket per exchange multiplexato a tutti i bot | Oggi ogni bot apre il proprio client ccxt REST (polling 60s, N+1 query). Con WS condiviso: 1 connessione per exchange, tick in push, latenza ordini da 60s → **< 1s**. |
| D3 | **Rate limiter centralizzato** (token bucket per exchange) | Oggi nessun rate limit esplicito oltre `enableRateLimit` di ccxt; più bot = rischio ban API. Un bucket condiviso per nodo garantisce conformità anche a densità massima. |
| D4 | **Risk manager integrato** (resuscitare `risk.py` nel path live) | Oggi il motore live NON ha risk management: il drawdown è solo misurato, mai azionato. |
| D5 | **Persistenza robusta**: journal immutabile + stato atomico | Oggi `total_profit` è in memoria, `entry_price` stimato `price*0.99`, `pnl_log.jsonl` mai riletto. |
| D6 | **Resource Supervisor locale** (adaptive throttling, circuit breaker RAM, zero OOM) | Direttiva zero OOM: nessun nuovo worker sopra soglie di RAM/CPU; riduzione automatica della frequenza di tick. |
| D7 | **Migrazione incrementale, non riscrittura** | Lezione delle 7 riscritture: il motore v3.3 resta la sorgente di verità della logica grid; il porting asincrono è guidato da test di parità. |
| D8 | **Auto-healing esterno via Zabbix** (già operativo) + watchdog locale nel Node | Doppio strato: watchdog interno (riavvio task) + Zabbix (riavvio unit systemd) già provato end-to-end. |

---

## 2. Diagramma logico dell'architettura target

```
┌─────────────────────────────── DENARO NODE (1 processo asyncio per macchina) ───────────────────────────────┐
│                                                                                                              │
│  ┌─────────────────────┐   ┌──────────────────────────────────────────────┐   ┌───────────────────────────┐  │
│  │  CONFIG (YAML/ENV)  │──▶│         ResourceSupervisor (D6)              │◀──│  Zabbix / Health API      │  │
│  │  bot registry,      │   │  · RAM/CPU/latenza monitor                   │   │  · push metriche 1min     │  │
│  │  parametri, risk    │   │  · backpressure: soglie → stop/riduci worker │   │  · auto-heal esterno      │  │
│  └─────────────────────┘   │  · gc tuning, rolling buffer pruning         │   └───────────────────────────┘  │
│                            └──────────────┬───────────────────────────────┘                                  │
│                                           │ quota tick/sec, densità                                        │
│  ┌────────────────────────────────────────▼───────────────────────────────┐                                 │
│  │                     TRADE ORCHESTRATOR (asyncio) (D1)                  │                                 │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌───────────┐  │                                 │
│  │  │ BotTask #1   │  │ BotTask #2   │  │ BotTask #N   │  │ PaperTask │  │  · 1 task ≈ 1-3 MB             │
│  │  │ ADA grid     │  │ SOL grid     │  │ ...          │  │ simulato  │  │  · stato per-bot isolato      │
│  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └─────┬─────┘  │                                 │
│  └─────────┼─────────────────┼─────────────────┼───────────────┼───────┘                                 │
│            │ subscribe tick  │                 │               │                                          │
│  ┌─────────▼─────────────────▼─────────────────▼───────────────▼───────┐                                 │
│  │  MARKET DATA HUB (D2) — 1 WS per exchange (ccxt.pro), cache prezzi   │                                 │
│  │  ticker/orderbook/ohlcv → broadcast ai task; fallback REST con TTL   │                                 │
│  └─────────┬────────────────────────────────────────────────────────────┘                                 │
│  ┌─────────▼────────────────────────────────────────────────────────────┐                                 │
│  │  EXECUTION MANAGER (D3) — RateLimiter (token bucket/exchange)        │                                 │
│  │  create/cancel/fetch ordini, riconciliazione, idempotenza, retry     │                                 │
│  └─────────┬────────────────────────────────────────────────────────────┘                                 │
│  ┌─────────▼────────────────────────────────────────────────────────────┐                                 │
│  │  RISK MANAGER (D4) — CB vol-scaled, daily loss, drawdown STOP,      │                                 │
│  │  Kelly, position sizing, dump-defense (da risk.py, riparato)         │                                 │
│  └─────────┬────────────────────────────────────────────────────────────┘                                 │
│  ┌─────────▼────────────────────────────────────────────────────────────┐                                 │
│  │  STORAGE (D5) — journal immutabile (trades.jsonl append+fsync) +     │                                 │
│  │  stato atomico (tmp+rename, pattern v3.3) + snapshot recovery        │                                 │
│  └──────────────────────────────────────────────────────────────────────┘                                 │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
        │                                                        │
        ▼                                                        ▼
  EXCHANGES (OKX EEA, Kraken, [Binance, Crypto.com])   DASHBOARD + ZABBIX (7 host, trigger, auto-heal)
```

---

## 3. Stack e runtime

| Componente | Scelta | Note |
|------------|--------|------|
| Runtime | **Python 3.12+ / asyncio** (stesso stack di oggi, no riscrittura linguaggio) | ccxt.pro per WS, `aiohttp` per HTTP |
| Concorrenza | 1 processo `denaro_node.py` + task asyncio per bot + process pool opzionale per calcoli pesanti (indicatori) | Niente thread per I/O: tutto event-driven |
| Market data | **ccxt.pro** (`watch_ticker`, `watch_order_book`) con **1 istanza per exchange** condivisa | Fallback REST con TTL se WS giù; riconnessione con backoff esponenziale |
| Persistenza | `trades.jsonl` (journal, append+`os.fsync`) + `state/*.json` atomici (tmp+rename) + snapshot periodico | Ripresa esatta dopo restart: journal → stato |
| Config | `config/node.yaml` (bot registry, risk, rate limit, soglie risorse) — **versionato nel repo** | Oggi i parametri vivono nei comandi systemd: da centralizzare |
| Monitoraggio | Health JSON (pattern attuale) + push Zabbix (pattern attuale) + **Health HTTP nel Node** | L'infrastruttura Zabbix/auto-heal già operativa resta invariata |

---

## 4. Moduli (Clean Architecture — porta esterna → infrastruttura)

### 4.1 Domain layer (puro Python, zero I/O)
```
denaro/domain/
  types.py          # CoreState, RegimeState, MicroState, CBState, ... (da types.py esistente)
  risk.py           # RiskManager: CB vol-scaled, daily loss, max DD azionato, Kelly, sizing (porting risk.py)
  strategy/
    grid.py         # geometria griglia + re-grid idempotente (logica v3.3 corretta: cancella stantii prima di ri-piazzare)
    dca.py          # logica DCA
  indicators.py     # RSI/MACD/BB/ATR/ADX/... (da indicators_advanced.py, con test)
```

### 4.2 Application layer (orchestrazione)
```
denaro/application/
  orchestrator.py   # TradeOrchestrator: crea/avvia/ferma BotTask, ciclo di vita, riconciliazione
  supervisor.py     # ResourceSupervisor: metriche RSS/CPU, soglie, backpressure, circuit breaker risorse
  portfolio.py      # PortfolioManager: equity aggregata, allocazione, riconciliazione saldi
```

### 4.3 Infrastructure layer (adattatori)
```
denaro/infrastructure/
  market_data.py    # MarketDataHub: 1 WS per exchange, broadcast tick, cache, fallback REST
  execution.py      # ExecutionManager: ordini idempotenti, retry, riconciliazione orfani
  rate_limiter.py   # TokenBucket per exchange (centrale), leaky bucket opzionale
  storage.py        # Journal, AtomicFile, StateStore, snapshot recovery
  exchanges/
    okx.py          # adapter OKX EEA (hostname eea.okx.com — vincolo attuale)
    kraken.py       # adapter Kraken
    binance.py      # nuovo (per direttiva multi-exchange)
    cryptocom.py    # nuovo (per direttiva multi-exchange)
  health.py         # HealthServer (pattern v3.3) + Zabbix push (pattern push_metrics)
```

---

## 5. Vincoli critici operativi (dal runtime reale)

1. **OKX EEA**: tutte le chiamate OKX DEBBONO usare `hostname: 'eea.okx.com'` (le chiavi EU falliscono altrimenti con 50119). Già verificato e da preservare nel nuovo adapter.
2. **Kraken**: nessun problema di hostname; attenzione a precisione/quote EUR; il bot Kraken vive su nuvola (25€) — la migrazione va coordinata con systemd.
3. **Rate limit OKX** (approssimativi): privati ~20 req/2s; pubblici ~20 req/2s. Il token bucket per nodo deve rispettarli anche con 20+ bot.
4. **RAM attuale per processo** (misurato): `engine_solo_v33.py` ≈ 117 MB RSS, `engine_paper.py` ≈ 122 MB RSS. Con asyncio: obiettivo ≤ 5 MB per bot oltre il base (~60-80 MB di Node).
5. **Zabbix push** usa la trapper API su `127.0.0.1:1080` (tunnel da MARCODG1 → mc2): pattern da riusare nel Node (health + metriche).
6. **Nessuna riscrittura della strategia**: la logica grid v3.3 (TP%, buy-distance, grid-levels, min(capital, free)) è la baseline di parità. Ogni refactor è verificato con **test di parità** (stesso comportamento a parità di tick storici).

---

## 6. Piano di migrazione (dalla baracca attuale al Node)

| Step | Azione | Rischio | Verifica |
|------|--------|---------|----------|
| M0 | Creare `denaro/` package con struttura a 3 layer, test di parità su grid v3.3 | Basso | test unitari verdi |
| M1 | Porting Domain: `types` + `risk` + `grid` (con fix re-grid idempotente) | Basso | test invarianti (mai > grid_levels, mai sovraesposizione) |
| M2 | `rate_limiter.py` + `execution.py` con adapter OKX EEA (REST) | Medio | test contro exchange sandbox/paper |
| M3 | `market_data.py` con ccxt.pro WS condiviso + fallback REST | Medio | test disconnessione/riconnessione WS |
| M4 | `supervisor.py` + `orchestrator.py`: Node asincrono che avvia gli stessi bot attuali (ADA, SOL, Kraken SOL) | Medio | parità di PnL/equity vs motori attuali in paper |
| M5 | Storage journal+stato; ripristino dopo kill -9 | Medio | test crash recovery |
| M6 | Paper bot sul Node (ADA/SOL/XRP 500€) in parallelo ai live → confronto | Basso | dashboard invariata |
| M7 | Cutover live: fermare motori v3.3, avviare Node sotto systemd (stesse unit, nuovo ExecStart) | Alto | health/Zabbix verdi, ordini riconciliati |
| M8 | Benchmark densità: scalare a 20-50 bot paper su MARCODG1, verificare zero OOM e latenza | Basso | report metriche |

**Gating M7**: solo dopo M1-M6 verdi + 48h di paper in parallelo senza divergenze.

---

## 7. Metriche di successo (KPI)

1. **Densità**: ≥ 20 bot paper attivi su MARCODG1 con RSS totale ≤ 800 MB e zero OOM (oggi 7 bot ≈ 820 MB).
2. **Latenza**: tempo tick→ordine < 1s con WS (oggi 0-60s di polling).
3. **Zero OOM**: nessun processo killato da OOM in 30 giorni di stress test.
4. **Parità**: equity/PnL del Node == motori v3.3 entro ±0.5% a parità di tick in paper.
5. **Crash recovery**: kill -9 → ripresa esatta (nessun ordine perso, nessun PnL sbagliato) in < 2 min.
6. **Auto-heal**: bot down → restart Zabbix in < 5 min (già provato).
7. **Rate limit**: zero errori 429/rate-limit in 7 giorni a densità massima.

---

## 8. Rischi e mitigazioni

| Rischio | Probabilità | Mitigazione |
|---------|-------------|-------------|
| Regressione strategia nel porting | Media | Test di parità obbligatori; paper in parallelo 48h prima del cutover |
| ccxt.pro WS instabile su EEA | Media | Fallback REST automatico + riconnessione backoff; il motore non si ferma mai |
| Adapter nuovi exchange (Binance/Crypto.com) incompleti | Media | Contratto comune ExchangeAdapter testato con sandbox; integrazione graduale |
| Over-engineering (troppi layer per 55€) | Alta | Priorità: M1-M5 sono il 90% del valore; Binance/Crypto.com solo dopo la stabilizzazione |
| RAM del Node base troppo alta | Bassa | Profiling a ogni modulo; soglie nel supervisor |

---

## 9. Fuori scope (esplicitamente rimandato)

- Riscrittura della strategia (grid/DCA): la strategia attuale è la baseline.
- Algoritmi ML/IA nel trading: niente finché la base non è stabile.
- Nuovi exchange: solo dopo M7 (cutover live OKX/Kraken).
- Infrastruttura Kubernetes: i nodi sono 3 macchine; systemd + Node bastano.

---

## 10. Approvazione

Questo blueprint richiede l'**approvazione esplicita** prima di iniziare la Fase 3 (implementazione modulare, step M0→M8).
Domande aperte per l'approvazione:
1. Confermi l'architettura **1 Node asincrono per macchina** (vs. più processi leggeri)?
2. Confermi la **priorità M1-M5** (risk, execution, WS, supervisor, storage) prima di nuovi exchange?
3. Il **cutover M7** va eseguito dopo 48h di paper in parallelo (sì/nò)?
