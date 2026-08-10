<div align="center">

# ⚡ ALPHA-OMEGA TRADING ⚡

### *The ultimate distributed algorithmic trading system — from paper to profit, across two nodes, with zero compromises.*

[![License: Unlicense](https://img.shields.io/badge/license-Unlicense-blue.svg)](http://unlicense.org/)
[![Python](https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![CCXT](https://img.shields.io/badge/exchange-CCXT%20Pro%20%2F%20Kraken%20%7C%20OKX-5741D9?logo=bitcoin&logoColor=white)](https://github.com/ccxt/ccxt)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20systemd%20%7C%20Docker-FCC624?logo=linux&logoColor=black)](https://www.freedesktop.org/wiki/Software/systemd/)
[![Status](https://img.shields.io/badge/status-LIVE%20%E2%82%AC101%20CAPITAL%20%7C%2024%20BOTS%20OPERATIONAL-brightgreen)](https://github.com/grivetto/alpha-omega-trading)
[![Architecture](https://img.shields.io/badge/architecture-distributed%2C%20async%2C%20fleet%20orchestrated-brightgreen)]()
[![Monitoring](https://img.shields.io/badge/monitoring-Zabbix%20%2B%20Grafana%20%2B%20Telegram-FF6F00?logo=grafana&logoColor=white)]()

**Distributed, async, multi-strategy trading fleet orchestrated across two machines. Real-time market data via ZeroMQ, shared state via Redis Streams, portfolio risk management, dynamic pair selection — all paper-validated, live-ready.**

[Architecture](#-architecture) · [Philosophy](#-philosophy) · [Quick Start](#-quick-start) · [Deployment](#-deployment) · [Monitoring](#-monitoring--observability) · [Roadmap](#-roadmap)

</div>

---

## 🚀 GO-LIVE: 2026-08-10 22:42:30 CEST — €101 REAL CAPITAL DEPLOYED

> **GO-LIVE CONFERMATO** — Il sistema è operativo con capitale reale su entrambi i nodi e entrambi gli exchange.

| Nodo | OKX (EEA) | Kraken | Totale Nodo |
|------|-----------|--------|-------------|
| **Nuvola** | ✅ **€25.00** | ✅ **€25.50** | **€50.50** |
| **MARCODG1** | ✅ **€25.00** | ✅ **€25.50** | **€50.50** |
| **TOTALE SISTEMA** | **€50** | **€51** | **€101** |

**Risk Limits Armed:**
- Max DD per bot: 15% (€3.75)
- Daily loss limit: 5% (€1.25)
- Portfolio kill switch: 20% (€20)
- Correlation filter: 0.7
- Max 2 positions per base currency

---

## 🎯 Philosophy

> **Capital protection is law. Efficiency is profit. Code is law. Profit is proof. Distribution is resilience.**

Alpha-Omega Trading was born from a simple constraint: **limited capital must not be speculated — it must be cultivated across a resilient, distributed infrastructure.**

Every design decision follows four rules:

1. **🛡️ Never risk what you cannot afford to lose** — circuit breakers, drawdown limits, position caps, and correlation limits are not optional features; they are the foundation at every layer (bot, portfolio, fleet).
2. **⚙️ Waste nothing** — no bloated frameworks, no redundant processes, no abandoned services consuming RAM. Async I/O, circular buffers, typed arrays, explicit GC. One process, one purpose, minimal footprint.
3. **📈 Asymmetric upside** — small, patient grid orders harvesting volatility. Many small wins, strictly bounded losses. Multiple strategies for multiple regimes.
4. **🌐 Distribution is resilience** — no single point of failure. Two trading nodes, central coordinator, shared state, automatic failover. The fleet survives node crashes, exchange outages, network partitions.

This is not a get-rich-quick bot. It is an **engineering discipline applied to markets**: start with €100, prove the strategy on paper across a distributed fleet, then — and only then — scale with confidence.

---

## 📜 Project History

| Milestone | Date / Commit | Description |
|-----------|---------------|-------------|
| **🌱 Live Bot (v0)** | pre-repo | Single-file Kraken DOGE/EUR grid bot. Ran live on Raspberry Pi with ~€200 capital for months. Systemd persistence, manual state reload. Proved the concept; exposed the limits of a monolith. |
| **📉 The Binance Collapse** | 2026-06-29 → 07-01 | **The project started dropping beats — and euros.** Denaro's live fleet was fully operational on Binance sub-accounts… until it wasn't. Binance silently revoked trading permissions on EU sub-account API keys. Bots starved, positions stranded, ~€206 frozen mid-grid. Cause: **MiCA enforcement on July 1st, 2026**. Lesson: **exchange risk is real risk**. |
| **🐙 The Kraken Pivot** | 2026-07-01 | Same day: everything converted to EUR on Binance (~€344 recovered), withdrawn via SEPA, infrastructure re-pointed at **Kraken** — MiCA-compliant, EU-licensed, superior API. Binance and Bybit permanently deprecated. |
| **🏗️ p1 — Modular Scaffold** | `504172c` | Full refactor. Monolith split into 5 clean modules: `engine`, `exchange`, `strategy`, `state`, `risk`. Architecture inspired by Freqtrade, Hummingbot, OctoBot, Jesse. |
| **🔄 p2 — Paper Runner** | `0b2e0f3` | `PaperEngine` main loop: configurable tick interval, grid strategy wiring, portfolio state persistence to JSON. Entry point `run_paper.py`. |
| **🩹 p2.1 — Kraken Sandbox Fix** | `054b957` | Kraken's CCXT client has no `sandbox` attribute. Exchange adapter catches error and falls back to live API readonly. |
| **🛡️ p2.2 — Guard + Graceful Shutdown** | `015627a` | `getattr` guard against `AttributeError`; SIGINT/SIGTERM handler stops engine, saves portfolio, exits cleanly. |
| **🧹 p3 — Infrastructure Cleanup** | — | Removal of **all** legacy Denaro services, cron jobs, system-wide units, timers, binaries and orphaned processes across both nodes. One service survives: `denaro-paper`. |
| **🧪 p4 — Paper Trading Test Suite** | current | 33 unit + integration tests. Engine tick, risk gates, grid strategy, trailing stop, paper exchange fill/orderbook, backtest runner. |
| **🌐 DDNS + Multi-Node Automation** | 2026-07-30 | **No-IP DDNS deployed on both trading nodes** (`nuvola` → `sgrivett.ddns.net`, `MARCODG1` → `mgrivett.ddns.net`). Systemd timer (10 min) + secure credential file. |
| **🔑 API Key Rotation & Validation** | 2026-07-31 | **Kraken key rotated** (post-MiCA). New key validated: trading permissions ✅. **MEXC keys validated on both nodes**. Bybit deprecated (MiCA), removed. |
| **💸 The 115 USDT Mystery** | 2026-07-22 | **115.74 USDT (ERC20) sent to Kraken — never arrived. Not on-chain.** Kraken API lacks funding perms. Support ticket opened with TxID, proof of non-arrival. |
| **🤖 Airdrop Farm v1** | 2026-07-31 | **Autonomous multi-strategy airdrop farmer** deployed on nuvola (systemd). 20 wallets, 4 strategies, €250 virtual/€100 real. Poisson scheduler, circuit breaker, idempotent. Zabbix monitoring on MC2. |
| **🔄 Full Reboot & Verification** | 2026-07-31 | Both nodes rebooted for kernel updates. Post-reboot: all systemd services healthy. |
| **⚡ ShadowGrid v2.0 & Multi-Bot Fleet** | 2026-08-07 | **Complete transformation into a 14-bot Adaptive Fleet across 2 exchanges.** ATR-adaptive spread, ADX/RSI momentum filter, 15% DD circuit breaker, 5% daily loss limit, 6% dynamic re-anchoring. Fleet supervisor, pair scanner, rebalancer. 14 bots total, 200€ paper capital. |
| **🛡️ ShadowGrid v2.1 — Risk & Alerts** | 2026-08-08 | **Portfolio-level risk management + multi-channel alerts.** Risk Manager: correlation matrix, exposure limits, volatility targeting, risk parity allocation, multi-layer kill switch. Alert System: Telegram/Email/Log channels with deduplication. Dynamic pair selection with regime detection, performance decay scoring, correlation filtering, weekly auto-rotation. |
| **🏗️ ShadowGrid v2.2 — Unified Architecture** | 2026-08-09 | **Unification of ShadowGrid v2 (production features) + neo (async performance).** New `alpha_omega` package with UnifiedTradingEngine, DistributedFleetCoordinator, DistributedPairScanner, PortfolioRiskManager. ZeroMQ Pub/Sub for market data, Redis Streams for shared state, Raft leader election. 24 bots (12/node), 200€ paper capital. All audit issues resolved. |
| **🚀 GO-LIVE — Live Trading with Real Capital** | **2026-08-10 22:42:30 CEST** | **€101 real capital deployed across 2 nodes × 2 exchanges.** OKX EEA endpoint (`eea.okx.com`) validated on both nodes with IP whitelist. Kraken live keys validated with full trading permissions. 24 bots operational (12/node). Risk management armed: 15% DD circuit breaker, 5% daily loss limit, 20% portfolio kill switch. Paper=Live infrastructure parity achieved via sandbox/testnet support. |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      ALPHA-OMEGA TRADING SYSTEM                              │
└─────────────────────────────────────────────────────────────────────────────┘

           ┌────────────────┐         ┌──────────────┐         ┌──────────────┐
           │     mc2      │◄───────►│    nuvola    │◄───────►│  MARCODG1    │
           │  (Home/DB)   │  ZeroMQ │  (Primary)   │  ZeroMQ │ (Secondary)  │
           └──────┬───────┘         └──────┬───────┘         └──────┬───────┘
                  │                        │                        │
                  │         ┌──────────────┴──────────────┐        │
                  │         │        Redis Cluster        │        │
                  │         │   (Shared State + Streams)  │        │
                  │         └──────────────┬──────────────┘        │
                  │                        │                        │
                  ▼                        ▼                        ▼
         ┌───────────────┐         ┌───────────────┐         ┌───────────────┐
         │ TimescaleDB   │         │  Kraken EUR   │         │  Kraken EUR   │
         │ Historical    │         │  OKX USDT     │         │  OKX USDT     │
         │ Zabbix/Alert  │         │  12 Bots      │         │  12 Bots      │
         └───────────────┘         └───────────────┘         └───────────────┘
 ```

## 🔬 Paper=Live Infrastructure Parity — Sandbox/Testnet Support

> **The paper trading environment now uses real exchange sandbox/testnet endpoints, making the infrastructure 100% identical to live mode.**

### Supported Exchanges

| Exchange | Sandbox/Testnet | REST Endpoint | WS Endpoint | Auth |
|----------|-----------------|---------------|-------------|------|
| **Kraken** | Spot Pilot | `https://api.pilot.kraken.com` | `wss://ws.pilot.kraken.com` | HMAC-SHA512 |
| **OKX** | Demo Trading | `https://www.okx.com` (same) | `wss://ws.okx.com:8443/api/v5/market` | HMAC-SHA256 + `x-simulated-trading: 1` |
| **OKX EEA Live** | — | `https://eea.okx.com` | `wss://ws.okx.com:8443/api/v5/market` | HMAC-SHA256 + Passphrase |

---

## 🧪 Testing

```bash
source venv/bin/activate
pip install pytest pytest-asyncio

# All tests
python -m pytest tests/ -v

# Unit tests
python -m pytest tests/unit/ -v

# Integration tests
python -m pytest tests/integration/ -v

# Chaos engineering tests (requires running cluster)
python -m pytest tests/chaos/ -v
```

**Test Coverage Targets:**
- Unit: >90% (core buffers, state, risk, strategies)
- Integration: Market data → signal → order → fill → state sync
- Chaos: Node crash, network partition, exchange API down, Redis split-brain

---

## 📈 Deployment

### Systemd Services (Bare Metal - Current Production)

**Fleet Coordinator** (`~/.config/systemd/user/shadowgrid-fleet.service`):

```ini
[Unit]
Description=ShadowGrid Fleet Orchestrator (Multi-Bot Grid)
After=network-online.target redis.service
Wants=network-online.target redis.service

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

**Deploy Commands:**

```bash
# On each trading node (nuvola, MARCODG1)
git clone https://github.com/grivetto/alpha-omega-trading.git /home/sergio/denaro
cd /home/sergio/denaro
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Configure .env files for LIVE MODE
# LIVE_MODE=true, USE_SANDBOX=false, CAPITAL=25.0

# Install systemd services
sudo cp systemd/shadowgrid@.service /etc/systemd/system/
sudo systemctl daemon-reload

# Start fleet (via fleet coordinator)
systemctl --user enable --now shadowgrid-fleet

# Health checks
curl http://localhost:8900/health | python3 -m json.tool
journalctl --user -u shadowgrid-fleet -f
```

### mc2 Coordinator Deployment

```bash
# On mc2
git clone https://github.com/grivetto/alpha-omega-trading.git
cd alpha-omega-trading
cp docker/.env.example docker/.env
docker compose -f docker/docker-compose.mc2.yml up -d

# Verify
curl http://localhost:3000  # Grafana
curl http://localhost:8080  # Zabbix
```

---

## 📊 Monitoring & Observability

### Key Metrics

| Category | Metrics |
|----------|---------|
| **Trading** | PnL (realized/unrealized), win rate, avg trade duration, Sharpe, Sortino, max DD |
| **Risk** | Portfolio DD, daily loss, exposure per base, correlation matrix, kill switch status |
| **System** | CPU, RAM, disk, FD count, network I/O, GC pauses, safe mode level |
| **Exchange** | API latency (p50/p95/p99), rate limit usage, order fill rate, slippage |
| **Fleet** | Bot count (running/error/draining), capital allocation, pair performance |

### Zabbix Integration
- **Templates**: `AlphaOmega Trading Node`, `AlphaOmega Fleet`, `AlphaOmega Coordinator`
- **Items**: All metrics above via HTTP `/metrics` endpoint (15 trapper items + daily cron)
- **Triggers**: DD > 10% (warning), DD > 15% (critical), bot down > 60s, safe mode >= SAFE, etc.
- **Actions**: Telegram/Email notifications, auto-restart via fleet coordinator

### Grafana Dashboards
1. **Fleet Overview**: Total equity, PnL, bot status, risk metrics, pair heatmap
2. **Node Deep Dive**: Per-bot performance, order book visualization, grid levels
3. **Risk Dashboard**: Correlation heatmap, exposure breakdown, DD waterfall, volatility regimes
4. **System Health**: Resource usage, latency percentiles, error rates, GC pauses

### Telegram Alerts
Configure `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` for real-time:
- 🚨 CRITICAL: Portfolio DD > 15%, Daily loss > 5%, Kill switch, Bot repeatedly crashing
- ⚠️ WARNING: DD > 10%, Daily loss > 3.5%, Bot restart, Stuck bot, Volatility spike, Correlation breach
- ℹ️ INFO: Pair rotation, Volatility regime change, New pair added

---

## 🧘 Principles

- **Modular architecture** — loosely coupled, easy to swap exchange, strategy, or risk model
- **Zero real risk** — circuit breakers at every layer: bot, portfolio, fleet
- **Deterministic backtesting** — same data, same results, every time
- **Transparent execution** — every order and fill logged to JSONL + Redis Streams
- **Production-ready** — systemd/Docker, graceful shutdown, state persistence, hot reload
- **Adaptive intelligence** — ATR-based spread, momentum filtering, regime detection, dynamic capital allocation
- **Distributed by design** — no single point of failure, automatic failover, shared state
- **Security first** — CURVE encryption, TLS everywhere, Vault secrets, 127.0.0.1 bind

---

## 🗺️ Roadmap

### ✅ Completed
- [x] p1 — Modular scaffold (engine, exchange, strategy, state, risk) — `neo/*`
- [x] p2 — Paper runner (live tick loop, grid strategy, portfolio persistence)
- [x] p3 — Infrastructure cleanup (deprecated services removed, single systemd unit)
- [x] p4 — Test suite (33 tests, engine integration, risk gates, backtest runner)
- [x] p4.5 — DDNS + multi-node automation (No-IP, systemd timers, secure creds)
- [x] p4.6 — API key rotation & validation (Kraken/MEXC, perms audit, Bybit deprecated)
- [x] p4.7 — Airdrop Farm v1 (20 wallets, 4 strategies, live on nuvola)
- [x] **⚡ ShadowGrid v2.0 & 14-Bot Fleet** — ATR-adaptive grid, ADX/RSI filter, fleet supervisor, pair scanner, rebalancer
- [x] **🛡️ ShadowGrid v2.1 — Risk & Alerts** — Portfolio risk manager, multi-channel alerts, dynamic pair selection
- [x] **🏗️ ShadowGrid v2.2 — Unified Architecture** — alpha_omega package, ZeroMQ/Redis, Raft, 24 bots
- [x] **🔍 Audit Fixes** — Legacy cleanup, health endpoint security, swap fix, config drift resolution
- [x] **🔬 Sandbox/Testnet Support** — Paper=Live infrastructure parity with Kraken Pilot + OKX Demo
- [x] **🚀 GO-LIVE — Live Trading** — €101 real capital, 24 bots operational, risk management armed

### 🎯 Next Phases

- [ ] **Phase 5 — Live Validation** (Week 1-4)
  - [ ] Live validation with €100 capital (1 month)
  - [ ] Scale to €1000 capital
  - [ ] Continuous optimization based on live metrics

- [x] **Phase 6 — Advanced Strategies** (Month 2) — **COMPLETED**
  - [x] Mean Reversion strategy (Bollinger + RSI) — `alpha_omega.strategies.mean_reversion`
  - [x] Momentum strategy (Donchian breakout + volume) — `alpha_omega.strategies.momentum`
  - [x] Scalp strategy (EMA crossover + volume) — `alpha_omega.strategies.scalp`
  - [x] DCA strategy (configurable entries, trailing) — `alpha_omega.strategies.dca`
  - [x] Grid strategy (ATR-adaptive + hybrid mode) — `alpha_omega.strategies.grid`
  - [x] Strategy Selector (regime-based switching) — `alpha_omega.strategies.selector`
  - [ ] Statistical Arbitrage (pair correlation + cointegration)
  - [ ] Funding Rate Arbitrage (perp vs spot)

- [x] **Phase 7 — Monitoring & Alerts** (Month 2) — **COMPLETED**
  - [x] Multi-channel Alert System (Telegram/Email/Zabbix/Log) — `alpha_omega.alerts.system`
  - [x] Alert Channels with deduplication — `alpha_omega.alerts.channels`
  - [x] Jinja2 Alert Templates — `alpha_omega.alerts.templates`
  - [x] Health Server with unified schema — `alpha_omega.monitoring.health`
  - [x] Prometheus/Zabbix Metrics Collector — `alpha_omega.monitoring.metrics`
  - [x] Resource Monitor with SafeMode — `alpha_omega.monitoring.resource`
  - [ ] ML-enhanced pair selection (XGBoost/LightGBM on regime features)
  - [ ] Regime detection with HMM/transformer
  - [ ] Dynamic spread optimization with RL
  - [ ] Anomaly detection for exchange issues

- [ ] **Phase 8 — Production Hardening** (Month 3-4)
  - [ ] HashiCorp Vault integration for secrets
  - [ ] WireGuard mesh for inter-node comms
  - [ ] Chaos engineering automation (Litmus/Gremlin)
  - [ ] Disaster recovery runbooks + drills
  - [ ] Multi-region deployment (EU + US)

- [ ] **Phase 9 — Scale** (Month 6)
  - [ ] 50+ bots across 3+ nodes
  - [ ] 5+ exchanges (Kraken, OKX, Binance.US, Coinbase, Bybit)
  - [ ] €10k+ capital under management
  - [ ] Institutional-grade reporting & compliance

---

## 📜 License

[The Unlicense](http://unlicense.org/) — public domain. Do whatever you want.

---

## 🙏 Acknowledgments

- **CCXT** — Unified exchange interface
- **Freqtrade** — Architecture inspiration (strategy callbacks, dry-run, backtesting)
- **Hummingbot** — Clock/loop architecture
- **OctoBot** — Grid trading mode
- **Jesse** — Broker abstraction
- **ZeroMQ** — Ultra-low latency messaging
- **Redis** — Streams for persistent shared state
- **TimescaleDB** — Time-series data at scale
- **Zabbix + Grafana** — Observability stack
- **TA-Lib / Pandas** — Quantitative foundations

---

*Built with engineering discipline. Validated on paper. Ready for profit.* ⚡
