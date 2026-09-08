# Alpha-Omega Trading

**_Codename "Denaro" — Distributed algorithmic trading system & multi-node execution engine for OKX and Kraken._**

![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![Zabbix](https://img.shields.io/badge/Zabbix-D40000?style=for-the-badge&logo=zabbix&logoColor=white)
![Ubuntu](https://img.shields.io/badge/Ubuntu-E95420?style=for-the-badge&logo=ubuntu&logoColor=white)
![Git](https://img.shields.io/badge/Git-F05032?style=for-the-badge&logo=git&logoColor=white)
![Cloudflare](https://img.shields.io/badge/Cloudflare-F38020?style=for-the-badge&logo=cloudflare&logoColor=white)

Alpha-Omega Trading is a multi-host execution platform operating across a distributed server topology (`nuvola`, `MARCODG1`, and `mc2`). It drives automated grid trading, momentum capture, and regime-adaptive execution models on crypto exchanges through CCXT, bound by strict real-time telemetry and risk supervisory gates.

> [English](README.md) · [Italiano](README.it.md) · [Español](README.es.md) · [ไทย](README.th.md)

---

## Architecture & Technology Stack

```
 ┌─────────────────────────────────────────────────────────┐
 │                   EXCHANGES LAYER                       │
 │              OKX (EEA)   ·   Kraken REST/WS             │
 └─────────────┬───────────────────────────┬───────────────┘
               │ CCXT Execution            │ CCXT Execution
 ┌─────────────▼─────────────┐ ┌───────────▼───────────────┐
 │       NODE: mc2           │ │      NODE: MARCODG1       │
 │   (Home Node / CGNAT)     │ │        (Cloud VPS)        │
 │ · denaro-node-mc2         │ │ · denaro-node-trend-live  │
 │ · Docker Zabbix Server    │ │ · Zabbix Push Metrics     │
 │ · Dashboard Web (:8913)   │ │ · Aggregator API (:8912)  │
 └─────────────┬─────────────┘ └───────────┬───────────────┘
               │                           │
               └─────────────►◄────────────┘
                 Reverse SSH Tunnels (autossh)
                 Zabbix Trapper :10051 / Reverse 2222
```

- **Runtime & Core Engine:** Python 3.12+, AsyncIO, CCXT Pro for exchange connectivity.
- **Topology & Communication:** 3 active nodes interconnected via reverse SSH tunnels (`autossh`) and Cloudflare tunnels to bridge CGNAT environments safely.
- **Monitoring & Observability:** Enterprise Zabbix 7.0 LTS monitoring stack running containerized on Docker, receiving high-frequency telemetry via Zabbix Trappers.
- **Dashboard & Telemetry:** Custom asynchronous HTTP/JSON service exposing real-time metrics, node states, and balance telemetry at `web.grivetto.eu`.

---

## History & Lessons Learned ("La Baracca")

This system originated as an exploratory algorithmic trading framework nicknamed *"La Baracca"* (Italian slang for a rickety contraption that constantly needs fixing).

### The Reality of Algorithmic Trading
In early development, naive strategies, over-fitted parameters, exchange API disconnections, and silent order rejections proved that optimistic backtests rarely survive live market execution. Real-world crypto markets impose heavy friction:
- **Exchange Fees & Slippage:** Maker/taker fee structures easily erode thin grid spreads.
- **API Rate Limits & IP Restrictions:** Exchange endpoints (especially EEA-compliant endpoints) require resilient reconnection routines and strict rate limiting.
- **Drawdown Realities:** Unhedged grids during sudden market crashes lead to locked capital and structural inventory traps.

Rather than hiding these failures behind marketing buzzwords, the system was re-engineered from the ground up with defensive engineering principles: hard stop-losses, anti-deadlock position validation, supervisor-driven safe mode throttles, and segregated staging accounts.

---

## Active Work in Progress (Live Stage: 25 + 25 EUR)

We operate on a strictly enforced **staged capital roadmap**. Live capital is capped at small test envelopes (~50 EUR total) while operational resilience is demonstrated:

| Exchange | Target Pair | Mode | Capital Budget | Strategy | Node Host |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Kraken** | `SOL/EUR` | **Live** | ~12.70 € | Trend Momentum | `MARCODG1` |
| **Kraken** | `XRP/EUR` | **Live** | ~12.70 € | Trend Momentum | `MARCODG1` |
| **OKX** | `DOGE/EUR` | **Live** | ~12.00 € | Multi-level Grid | `mc2` (`mc2sub1`) |
| **OKX** | `SOL/EUR` | **Live** | ~12.00 € | Multi-level Grid | `mc2` (`mc2sub1`) |

### Active Development Priorities:
1. **Live Observation Window:** Monitoring fill frequencies, slippage, and fee friction over multi-week observation periods across the 4 active live bots.
2. **Dynamic Spacing & Volatility Adaptation:** Enhancing the grid spacing engine based on historical volatility (ATR) rather than static price percentages.
3. **Threshold-Gated Staging:** Advancing capital allocation from the current ~50 EUR envelope to 100 EUR, 500 EUR, and ultimately 1,000 EUR strictly upon meeting verified Sharpe and profit-factor thresholds.

---

## Safety & Risk Controls

- **Pre-Flight Order Validation:** Anti-deadlock checks inspect free quote equity and order notional before dispatching orders to CCXT.
- **Supervisor Safe Mode:** Real-time RAM, CPU, and tick-lag monitoring. If resource pressure exceeds thresholds (`caution` -> `safe` -> `emergency`), the supervisor automatically throttles or suspends trading loops.
- **Sub-Account Isolation:** All live execution runs on dedicated API sub-accounts (`TRENDSUB` on Kraken, `mc2sub1` on OKX), ensuring operational errors can never impact core account assets.
- **Zero-Secret Commits:** Credentials exist strictly inside server-local `.env` configurations excluded by `.gitignore`.

---

## Getting Started

### Prerequisites
- Linux (Ubuntu 22.04 / Debian 12 recommended)
- Python 3.12+ and `venv`
- Docker & Docker Compose (for the Zabbix telemetry stack)
- Exchange API credentials with Spot trading permissions

### Installation
```bash
# Clone the repository
git clone git@github.com:grivetto/alpha-omega-trading.git
cd alpha-omega-trading

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your sub-account keys
```

### Running the Engine
```bash
# Start a node with a specific configuration
python -m denaro.denaro_node --config config/node_trend_live_kraken.yaml

# Run tests
pytest
```

---

## Disclaimer

**This software is distributed strictly for educational, academic, and research purposes. It is not financial or investment advice.** Cryptocurrency algorithmic trading involves substantial financial risk, including the possible loss of all invested capital. The authors make no representations or warranties regarding system profitability or performance. Never trade with capital you cannot afford to lose.

---

## License

Dedicated to the public domain under Creative Commons Zero (CC0). See [LICENSE](LICENSE) for details.
