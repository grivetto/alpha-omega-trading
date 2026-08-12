# Alpha-Omega Trading: Ultimate Distributed Trading System Architecture

## 1. System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        ALPHA-OMEGA TRADING SYSTEM                             │
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

---

## 2. Core Components

### 2.1 Unified Trading Engine (`alpha_omega/core/engine.py`)

**Merges**: shadowgrid_v2.py (production features) + neo/core.py (async performance)

```python
class UnifiedTradingEngine:
    """
    Single trading engine supporting:
    - Multiple strategies: Grid, DCA, Scalp, MeanReversion, Momentum, Arbitrage
    - Async I/O with aiohttp + aioredis + ZeroMQ
    - Paper/Live mode per exchange via env config
    - Portfolio-level risk management
    - State persistence to Redis Streams + local SQLite
    - Hot-reload configuration via SIGHUP
    """
    
    # Core loops
    async def market_data_loop()      # 100ms - fetch ticker/OHLCV via WS
    async def strategy_loop()         # cooldown_sec - analyze + signal
    async def execution_loop()        # immediate - place/cancel orders
    async def risk_loop()             # 1s - portfolio risk checks
    async def state_sync_loop()       # 500ms - sync to Redis Streams
    async def health_loop()           # 10s - publish health metrics
```

**Key Features from shadowgrid_v2:**
- ATR-adaptive spread (ATR × multiplier, clamped)
- Momentum filter (ADX < 25, RSI 40-60)
- HYBRID mode: scalper directional in trending markets (ADX > 25)
- Risk: 15% max DD, 5% daily loss, 6% re-anchor drift
- Multi-exchange: Kraken + OKX with passphrase/EEA
- Performance CSV logging, health HTTP endpoint, state persistence

**Key Features from neo:**
- Async I/O with aiohttp ClientSession + WebSocket multiplexing
- Token bucket rate limiter with progressive backoff
- Circular buffers (OhlcvBuffer, TickBuffer) with typed arrays
- StrategySelector with regime-based switching
- StateStore with SQLite WAL + write queue
- ResourceMonitor with SafeMode levels
- Explicit GC management

### 2.2 Fleet Coordinator (`alpha_omega/fleet/coordinator.py`)

**Enhanced shadowgrid_fleet.py with distributed consensus:**

```python
class DistributedFleetCoordinator:
    """
    - Raft-based leader election between nuvola/MARCODG1
    - Pair lifecycle: STARTING → RUNNING → DRAINING → STOPPED
    - Hot reload via SIGHUP + ZeroMQ config broadcast
    - Graceful pair rotation with drain periods
    - Kill switch monitoring (file + Redis + portfolio DD)
    - Alert integration (Telegram/Email/Zabbix)
    """
```

### 2.3 Pair Scanner (`alpha_omega/scanner/pair_scanner.py`)

**Enhanced pair_scanner.py with distributed scanning:**

```python
class DistributedPairScanner:
    """
    - Runs on mc2 (central) OR elected leader
    - Scans Kraken EUR + OKX USDT markets
    - Regime detection: Range (ADX<25) vs Trend (ADX>30)
    - Performance decay scoring: recent(70%) + historical(30%) × win_rate boost
    - Correlation matrix filtering (max 0.7)
    - Volatility regime: ATR ratio vs 30-day median
    - Outputs fleet_config.json for both nodes
    - Weekly auto-rotation (replace worst 50%)
    """
```

### 2.4 Risk Manager (`alpha_omega/risk/risk_manager.py`)

**Enhanced risk_manager.py with portfolio-level controls:**

```python
class PortfolioRiskManager:
    """
    - Portfolio DD limit (20% default) with kill switch
    - Daily loss limit (5% default)
    - Exposure per base currency (30% max)
    - Correlation limit (0.7 max between positions)
    - Max positions per base (2 default)
    - Volatility targeting: ATR regime detection (pause/reduce/expand/normal)
    - Risk parity allocation: inverse volatility weighting
    - Kill switch: file-based + portfolio DD + daily loss + manual
    """
```

### 2.5 Alert System (`alpha_omega/alerts/alert_system.py`)

**Multi-channel with deduplication:**
- LogChannel (always enabled)
- TelegramChannel (HTML, rate-limited)
- EmailChannel (SMTP, rate-limited)
- ZabbixChannel (trapper items for integration)

Alert types: portfolio DD, daily loss, bot crash/restart, bot stuck, kill switch, pair rotation, volatility regime, exposure limit, correlation breach.

---

## 3. Communication Protocols

### 3.1 ZeroMQ Pub-Sub (Market Data Distribution)

**Topology**: Publisher on each trading node → Subscribers on peer + mc2

```
# Publisher (each trading node)
# Binds to: tcp://*:5555 (market data), tcp://*:5556 (orders), tcp://*:5557 (signals)

# Subscriber (peer + mc2)
# Connects to: tcp://nuvola:5555, tcp://MARCODG1:5555
```

**Topics & Message Schemas:**

| Topic | Publisher | Subscribers | Schema |
|-------|-----------|-------------|--------|
| `market.ticker.{exchange}.{symbol}` | Trading node | All nodes + mc2 | `{symbol, bid, ask, last, volume, timestamp}` |
| `market.ohlcv.{exchange}.{symbol}` | Trading node | All nodes + mc2 | `{symbol, timeframe, open, high, low, close, volume, timestamp}` |
| `orders.{exchange}.{symbol}` | Trading node | Peer + mc2 | `{order_id, symbol, side, price, amount, filled, status, timestamp}` |
| `signals.{strategy}.{symbol}` | Trading node | Peer (for coordination) | `{symbol, strategy, action, price, amount, confidence, timestamp}` |
| `risk.alert.{type}` | Risk manager | All nodes + mc2 | `{type, severity, symbol, message, timestamp}` |
| `fleet.config.update` | Coordinator | All trading nodes | `{config_version, pairs, capital_allocation, timestamp}` |
| `fleet.kill_switch` | Coordinator/Node | All nodes | `{reason, triggered_by, timestamp}` |

**Security**: CURVE encryption with pre-shared keys per node pair.

### 3.2 Redis Streams (Shared State Persistence)

**Cluster**: 3 masters (1 per machine) + replicas

**Streams & Consumer Groups:**

| Stream | Producers | Consumers | Retention | Schema |
|--------|-----------|-----------|-----------|--------|
| `trades` | Trading nodes | mc2 (archive), risk manager | 30 days | `{trade_id, symbol, exchange, side, price, amount, pnl, fee, strategy, timestamp}` |
| `positions` | Trading nodes | mc2, risk manager, peer | 7 days | `{symbol, exchange, base, quote, size, entry_price, current_price, unrealized_pnl, timestamp}` |
| `orders` | Trading nodes | mc2, peer | 7 days | `{order_id, symbol, exchange, side, price, amount, filled, status, timestamp}` |
| `equity` | Trading nodes | mc2, dashboard | 90 days | `{node, total_equity, realized_pnl, unrealized_pnl, drawdown, timestamp}` |
| `risk.metrics` | Risk manager | mc2, alerts | 30 days | `{portfolio_dd, daily_loss, exposure_per_base, correlations, kill_switch_triggered, timestamp}` |
| `health.metrics` | All nodes | mc2, Zabbix | 7 days | `{node, cpu_pct, ram_pct, fd_count, bot_count, uptime, safe_level, timestamp}` |

**Consumer Groups**: Each service has its own consumer group for exactly-once processing.

### 3.3 HTTP/REST (Control Plane)

| Endpoint | Node | Purpose |
|----------|------|---------|
| `GET /health` | All | Unified health check (binds 127.0.0.1) |
| `GET /risk` | Trading | Detailed risk status |
| `GET /fleet` | Coordinator | Fleet-wide status |
| `POST /fleet/reload` | Coordinator | Trigger hot reload |
| `POST /fleet/rotate` | Coordinator | Trigger pair rotation |
| `POST /kill` | All | Activate kill switch |
| `GET /metrics` | All | Prometheus/Zabbix metrics |

---

## 4. Data Flow

### 4.1 Market Data Flow
```
Exchange WS/REST → ExchangeAdapter → ZeroMQ Pub → Peer Node + mc2 Redis
                                      ↓
                              OhlcvBuffer (circular)
                                      ↓
                              Strategy Analyze → Signal
                                      ↓
                              Risk Check → Order
                                      ↓
                              Execution → Fill
                                      ↓
                              State Update → Redis Streams
                                      ↓
                              Risk Manager Update
```

### 4.2 Pair Rotation Flow
```
Scheduler (Monday 00:00) → Pair Scanner (mc2/leader)
                           → Generate fleet_config.json
                           → ZeroMQ broadcast to nodes
                           → Fleet Coordinator hot reload
                           → Drain old pairs (DRAINING)
                           → Start new pairs (STARTING→RUNNING)
                           → Alert notification
```

### 4.3 Failover Flow
```
Health check failure (30s no heartbeat)
    → mc2 detects via Redis health.metrics
    → mc2 promotes peer to primary for affected pairs
    → Peer starts DRAINING→STARTING for orphaned pairs
    → Alert: "Node failover: {failed_node} → {peer}"
    → Failed node recovers → rebalances
```

---

## 5. Deployment Topology

### 5.1 Docker Compose (per machine)

**mc2 (docker-compose.yml):**
```yaml
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

**nuvola/MARCODG1 (docker-compose.yml):**
```yaml
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
      - ZMQ_PEER=tcp://MARCODG1:5555  # or nuvola
    deploy:
      replicas: 12  # 12 bot instances via fleet coordinator
  fleet-coordinator:
    build: .
    command: python -m alpha_omega.fleet.coordinator
    environment:
      - NODE_ROLE=fleet_coordinator
      - FLEET_CONFIG=/config/fleet_config_nuvola.json
```

### 5.2 Systemd Services (bare metal alternative)

Each bot runs as independent systemd service:
```ini
# shadowgrid@.service
[Unit]
Description=ShadowGrid Bot %i
After=network.target redis.service

[Service]
Type=simple
User=sergio
WorkingDirectory=/home/sergio/denaro
EnvironmentFile=/home/sergio/denaro/.env.%i
ExecStart=/home/sergio/denaro/venv/bin/python -m alpha_omega.core.engine
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Fleet coordinator manages service lifecycle via systemd D-Bus.

---

## 6. Configuration Management

### 6.1 Environment Variables (per bot)

```bash
# Exchange
EXCHANGE=kraken                    # kraken|okx
SYMBOL=SOL/EUR                     # Trading pair
CAPITAL=50.0                       # EUR allocated
LIVE_MODE=0                        # 0=paper, 1=live

# Grid Parameters
LEVELS=5
BASE_SPREAD_PCT=0.5
PER_LEVEL=0.2
ATR_SPREAD_MULTIPLIER=0.7
MIN_SPREAD_PCT=0.2
MAX_SPREAD_PCT=2.5
DRIFT_PCT=6.0

# Risk
USE_MOMENTUM_FILTER=1
MAX_DRAWDOWN_PCT=0.15
MAX_DAILY_LOSS_PCT=0.05
HYBRID_MODE=0
RISK_MANAGER_ENABLED=1
MAX_PORTFOLIO_DD=0.20
MAX_EXPOSURE_PER_BASE=0.30
MAX_CORRELATION=0.7
VOLATILITY_TARGETING=1

# Network
HEALTH_PORT=8912
LOG_FILE=/var/log/shadowgrid/SOL_EUR.log
STATE_FILE=/var/lib/shadowgrid/SOL_EUR_state.json

# API Keys (from secret manager)
KRAKEN_API_KEY=${KRAKEN_API_KEY}
KRAKEN_API_SECRET=${KRAKEN_API_SECRET}
OKX_API_KEY=${OKX_API_KEY}
OKX_API_SECRET=${OKX_API_SECRET}
OKX_PASSPHRASE=${OKX_PASSPHRASE}
```

### 6.2 Fleet Config (versioned, generated by scanner)

```json
{
  "version": "2024-01-15T00:00:00Z",
  "total_fleet_capital": 200.0,
  "capital_per_exchange": {"kraken": 100.0, "okx": 100.0},
  "pairs": [
    {"symbol": "SOL/EUR", "port": 8912, "capital": 16.67, "exchange": "kraken",
     "regime": "range", "suitability": "grid", "atr_pct": 2.5, "adx": 18.5}
  ],
  "okx_pairs": [
    {"symbol": "BICO/USDT", "port": 8930, "capital": 16.67, "exchange": "okx",
     "regime": "range", "suitability": "grid", "atr_pct": 1.8, "adx": 22.1}
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

### 6.3 Secret Management

- **Development**: `.env` files (gitignored)
- **Production**: HashiCorp Vault or AWS Secrets Manager
- **Injection**: Init container reads secrets → writes to `/run/secrets/` → env vars

---

## 7. Security Model

### 7.1 Network Security
- **ZeroMQ**: CURVE encryption (public/private keys per node)
- **Redis**: TLS + ACL (separate users per service)
- **PostgreSQL**: TLS + role-based access
- **Health endpoints**: Bind 127.0.0.1 only, SSH tunnel for access
- **Inter-node**: WireGuard mesh or Tailscale

### 7.2 API Key Management
- Exchange keys stored in Vault, never in config files
- Per-exchange, per-environment (paper/live) key sets
- Automatic rotation via exchange API (where supported)
- Audit logging for all key access

### 7.3 Kill Switch Authority
- **Global**: mc2 coordinator + any trading node (file-based)
- **Portfolio**: Risk manager (DD/daily loss limits)
- **Symbol**: Per-bot kill file
- **Manual**: Telegram command `/kill [global|symbol|portfolio]`

---

## 8. Scaling Strategy

### 8.1 Horizontal Scaling (More Bots)
- Add pairs to fleet_config.json
- Fleet coordinator auto-assigns ports
- Capital rebalanced via risk parity
- Max bots per node: 20 (4GB RAM, 4GB swap, 2 vCPU)

### 8.2 Vertical Scaling (More Capital)
- Increase `capital_per_bot` in fleet config
- Risk parity recalculates allocations
- Monitor min notional requirements per exchange

### 8.3 Geographic Scaling (More Nodes)
- Add new trading node to ZeroMQ mesh
- Join Redis cluster
- Register with mc2 coordinator
- Automatic pair distribution

### 8.4 Exchange Scaling
- New exchange = new ExchangeAdapter implementation
- Add to pair scanner exchange list
- Separate capital allocation per exchange
- Independent health monitoring

---

## 9. Failure Scenarios & Mitigations

| Scenario | Detection | Mitigation |
|----------|-----------|------------|
| **Node crash** | Health heartbeat missing 30s | Peer takes over pairs via fleet coordinator |
| **Exchange API down** | 429/5xx errors > threshold | Switch to paper mode, alert, retry with backoff |
| **Network partition** | ZeroMQ heartbeat timeout | Local risk limits enforce safe mode, no new orders |
| **Redis cluster split** | Cluster slots uncovered | Fallback to local SQLite state, sync on recovery |
| **Runaway bot** | DD > 15% or daily loss > 5% | Kill switch triggers, positions closed, alert |
| **Stuck orders** | No fills > 1 hour | Auto-cancel, re-anchor grid, alert |
| **Correlation breach** | Risk manager detects > 0.7 | Block new positions, reduce existing, alert |
| **Volatility spike** | ATR > 3× median | Pause new orders, widen spreads, reduce grid |
| **Config drift** | File hash mismatch | Auto-sync from leader, alert on manual changes |
| **Zombie process** | Port in use, no PID match | Force kill, restart via fleet coordinator |

---

## 10. Implementation Roadmap

### Phase 1: Foundation (Week 1-2)
- [ ] Create `alpha_omega/` package structure
- [ ] Implement UnifiedTradingEngine (merge shadowgrid_v2 + neo)
- [ ] Implement ExchangeAdapter with aiohttp + WS multiplexing
- [ ] Implement Circular Buffers (OhlcvBuffer, TickBuffer)
- [ ] Implement StateStore with Redis Streams + SQLite WAL
- [ ] Unit tests for core components

### Phase 2: Risk & Strategies (Week 2-3)
- [ ] Implement PortfolioRiskManager
- [ ] Implement Strategy classes: Grid, DCA, Scalp, MeanReversion, Momentum
- [ ] Implement StrategySelector with regime detection
- [ ] Implement Alert System (Telegram/Email/Zabbix)
- [ ] Integration tests with paper trading

### Phase 3: Distributed Layer (Week 3-4)
- [ ] Implement ZeroMQ Pub/Sub for market data
- [ ] Implement Redis Streams consumer groups
- [ ] Implement DistributedFleetCoordinator with Raft
- [ ] Implement DistributedPairScanner
- [ ] Implement hot reload + pair rotation
- [ ] Chaos engineering tests

### Phase 4: Production Hardening (Week 4-5)
- [ ] Docker Compose + systemd service templates
- [ ] Zabbix templates + Grafana dashboards
- [ ] Secret management integration
- [ ] CURVE encryption for ZeroMQ
- [ ] TLS for Redis/PostgreSQL
- [ ] Load testing + latency benchmarking

### Phase 5: Live Validation (Week 5-6)
- [ ] Paper trading on both nodes (2 weeks)
- [ ] Live validation with €200 capital (1 month)
- [ ] Scale to €1000 capital
- [ ] Continuous optimization

---

## 11. Monitoring & Observability

### 11.1 Key Metrics

| Category | Metrics |
|----------|---------|
| **Trading** | PnL (realized/unrealized), win rate, avg trade duration, sharpe, sortino, max DD |
| **Risk** | Portfolio DD, daily loss, exposure per base, correlation matrix, kill switch status |
| **System** | CPU, RAM, disk, FD count, network I/O, GC pauses |
| **Exchange** | API latency, rate limit usage, order fill rate, slippage |
| **Fleet** | Bot count (running/error/draining), capital allocation, pair performance |

### 11.2 Zabbix Integration
- **Templates**: `AlphaOmega Trading Node`, `AlphaOmega Fleet`
- **Items**: All metrics above via HTTP `/metrics` endpoint
- **Triggers**: DD > 10% (warning), DD > 15% (critical), bot down > 60s, etc.
- **Actions**: Telegram/Email notifications, auto-restart via fleet coordinator

### 11.3 Grafana Dashboards
1. **Fleet Overview**: Total equity, PnL, bot status, risk metrics
2. **Node Deep Dive**: Per-bot performance, order book, grid visualization
3. **Risk Dashboard**: Correlation heatmap, exposure breakdown, DD waterfall
4. **System Health**: Resource usage, latency percentiles, error rates

---

## 12. Appendix: File Structure

```
alpha-omega-trading/
├── alpha_omega/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── engine.py              # UnifiedTradingEngine
│   │   ├── exchange.py            # ExchangeAdapter
│   │   ├── buffers.py             # OhlcvBuffer, TickBuffer, CircularBuffer
│   │   ├── state.py               # StateStore (Redis Streams + SQLite)
│   │   ├── config.py              # Config dataclasses
│   │   └── types.py               # Shared typed dataclasses
│   ├── strategies/
│   │   ├── __init__.py
│   │   ├── base.py                # BaseStrategy
│   │   ├── grid.py                # GridStrategy (ATR-adaptive)
│   │   ├── dca.py                 # DCAStrategy
│   │   ├── scalp.py               # ScalpStrategy
│   │   ├── mean_reversion.py      # MeanReversionStrategy
│   │   ├── momentum.py            # MomentumStrategy
│   │   └── selector.py            # StrategySelector
│   ├── risk/
│   │   ├── __init__.py
│   │   ├── manager.py             # PortfolioRiskManager
│   │   ├── correlation.py         # Correlation matrix
│   │   ├── volatility.py          # Volatility regime detection
│   │   └── kill_switch.py         # Multi-layer kill switch
│   ├── fleet/
│   │   ├── __init__.py
│   │   ├── coordinator.py         # DistributedFleetCoordinator
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
│   │   ├── channels.py            # Telegram/Email/Zabbix/Log
│   │   └── templates.py           # Alert message templates
│   └── monitoring/
│       ├── __init__.py
│       ├── health.py              # Health HTTP server
│       ├── metrics.py             # Prometheus/Zabbix metrics
│       └── resource.py            # ResourceMonitor
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
├── ARCHITECTURE.md
├── requirements.txt
├── pyproject.toml
└── README.md
```

---

*This architecture document is the single source of truth for the Alpha-Omega Trading System implementation. All code must align with these specifications.*