<div align="center">

# ⚡ DENARO ⚡

### *A machine for making money from little — without wasting resources.*

[![License: Unlicense](https://img.shields.io/badge/license-Unlicense-blue.svg)](http://unlicense.org/)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![CCXT](https://img.shields.io/badge/exchange-CCXT%20%2F%20Kraken-5741D9?logo=bitcoin&logoColor=white)](https://github.com/ccxt/ccxt)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20systemd-FCC624?logo=linux&logoColor=black)](https://www.freedesktop.org/wiki/Software/systemd/)
[![Status](https://img.shields.io/badge/status-live%20paper%20trading-success)](https://github.com/grivetto/alpha-omega-trading)
[![Code Style](https://img.shields.io/badge/style-clean%20%26%20modular-brightgreen)](https://github.com/grivetto/alpha-omega-trading)
[![Docker](https://img.shields.io/badge/docker-postgres%2016%20%2B%20redis%207-2496ED?logo=docker&logoColor=white)](docker/docker-compose.yml)

**Modular paper trading engine for crypto markets. Real-time price feeds, grid strategies, zero real money at risk — and zero waste.**

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

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                     PaperEngine                      │
│  ┌─────────┐  ┌───────────┐  ┌──────┐  ┌──────┐   │
│  │ Exchange │  │  Strategy  │  │ Risk │  │State │   │
│  │ (paper)  │  │  (grid)   │  │  Mgr │  │ Port │   │
│  └────┬────┘  └─────┬─────┘  └──┬───┘  └──┬───┘   │
│       │              │           │         │        │
│       └──────┬───────┴───────────┴─────────┘        │
│              │                                      │
│         ┌────▼────┐                                 │
│         │   Tick  │  every 30s (configurable)       │
│         │  Loop   │                                 │
│         └─────────┘                                 │
└─────────────────────────────────────────────────────┘
```

**Core modules:**

| Module | File | Role |
|--------|------|------|
| **Engine** | `denaro/core/engine.py` | Main loop — tick timing, signal handling, orchestration |
| **Exchange** | `denaro/exchange/paper_exchange.py` | Paper order book, fill simulation, balance tracking |
| **Strategy** | `denaro/strategy/grid.py` | Grid strategy — buy below reference, sell above, trailing stop, recentering |
| **Risk** | `denaro/core/risk.py` | Risk limits, circuit breaker state machine, position sizing gates |
| **State** | `denaro/core/state.py` | Portfolio, position, and order dataclasses + serialization |
| **Backtest** | `denaro/backtest/` | Historical data replay engine, trade journal, performance metrics |

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
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
         ┌─────────────────────┐           ┌─────────────────────┐
         │      nuvola         │           │     MARCODG1        │
         │  (87.106.3.15)      │           │  (87.106.222.123)   │
         │ sgrivett.ddns.net   │           │ mgrivett.ddns.net   │
         ├─────────────────────┤           ├─────────────────────┤
         │ denaro-kraken-health│           │ main_mexc.py        │
         │ (paper DOGE/EUR)    │           │ (SHADOW SOL/USDT)   │
         │ airdrop-farm-nuvola │           │ denaro-paper        │
         │ (live, 20 wallets)  │           │ (paper trading)     │
         │ DDNS timer 10m      │           │ DDNS timer 10m      │
         │ Kraken: 1t3Jpcv...  │           │ Kraken: nVN31AX...  │
         │ MEXC: mx0vgl1Tr...  │           │ MEXC: mx0vglZz...   │
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

```bash
git clone https://github.com/grivetto/alpha-omega-trading.git
cd alpha-omega-trading
python3 -m venv venv && source venv/bin/activate
pip install ccxt
python denaro/run_paper.py
```

**Docker infrastructure (optional):**

```bash
cp docker/.env.example docker/.env
docker compose -f docker/docker-compose.yml up -d
```

*See [Docker](#-docker) for PostgreSQL/Redis details.*

**Live output:**

```
=== Paper Trade LIVE ===
Exchange: kraken (sandbox=False)
Symbol:   DOGE/EUR
Capital:  100.00 EUR
Tick:     every 30.0s
==============================
INFO     GRID BUY 262.84 @ 0.05706819
INFO     GRID BUY 258.96 @ 0.05792421
    Tick#1 | Equity=100.00 | Free=100.00 | Pos=0 Ord=7 | CB=closed DD=0.0%
```

---

## 🎛️ Configuration

Environment variables (loaded from `.env` or shell):

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
denaro/
├── __init__.py
├── run_paper.py              # Entry point — start paper trading
├── core/
│   ├── engine.py             # Main loop, tick orchestration, signal handling
│   ├── risk.py               # Risk limits, circuit breaker, order gating
│   ├── state.py              # Portfolio, position, order dataclasses
│   └── __init__.py
├── exchange/
│   ├── paper_exchange.py     # Paper order book, fill simulation, balance
│   └── __init__.py
├── strategy/
│   ├── grid.py               # Grid strategy — buy/sell grids, trailing stop, recentering
│   └── __init__.py
├── backtest/
│   ├── __init__.py
│   ├── engine.py             # Historical data replay, trade journal
│   └── journal.py            # Performance metrics, trade log
tests/
├── test_engine_loop.py       # Integration test: engine tick → grid → fill → TP
├── test_grid_strategy.py     # Unit tests: grid construction, levels, recenter
├── test_paper_exchange.py    # Unit tests: orders, fills, orderbook
├── test_risk.py              # Unit tests: risk limits, circuit breaker
├── test_backtest.py          # Backtest runner against historical data
docker/
├── docker-compose.yml        # PostgreSQL 16 + Redis 7
├── .env.example              # Environment template
└── init_db.sql               # Database schema
```

---

## 🧪 Testing

```bash
source venv/bin/activate
pip install pytest

# All tests
python -m pytest tests/ -v

# By module
python -m pytest tests/test_risk.py -v
python -m pytest tests/test_engine_loop.py -v
python -m pytest tests/test_backtest.py -v
```

**Test coverage:**

| Test file | Tests | Scope |
|-----------|-------|-------|
| `test_engine_loop.py` | 2 | Integration: price movements, fills, drawdown floor |
| `test_grid_strategy.py` | 12 | Grid construction, trailing stop, recenter, safety bounds |
| `test_paper_exchange.py` | 8 | Order lifecycle, orderbook, balance, error handling |
| `test_risk.py` | 8 | Circuit breaker, max position, daily loss, drawdown |
| `test_backtest.py` | 3 | Data load, replay, trade journal, win rate |

---

## 📈 Deployment (systemd)

On each target node (nuvola, MARCODG1):

```bash
git clone https://github.com/grivetto/alpha-omega-trading.git
cd alpha-omega-trading
python3 -m venv venv && source venv/bin/activate
pip install ccxt
```

**User service** (`~/.config/systemd/user/denaro-paper.service`):

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

**Start it:**

```bash
systemctl --user daemon-reload
systemctl --user enable --now denaro-paper
systemctl --user status denaro-paper --no-pager

# Follow live logs
journalctl --user -u denaro-paper -f
```

---

## 🧘 Principles

- **Modular architecture** — loosely coupled, easy to swap exchange or strategy
- **Zero real risk** — circuit breakers, position caps, drawdown limits
- **Deterministic backtesting** — same data, same results, every time
- **Transparent execution** — every order and fill logged to JSONL trade journal
- **Production-ready** — systemd service, graceful shutdown, state persistence

---

## 🗺️ Roadmap

- [x] p1 — Modular scaffold (engine, exchange, strategy, state, risk)
- [x] p2 — Paper runner (live tick loop, grid strategy, portfolio persistence)
- [x] p3 — Infrastructure cleanup (deprecated services removed, single systemd unit)
- [x] p4 — Test suite (33 tests, engine integration, risk gates, backtest runner)
- [x] p4.5 — DDNS + multi-node automation (No-IP, systemd timers, secure creds)
- [x] p4.6 — API key rotation & validation (Kraken/MEXC, perms audit, Bybit deprecated)
- [x] p4.7 — Airdrop Farm v1 (20 wallets, 4 strategies, live on nuvola)
- [ ] p5 — Live deploy to Kraken (real orders, sub-account isolation, daily PnL)
- [ ] p6 — Grid performance dashboard (landing page, metrics, trade journal viewer)
- [ ] p7 — Multi-strategy engine (momentum, funding rate, arbitrage runner)

---

## 📜 License

[The Unlicense](http://unlicense.org/) — public domain. Do whatever you want.