# ⚡ ALPHA-OMEGA TRADING — ATLAS

[![License: Unlicense](https://img.shields.io/badge/license-Unlicense-blue.svg)](http://unlicense.org/)
[![Python](https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![CCXT](https://img.shields.io/badge/exchange-CCXT%20Pro%20%2F%20Kraken%20%7C%20OKX-5741D9?logo=bitcoin&logoColor=white)](https://github.com/ccxt/ccxt)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20systemd-FCC624?logo=linux&logoColor=black)](https://www.freedesktop.org/wiki/Software/systemd/)
[![Status](https://img.shields.io/badge/status-LIVE-brightgreen)](https://github.com/grivetto/alpha-omega-trading)

> **ATLAS** is the modular, async, multi-exchange evolution of the legacy **Denaro** trading system. Same exchanges, same credentials, same philosophy — rebuilt with clean architecture, resilience patterns and integrated risk management.

---

## 🏗️ What is ATLAS

ATLAS is a distributed algorithmic trading system written in Python 3.12 with `asyncio`. It replaces the monolithic Denaro codebase with a modular architecture:

- **Multi-exchange**: Kraken and OKX Europe (EEA) via CCXT async + CCXT Pro (WebSocket)
- **Multi-node**: one instance per trading node (`nuvola`, `MARCODG1`)
- **Grid strategy**: limit buy/sell orders around the mid price
- **Resilient**: timeout → retry with exponential backoff → non-retryable error classification
- **Risk-managed**: drawdown, daily loss, position size, exposure and correlation limits + kill switch
- **Observable**: JSON logging, HTTP health/readiness API

## 🧩 Architecture

```
atlas/
├── main.py                 # Application entry point: lifecycle + dependency injection
├── core/
│   ├── config.py           # Pydantic settings + YAML loading with ${VAR} env substitution
│   ├── events.py           # EventBus (async pub/sub: ticks, fills, risk events)
│   ├── lifecycle.py        # GracefulShutdown (SIGINT/SIGTERM handling)
│   └── resilience.py       # exchange_call decorator: timeout → retry → circuit breaker
├── connector/
│   ├── interface.py        # ExchangeConnector abstract base
│   ├── ccxt_adapter.py     # CCXT async implementation (REST + WebSocket)
│   └── models.py           # Ticker, OrderBook, Balance
├── strategy/
│   └── engine.py           # GridStrategy + StrategyEngine (tick loop, open-order dedup)
├── execution/
│   ├── router.py           # ExecutionRouter: order submission pipeline
│   └── models.py           # OrderRequest, OrderResponse, CancelResponse
├── portfolio/
│   └── manager.py          # ExchangeRegistry + PortfolioManager (risk limits, equity tracking)
├── observability/
│   └── logging.py          # Structured JSON logging
└── storage/                # State persistence
```

### Execution pipeline

```
Ticker → StrategyEngine (GridStrategy.on_tick)
       → ExecutionRouter.submit(OrderRequest)
       → CCXTAdapter.create_order (via exchange_call: timeout→retry→classify)
       → Exchange (Kraken / OKX EEA)
```

The strategy loop is throttled (max 1 signal per symbol per 60s) and deduplicated against open orders, so the bot never stacks orders blindly.

## ⚙️ Configuration

All configuration lives in `config/` as YAML, with `${VAR}` substitution resolved from `.env`:

**`config/exchanges.yaml`** — exchange credentials and tuning:

```yaml
exchanges:
  - name: kraken
    api_key: ${KRAKEN_API_KEY}
    api_secret: ${KRAKEN_API_SECRET}
    rate_limit_rps: 5.0
    rate_limit_burst: 10
  - name: okx
    api_key: ${OKX_API_KEY}
    api_secret: ${OKX_API_SECRET}
    passphrase: ${OKX_API_PASSPHRASE}
    extra:
      eea: true        # → forces hostname eea.okx.com (OKX Europe)
```

> ⚠️ **OKX Europe (EEA)**: the `extra.eea: true` flag is mandatory. Without it the bot targets `api.okx.com` and every authenticated call fails with error 50119/50111.

**`config/strategies.yaml`** — strategy parameters:

```yaml
strategies:
  - strategy_id: grid_btc_eur
    class_path: atlas.strategy.engine.GridStrategy
    enabled: true
    symbols: ["BTC/EUR"]
    exchanges: ["kraken"]
    params:
      grid_levels: 3          # number of grid levels around mid price
      spread_pct: 0.005       # distance between levels (0.5%)
      per_level_pct: 0.10     # equity allocation per level
      order_size: 0.00005     # explicit size (overrides per_level_pct)
      min_notional: 5.0       # minimum order value
```

**`.env`** — API credentials (never committed; see `.gitignore`).

## 🛡️ Risk Management

Default limits (`atlas/core/config.py`), enforced by `PortfolioManager`:

| Limit | Value |
|-------|-------|
| Max portfolio drawdown | 20% |
| Max daily loss | 5% |
| Max position size | 25% of equity |
| Max exposure per base currency | 30% |
| Max correlation exposure | 70% |
| Max leverage | 1.0 (spot only) |

Violations emit `RiskEvent`s on the event bus and can trigger the **kill switch**.

## 🔄 Compatibility with Denaro

ATLAS is the direct evolution of **Denaro**: it preserves what worked and fixes what didn't.

| Aspect | Denaro (legacy) | ATLAS |
|--------|-----------------|-------|
| Codebase | Monolithic (`engine_solo.py`, `bot_v5.py`) | Modular package `atlas/` |
| Exchange access | CCXT direct calls | CCXT async via `CCXTAdapter` + resilience layer |
| Strategy | Grid hardcoded per bot | Declarative `GridStrategy` from YAML |
| Risk | Spread across ad-hoc checks | Central `PortfolioManager` with hard limits |
| Observability | Log files | JSON logging + `/health` + `/ready` HTTP API |
| Resilience | None | Timeout → retry → circuit breaker (`exchange_call`) |
| Config | Code constants | YAML + `.env` with `${VAR}` substitution |

**Coexistence**: both systems run on the same nodes and exchanges. They read **separate sections** of the same `.env` (Denaro keys vs ATLAS keys), use separate systemd units, and never share order state. The Denaro grid parameters map directly onto `GridStrategy` params (`grid_levels`, `spread_pct`, `per_level_pct`).

**Migration path**: a Denaro grid bot is migrated by (1) writing its parameters into `config/strategies.yaml`, (2) adding its API key section to `.env`, (3) starting `atlas-engine.service`.

## 🚀 Deployment

```bash
# 1. Install dependencies
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2. Configure
cp .env.example .env            # fill in API credentials
# edit config/exchanges.yaml + config/strategies.yaml

# 3. Run (foreground)
.venv/bin/python -m atlas.main

# 4. Run as a service (production)
sudo systemctl enable --now atlas-engine
sudo systemctl enable --now atlas-watchdog   # auto-healing
```

**`atlas-engine.service`** runs the bot with `Restart=always`; **`atlas-watchdog.service`** restarts the engine when it stops responding.

### Health API

```
GET /health   → {"status": "healthy", "service": "atlas-engine", "exchanges": [...], "strategies": [...]}
GET /ready    → {"ready": true|false, "service": "atlas-engine"}
```

The health server binds `[::]:8080` (dual-stack IPv4/IPv6) so nodes behind CGNAT can be monitored remotely.

## 📊 Current Deployment

| Node | Exchange | Pair(s) | Service |
|------|----------|---------|---------|
| `nuvola` | Kraken | BTC/EUR | atlas-engine + watchdog |
| `MARCODG1` | OKX (EEA) | ETH/EUR, SOL/EUR, XRP/EUR, DOGE/EUR | atlas-engine + watchdog |

## 🧠 Design Principles

1. **Code is law, profit is proof** — every trade decision is deterministic and auditable.
2. **Capital protection first** — risk limits are enforced in the code path, not on a wish list.
3. **Distribution is resilience** — two independent nodes, no single point of failure.
4. **Waste nothing** — async I/O, no frameworks beyond what is used, one process per node.
5. **Never trust credentials in code** — secrets live only in `.env` (gitignored).

## 📄 License

[The Unlicense](http://unlicense.org/) — public domain. Use it, study it, break it, improve it.
