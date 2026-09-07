# Alpha-Omega Trading

**_Codename "Denaro" — a unified, distributed grid-trading engine for OKX and Kraken, with realistic paper trading, staged live capital, and Zabbix-based monitoring._

Alpha-Omega trading is a Python system that runs the same trading engine across several machines ("nodes"), each trading one or more markets on OKX or Kraken through the CCXT library. It is designed for disciplined, backtested and paper-validated deployment, with a **small, staged live budget** — the live account is deliberately kept separate from development and is small enough that a full drawdown is affordable while the engine is still in validation.

> [English](README.md) · [Italiano](README.it.md) · [Español](README.es.md) · [ไทย](README.th.md)

---

## Table of contents

- [Honest status](#honest-status)
- [What it does](#what-it-does)
- [Architecture](#architecture)
- [Safety and risk controls](#safety-and-risk-controls)
- [Monitoring and alerting](#monitoring-and-alerting)
- [Getting started](#getting-started)
- [Running live and paper nodes](#running-live-and-paper-nodes)
- [Running as systemd services](#running-as-systemd-services)
- [Configuration](#configuration)
- [Repository layout](#repository-layout)
- [Testing](#testing)
- [Roadmap](#roadmap)
- [Disclaimer](#disclaimer)
- [License](#license)

---

## Honest status

This is **research-grade software in live validation**, not a finished money-making product.

- Trading is real but conducted on a **small capital budget** (order of tens of euros), intentionally bounded so that bugs and drawdowns are affordable while the engine is proven out.
- Strategies are first validated in a **realistic paper-trading engine** before any live capital is committed, and live capital is supposed to be increased in **stages** only after stat-based thresholds are met (see [Roadmap](#roadmap)).
- Past attempts have **not consistently produced strong results**. The current codebase reflects lessons from those attempts: an emphasis on kill-switches, stop-losses, pre-flight checks, and honest accounting of fees/slippage rather than on optimistic forecasts.
- No figure in this repository is a promise of future returns. See the [Disclaimer](#disclaimer).

Treat this repository as a reference for how-not-to and how-to operate a small algorithmic trading fleet — and manage your own expectations accordingly.

---

## What it does

The engine runs **two-sided grid trading**: it places buy orders as the price falls within a configured ladder of levels, and sell orders at take-profit levels above, harvesting small gains from oscillation while holding inventory between the levels. Several strategy families live under `denaro/domain/` (grid, momentum, mean-reversion, adaptive/volatility and regime-aware variants); the node engine around them is shared and exchange-agnostic.

Core traits:

- **Unified engine, many markets.** The same `denaro.denaro_node` process, configured via a YAML file, runs any combination of live and paper markets with per-bot capital, symbols, levels and risk settings.
- **Realistic paper trading.** A dedicated paper engine applies real exchange fees, minimum notional, slippage and stop-losses so that simulation results are comparable to live behaviour.
- **Exchange-agnostic.** All order and market-data access sits behind an adapter layer (CCXT-based) in `denaro/infrastructure/exchanges`, so strategies never talk to a specific exchange.
- **Performance orientation.** Asynchronous I/O, WebSocket price feeds with ZMQ fan-out, rate limiting, and a supervisor that throttles ticks under CPU/RAM pressure.

---

## Architecture

The fleet is distributed across three machine classes by role, not by a fixed topology:

- **Trading nodes** — VPS hosts (the project currently uses two, referred to as nodes) that run one or more `denaro_node` processes. Each interprets its own `config/node_*.yaml` and reports health.
- **Monitoring host** — a machine that aggregates node health and runs monitoring. In this deployment it sits behind CGNAT and is reached only through **reverse SSH tunnels** originated by the trading nodes, so no inbound firewall rule is required.
- **Optional orchestration / feeder tiers** — the engine also includes a "brain"/feeder layer used to coordinate higher-level decisions and feed signals between components.

A simplified view of the runtime relationships:

```
┌──────────────┐   ┌──────────────┐     ┌──────────────┐
│   NODE A     │   │   NODE B     │     │  ORCHESTRATOR│
│ denaro_node  │   │ denaro_node  │     │ (optional)   │
│ grid markets │   │ grid markets │     │  brain/feed  │
└──────┬───────┘   └──────┬───────┘     └──────┬───────┘
       │                  │                    │
       └─────────┬────────┴────────────────────┘
                 │   health / metrics over network
        ┌────────▼─────────┐
        │   MONITORING     │   Zabbix server + web dashboard
        │   (aggregates,   │   reachable over reverse SSH tunnel
        │    https access) │
        └──────────────────┘
```

Communication, control-plane and monitoring details depend on the deployment; the mechanism currently used is **reverse SSH tunnels (autossh)** so that even a NATed host can be reached and can act as the monitoring server.

---

## Safety and risk controls

Risk management is a first-class concern, baked into the node engine rather than bolted on per strategy:

- **Stop-loss** per bot and a **global daily / weekly circuit-breaker** that halts a symbol or node when configured loss limits are crossed.
- **Pre-flight checks** before every order placement (anti-deadlock validation and position sizing) so a misconfigured or stale bot cannot trade blindly.
- **Safe mode** — a graduated set of throttle states (caution → safe → emergency) driven by the supervisor (RAM/CPU/tick pressure) that progressively slows or stops a node before resources are exhausted.
- **Sub-accounts.** Live OKX/Kraken trading runs on dedicated exchange **sub-accounts**, never on the main account, so operating mistakes stay contained.
- **Credentials** live only in a local `.env` (never committed) and are loaded at runtime.
- **Live budget staging.** Capital is grown in explicit stages (paper → small live → larger live) and only after the recorded triggers in the roadmap are met.

---

## Monitoring and alerting

- **Zabbix** is used as the aggregation and alerting backend. Nodes push metrics (equity, per-bot PnL, pre-flight blocks, stale health, resource pressure) to the Zabbix **trapper**.
- Triggers exist for: circuit-breaker crossings, daily/weekly loss, stale heartbeats, pre-flight blocks, resource pressure.
- **Auto-heal is disabled by default.** Early iterations restarted live bots spuriously; recovery is now a deliberate, logged action rather than an automatic restart.
- A read-only **web dashboard** provides an at-a-glance view of node and bot health.

---

## Getting started

Requirements:

- Python **3.12+**
- A `uv` or `venv` environment
- Docker + Docker Compose only if you also run the Zabbix monitoring stack
- Exchange API keys for OKX and/or Kraken (in a local `.env`, never committed)

Clone and install:

```bash
git clone git@github.com:grivetto/alpha-omega-trading.git
cd alpha-omega-trading

python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env      # then fill in your API keys
```

---

## Running live and paper nodes

The engine is a console application driven by a config file:

```bash
# Live grid node (per config file)
python -m denaro.denaro_node --config config/node.yaml

# Paper trading node
python -m denaro.denaro_node --config config/node_paper.yaml

# A Kraken trend-following live config (example)
python -m denaro.denaro_node --config config/node_trend_live_kraken.yaml
```

Additional provided configs (`config/node_nuvola.yaml`, `config/node_mc2.yaml`, `config/node_adaptive_vol_grid_paper.yaml`, …) correspond to specific node/strategy roles; see the [Configuration](#configuration) section.

Run `python -m denaro.denaro_node --help` for flags (`--verbose` is supported).

---

## Running as systemd services

For production nodes, unit files are provided under `systemd/`. Typical steps on a given host:

```bash
sudo cp systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now denaro-node            # name depends on the host role
```

Unit files currently cover node, health, aggregator, dashboard, feeder and the reverse-tunnel (`zabbix-tunnel`) roles. **Adjust the `ExecStart` paths** in the units to match the user home, repository path and venv used on each host — the shipped values reflect one specific deployment.

---

## Configuration

Each node reads a YAML file that defines, among other things:

- `exchange_rest`: exchange (e.g. `okx`) and EEA mode.
- `bots`: a list of markets, each with symbol, `mode` (`live`/`paper`), `capital`, grid `levels` and strategy-specific settings.
- `safemode`: the RAM/CPU throttle thresholds (`caution_pct`, `safe_pct`, `emergency_pct`) and their interval.
- `supervisor`: resource-critical thresholds and tick throttling.
- `data_dir`: where the node persists runtime state and market data.

Keep exchange credentials out of config files — put them in `.env` and load them at runtime.

---

## Repository layout

```
config/                  Per-node YAML configuration
denaro/
  domain/                Strategies and risk/regime/indicator logic (grid, momentum, adaptive, …)
  application/           Orchestration: portfolio, supervisor, safe-mode
  infrastructure/        Exchange adapters (CCXT), market data, storage, feeder
  denaro_node.py         Unified node entry point
scripts/                 Deployment helpers
systemd/                 systemd unit files (node, health, aggregator, tunnel, …)
zabbix/                  Monitoring integration (healer, push_metrics)
tests/                   Tests
.env.example             Credential template (keys never committed)
```

---

## Testing

The project uses `pytest` (with `pytest-asyncio` for the async layers). Install the dev extras and run:

```bash
pip install -e ".[dev]"
pytest
```

---

## Roadmap

- [ ] Sustain a validated live record over a defined observation window (e.g. several weeks per bot).
- [ ] Automatic promotion gates: a strategy may receive more capital only when it clears the recorded thresholds (profit factor, max drawdown, Sharpe).
- [ ] Staged capital increase (paper → small live → 100–500 EUR → 1000 EUR) as conditions are met.
- [ ] Monitoring templates with equity/PnL/volume charts per bot.
- [ ] Cleaner packaging: align `pyproject.toml` metadata with the actual `denaro` package layout.

---

## Disclaimer

**This software is provided for educational and research purposes only. It is not financial advice.** Algorithmic trading of crypto assets carries substantial risk, including total loss of the deployed capital. Past or paper performance does not guarantee future results; fees, slippage, liquidity gaps and exchange outages can all turn a profitable backtest into a losing live campaign. Only deploy capital you can afford to lose entirely, and never trade with money you rely on. The authors accept no liability for any loss arising from the use of this code.

---

## License

Public domain (CC0-equivalent). See the [LICENSE](LICENSE) file for the full dedication — no rights reserved; use, copy, modify and sell freely, at your own risk.
