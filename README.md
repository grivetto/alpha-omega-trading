# Denaro V3 — Adaptive Grid Trading System

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![Binance](https://img.shields.io/badge/Exchange-Binance-F0B90B.svg)](https://www.binance.com/)
[![ccxt](https://img.shields.io/badge/Library-ccxt-222.svg)](https://github.com/ccxt/ccxt)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Production-green.svg)]()

**Adaptive grid trading with fee-aware tracking, auto-compounding, and real-time monitoring.**

</div>

---

## Overview

Denaro V3 is a production-grade automated trading system running on Binance spot markets. It employs an adaptive grid strategy with symbol-specific optimization, real-time fee tracking, and automatic profit compounding.

The system runs across a 3-server architecture with centralized monitoring via Zabbix 7.0.

| Metric | Value |
|--------|-------|
| **Architecture** | 3-server distributed fleet |
| **Strategy** | Adaptive grid with dynamic spacing |
| **Fee Discount** | BNB burn enabled (25% savings) |
| **Monitoring** | Zabbix 7.0 with custom metrics |
| **License** | MIT |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    DENARO V3 FLEET                          │
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐   │
│  │     mc2      │    │   Nuvola     │    │   MARCODG1   │   │
│  │  (On-Prem)   │    │  (Cloud VPS) │    │  (Cloud VPS) │   │
│  │              │    │              │    │              │   │
│  │ ┌──────────┐ │    │ ┌──────────┐ │    │ ┌──────────┐ │   │
│  │ │ Zabbix  │ │    │ │ Denaro   │ │    │ │ Denaro   │ │   │
│  │ │ Server  │ │    │ │ V3       │ │    │ │ V3       │ │   │
│  │ │ (Hub)   │ │    │ │ SOL/EUR  │ │    │ │ ADA/EUR  │ │   │
│  │ └──────────┘ │    │ └──────────┘ │    │ └──────────┘ │   │
│  └──────────────┘    └──────────────┘    └──────────────┘   │
│         │                   │                   │            │
│         └───────────────────┼───────────────────┘            │
│                             │                                │
│                    ┌────────▼────────┐                       │
│                    │    Binance      │                       │
│                    │  Spot Markets   │                       │
│                    └─────────────────┘                       │
└─────────────────────────────────────────────────────────────┘
```

## Features

### Adaptive Grid Engine

| Feature | Description |
|---------|-------------|
| **Dynamic Spacing** | Grid spacing adapts per symbol (ADA: 0.3%, SOL: 0.3%) |
| **Capital-Aware Levels** | 3–10 grid levels based on available EUR |
| **Auto-Compounding** | Order size grows with net profit (cap 1.8x) |
| **Fee-Aware Tracking** | Net profit calculated after BNB burn discount (0.075%/side) |
| **Verified Fills** | Uses `fetch_my_trades` to prevent false fill detection |
| **Minimum Notional Guard** | Skips orders when capital < 5.5 EUR |

### Symbol-Specific Optimization

| Parameter | ADA/EUR | SOL/EUR |
|-----------|---------|---------|
| **Grid Spacing** | 0.3% | 0.3% |
| **Profit Target** | 0.4% | 0.4% |
| **Grid Levels** | 5–10 | 3–5 |
| **Base Order** | 5.5 EUR | 5.5 EUR |
| **Max Compound** | 1.8x | 1.8x |

### Monitoring

Real-time telemetry via Zabbix 7.0:

- **Bot Status**: Process health, order counts, fill rates
- **Portfolio**: EUR balance, asset holdings, total value
- **Grid Metrics**: Buys/sells placed, invested capital, net profit
- **System Health**: CPU load, memory usage, disk space
- **Watchdog**: Multi-service health aggregation

## Project Structure

```
denaro/
├── denaro_v3.py              # Main V3 grid bot (adaptive, fee-aware)
├── zabbix_metrics.py         # Unified Zabbix metric helper
├── zabbix_grid_metric.py     # Grid-specific metric parser from logs
├── zabbix/
│   ├── mc2.conf              # Zabbix config for mc2 (Hub)
│   ├── nuvola.conf           # Zabbix config for nuvola (SOL)
│   └── marcodg1.conf         # Zabbix config for MARCODG1 (ADA)
└── README.md                 # This file
```

## Quick Start

### Prerequisites

- Python 3.12+
- Binance API keys (spot trading)
- `ccxt` library (`pip install ccxt`)
- Zabbix Agent 7.0+ (for monitoring)

### Installation

```bash
# Clone the repository
git clone https://github.com/grivetto/alpha-omega-trading.git denaro
cd denaro

# Install dependencies
pip install ccxt

# Configure API keys
cat > .env << EOF
BINANCE_API_KEY=your_api_key
BINANCE_API_SECRET=your_api_secret
EOF
```

### Running a Bot

```bash
# Direct execution
python3 denaro_v3.py SOL/EUR
python3 denaro_v3.py ADA/EUR

# Production (background)
nohup python3 denaro_v3.py ADA/EUR > denaro_v3.log 2>&1 &
```

### Deploying Zabbix Monitoring

```bash
# Copy config to Zabbix agent directory
sudo cp zabbix/nuvola.conf /etc/zabbix/zabbix_agentd.d/denaro_v3.conf
sudo systemctl restart zabbix-agent

# Test metrics from Zabbix server
zabbix_get -s <server> -k "denaro.v3.load.1m"
zabbix_get -s <server> -k "denaro.v3.bot.sol_grid"
```

## Configuration

The bot auto-detects the symbol and applies optimized parameters. Override defaults by editing `denaro_v3.py`:

```python
# Symbol-specific optimization
if "ADA" in self.asset:
    self.grid_spacing = 0.003     # 0.3% spacing
    self.profit_pct = 0.004       # 0.4% profit target
    self.min_grid_levels = 5      # Minimum grid levels
    self.max_grid_levels = 10     # Maximum grid levels
    self.base_order_eur = 5.5     # Base order size
```

## Risk Management

| Guard | Threshold | Action |
|-------|-----------|--------|
| **Minimum Order** | 5.5 EUR | Skip grid placement |
| **Minimum Notional** | 5.0 EUR per order | Skip individual orders |
| **Max Investment** | 100 EUR per grid | Cap total grid exposure |
| **Compound Cap** | 1.8x | Limit order size growth |
| **BNB Fee Discount** | Enabled | 25% fee reduction via API |

## License

This project is licensed under the **MIT License**.

```
MIT License

Copyright (c) 2026 Sergio Grivetto

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## History

Full development history (V1 → V2 → V3): [github.com/grivetto/dollari](https://github.com/grivetto/dollari)

## Contact

**Sergio Grivetto** — [sergio@grivetto.eu](mailto:sergio@grivetto.eu)

## Disclaimer

This software is provided for educational and research purposes only. It is **not** financial advice. Cryptocurrency trading involves substantial risk of loss. Always do your own research and never trade with money you cannot afford to lose. The authors are not responsible for any financial losses incurred through the use of this software.
