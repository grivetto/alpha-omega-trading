<div align="center">

# ⚡ DENARO ⚡

### *Una macchina per fare soldi dal poco — senza sprecare risorse.*

[![License: Unlicense](https://img.shields.io/badge/license-Unlicense-blue.svg)](http://unlicense.org/)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![CCXT](https://img.shields.io/badge/exchange-CCXT%20%2F%20Kraken%20%7C%20OKX-5741D9?logo=bitcoin&logoColor=white)](https://github.com/ccxt/ccxt)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20systemd-FCC624?logo=linux&logoColor=black)](https://www.freedesktop.org/wiki/Software/systemd/)
[![Status](https://img.shields.io/badge/status-live%20paper%20trading%20%7C%2014%20bots-success)](https://github.com/grivetto/alpha-omega-trading)
[![Code Style](https://img.shields.io/badge/style-clean%20%26%20modular-brightgreen)](https://github.com/grivetto/alpha-omega-trading)
[![Docker](https://img.shields.io/badge/docker-postgres%2016%20%2B%20redis%207-2496ED?logo=docker&logoColor=white)](docker/docker-compose.yml)

**Motore di paper trading modulare per mercati crypto. Feed prezzi real-time, strategie grid adattive, orchestrazione flotta multi-exchange, zero denaro reale a rischio — e zero sprechi.**

[Architettura](#-architettura) · [Filosofia](#-filosofia) · [Docker](#-docker) · [Avvio Rapido](#-avvio-rapido) · [Deployment](#-deployment-systemd) · [Roadmap](#-roadmap)

</div>

---

## 🎯 Filosofia

> **La protezione del capitale è legge. L'efficienza è profitto. Il codice è legge. Il profitto è la prova.**

Denaro nasce da un vincolo semplice: **il capitale limitato non deve essere speculato — deve essere coltivato.**

Ogni decisione di progettazione segue tre regole:

1. **🛡️ Non rischiare mai ciò che non puoi permetterti di perdere** — circuit breaker, limiti di drawdown e cap di posizione non sono funzionalità opzionali; sono le fondamenta.
2. **⚙️ Non sprecare nulla** — niente framework gonfiati, niente processi ridondanti, niente servizi abbandonati che consumano RAM su un nodo headless. Un processo, uno scopo, footprint minimo.
3. **📈 Upside asimmetrico** — piccoli ordini grid pazienti che raccolgono volatilità. Molte piccole vittorie, perdite strettamente limitate.

Questo non è un bot "arricchisciti in fretta". È una **disciplina ingegneristica applicata ai mercati**: parti con €100, dimostra la strategia su carta, poi — e solo allora — scala.

---

## 📜 Storia del Progetto

| Milestone | Data / Commit | Descrizione |
|-----------|---------------|-------------|
| **🌱 Live Bot (v0)** | pre-repo | Singolo bot grid Kraken DOGE/EUR in un file. Girato live su Raspberry Pi con ~€200 capitale per mesi. Persistenza systemd, reload manuale dello stato. Ha provato il concetto; ha esposto i limiti di un monolite. |
| **📉 Il Collasso Binance** | 2026-06-29 → 07-01 | **Il progetto ha iniziato a perdere colpi — e euro.** La flotta live di Denaro (DOGE su nuvola, ADA+SOL su MARCODG1, ETH su MC2) era pienamente operativa su sub-account Binance… finché non lo è più stata. Negli ultimi giorni di giugno, Binance ha iniziato a revocare silenziosamente i permessi di trading sulle API key dei sub-account EU: `GET /account` tornava 200, ma ogni `POST /order` moriva con `401 -2015 ("Invalid API-key, IP, or permissions")`. I bot non crashavano — **morivano di fame**. Zero fill, posizioni bloccate, ~€206 di capitale congelati a metà grid mentre il mercato si muoveva senza di loro. La causa non era un bug: era **MiCA**. Binance stava perdendo le licenze europee, e l'applicazione è arrivata esattamente il **1° luglio 2026** — il giorno in cui Binance è diventato inutilizzabile per lo spot trading UE. La flotta era completamente costruita, deployata, pronta… e l'exchange ha staccato la spina. Lezione bruciata nel repo: **il rischio exchange è rischio reale**. |
| **🐙 Il Pivot su Kraken** | 2026-07-01 | Stesso giorno, stessa ora: tutto convertito in EUR su Binance (~€344 recuperati tra main + sub-account), prelevato via SEPA, e tutta l'infrastruttura ripuntata su **Kraken** — MiCA-compliant, licenza EU, API superiore. Binance e Bybit deprecati permanentemente. |
| **🏗️ p1 — Scaffold Modulare** | `504172c` | Refactor completo. Monolite diviso in 5 moduli puliti: `engine`, `exchange`, `strategy`, `state`, `risk`. Architettura ispirata a Freqtrade (loop), Hummingbot (clock), OctoBot (grid mode), Jesse (broker abstraction). |
| **🔄 p2 — Paper Runner** | `0b2e0f3` | Main loop `PaperEngine`: intervallo tick configurabile, wiring strategia grid, persistenza stato portfolio su JSON. Entry point `run_paper.py`. |
| **🩹 p2.1 — Fix Kraken Sandbox** | `054b957` | Il client CCXT di Kraken non ha attributo `sandbox`. L'adattatore exchange cattura l'errore e fa fallback su live API readonly, impostando manualmente `sandbox=False`. |
| **🛡️ p2.2 — Guard + Graceful Shutdown** | `015627a` | Guard `getattr` contro `AttributeError`; handler SIGINT/SIGTERM ferma engine, salva portfolio, esce pulito. |
| **🧹 p3 — Pulizia Infrastruttura** | — | Rimozione di **tutti** i servizi legacy Denaro, cron job, unit system-wide, timer, binari e processi orfani su entrambi i nodi. Un servizio sopravvive: `denaro-paper`. |
| **🧪 p4 — Test Suite Paper Trading** | current | 33 test unit + integration. Engine tick, risk gate, strategia grid, trailing stop, paper exchange fill/orderbook, backtest runner. `test_engine_up_down_up` valida ciclo end-to-end: calo prezzo → buy grid → TP sell → profit. |
| **🌐 DDNS + Automazione Multi-Nodo** | 2026-07-30 | **No-IP DDNS deployato su entrambi i nodi trading** (`nuvola` → `sgrivett.ddns.net`, `MARCODG1` → `mgrivett.ddns.net`). Systemd timer (10 min) + file credenziali sicuro (`/etc/noip.conf`, 600, root:root). Free tier richiede conferma email ogni 30 giorni. |
| **🔑 Rotazione & Validazione API Key** | 2026-07-31 | **Kraken key ruotata** (post-MiCA). Nuova key `1t3Jpcv...` validata: permessi trading ✅ (Query Funds + Create/Modify Orders), permessi funding ❌ (serve `Deposit/Withdraw` abilitato su UI Kraken). **MEXC keys validate su entrambi i nodi**: nuvola (`mx0vgl1Tr...`) + MARCODG1 (`mx0vglZz...`) — spot trading + account perms, IP whitelist `700006` (entrambe le IP). Bybit deprecato (MiCA), rimosso da tutti i config. |
| **💸 Il Mistero dei 115 USDT** | 2026-07-22 | **115.74 USDT (ERC20) inviati a indirizzo deposito Kraken `0x0e7b7d8634c36994571a0f82f6abb70cde283493` — TxID `0xc2a95bb787aa0cc7c46323840cc61ac550538f539faeabd95b1fb24f42e936e7`**. **Mai arrivati. Non on-chain (Etherscan: no such tx).** API Kraken manca permessi funding per query stato deposito. Ticket support richiede: TxID, amount, destination, timestamp, prova non-arrivo on-chain. Prossimo passo: abilita `Deposit/Withdraw` su API key → fetch full `Ledgers`/`DepositStatus` JSON per evidenza. |
| **🤖 Airdrop Farm v1** | 2026-07-31 | **Airdrop farmer autonomo multi-strategia** deployato su nuvola (systemd service). 20 wallet da mnemonic BIP39 + crittografia Fernet. 4 strategie: airdrop (Base/Scroll/Abstract/Linea), Hyperliquid points, yield, MEXC launchpad. €250 virtuali, €100 reali post-2026-08-05. Scheduler Poisson, circuit breaker, esecuzione idempotente. 22 moduli. Monitoraggio Zabbix su MC2 (15 trapper items + daily cron). |
| **🔄 Full Reboot & Verifica** | 2026-07-31 | Entrambi i nodi riavviati per aggiornamenti kernel. Post-reboot: tutti i servizi systemd sani. nuvola: `denaro-kraken-health` (paper DOGE/EUR), `airdrop-farm-nuvola` (live), DDNS timer. MARCODG1: MEXC SHADOW mode (SOL/USDT, equity 100 USDT), DDNS timer, paper trading. |
| **⚡ ShadowGrid v2.0 & Multi-Bot Fleet** | 2026-08-07 | **Trasformazione completa in una Flotta Adattiva a 14 bot su 2 exchange.** Engine grid aggiornato (`shadowgrid_v2.py`) con spread dinamico basato su ATR, filtro momentum ADX/RSI, circuit breaker drawdown 15%, limite perdita giornaliera 5%, re-anchoring dinamico 6%. Aggiunto supervisore `shadowgrid_fleet.py` (7 bot/nodo, auto-restart, health dashboard `:8900`), `pair_scanner.py` per discovery real-time mercati (alto ATR%, basso ADX, spread stretto), e `fleet_rebalancer.py` per allocazione capitale guidata da performance oraria. Deployato su `nuvola` (4 Kraken EUR + 3 OKX USDT) e `MARCODG1` (4 Kraken EUR + 3 OKX USDT) — **14 bot totali, 200€ capitale paper**. Ottimizzazione pair: sostituiti pair OKX underperforming (XSPCX/USDT, XSNDK/USDT — ADX >44) con **GRVT/USDT** (ADX 24.1, grid_score 0.923) e **ADA/USDT** (ADX 13.5). Swap 2GB aggiunto su MARCODG1. Tutti i processi legacy purgati. |

---

## 🏗️ Architettura

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      ShadowGrid Fleet Orchestrator                           │
│  ┌─────────────────────────────┐         ┌─────────────────────────────┐    │
│  │         nuvola              │         │        MARCODG1             │    │
│  │  shadowgrid_fleet.py :8900  │         │  shadowgrid_fleet.py :8900  │    │
│  │  (supervisore + health)     │         │  (supervisore + health)     │    │
│  └──────────────┬──────────────┘         └──────────────┬──────────────┘    │
│                 │                                        │                  │
│   ┌─────┬─────┬─────┬─────┬─────┬─────┬─────┐  ┌─────┬─────┬─────┬─────┬─────┬─────┐
│   │SOL/E│DOGE/│XRP/E│ADA/E│BICO/│GRVT/│ADA/U│  │BTC/E│ETH/E│LINK/│AVAX/│BICO/│GRVT/│ADA/U│
│   │UR   │UR   │UR   │UR   │USDT │USDT │SDT  │  │UR   │UR   │UR   │UR   │USDT │USDT │SDT  │
│   │8912 │8913 │8914 │8915 │8930 │8931 │8932 │  │8920 │8921 │8922 │8923 │8930 │8931 │8932 │
│   └─────┴─────┴─────┴─────┴─────┴─────┴─────┘  └─────┴─────┴─────┴─────┴─────┴─────┘
│        │     │     │     │     │     │     │         │     │     │     │     │     │     │
│        └─────┴─────┴─────┴─────┴─────┴─────┴─────────┴─────┴─────┴─────┴─────┴─────┘
│                                      │
│                    ┌─────────────────┴─────────────────┐
│                    ▼                                   ▼
│           ┌─────────────────┐                 ┌─────────────────┐
│           │     KRAKEN      │                 │      OKX        │
│           │   (pair EUR)    │                 │   (pair USDT)   │
│           │  REST + WS      │                 │  REST + WS      │
│           └─────────────────┘                 └─────────────────┘
└─────────────────────────────────────────────────────────────────────────────┘
```

**Moduli core:**

| Modulo | File | Ruolo |
|--------|------|-------|
| **Fleet Supervisor** | `shadowgrid_fleet.py` | Orchestrazione multi-bot, auto-restart, health dashboard `:8900` |
| **Grid Engine v2** | `shadowgrid_v2.py` | Spread adattivo ATR, filtro momentum ADX/RSI, risk management, re-anchoring dinamico |
| **Market Scanner** | `pair_scanner.py` | Discovery real-time pair grid ottimali (alto ATR%, basso ADX <25, spread stretto) |
| **Capital Rebalancer** | `fleet_rebalancer.py` | Riallocazione capitale oraria guidata da performance verso best performer |
| **Paper Engine (legacy)** | `denaro/core/engine.py` | Loop tick originale — timing tick, gestione segnali, orchestrazione |
| **Paper Exchange (legacy)** | `denaro/exchange/paper_exchange.py` | Paper order book, simulazione fill, tracking balance |
| **Grid Strategy (legacy)** | `denaro/strategy/grid.py` | Strategia grid — buy/sell grid, trailing stop, recentering |
| **Risk (legacy)** | `denaro/core/risk.py` | Limiti rischio, circuit breaker state machine, gate position sizing |
| **State (legacy)** | `denaro/core/state.py` | Portfolio, position, order dataclasses + serializzazione |
| **Backtest (legacy)** | `denaro/backtest/` | Engine replay dati storici, trade journal, metriche performance |

---

## 🌐 Topologia Infrastruttura

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           MC2 (Solo Monitoraggio)                        │
│  ┌─────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐  │
│  │ Zabbix      │  │ Hermes Agent    │  │ No-IP DDNS (no trading)     │  │
│  │ 15 traps    │  │ (questa sessione)│  │ mgrivett.ddns.net           │  │
│  │ + daily cron│  │                 │  │ sgrivett.ddns.net           │  │
│  └─────────────┘  └─────────────────┘  └─────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────────┐
                    ▼                                   ▼
         ┌─────────────────────┐           ┌─────────────────────┐
         │      nuvola         │           │     MARCODG1        │
         │  (87.106.3.15)      │           │  (87.106.222.123)   │
         │ sgrivett.ddns.net   │           │ mgrivett.ddns.net   │
         ├─────────────────────┤           ├─────────────────────┤
         │ shadowgrid-fleet    │           │ shadowgrid-fleet    │
         │ (7 bot, :8900)      │           │ (7 bot, :8900)      │
         │ airdrop-farm-nuvola │           │ MEXC SHADOW (SOL)   │
         │ (live, 20 wallet)   │           │ DDNS timer 10m      │
         │ DDNS timer 10m      │           │ Kraken: nVN31AX...  │
         │ Kraken: 1t3Jpcv...  │           │ MEXC: mx0vglZz...   │
         │ MEXC: mx0vgl1Tr...  │           │ Swap: 2GB           │
         │ OKX: f28aa65d...    │           │ OKX: f28aa65d...    │
         └─────────────────────┘           └─────────────────────┘
```

---

## 📦 Docker

PostgreSQL 16 Alpine + Redis 7 Alpine per journaling trade persistente e stato sessione.

```bash
cp docker/.env.example docker/.env
docker compose -f docker/docker-compose.yml up -d
```

**Servizi:**

| Servizio | Porta | Immagine | Scopo |
|---------|------|-------|---------|
| `trading-bot-db` | 5432 | `postgres:16-alpine` | Trade journal, history performance |
| `trading-bot-redis` | 6379 | `redis:7-alpine` | Stato sessione, publish/subscribe |

Vedi [docker/init_db.sql](docker/init_db.sql) per lo schema (tabelle: `trades`, `grid_events`, `daily_summary`).

---

## 🚀 Avvio Rapido

**ShadowGrid Fleet (consigliato):**

```bash
git clone https://github.com/grivetto/alpha-omega-trading.git
cd alpha-omega-trading
python3 -m venv venv && source venv/bin/activate
pip install ccxt numpy

# Configura .env con API key exchange
# Configura fleet_config.json con pair desiderati
python3 shadowgrid_fleet.py
```

**Legacy Paper Engine:**

```bash
python denaro/run_paper.py
```

**Infrastruttura Docker (opzionale):**

```bash
cp docker/.env.example docker/.env
docker compose -f docker/docker-compose.yml up -d
```

*Vedi [Docker](#-docker) per dettagli PostgreSQL/Redis.*

**Output live (ShadowGrid v2):**

```
=== ShadowGrid v2.0 Fleet ===
Exchange: kraken | okx
Bot:      7 per nodo (14 totali)
Capitale: 100 EUR per nodo
Tick:     ogni 30s (configurabile)
==============================
INFO [  142] price=0.888880 eq=25.07 spread=0.20% RSI=36.3 ADX=6.2 orders=12 trades=30 BUY creation paused by momentum filter (RSI=36.3, ADX=6.2)
```

---

## 🎛️ Configurazione

### Variabili Ambiente ShadowGrid v2

| Variabile | Default | Descrizione |
|----------|---------|-------------|
| `EXCHANGE` | `kraken` | Exchange: `kraken` o `okx` |
| `SYMBOL` | `DOGE/EUR` | Trading pair (es. `SOL/EUR`, `BICO/USDT`) |
| `CAPITAL` | `25` | Capitale paper per bot in EUR/USDT |
| `LEVELS` | `10` | Numero livelli grid per lato |
| `SPREAD_PCT` | `0.5` | Spread base % (sovrascritto da ATR-adaptive) |
| `PER_LEVEL` | `0.1` | Frazione capitale per ordine (10%) |
| `COOLDOWN` | `30` | Secondi tra tick |
| `FEE_PCT` | `0.26` | Fee exchange % |
| `HEALTH_PORT` | `8912` | Porta endpoint HTTP health |
| `LIVE_MODE` | `0` | Imposta `1` per live trading |
| `USE_MOMENTUM_FILTER` | `1` | Attiva filtro momentum ADX/RSI |
| `MAX_DRAWDOWN_PCT` | `0.15` | Hard stop a 15% max drawdown |
| `MAX_DAILY_LOSS_PCT` | `0.05` | Freeze a 5% perdita giornaliera |
| `ATR_SPREAD_MULTIPLIER` | `0.7` | ATR × moltiplicatore per spread dinamico |
| `MIN_SPREAD_PCT` | `0.2` | Floor spread minimo |
| `MAX_SPREAD_PCT` | `2.5` | Ceiling spread massimo |

### Fleet Config (`fleet_config.json`)

```json
{
  "exchange": "kraken",
  "capital_per_bot": 25.0,
  "total_fleet_capital": 100.0,
  "pairs": [
    {"symbol": "SOL/EUR", "port": 8912, "capital": 25.0, "exchange": "kraken"},
    {"symbol": "DOGE/EUR", "port": 8913, "capital": 25.0, "exchange": "kraken"},
    {"symbol": "XRP/EUR", "port": 8914, "capital": 25.0, "exchange": "kraken"},
    {"symbol": "ADA/EUR", "port": 8915, "capital": 25.0, "exchange": "kraken"}
  ],
  "okx_pairs": [
    {"symbol": "BICO/USDT", "port": 8930, "capital": 25.0, "exchange": "okx"},
    {"symbol": "GRVT/USDT", "port": 8931, "capital": 25.0, "exchange": "okx"},
    {"symbol": "ADA/USDT", "port": 8932, "capital": 25.0, "exchange": "okx"}
  ]
}
```

### Config Legacy Denaro

| Variabile | Default | Descrizione |
|----------|---------|-------------|
| `DENARO_EXCHANGE_ID` | `kraken` | Exchange per streaming prezzi |
| `DENARO_SYMBOL` | `DOGE/EUR` | Trading pair |
| `DENARO_INITIAL_CAPITAL` | `100` | Capitale paper in EUR |
| `DENARO_TICK_INTERVAL` | `30` | Secondi tra tick |
| `DENARO_GRID_LEVELS` | `5` | Numero livelli grid per lato |
| `DENARO_GRID_SPREAD` | `0.01` | Spread tra livelli grid (1%) |
| `DENARO_CAPITAL_PER_LEVEL` | `0.2` | Frazione capitale libero per ordine (20%) |
| `DENARO_UPPER_BOUND` | `0.02` | Threshold take-profit sopra entry (2%) |
| `DENARO_LOWER_BOUND` | `0.06` | Livello grid più basso sotto reference (6%) |
| `DENARO_TRAILING_STOP` | `0.04` | Attivazione trailing stop (4%) |
| `DENARO_PAPER_JSON` | `paper_state.json` | File persistenza stato portfolio |
| `DENARO_RISK_MAX_POS_PCT` | `0.25` | Max singola posizione come % equity |
| `DENARO_RISK_MAX_DRAWDOWN` | `0.10` | Limite drawdown prima circuit breaker |
| `DENARO_RISK_MAX_OPEN_ORDERS` | `5` | Max ordini aperti contemporanei |

---

## 📁 Struttura Progetto

```
alpha-omega-trading/
├── shadowgrid_v2.py              # Adaptive grid engine (NEW)
├── shadowgrid_fleet.py           # Multi-bot fleet supervisor (NEW)
├── pair_scanner.py               # Real-time market scanner (NEW)
├── fleet_rebalancer.py           # Hourly capital rebalancer (NEW)
├── fleet_config.json             # Fleet configuration (NEW)
├── README.md                     # English
├── README.it.md                  # Italiano (this file)
├── README.th.md                  # Thai
├── denaro/
│   ├── run_paper.py              # Legacy entry point
│   ├── core/
│   │   ├── engine.py             # Legacy main loop
│   │   ├── risk.py               # Legacy risk limits
│   │   ├── state.py              # Legacy dataclasses
│   │   └── __init__.py
│   ├── exchange/
│   │   ├── paper_exchange.py     # Legacy paper order book
│   │   └── __init__.py
│   ├── strategy/
│   │   ├── grid.py               # Legacy grid strategy
│   │   └── __init__.py
│   ├── backtest/
│   │   ├── engine.py             # Legacy backtest runner
│   │   └── journal.py            # Legacy trade journal
│   └── __init__.py
├── neo/                          # Modular scaffold (p1)
│   ├── core.py
│   ├── strategies.py
│   ├── state.py
│   ├── monitor.py
│   ├── memory.py
│   ├── exchange.py
│   ├── main.py
│   ├── types.py
│   └── requirements.txt
├── enhanced/                     # Health & dashboard
│   ├── health_server.py
│   ├── update_dashboard.py
│   └── __init__.py
├── airdrop-farm/                 # Multi-strategy airdrop farmer
│   ├── main.py
│   ├── core/
│   ├── strategies/
│   ├── chains/
│   ├── monitoring/
│   ├── activity/
│   └── configs
├── tests/                        # Legacy test suite (33 tests)
│   ├── test_engine_loop.py
│   ├── test_grid_strategy.py
│   ├── test_paper_exchange.py
│   ├── test_risk.py
│   └── test_backtest.py
├── docker/
│   ├── docker-compose.yml
│   ├── .env.example
│   └── init_db.sql
├── .github/workflows/ci.yml
├── requirements.txt
├── deploy.sh
├── notifier.py
├── denaro_core.py
├── denaro_zabbix.py
├── kraken_engine.py
├── mexc_engine.py
├── bybit_engine.py
├── main.py
├── main_mexc.py
├── main_v5.py
└── mock_runner.py
```

---

## 🧪 Testing

```bash
source venv/bin/activate
pip install pytest

# Tutti i test legacy
python -m pytest tests/ -v

# Per modulo
python -m pytest tests/test_risk.py -v
python -m pytest tests/test_engine_loop.py -v
python -m pytest tests/test_backtest.py -v
```

**Copertura test legacy:**

| File test | Test | Scope |
|-----------|-------|-------|
| `test_engine_loop.py` | 2 | Integration: movimenti prezzo, fill, drawdown floor |
| `test_grid_strategy.py` | 12 | Costruzione grid, trailing stop, recenter, safety bounds |
| `test_paper_exchange.py` | 8 | Ciclo vita ordini, orderbook, balance, gestione errori |
| `test_risk.py` | 8 | Circuit breaker, max position, daily loss, drawdown |
| `test_backtest.py` | 3 | Caricamento dati, replay, trade journal, win rate |

---

## 📈 Deployment (systemd)

### Servizio ShadowGrid Fleet

Su ogni nodo target (nuvola, MARCODG1):

```bash
git clone https://github.com/grivetto/alpha-omega-trading.git
cd alpha-omega-trading
python3 -m venv venv && source venv/bin/activate
pip install ccxt numpy
```

**User service** (`~/.config/systemd/user/shadowgrid-fleet.service`):

```ini
[Unit]
Description=ShadowGrid Fleet Orchestrator (Multi-Bot Grid)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=%h/denaro/venv/bin/python %h/denaro/shadowgrid_fleet.py
WorkingDirectory=%h/denaro
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
```

**Avvialo:**

```bash
systemctl --user daemon-reload
systemctl --user enable --now shadowgrid-fleet
systemctl --user status shadowgrid-fleet --no-pager

# Segui log live
journalctl --user -u shadowgrid-fleet -f

# Health dashboard
curl http://localhost:8900/health | python3 -m json.tool
```

### Servizio Legacy Denaro Paper

```ini
[Unit]
Description=Denaro Paper Trading Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=%h/dev/alpha-omega-trading/venv/bin/python %h/dev/alpha-omega-trading/denaro/run_paper.py
WorkingDirectory=%h/dev/alpha-omega-trading
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
```

---

## 🧘 Principi

- **Architettura modulare** — loosely coupled, facile swap exchange o strategy
- **Zero rischio reale** — circuit breaker, position cap, limiti drawdown
- **Backtesting deterministico** — stessi dati, stessi risultati, sempre
- **Esecuzione trasparente** — ogni ordine e fill loggato su JSONL trade journal
- **Production-ready** — systemd service, graceful shutdown, persistenza stato
- **Intelligenza adattiva** — spread basato su ATR, filtro momentum, allocazione capitale dinamica

---

## 🗺️ Roadmap

- [x] p1 — Scaffold modulare (engine, exchange, strategy, state, risk)
- [x] p2 — Paper runner (live tick loop, grid strategy, portfolio persistence)
- [x] p3 — Pulizia infrastruttura (servizi deprecati rimossi, singola unit systemd)
- [x] p4 — Test suite (33 test, engine integration, risk gate, backtest runner)
- [x] p4.5 — DDNS + automazione multi-nodo (No-IP, systemd timer, credenziali sicure)
- [x] p4.6 — Rotazione & validazione API key (Kraken/MEXC, audit permessi, Bybit deprecato)
- [x] p4.7 — Airdrop Farm v1 (20 wallet, 4 strategie, live su nuvola)
- [x] **⚡ ShadowGrid v2.0 & Flotta 14-Bot** — Grid adattivo ATR, filtro ADX/RSI, fleet supervisor, pair scanner, rebalancer
- [ ] p5 — Live deploy su Kraken/OKX (ordini reali, isolamento sub-account, PnL giornaliero)
- [ ] p6 — Dashboard performance grid (landing page, metriche, trade journal viewer)
- [ ] p7 — Engine multi-strategia (momentum, funding rate, arbitrage runner)
- [ ] p8 — Selezione pair ML-enhanced & regime detection

---

## 📜 Licenza

[The Unlicense](http://unlicense.org/) — public domain. Fai quello che vuoi.