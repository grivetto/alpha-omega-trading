<div align="center">

# ⚡ ALPHA-OMEGA TRADING ⚡

### *The ultimate distributed algorithmic trading system — from paper to profit, across three nodes, with zero compromises.*

[![License: Unlicense](https://img.shields.io/badge/license-Unlicense-blue.svg)](http://unlicense.org/)
[![Python](https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![CCXT](https://img.shields.io/badge/exchange-CCXT%20Pro%20%2F%20Kraken%20%7C%20OKX-5741D9?logo=bitcoin&logoColor=white)](https://github.com/ccxt/ccxt)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20systemd%20%7C%20Docker-FCC624?logo=linux&logoColor=black)](https://www.freedesktop.org/wiki/Software/systemd/)
[![Status](https://img.shields.io/badge/status-24%20bots%20paper%20trading%20%7C%20ShadowGrid%20v2.2-success)](https://github.com/grivetto/alpha-omega-trading)
[![Architecture](https://img.shields.io/badge/architecture-distributed%2C%20async%2C%20fleet%20orchestrated-brightgreen)]()
[![Monitoring](https://img.shields.io/badge/monitoring-Zabbix%20%2B%20Grafana%20%2B%20Telegram-FF6F00?logo=grafana&logoColor=white)]()

**Distributed, async, multi-strategy trading fleet orchestrated across three machines. Real-time market data via ZeroMQ, shared state via Redis Streams, portfolio risk management, dynamic pair selection — all paper-validated, live-ready.**

[Architecture](#-architecture) · [Philosophy](#-philosophy) · [Quick Start](#-quick-start) · [Deployment](#-deployment) · [Monitoring](#-monitoring--observability) · [Roadmap](#-roadmap)

</div>

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
| **🏗️ ShadowGrid v2.2 — Unified Architecture** | 2026-08-09 | **Unification of ShadowGrid v2 (production features) + neo (async performance).** New `alpha_omega` package with UnifiedTradingEngine, DistributedFleetCoordinator, DistributedPairScanner, PortfolioRiskManager. ZeroMQ Pub/Sub for market data, Redis Streams for shared state, Raft leader election. 24 bots (12/node), 200€ paper capital. All audit issues resolved: legacy processes killed, health endpoints secured, swap fixed, config drift eliminated. |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      ALPHA-OMEGA TRADING SYSTEM                              │
└─────────────────────────────────────────────────────────────────────────────┘

          ┌──────────────┐         ┌──────────────┐         ┌──────────────┐
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

### Machine Roles

| Machine | Role | Services |
|---------|------|----------|
| **mc2** | Central Coordinator | PostgreSQL/TimescaleDB, Redis Cluster, Zabbix Server, Hermes Message Bus, Fleet Coordinator API, Historical Data Archive |
| **nuvola** | Primary Trading Node | 12 ShadowGrid bots (6 Kraken EUR + 6 OKX USDT), Local Redis, ZeroMQ Pub/Sub, Health API |
| **MARCODG1** | Secondary Trading Node | 12 ShadowGrid bots (6 Kraken EUR + 6 OKX USDT), Local Redis, ZeroMQ Pub/Sub, Health API |

### Core Components (alpha_omega package)

| Component | Module | Description |
|-----------|--------|-------------|
| **UnifiedTradingEngine** | `alpha_omega.core.engine` | Merges ShadowGrid v2 + neo: async I/O, multiple strategies (Grid, DCA, Scalp, MeanReversion, Momentum, Arbitrage), paper/live mode, portfolio risk, Redis Streams + SQLite state, hot-reload |
| **DistributedFleetCoordinator** | `alpha_omega.fleet.coordinator` | Raft leader election, pair lifecycle (STARTING→RUNNING→DRAINING→STOPPED), hot reload via SIGHUP + ZeroMQ config broadcast, graceful rotation, kill switch monitoring, alert integration |
| **DistributedPairScanner** | `alpha_omega.scanner.pair_scanner` | Runs on mc2/leader, scans Kraken EUR + OKX USDT, regime detection (Range/Trend), performance decay scoring, correlation filtering (max 0.7), volatility regime (ATR ratio), weekly auto-rotation |
| **PortfolioRiskManager** | `alpha_omega.risk.manager` | Portfolio DD (20%), daily loss (5%), exposure per base (30%), correlation limit (0.7), max positions per base (2), volatility targeting, risk parity allocation, multi-layer kill switch (file + portfolio DD + daily loss + manual) |
| **AlertSystem** | `alpha_omega.alerts.system` | Multi-channel: Log (always), Telegram (HTML, rate-limited), Email (SMTP), Zabbix (trapper items). Alerts: DD, daily loss, bot crash/restart, stuck, kill switch, pair rotation, volatility regime, exposure, correlation breach |
| **ExchangeAdapter** | `alpha_omega.core.exchange` | Async aiohttp + WebSocket multiplexing, token bucket rate limiter with backoff, connection pooling (max 10 conn, 5/host), automatic reconnection |
| **Circular Buffers** | `alpha_omega.core.buffers` | OhlcvBuffer, TickBuffer with typed arrays (float32), zero-copy stats, explicit GC management |
| **StateStore** | `alpha_omega.core.state` | SQLite WAL + write queue + Redis Streams consumer groups, exactly-once processing |
| **Strategy Classes** | `alpha_omega.strategies.*` | Grid (ATR-adaptive), DCA, Scalp, MeanReversion, Momentum, Arbitrage — all with `Signal` output, regime-aware |
| **StrategySelector** | `alpha_omega.strategies.selector` | Regime-based switching: ATR + momentum + trend strength → Grid/DCA/Scalp/Cooldown, min 5min between switches |
| **ResourceMonitor** | `alpha_omega.monitoring.resource` | Async resource monitor: RAM/CPU/FD, SafeMode levels (NORMAL/CAUTION/SAFE/EMERGENCY), heartbeat to `/tmp/denaro-neo.health` |
| **DCA Strategy** | `alpha_omega.strategies.dca` | Dollar-Cost Averaging with configurable entries, spacing, take-profit, trailing stop, max drawdown per position |
| **Scalp Strategy** | `alpha_omega.strategies.scalp` | Fast scalping for trending markets with EMA crossover, volume confirmation, tight stops, max hold time |
| **Mean Reversion** | `alpha_omega.strategies.mean_reversion` | Bollinger Bands + RSI oversold/overbought, middle band exit, configurable thresholds |
| **Momentum Strategy** | `alpha_omega.strategies.momentum` | Donchian channel breakouts with ADX filter, trailing stops, volume confirmation |
| **Grid Strategy** | `alpha_omega.strategies.grid` | ATR-adaptive grid with dynamic re-anchoring, momentum filter, hybrid mode for trending markets |

---

## 🌐 Infrastructure Topology

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           MC2 (Home - Coordinator)                     │
│  ┌─────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐  │
│  │ TimescaleDB │  │ Redis Cluster   │  │ Zabbix Server + Grafana     │  │
│  │ (Historical)│  │ (3 masters)     │  │ (Templates + Dashboards)    │  │
│  └─────────────┘  └─────────────────┘  └─────────────────────────────┘  │
│  ┌─────────────────┐  ┌─────────────────────────────┐                  │
│  │ Hermes Agent    │  │ Fleet Coordinator API       │                  │
│  │ (this session)  │  │ (Leader election, config)   │                  │
│  └─────────────────┘  └─────────────────────────────┘                  │
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
          │ (12 bots, :8900)    │           │ (12 bots, :8900)    │
          │ airdrop-farm-nuvola │           │ MEXC SHADOW (SOL)   │
          │ (live, 20 wallets)  │           │ DDNS timer 10m      │
          │ DDNS timer 10m      │           │ Kraken: nVN31AX...  │
          │ Kraken: 1t3Jpcv...  │           │ MEXC: mx0vglZz...   │
          │ MEXC: mx0vgl1Tr...  │           │ Swap: 4GB           │
          │ OKX: f28aa65d...    │           │ OKX: f28aa65d...    │
          │ Swap: 4GB           │           │                     │
          └─────────────────────┘           └─────────────────────┘
```

### Communication Layer

**ZeroMQ Pub/Sub (Market Data)** — Ultra-low latency:
- `tcp://*:5555` — Market data (ticker, OHLCV)
- `tcp://*:5556` — Orders (placement, fills, cancellations)
- `tcp://*:5557` — Signals (strategy signals for coordination)
- `tcp://*:5558` — Risk alerts
- `tcp://*:5559` — Fleet config updates
- CURVE encryption with pre-shared keys

**Redis Streams (Shared State)** — Persistent, exactly-once:
- `trades` — Completed trades (30d retention)
- `positions` — Open positions (7d)
- `orders` — Order lifecycle (7d)
- `equity` — Equity curves (90d)
- `risk.metrics` — Portfolio risk (30d)
- `health.metrics` — Node health (7d)
- Consumer groups per service for exactly-once processing

**HTTP/REST (Control Plane)** — Bind 127.0.0.1 only:
- `GET /health` — Unified health check
- `GET /risk` — Detailed risk status
- `GET /fleet` — Fleet-wide status
- `POST /fleet/reload` — Hot reload trigger
- `POST /fleet/rotate` — Pair rotation trigger
- `POST /kill` — Kill switch activation
- `GET /metrics` — Prometheus/Zabbix metrics

---

## 📦 Docker

### mc2 (Coordinator)
```yaml
# docker/docker-compose.mc2.yml
services:
  postgres:
    image: timescale/timescaledb:latest-pg16
    volumes: [timeseries:/var/lib/postgresql/data]
    environment:
      - POSTGRES_DB=alpha_omega
  redis:
    image: redis:7-alpine
    command: redis-server --cluster-enabled yes --port 6379
  zabbix-server:
    image: zabbix/zabbix-server-pgsql:alpine-6.4
  zabbix-web:
    image: zabbix/zabbix-web-nginx-pgsql:alpine-6.4
  coordinator:
    build: .
    command: python -m alpha_omega.fleet.coordinator
    environment:
      - NODE_ROLE=coordinator
      - REDIS_URL=redis://redis:6379
      - PG_DSN=postgresql://postgres@postgres/alpha_omega
  grafana:
    image: grafana/grafana:latest
```

### nuvola / MARCODG1 (Trading Nodes)
```yaml
# docker/docker-compose.trading.yml
services:
  redis:
    image: redis:7-alpine
  trading-engine:
    build: .
    command: python -m alpha_omega.core.engine
    environment:
      - NODE_ROLE=trading
      - EXCHANGE=kraken
      - SYMBOL=SOL/EUR
      - CAPITAL=50
      - LIVE_MODE=0
      - HEALTH_PORT=8912
      - REDIS_URL=redis://redis:6379
      - ZMQ_PUB=tcp://*:5555
      - ZMQ_PEER=tcp://MARCODG1:5555
    deploy:
      replicas: 12
  fleet-coordinator:
    build: .
    command: python -m alpha_omega.fleet.coordinator
    environment:
      - NODE_ROLE=fleet_coordinator
      - FLEET_CONFIG=/config/fleet_config_nuvola.json
```

```bash
# On mc2
cp docker/.env.example docker/.env
docker compose -f docker/docker-compose.mc2.yml up -d

# On nuvola / MARCODG1
docker compose -f docker/docker-compose.trading.yml up -d
```

---

## 🚀 Quick Start

### Alpha-Omega Trading (Unified Engine - Recommended)

```bash
# 1. Clone
cd /home/sergio/denaro  # or your preferred location
git clone https://github.com/grivetto/alpha-omega-trading.git
cd alpha-omega-trading

# 2. Virtual environment
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 3. Configure environment (per bot)
# See config/.env.example for all variables
export EXCHANGE=kraken
export SYMBOL=SOL/EUR
export CAPITAL=50
export LIVE_MODE=0
export HEALTH_PORT=8912
# ... API keys from secret manager

# 4. Run single bot (paper)
python -m alpha_omega.core.engine

# 5. Run fleet (via fleet coordinator)
python -m alpha_omega.fleet.coordinator
```

### ShadowGrid v2.2 Fleet (Legacy - Still Operational)

```bash
# Quick fleet start with existing shadowgrid_fleet.py
python3 shadowgrid_fleet.py

# Health dashboard
curl http://localhost:8900/health | python3 -m json.tool
```

### Docker Infrastructure

```bash
cp docker/.env.example docker/.env
docker compose -f docker/docker-compose.yml up -d
```

### Live Output (Unified Engine)

```
=== Alpha-Omega Trading Engine v2.2 ===
Node: nuvola | Role: trading
Exchange: kraken | Symbol: SOL/EUR
Capital: 50.00 EUR | Mode: PAPER
Strategy: Grid (ATR-adaptive) | Hybrid: False
Risk: Portfolio DD 20% | Daily Loss 5% | Exposure/Base 30%
Buffers: OHLCV=100 | Tick=1000 | Cooldown=30s
ZeroMQ: Pub=5555 | Sub=MARCODG1:5555
Redis: redis://localhost:6379
Health: 127.0.0.1:8912
=====================================
[2026-08-09 02:05:12] price=0.888880 eq=52.07 spread=0.20% RSI=36.3 ADX=6.2 regime=range strategy=grid orders=12 trades=30
[2026-08-09 02:05:42] price=0.890120 eq=52.15 spread=0.19% RSI=38.1 ADX=5.8 regime=range strategy=grid orders=12 trades=31  fill BUY @ 0.8895
```

---

## 🎛️ Configuration

### Unified Engine Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `EXCHANGE` | `kraken` | Exchange: `kraken`  `okx` |
| `SYMBOL` | `DOGE/EUR` | Trading pair (e.g., `SOL/EUR`, `BICO/USDT`) |
| `CAPITAL` | `50` | Paper capital per bot in EUR/USDT |
| `LIVE_MODE` | `0` | Set to `1` for live trading |
| `HEALTH_PORT` | `8911` | HTTP health endpoint port (127.0.0.1 only) |
| `ZMQ_PUB_PORT` | `5555` | ZeroMQ publisher port |
| `ZMQ_PEER` | `tcp://peer:5555` | Peer ZeroMQ address |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection URL |
| `DB_PATH` | `denaro_neo.db` | SQLite database path |
| `STATE_FILE` | `/tmp/shadowgrid_state.json` | Local state persistence |
| `LOG_FILE` | `/tmp/shadowgrid.log` | Log file path |
| `LOG_LEVEL` | `INFO` | Logging level |
| `COOLDOWN_SEC` | `30` | Seconds between strategy cycles |
| `MAX_OPEN_ORDERS` | `10` | Max concurrent open orders |
| `OHLCV_WINDOW` | `100` | Circular buffer size for OHLCV |
| `TICK_WINDOW` | `1000` | Circular buffer size for ticks |

### Grid Strategy Parameters

| Variable | Default | Description |
|----------|---------|-------------|
| `GRID_LEVELS` | `5` | Number of grid levels per side |
| `BASE_SPREAD_PCT` | `0.5` | Base spread % (overridden by ATR-adaptive) |
| `PER_LEVEL` | `0.2` | Fraction of capital per order (20%) |
| `ATR_SPREAD_MULTIPLIER` | `0.7` | ATR × multiplier for dynamic spread |
| `MIN_SPREAD_PCT` | `0.2` | Minimum spread floor % |
| `MAX_SPREAD_PCT` | `2.5` | Maximum spread ceiling % |
| `DRIFT_PCT` | `6.0` | Grid re-anchor drift threshold % |

### Risk Parameters

| Variable | Default | Description |
|----------|---------|-------------|
| `USE_MOMENTUM_FILTER` | `1` | Enable ADX/RSI momentum filter |
| `MAX_DRAWDOWN_PCT` | `0.15` | Hard stop at 15% max drawdown (bot-level) |
| `MAX_DAILY_LOSS_PCT` | `0.05` | Freeze at 5% daily loss (bot-level) |
| `HYBRID_MODE` | `0` | Enable directional scalper in trending markets |
| `RISK_MANAGER_ENABLED` | `1` | Enable portfolio-level risk manager |
| `MAX_PORTFOLIO_DD` | `0.20` | Portfolio drawdown limit (kill switch) |
| `MAX_EXPOSURE_PER_BASE` | `0.30` | Max exposure per base currency |
| `MAX_CORRELATION` | `0.7` | Max correlation between positions |
| `MAX_POSITIONS_PER_BASE` | `2` | Max positions per base currency |
| `VOLATILITY_TARGETING` | `1` | Enable ATR-based volatility regime detection |

### Alert Parameters

| Variable | Default | Description |
|----------|---------|-------------|
| `ALERT_ENABLED` | `1` | Enable alert system |
| `TELEGRAM_BOT_TOKEN` | `` | Telegram bot token for alerts |
| `TELEGRAM_CHAT_ID` | `` | Telegram chat ID for alerts |
| `SMTP_HOST` | `` | SMTP server for email alerts |
| `SMTP_PORT` | `587` | SMTP port |
| `SMTP_USERNAME` | `` | SMTP username |
| `SMTP_PASSWORD` | `` | SMTP password |
| `SMTP_FROM` | `` | From address |
| `SMTP_TO` | `` | Comma-separated to addresses |

### Fleet Config (`fleet_config.json`) — Versioned, Generated by Scanner

```json
{
  "version": "2026-08-09T00:00:00Z",
  "total_fleet_capital": 200.0,
  "capital_per_exchange": {"kraken": 100.0, "okx": 100.0},
  "pairs": [
    {"symbol": "SOL/EUR", "port": 8912, "capital": 16.67, "exchange": "kraken",
     "regime": "range", "suitability": "grid", "atr_pct": 2.5, "adx": 18.5},
    {"symbol": "DOGE/EUR", "port": 8913, "capital": 16.67, "exchange": "kraken",
     "regime": "range", "suitability": "grid", "atr_pct": 1.8, "adx": 22.1}
  ],
  "okx_pairs": [
    {"symbol": "BICO/USDT", "port": 8930, "capital": 16.67, "exchange": "okx",
     "regime": "range", "suitability": "grid", "atr_pct": 1.5, "adx": 15.2},
    {"symbol": "GRVT/USDT", "port": 8931, "capital": 16.67, "exchange": "okx",
     "regime": "range", "suitability": "grid", "atr_pct": 2.1, "adx": 24.1}
  ],
  "risk_params": {
    "max_portfolio_dd": 0.20,
    "max_daily_loss": 0.05,
    "max_exposure_per_base": 0.30,
    "max_correlation": 0.7,
    "max_positions_per_base": 2
  }
}
```

---

## 📁 Project Structure

```
alpha-omega-trading/
├── alpha_omega/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── engine.py              # UnifiedTradingEngine
│   │   ├── exchange.py            # ExchangeAdapter (async, WS multiplexing)
│   │   ├── buffers.py             # OhlcvBuffer, TickBuffer, CircularBuffer
│   │   ├── state.py               # StateStore (Redis Streams + SQLite WAL)
│   │   ├── config.py              # Config dataclasses + env loading
│   │   └── types.py               # Shared typed dataclasses (__slots__)
│   ├── strategies/
│   │   ├── __init__.py
│   │   ├── base.py                # BaseStrategy + Signal dataclass
│   │   ├── grid.py                # GridStrategy (ATR-adaptive, HYBRID mode)
│   │   ├── dca.py                 # DCAStrategy
│   │   ├── scalp.py               # ScalpStrategy
│   │   ├── mean_reversion.py      # MeanReversionStrategy
│   │   ├── momentum.py            # MomentumStrategy
│   │   └── selector.py            # StrategySelector (regime-based)
│   ├── risk/
│   │   ├── __init__.py
│   │   ├── manager.py             # PortfolioRiskManager
│   │   ├── correlation.py         # Correlation matrix
│   │   ├── volatility.py          # Volatility regime detection
│   │   └── kill_switch.py         # Multi-layer kill switch
│   ├── fleet/
│   │   ├── __init__.py
│   │   ├── coordinator.py         # DistributedFleetCoordinator (Raft)
│   │   ├── bot_instance.py        # BotInstance with lifecycle
│   │   ├── raft.py                # Leader election
│   │   └── hot_reload.py          # SIGHUP + ZeroMQ config sync
│   ├── scanner/
│   │   ├── __init__.py
│   │   ├── pair_scanner.py        # DistributedPairScanner
│   │   ├── regime.py              # Market regime detection
│   │   ├── performance.py         # Performance decay scoring
│   │   └── correlation.py         # Pair correlation filtering
│   ├── alerts/
│   │   ├── __init__.py
│   │   ├── system.py              # AlertSystem
│   │   ├── channels.py            # Telegram/Email/Zabbix/Log channels
│   │   └── templates.py           # Alert message templates
│   └── monitoring/
│       ├── __init__.py
│       ├── health.py              # Health HTTP server (127.0.0.1)
│       ├── metrics.py             # Prometheus/Zabbix metrics
│       └── resource.py            # ResourceMonitor (SafeMode)
├── config/
│   ├── fleet_config_nuvola.json
│   ├── fleet_config_marcodg1.json
│   └── scanner_config.yaml
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.mc2.yml
│   ├── docker-compose.trading.yml
│   └── .env.example
├── systemd/
│   ├── shadowgrid@.service
│   └── fleet-coordinator.service
├── tests/
│   ├── unit/
│   ├── integration/
│   └── chaos/
├── scripts/
│   ├── deploy.sh
│   ├── migrate_state.py
│   └── benchmark.py
├── legacy/
│   ├── shadowgrid_v2.py           # ShadowGrid v2.2 (production)
│   ├── shadowgrid_fleet.py        # Fleet supervisor v2.2
│   ├── pair_scanner.py            # Pair scanner v2.2
│   ├── fleet_rebalancer.py        # Rebalancer v2.2
│   ├── risk_manager.py            # Risk manager v2.2
│   ├── alert_system.py            # Alert system v2.2
│   ├── migrate_v1_to_v2.py        # v1→v2 state migration
│   └── denaro/                    # Original Denaro (p1-p4)
├── neo/                           # Modular scaffold (p1)
├── enhanced/                      # Health & dashboard
├── airdrop-farm/                  # Multi-strategy airdrop farmer
├── ARCHITECTURE.md                # This architecture spec
├── requirements.txt
├── pyproject.toml
└── README.md
```

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

**Per-Bot Service Template** (`/etc/systemd/system/shadowgrid@.service`):

```ini
[Unit]
Description=ShadowGrid Bot %i
After=network-online.target redis.service
Wants=network-online.target redis.service

[Service]
Type=simple
User=sergio
WorkingDirectory=/home/sergio/denaro
EnvironmentFile=/home/sergio/denaro/.env.%i
ExecStart=/home/sergio/denaro/venv/bin/python -m alpha_omega.core.engine
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Deploy Commands:**

```bash
# On each trading node (nuvola, MARCODG1)
git clone https://github.com/grivetto/alpha-omega-trading.git /home/sergio/denaro
cd /home/sergio/denaro
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Configure .env files for each pair
# .env.SOL_EUR, .env.DOGE_EUR, etc.

# Install systemd services
sudo cp systemd/shadowgrid@.service /etc/systemd/system/
sudo systemctl daemon-reload

# Start fleet (via fleet coordinator)
systemctl --user enable --now shadowgrid-fleet

# Or start individual bots
for pair in SOL_EUR DOGE_EUR XRP_EUR ADA_EUR LINK_EUR ETH_EUR; do
    sudo systemctl enable --now shadowgrid@$pair

done

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
- [x] p1 — Modular scaffold (engine, exchange, strategy, state, risk) — *neo/*
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

### 🎯 Next Phases

- [ ] **Phase 5 — Live Validation** (Week 1-4)
  - [ ] Paper trading on both nodes with unified engine (2 weeks)
  - [ ] Live validation with €200 capital (1 month)
  - [ ] Scale to €1000 capital
  - [ ] Continuous optimization based on live metrics

- [ ] **Phase 6 — Advanced Strategies** (Month 2)
  - [ ] Mean Reversion strategy (Bollinger + RSI)
  - [ ] Momentum strategy (breakout + volume confirmation)
  - [ ] Statistical Arbitrage (pair correlation + cointegration)
  - [ ] Funding Rate Arbitrage (perp vs spot)

- [ ] **Phase 7 — ML Enhancement** (Month 3)
  - [ ] ML-enhanced pair selection (XGBoost/LightGBM on regime features)
  - [ ] Regime detection with HMM/transformer
  - [ ] Dynamic spread optimization with RL
  - [ ] Anomaly detection for exchange issues

- [ ] **Phase 8 — Production Hardening** (Month 4)
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