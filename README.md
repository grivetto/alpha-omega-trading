# Alpha-Omega Trading

<p align="center">
  <img src="assets/banner.svg" alt="Alpha-Omega Trading Banner" width="100%"/>
</p>

<h3 align="center">Distributed Algorithmic Trading Fleet & High-Frequency Telemetry</h3>

<p align="center">
  <i>Multi-node execution engine for OKX and Kraken, backed by strict supervisor throttles, Docker Zabbix monitoring, and staged capital validation.</i>
</p>

<p align="center">
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.12"></a>
  <a href="https://fastapi.tiangolo.com/"><img src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI"></a>
  <a href="https://www.docker.com/"><img src="https://img.shields.io/badge/Docker-Containerized-2496ED?style=flat-square&logo=docker&logoColor=white" alt="Docker"></a>
  <a href="https://www.zabbix.com/"><img src="https://img.shields.io/badge/Zabbix-7.0_LTS-D40000?style=flat-square&logo=zabbix&logoColor=white" alt="Zabbix 7.0 LTS"></a>
  <a href="https://ubuntu.com/"><img src="https://img.shields.io/badge/Ubuntu-24.04_LTS-E95420?style=flat-square&logo=ubuntu&logoColor=white" alt="Ubuntu"></a>
  <a href="https://www.cloudflare.com/"><img src="https://img.shields.io/badge/Cloudflare-Tunnel-F38020?style=flat-square&logo=cloudflare&logoColor=white" alt="Cloudflare"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-CC0_1.0-blue.svg?style=flat-square" alt="CC0 License"></a>
</p>

<p align="center">
  <a href="README.md"><b>English</b></a> •
  <a href="README.it.md"><b>Italiano</b></a> •
  <a href="README.es.md"><b>Español</b></a> •
  <a href="README.th.md"><b>ไทย</b></a>
</p>

---

## 🏛 Architecture & Distributed Fleet Topology

The system operates across an asymmetric multi-host topology (`nuvola`, `MARCODG1`, and `mc2`). Each machine fills a designated runtime role to maintain continuous operations, resilient data capture, and zero-inbound exposure behind NAT/CGNAT firewalls.

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

### Core Technologies
| Component | Tech / Framework | Function |
| :--- | :--- | :--- |
| **Execution Core** | `Python 3.12`, `AsyncIO`, `CCXT` | Unified node runtime running grid and momentum policies. |
| **Fleet Network** | `autossh`, `systemd`, `Cloudflare` | Encrypted reverse SSH tunnels (2222/10051/8912) across NATs. |
| **Telemetry & Alerts** | `Zabbix 7.0 LTS`, `Docker`, `PostgreSQL` | 350+ metric trappers monitoring equity, drawdown, and heartbeats. |
| **Real-time Dashboard** | `FastAPI` / `HTTP Server`, CSS Neon UI | Live portfolio state and tick health at `web.grivetto.eu`. |

---

## 📖 History & The Reality of Trading ("La Baracca")

This platform was originally christened *"La Baracca"* — an honest Italian expression for a makeshift, fragile contraption that always needed something patched or fixed.

### The Lessons of Live Markets
In its early days, theoretical backtests suggested easy profits. The reality of live crypto markets quickly taught different lessons:
- **Fee Drag & Slippage:** Unaccounted exchange fees (maker/taker) and order slippage easily wiped out theoretical grid profits.
- **API & Regulatory Friction:** EEA regulatory changes, endpoint rate limits, and exchange maintenance spikes caused missed ticks and deadlocks.
- **Market Asymmetry:** Unchecked buy-ladders during sudden sell-offs resulted in locked capital and structural inventory traps.

Rather than abandoning the project, the system was refactored with **rigorous defensive engineering**: anti-deadlock pre-flight filters, sub-account isolation, dynamic supervisor throttles, and automated circuit breakers.

---

## 🚀 Active Work in Progress (Live Stage: 25 + 25 EUR)

We enforce a strict **data-driven capital progression**. Real funds are kept in small envelopes (~50 EUR total) while statistical criteria are proven:

| Exchange | Target Pair | Mode | Budget | Strategy | Execution Host | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Kraken** | `SOL/EUR` | **Live** | ~12.70 € | Momentum Capture | `MARCODG1` | <img src="https://img.shields.io/badge/Active-brightgreen?style=flat-square" alt="Active"> |
| **Kraken** | `XRP/EUR` | **Live** | ~12.70 € | Momentum Capture | `MARCODG1` | <img src="https://img.shields.io/badge/Active-brightgreen?style=flat-square" alt="Active"> |
| **OKX** | `DOGE/EUR` | **Live** | ~12.00 € | Multi-level Grid | `mc2` (`mc2sub1`) | <img src="https://img.shields.io/badge/Active-brightgreen?style=flat-square" alt="Active"> |
| **OKX** | `SOL/EUR` | **Live** | ~12.00 € | Multi-level Grid | `mc2` (`mc2sub1`) | <img src="https://img.shields.io/badge/Active-brightgreen?style=flat-square" alt="Active"> |

### Staged Scaling Roadmap
- [x] **Stage 1 (Current):** 4 active live bots (~50 EUR budget). Multi-week observation of real fee drag, fill frequencies, and API stability.
- [ ] **Stage 2:** Promotion to 100 EUR – 250 EUR total equity upon achieving a sustained Profit Factor > 1.25 and Max Drawdown < 8%.
- [ ] **Stage 3:** Expansion to 500 EUR with automated dynamic ATR grid spacing and volatility regime detection.
- [ ] **Stage 4:** Production fleet target (1,000 EUR) across segregated exchange sub-accounts.

---

## 🛡 Risk Management & Defensive Controls

- **Pre-Flight Order Validation:** Anti-deadlock checks inspect free quote equity and order notional before dispatching orders to CCXT.
- **Supervisor Safe Mode:** Real-time RAM, CPU, and tick-lag monitoring. If resource pressure exceeds thresholds (`caution` -> `safe` -> `emergency`), the supervisor automatically throttles or suspends trading loops.
- **Sub-Account Isolation:** All live execution runs on dedicated API sub-accounts (`TRENDSUB` on Kraken, `mc2sub1` on OKX), ensuring operational errors can never impact core account assets.
- **Zero-Secret Commits:** Credentials exist strictly inside server-local `.env` configurations excluded by `.gitignore`.

---

## 🛠 Quick Start

### Installation
```bash
# Clone the repository
git clone git@github.com:grivetto/alpha-omega-trading.git
cd alpha-omega-trading

# Create virtual environment & install requirements
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
```

### Running a Node
```bash
# Start Kraken trend-following node
python -m denaro.denaro_node --config config/node_trend_live_kraken.yaml

# Start OKX grid node
python -m denaro.denaro_node --config config/node_mc2.yaml

# Run test suite
pytest
```

---

## ⚖️ Disclaimer

**This software is distributed strictly for educational, academic, and research purposes. It is not financial or investment advice.** Cryptocurrency algorithmic trading involves substantial financial risk, including the possible loss of all invested capital. The authors make no representations or warranties regarding system profitability or performance. Never trade with capital you cannot afford to lose.

---

## 📄 License

Dedicated to the public domain under Creative Commons Zero (CC0 1.0 Universal). See [LICENSE](LICENSE) for details.
