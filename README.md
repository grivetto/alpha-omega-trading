# Denaro V3 — Multi-Strategy Trading System

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![Binance](https://img.shields.io/badge/Exchange-Binance-F0B90B.svg)](https://www.binance.com/)
[![ccxt](https://img.shields.io/badge/Library-ccxt-222.svg)](https://github.com/ccxt/ccxt)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Production-green.svg)]()
[![Bots](https://img.shields.io/badge/Bots-5%20Active-brightgreen.svg)]()

**5 specialized bots running 24/7 across 3 servers. Grid + RSI + Momentum + Micro Scalping.**

</div>

---

## Live Bot Fleet

| Bot | Server | Pair | Strategy | Status |
|-----|--------|------|----------|--------|
| **Denaro V3 Grid** | MARCODG1 | ADA/EUR | Adaptive grid (0.3%) | 🟢 Active |
| **RSI Reversion** | MARCODG1 | ADA/EUR | Mean reversion (RSI < 25) | 🟢 Active |
| **Micro Scalper** | MARCODG1 | ADA/EUR | Ultra-tight grid (0.15%) | 🟢 Active |
| **Denaro V3 Grid** | nuvola | SOL/EUR | Adaptive grid (0.3%) | 🟢 Active |
| **Momentum Breakout** | nuvola | SOL/EUR | Volume + price breakout | 🟢 Active |

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DENARO V3 FLEET                              │
│                                                                     │
│  ┌──────────────┐        ┌──────────────┐        ┌──────────────┐   │
│  │     mc2      │        │   Nuvola     │        │   MARCODG1   │   │
│  │  (On-Prem)   │        │  (Cloud VPS) │        │  (Cloud VPS) │   │
│  │              │        │              │        │              │   │
│  │ ┌──────────┐ │        │ ┌──────────┐ │        │ ┌──────────┐ │   │
│  │ │ Zabbix  │ │        │ │ V3 Grid  │ │        │ │ V3 Grid  │ │   │
│  │ │ Server  │ │        │ │ SOL/EUR  │ │        │ │ ADA/EUR  │ │   │
│  │ │ (Hub)   │ │        │ ├──────────┤ │        │ ├──────────┤ │   │
│  │ └──────────┘ │        │ │Momentum  │ │        │ │ RSI      │ │   │
│  └──────────────┘        │ │Breakout  │ │        │ │Reversion │ │   │
│         │                │ └──────────┘ │        │ ├──────────┤ │   │
│         │                └──────────────┘        │ │Micro     │ │   │
│         │                                        │ │Scalper   │ │   │
│         └───────────────────┬────────────────────┤ └──────────┘ │   │
│                             │                    └──────────────┘   │
│                    ┌────────▼────────┐                               │
│                    │    Binance      │                               │
│                    │  Spot Markets   │                               │
│                    └─────────────────┘                               │
└─────────────────────────────────────────────────────────────────────┘
```

## Bot Strategies

### 1. Denaro V3 Grid (`denaro_v3.py`)

Adaptive grid trading with symbol-specific optimization and auto-compounding.

| Feature | ADA/EUR | SOL/EUR |
|---------|---------|---------|
| **Grid Spacing** | 0.3% | 0.3% |
| **Profit Target** | 0.4% | 0.4% |
| **Grid Levels** | 5–10 | 3–5 |
| **Base Order** | 5.5 EUR | 5.5 EUR |
| **Compound Cap** | 1.8x | 1.8x |

### 2. RSI Mean Reversion (`rsi_reversion.py`)

Buys when RSI drops below 25 (oversold), sells on recovery above 55.

| Parameter | Value |
|-----------|-------|
| **RSI Period** | 14 |
| **Buy Threshold** | RSI < 25 |
| **Sell Threshold** | RSI > 55 |
| **Force Sell** | RSI > 70 |
| **Take Profit** | 1.5% |
| **Stop Loss** | 2.0% |
| **Max Positions** | 5 |
| **Candle Interval** | 5m |

### 3. Micro Scalper (`micro_scalper.py`)

Ultra-tight grid for maximum fill frequency on ranging markets.

| Parameter | Value |
|-----------|-------|
| **Grid Spacing** | 0.15% (ultra-tight) |
| **Profit per Scalp** | 0.2% |
| **Grid Levels** | 8 |
| **Base Order** | 5.5 EUR |
| **Max Invested** | 50 EUR |
| **Rebalance** | Every 120 seconds |

### 4. Momentum Breakout (`momentum_breakout.py`)

Detects volume spikes + price breakouts, enters fast, exits on reversal.

| Parameter | Value |
|-----------|-------|
| **Candle Interval** | 3m |
| **Volume Multiplier** | 2.5x average |
| **Price Change** | > 0.8% in 3 candles |
| **RSI Confirmation** | > 55 |
| **Take Profit** | 2.0% |
| **Stop Loss** | 1.5% |
| **Trailing Stop** | 1.0% |
| **Max Positions** | 3 |

## Features

### Shared Across All Bots

- **Fee-Aware Tracking**: Net profit calculated after BNB burn (0.075%/side)
- **Auto-Compounding**: Profits reinvested automatically
- **Verified Fills**: Uses `fetch_my_trades` to prevent false detections
- **Minimum Notional Guard**: Skips orders when capital < 5.0 EUR
- **State Persistence**: Trade history saved to JSON for recovery
- **Real-Time Logging**: Every action logged with timestamps

### Monitoring

Zabbix 7.0 with custom metrics:

- Bot process health and order counts
- Portfolio balances and asset holdings
- Grid metrics (buys/sells, invested, profit)
- System health (CPU, memory, disk)
- Watchdog aggregation

## Project Structure

```
denaro/
├── denaro_v3.py              # Adaptive grid bot (ADA + SOL)
├── rsi_reversion.py          # RSI mean reversion bot (ADA)
├── micro_scalper.py          # Ultra-tight grid scalper (ADA)
├── momentum_breakout.py      # Volume + price breakout bot (SOL)
├── zabbix_metrics.py         # Unified Zabbix metric helper
├── zabbix_grid_metric.py     # Grid-specific metric parser
├── zabbix/
│   ├── mc2.conf              # Zabbix config for mc2 (Hub)
│   ├── nuvola.conf           # Zabbix config for nuvola (SOL)
│   └── marcodg1.conf         # Zabbix config for MARCODG1 (ADA)
├── README.md                 # This file
└── LICENSE                   # MIT License
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

### Running Bots

```bash
# Grid bot (adaptive spacing)
python3 denaro_v3.py ADA/EUR
python3 denaro_v3.py SOL/EUR

# RSI mean reversion
python3 rsi_reversion.py ADA/EUR

# Micro scalper (ultra-tight grid)
python3 micro_scalper.py ADA/EUR

# Momentum breakout
python3 momentum_breakout.py SOL/EUR

# Production (background)
nohup python3 denaro_v3.py ADA/EUR > denaro_v3.log 2>&1 &
nohup python3 rsi_reversion.py ADA/EUR > rsi_reversion.log 2>&1 &
nohup python3 micro_scalper.py ADA/EUR > micro_scalper.log 2>&1 &
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
