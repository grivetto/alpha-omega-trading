# Denaro — Automated Crypto Trading System

<div align="center">

**Survival → Protection → Intelligence → Professionalism**

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![Binance](https://img.shields.io/badge/Exchange-Binance-F0B90B.svg)](https://www.binance.com/)
[![ccxt](https://img.shields.io/badge/Library-ccxt-222.svg)](https://github.com/ccxt/ccxt)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

</div>

---

## Overview

Denaro is a multi-strategy, multi-server automated trading system designed for Binance spot markets. It runs as a fleet of independent bots coordinated by a central orchestrator, each executing a distinct strategy across different asset pairs and timeframes.

The system follows a four-phase evolution philosophy:

| Phase | Focus | Implementation |
|-------|-------|----------------|
| **Survival** | Capital preservation | Circuit breakers, adaptive position sizing, self-healing |
| **Protection** | Risk management | Stop-loss enforcement, drawdown limits, exposure guards |
| **Intelligence** | Adaptive learning | Volatility-adaptive grids, sentiment analysis, profit optimization |
| **Professionalism** | Production-grade ops | systemd services, structured logging, web dashboard, SQLite persistence |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        DENARO FLEET                             │
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │     mc2      │    │   Nuvola     │    │   MARCODG1   │       │
│  │  (On-Prem)   │    │  (Cloud VPS) │    │  (Cloud VPS) │       │
│  │              │    │              │    │              │       │
│  │ ┌──────────┐ │    │ ┌──────────┐ │    │ ┌──────────┐ │       │
│  │ │  Ares    │ │    │ │ GridBot  │ │    │ │ GridBot  │ │       │
│  │ │ETH/EUR 5m│ │    │ │SOL/EUR   │ │    │ │ADA/EUR   │ │       │
│  │ └──────────┘ │    │ └──────────┘ │    │ └──────────┘ │       │
│  │ ┌──────────┐ │    └──────────────┘    └──────────────┘       │
│  │ │  Hermes  │ │                                                │
│  │ │SOL/EUR 1m│ │    ┌──────────────────────────────┐           │
│  │ └──────────┘ │    │        Orchestrator           │           │
│  │ ┌──────────┐ │    │  • Web Dashboard (:8899)      │           │
│  │ │  Apollo  │ │    │  • Portfolio Tracker           │           │
│  │ │ETH/BTC 5m│ │    │  • Risk Manager                │           │
│  │ └──────────┘ │    │  • Capital Pooling             │           │
│  │ ┌──────────┐ │    │  • Bot Health Monitoring       │           │
│  │ │ Artemis  │ │    └──────────────────────────────┘           │
│  │ │BTC/EUR 1d│ │                                                │
│  │ └──────────┘ │                                                │
│  └──────────────┘                                                │
└─────────────────────────────────────────────────────────────────┘
```

## Strategies

### Grid Bot (Nuvola + MARCODG1)

Adaptive grid trading with volatility-aware spacing and martingale-lite position sizing.

| Feature | Description |
|---------|-------------|
| **AdaptiveTrendFilter** | EMA-200 + RSI-14 continuous risk factor (0.0–1.0) |
| **VolatilityGrid** | ATR-based grid spacing, adapts to market conditions |
| **MartingaleLite** | Progressive sizing at lower grid levels (factor 1.12–1.15) |
| **ProfitOptimizer** | Hourly performance review with automatic risk adjustment |
| **Trailing Stop** | State-based with auto-breakeven on profit |
| **Kill Switch** | Automatic pause on catastrophic drops (>5%) |

### Squadra Bots (mc2)

Four specialized bots sharing a capital pool with centralized risk management.

| Bot | Pair | Timeframe | Strategy | Entry Signal |
|-----|------|-----------|----------|--------------|
| **Ares** | ETH/EUR | 5m | SMA Crossover | Fast SMA crosses above Slow SMA |
| **Hermes** | SOL/EUR | 1m | Sentiment Score | RSI + Volume Spike + VWAP composite |
| **Apollo** | ETH/BTC | 5m | Pair Trading | Z-score mean reversion on ratio |
| **Artemis** | BTC/EUR | 1d | Long-Only Trend | SMA50/SMA200 golden cross |

## Project Structure

```
denaro/
├── grid_bot_v3.py              # Grid trading bot (Nuvola + MARCODG1)
├── denaro_core.py              # Async base class: exchange, balance, orders
├── denaro_strategies.py        # Shared strategy engine (trend, grid, optimizer)
├── orchestrator.py             # Fleet orchestrator + web dashboard
├── trade_db.py                 # SQLite persistence layer (WAL mode)
├── grid_config.json            # Grid bot configuration
├── requirements.txt            # Python dependencies
│
├── squadra/                    # Squadra bots (mc2)
│   ├── run_squadra.py          # Entry point
│   ├── orchestrator.py         # Squadra coordinator + risk loop
│   ├── core.py                 # Async base class for squad bots
│   ├── ares_bot.py             # ETH/EUR trend follower
│   ├── hermes_bot.py           # SOL/EUR sentiment bot
│   ├── apollo_bot.py           # ETH/BTC pair trading
│   ├── artemis_bot.py          # BTC/EUR long-term trend
│   ├── config/                 # Per-bot JSON configurations
│   └── strategies/             # Pure strategy functions
│
├── dashboard/                  # Web UI
│   ├── index.html              # Main dashboard
│   └── public/                 # Live JSON data feeds
│
└── utils/                      # Shared utilities
    ├── indicators.py           # Technical indicators
    ├── risk_engine.py          # Risk management
    ├── exit_strategy.py        # Exit logic
    └── sentiment.py            # Social sentiment engine
```

## Quick Start

### Prerequisites

- Python 3.12+
- Binance API keys (spot trading)
- systemd (for production deployment)

### Installation

```bash
# Clone the repository
git clone https://github.com/grivetto/alpha-omega-trading.git denaro
cd denaro

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure API keys
cp .env.example .env
# Edit .env with your BINANCE_API_KEY and BINANCE_API_SECRET
```

### Running a Grid Bot

```bash
# Direct execution
python3 grid_bot_v3.py

# As a systemd service (production)
sudo cp systemd/denaro-grid.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now denaro-grid
```

### Running the Squadra

```bash
# Direct execution
python3 squadra/run_squadra.py

# As a systemd service (production)
sudo cp systemd/denaro-squadra.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now denaro-squadra
```

### Dashboard

The orchestrator serves a live web dashboard on port 8899:

```
http://<server-ip>:8899
```

## Monitoring

```bash
# Check all services
ssh mc2     'sudo systemctl status denaro-squadra'
ssh nuvola  'sudo systemctl status denaro-grid'
ssh MARCODG1 'sudo systemctl status denaro-grid'

# Follow logs in real-time
ssh mc2 'sudo journalctl -fu denaro-squadra --output=cat'

# Restart a bot
ssh mc2 'sudo systemctl restart denaro-squadra'
```

## Configuration

Each bot reads its parameters from a JSON config file. Key settings:

| Parameter | Grid Bot | Squadra | Description |
|-----------|----------|---------|-------------|
| `grid_range_pct` | 0.10 (SOL), 0.08 (ADA) | — | Total grid width as % of price |
| `grid_levels` | 7 | — | Number of buy/sell levels |
| `base_order_eur` | 20.0 (SOL), 12.0 (ADA) | 8–10 | Base order size in EUR |
| `take_profit_pct` | 0.015 | 0.015–0.020 | Take profit threshold |
| `stop_loss_pct` | 0.015 | 0.010–0.015 | Stop loss threshold |
| `martingale_factor` | 1.12–1.15 | — | Size multiplier per level |

## Risk Management

- **Circuit Breaker**: All bots halt if portfolio drawdown exceeds 15%
- **Daily Loss Limit**: €10 maximum daily loss per bot group
- **Exposure Cap**: Maximum €200 total allocation across all squad bots
- **Per-Bot Limit**: €30 maximum per individual bot
- **Phantom Position Detection**: Exchange balance validation on startup

## License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

## Contact

**Sergio Grivetto** — [sergio@grivetto.eu](mailto:sergio@grivetto.eu)

## Disclaimer

This software is provided for educational and research purposes only. It is **not** financial advice. Cryptocurrency trading involves substantial risk of loss. Always do your own research and never trade with money you cannot afford to lose. The authors are not responsible for any financial losses incurred through the use of this software.
