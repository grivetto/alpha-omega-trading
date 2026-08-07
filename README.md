<div align="center">

# ⚡ DENARO ⚡

### *A machine for making money from little — without wasting resources.*

[![License: Unlicense](https://img.shields.io/badge/license-Unlicense-blue.svg)](http://unlicense.org/)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![CCXT](https://img.shields.io/badge/exchange-CCXT%20%2F%20Kraken%20%7C%20OKX-5741D9?logo=bitcoin&logoColor=white)](https://github.com/ccxt/ccxt)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20systemd-FCC624?logo=linux&logoColor=black)](https://www.freedesktop.org/wiki/Software/systemd/)
[![Status](https://img.shields.io/badge/status-live%20paper%20trading%20%7C%2014%20bots-success)](https://github.com/grivetto/alpha-omega-trading)
[![Code Style](https://img.shields.io/badge/style-clean%20%26%20modular-brightgreen)](https://github.com/grivetto/alpha-omega-trading)
[![Docker](https://img.shields.io/badge/docker-postgres%2016%20%2B%20redis%207-2496ED?logo=docker&logoColor=white)](docker/docker-compose.yml)

**Modular paper trading engine for crypto markets. Real-time price feeds, adaptive grid strategies, multi-exchange fleet orchestration, zero real money at risk — and zero waste.**

[Architecture](#-architecture) · [Philosophy](#-philosophy) · [Docker](#-docker) · [Quick Start](#-quick-start) · [Deployment](#-deployment-systemd) · [Roadmap](#-roadmap)

</div>

---

## 🎯 Philosophy

> **Capital protection is law. Efficiency is profit. Code is law. Profit is proof.**

Denaro was born from a simple constraint: **limited capital must not be speculated — it must be cultivated.**

Every design decision follows three rules:

1. **🛡️ Never risk what you cannot afford to lose** — circuit breakers, drawdown limits, and position caps are not optional features; they are the foundation.
2. **⚙️ Waste nothing** — no bloated frameworks, no redundant processes, no abandoned services consuming RAM on a headless node. One process, one purpose, minimal footprint.
3. **📈 Asymmetric upside** — small, patient grid orders harvesting volatility. Many small wins, strictly bounded losses.

This is not a get-rich-quick bot. It is an **engineering discipline applied to markets**: start with €100, prove the strategy on paper, then — and only then — scale.

---

## 📜 Project History

| Milestone | Date / Commit | Description |
|-----------|---------------|-------------|
| **🌱 Live Bot (v0)** | pre-repo | Single-file Kraken DOGE/EUR grid bot. Ran live on Raspberry Pi with ~€200 capital for months. Systemd persistence, manual state reload. Proved the concept; exposed the limits of a monolith. |
| **📉 The Binance Collapse** | 2026-06-29 → 07-01 | **The project started dropping beats — and euros.** Denaro's live fleet (DOGE on nuvola, ADA+SOL on MARCODG1, ETH on MC2) was fully operational on Binance sub-accounts… until it wasn't. In the last days of June, Binance began silently revoking trading permissions on EU sub-account API keys: `GET /account` kept returning 200, but every `POST /order` died with `401 -2015 ("Invalid API-key, IP, or permissions")`. The bots didn't crash — they **starved**. Zero fills, positions stranded, ~€206 in capital frozen mid-grid while the market moved without them. The cause wasn't a bug: it was **MiCA**. Binance was losing its European licenses, and the enforcement arrived exactly on **July 1st, 2026** — the day Binance became unusable for EU spot trading. The fleet was fully built, fully deployed, fully ready… and the exchange pulled the plug. Lesson burned into the repo: **exchange risk is real risk**. |
| **🐙 The Kraken Pivot** | 2026-07-01 | Same day, same hour: everything converted to EUR on Binance (~€344 recovered across main + sub-accounts), withdrawn via SEPA, and the entire infrastructure re-pointed at **Kraken** — MiCA-compliant, EU-licensed, superior API. Binance and Bybit permanently deprecated. |
| **🏗️ p1 — Modular Scaffold** | `504172c` | Full refactor. Monolith split into 5 clean modules: `engine`, `exchange`, `strategy`, `state`, `risk`. Architecture inspired by Freqtrade (loop), Hummingbot (clock), OctoBot (grid mode), Jesse (broker abstraction). |
| **🔄 p2 — Paper Runner** | `0b2e0f3` | `PaperEngine` main loop: configurable tick interval, grid strategy wiring, portfolio state persistence to JSON. Entry point `run_paper.py`. |
| **🩹 p2.1 — Kraken Sandbox Fix** | `054b957` | Kraken's CCXT client has no `sandbox` attribute. Exchange adapter catches the error and falls back to live API readonly, manually setting `sandbox=False`. |
| **🛡️ p2.2 — Guard + Graceful Shutdown** | `015627a` | `getattr` guard against `AttributeError`; SIGINT/SIGTERM handler stops engine, saves portfolio, exits cleanly. |
| **🧹 p3 — Infrastructure Cleanup** | — | Removal of **all** legacy Denaro services, cron jobs, system-wide units, timers, binaries and orphaned processes across both nodes. One service survives: `denaro-paper`. |
| **🧪 p4 — Paper Trading Test Suite** | current | 33 unit + integration tests. Engine tick, risk gates, grid strategy, trailing stop, paper exchange fill/orderbook, backtest runner. `test_engine_up_down_up` validates end-to-end cycle: price dip → buy grid → TP sell → profit. |
| **🌐 DDNS + Multi-Node Automation** | 2026-07-30 | **No-IP DDNS deployed on both trading nodes** (`nuvola` → `sgrivett.ddns.net`, `MARCODG1` → `mgrivett.ddns.net`). Systemd timer (10 min) + secure credential file (`/etc/noip.conf`, 600, root:root). Free tier requires email confirmation every 30 days. |
| **🔑 API Key Rotation & Validation** | 2026-07-31 | **Kraken key rotated** (post-MiCA). New key `1t3Jpcv...` validated: trading permissions ✅ (Query Funds + Create/Modify Orders), funding permissions ❌ (needs `Deposit/Withdraw` enabled on Kraken UI). **MEXC keys validated on both nodes**: nuvola (`mx0vgl1Tr...`) + MARCODG1 (`mx0vglZz...`) — spot trading + account perms, IP whitelist `700006` (both IPs). Bybit deprecated (MiCA), removed from all configs. |
| **💸 The 115 USDT Mystery** | 2026-07-22 | **115.74 USDT (ERC20) sent to Kraken deposit address `0x0e7b7d8634c36994571a0f82f6abb70cde283493` — TxID `0xc2a95bb787aa0cc7c46323840cc61ac550538f539faeabd95b1fb24f42e936e7`**. **Never arrived. Not on-chain (Etherscan: no such tx).** Kraken API lacks funding perms to query deposit status. Support ticket requires: TxID, amount, destination, timestamp, proof of non-arrival on-chain. Next step: enable `Deposit/Withdraw` on API key → fetch full `Ledgers`/`DepositStatus` JSON for evidence. |
| **🤖 Airdrop Farm v1** | 2026-07-31 | **Autonomous multi-strategy airdrop farmer** deployed on nuvola (systemd service). 20 wallets from BIP39 mnemonic + Fernet encryption. 4 strategies: airdrop (Base/Scroll/Abstract/Linea), Hyperliquid points, yield, MEXC launchpad. €250 virtual, €100 real post-2026-08-05. Poisson scheduler, circuit breaker, idempotent execution. 22 modules. Zabbix monitoring on MC2 (15 trapper items + daily cron). |
| **🔄 Full Reboot & Verification** | 2026-07-31 | Both nodes rebooted for kernel updates. Post-reboot: all systemd services healthy. nuvola: `denaro-kraken-health` (paper DOGE/EUR), `airdrop-farm-nuvola` (live), DDNS timer. MARCODG1: MEXC SHADOW mode (SOL/USDT, equity 100 USDT), DDNS timer, paper trading. |
| **⚡ ShadowGrid v2.0 & Multi-Bot Fleet** | 2026-08-07 | **Complete transformation into a 14-bot Adaptive Fleet across 2 exchanges.** Upgraded grid engine (`shadowgrid_v2.py`) with dynamic ATR-based spread, ADX/RSI momentum filter, 15% drawdown circuit breaker, 5% daily loss limit, and 6% dynamic re-anchoring. Added `shadowgrid_fleet.py` supervisor (7 bots/node, auto-restart, health dashboard `:8900`), `pair_scanner.py` for real-time market discovery (high ATR%, low ADX, tight spread), and `fleet_rebalancer.py` for hourly performance-driven capital allocation. Deployed across `nuvola` (4 Kraken EUR + 3 OKX USDT) and `MARCODG1` (4 Kraken EUR + 3 OKX USDT) — **14 bots total, 200€ paper capital**. Pair optimization: replaced underperforming OKX pairs (XSPCX/USDT, XSNDK/USDT — ADX >44) with **GRVT/USDT** (ADX 24.1, grid_score 0.923) and **ADA/USDT** (ADX 13.5). Swap 2GB added on MARCODG1. All legacy processes purged. |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      ShadowGrid Fleet Orchestrator                           │
│  ┌─────────────────────────────┐         ┌─────────────────────────────┐    │
│  │         nuvola              │         │        MARCODG1             │    │
│  │  shadowgrid_fleet.py :8900  │         │  shadowgrid_fleet.py :8900  │    │
│  │  (supervisor + health)      │         │  (supervisor + health)      │    │
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
│           │   (EUR pairs)   │                 │   (USDT pairs)  │
│           │  REST + WS      │                 │  REST + WS      │
│           └─────────────────┘                 └─────────────────┘
└─────────────────────────────────────────────────────────────────────────────┘
```

**Core modules:**

| Module | File | Role |
|--------|------|------|
| **Fleet Supervisor** | `shadowgrid_fleet.py` | Multi-bot orchestration, auto-restart, health dashboard `:8900` |
| **Grid Engine v2** | `shadowgrid_v2.py` | ATR-adaptive spread, ADX/RSI momentum filter, risk management, dynamic re-anchoring |
| **Market Scanner** | `pair_scanner.py` | Real-time discovery of optimal grid pairs (high ATR%, low ADX <25, tight spread) |
| **Capital Rebalancer** | `fleet_rebalancer.py` | Hourly performance-driven capital reallocation to best performers |
| **Paper Engine (legacy)** | `denaro/core/engine.py` | Original tick loop — tick timing, signal handling, orchestration |
| **Paper Exchange (legacy)** | `denaro/exchange/paper_exchange.py` | Paper order book, fill simulation, balance tracking |
| **Grid Strategy (legacy)** | `denaro/strategy/grid.py` | Grid strategy — buy/sell grids, trailing stop, recentering |
| **Risk (legacy)** | `denaro/core/risk.py` | Risk limits, circuit breaker state machine, position sizing gates |
| **State (legacy)** | `denaro/core/state.py` | Portfolio, position, and order dataclasses + serialization |
| **Backtest (legacy)** | `denaro/backtest/` | Historical data replay engine, trade journal, performance metrics |

---

## 🌐 Infrastructure Topology

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           MC2 (Monitoring Only)                          │
│  ┌─────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐  │
│  │ Zabbix      │  │ Hermes Agent    │  │ No-IP DDNS (no trading)     │  │
│  │ 15 traps    │  │ (this session)  │  │ mgrivett.ddns.net           │  │
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
         │ (7 bots, :8900)     │           │ (7 bots, :8900)     │
         │ airdrop-farm-nuvola │           │ MEXC SHADOW (SOL)   │
         │ (live, 20 wallets)  │           │ DDNS timer 10m      │
         │ DDNS timer 10m      │           │ Kraken: nVN31AX...  │
         │ Kraken: 1t3Jpcv...  │           │ MEXC: mx0vglZz...   │
         │ MEXC: mx0vgl1Tr...  │           │ Swap: 2GB           │
         │ OKX: f28aa65d...    │           │ OKX: f28aa65d...    │
         └─────────────────────┘           └─────────────────────┘
```

---

## 📦 Docker

PostgreSQL 16 Alpine + Redis 7 Alpine for persistent trade journaling and session state.

```bash
cp docker/.env.example docker/.env
docker compose -f docker/docker-compose.yml up -d
```

**Services:**

| Service | Port | Image | Purpose |
|---------|------|-------|---------|
| `trading-bot-db` | 5432 | `postgres:16-alpine` | Trade journal, performance history |
| `trading-bot-redis` | 6379 | `redis:7-alpine` | Session state, publish/subscribe |

See [docker/init_db.sql](docker/init_db.sql) for the schema (tables: `trades`, `grid_events`, `daily_summary`).

---

## 🚀 Quick Start

**ShadowGrid Fleet (recommended):**

```bash
git clone https://github.com/grivetto/alpha-omega-trading.git
cd alpha-omega-trading
python3 -m venv venv && source venv/bin/activate
pip install ccxt numpy

# Configure .env with exchange API keys
# Configure fleet_config.json with desired pairs
python3 shadowgrid_fleet.py
```

**Legacy Paper Engine:**

```bash
python denaro/run_paper.py
```

**Docker infrastructure (optional):**

```bash
cp docker/.env.example docker/.env
docker compose -f docker/docker-compose.yml up -d
```

*See [Docker](#-docker) for PostgreSQL/Redis details.*

**Live output (ShadowGrid v2):**

```
=== ShadowGrid v2.0 Fleet ===
Exchange: kraken | okx
Bots:     7 per node (14 total)
Capital:  100 EUR per node
Tick:     every 30s (configurable)
==============================
INFO [  142] price=0.888880 eq=25.07 spread=0.20% RSI=36.3 ADX=6.2 orders=12 trades=30 BUY creation paused by momentum filter (RSI=36.3, ADX=6.2)
```

---

## 🎛️ Configuration

### ShadowGrid v2 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `EXCHANGE` | `kraken` | Exchange: `kraken` or `okx` |
| `SYMBOL` | `DOGE/EUR` | Trading pair (e.g., `SOL/EUR`, `BICO/USDT`) |
| `CAPITAL` | `25` | Paper capital per bot in EUR/USDT |
| `LEVELS` | `10` | Number of grid levels per side |
| `SPREAD_PCT` | `0.5` | Base spread % (overridden by ATR-adaptive) |
| `PER_LEVEL` | `0.1` | Fraction of capital per order (10%) |
| `COOLDOWN` | `30` | Seconds between ticks |
| `FEE_PCT` | `0.26` | Exchange fee % |
| `HEALTH_PORT` | `8912` | HTTP health endpoint port |
| `LIVE_MODE` | `0` | Set to `1` for live trading |
| `USE_MOMENTUM_FILTER` | `1` | Enable ADX/RSI momentum filter |
| `MAX_DRAWDOWN_PCT` | `0.15` | Hard stop at 15% max drawdown |
| `MAX_DAILY_LOSS_PCT` | `0.05` | Freeze at 5% daily loss |
| `ATR_SPREAD_MULTIPLIER` | `0.7` | ATR × multiplier for dynamic spread |
| `MIN_SPREAD_PCT` | `0.2` | Minimum spread floor |
| `MAX_SPREAD_PCT` | `2.5` | Maximum spread ceiling |

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

### Legacy Denaro Config

| Variable | Default | Description |
|----------|---------|-------------|
| `DENARO_EXCHANGE_ID` | `kraken` | Exchange to stream prices from |
| `DENARO_SYMBOL` | `DOGE/EUR` | Trading pair |
| `DENARO_INITIAL_CAPITAL` | `100` | Paper capital in EUR |
| `DENARO_TICK_INTERVAL` | `30` | Seconds between ticks |
| `DENARO_GRID_LEVELS` | `5` | Number of grid levels per side |
| `DENARO_GRID_SPREAD` | `0.01` | Spread between grid levels (1%) |
| `DENARO_CAPITAL_PER_LEVEL` | `0.2` | Fraction of free capital per order (20%) |
| `DENARO_UPPER_BOUND` | `0.02` | Take-profit threshold above entry (2%) |
| `DENARO_LOWER_BOUND` | `0.06` | Lowest grid level below reference (6%) |
| `DENARO_TRAILING_STOP` | `0.04` | Trailing stop activation (4%) |
| `DENARO_PAPER_JSON` | `paper_state.json` | Portfolio state persistence file |
| `DENARO_RISK_MAX_POS_PCT` | `0.25` | Max single position as % of equity |
| `DENARO_RISK_MAX_DRAWDOWN` | `0.10` | Drawdown limit before circuit breaker |
| `DENARO_RISK_MAX_OPEN_ORDERS` | `5` | Max concurrent open orders |

---

## 📁 Project Structure

```
alpha-omega-trading/
├── shadowgrid_v2.py              # Adaptive grid engine (NEW)
├── shadowgrid_fleet.py           # Multi-bot fleet supervisor (NEW)
├── pair_scanner.py               # Real-time market scanner (NEW)
├── fleet_rebalancer.py           # Hourly capital rebalancer (NEW)
├── fleet_config.json             # Fleet configuration (NEW)
├── README.md
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

# All legacy tests
python -m pytest tests/ -v

# By module
python -m pytest tests/test_risk.py -v
python -m pytest tests/test_engine_loop.py -v
python -m pytest tests/test_backtest.py -v
```

**Legacy test coverage:**

| Test file | Tests | Scope |
|-----------|-------|-------|
| `test_engine_loop.py` | 2 | Integration: price movements, fills, drawdown floor |
| `test_grid_strategy.py` | 12 | Grid construction, trailing stop, recenter, safety bounds |
| `test_paper_exchange.py` | 8 | Order lifecycle, orderbook, balance, error handling |
| `test_risk.py` | 8 | Circuit breaker, max position, daily loss, drawdown |
| `test_backtest.py` | 3 | Data load, replay, trade journal, win rate |

---

## 📈 Deployment (systemd)

### ShadowGrid Fleet Service

On each target node (nuvola, MARCODG1):

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

**Start it:**

```bash
systemctl --user daemon-reload
systemctl --user enable --now shadowgrid-fleet
systemctl --user status shadowgrid-fleet --no-pager

# Follow live logs
journalctl --user -u shadowgrid-fleet -f

# Health dashboard
curl http://localhost:8900/health | python3 -m json.tool
```

### Legacy Denaro Paper Service

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

## 🧘 Principles

- **Modular architecture** — loosely coupled, easy to swap exchange or strategy
- **Zero real risk** — circuit breakers, position caps, drawdown limits
- **Deterministic backtesting** — same data, same results, every time
- **Transparent execution** — every order and fill logged to JSONL trade journal
- **Production-ready** — systemd service, graceful shutdown, state persistence
- **Adaptive intelligence** — ATR-based spread, momentum filtering, dynamic capital allocation

---

## 🗺️ Roadmap

- [x] p1 — Modular scaffold (engine, exchange, strategy, state, risk)
- [x] p2 — Paper runner (live tick loop, grid strategy, portfolio persistence)
- [x] p3 — Infrastructure cleanup (deprecated services removed, single systemd unit)
- [x] p4 — Test suite (33 tests, engine integration, risk gates, backtest runner)
- [x] p4.5 — DDNS + multi-node automation (No-IP, systemd timers, secure creds)
- [x] p4.6 — API key rotation & validation (Kraken/MEXC, perms audit, Bybit deprecated)
- [x] p4.7 — Airdrop Farm v1 (20 wallets, 4 strategies, live on nuvola)
- [x] **⚡ ShadowGrid v2.0 & 14-Bot Fleet** — ATR-adaptive grid, ADX/RSI filter, fleet supervisor, pair scanner, rebalancer
- [ ] p5 — Live deploy to Kraken/OKX (real orders, sub-account isolation, daily PnL)
- [ ] p6 — Grid performance dashboard (landing page, metrics, trade journal viewer)
- [ ] p7 — Multi-strategy engine (momentum, funding rate, arbitrage runner)
- [ ] p8 — ML-enhanced pair selection & regime detection

---

## 📜 License

[The Unlicense](http://unlicense.org/) — public domain. Do whatever you want.