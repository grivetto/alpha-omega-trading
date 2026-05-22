<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://placehold.co/600x120/0d1117/58a6ff?text=βενάρο&font=source-code-pro">
    <img src="https://placehold.co/600x120/f0f0f0/1f1f1f?text=βενάρο&font=source-code-pro" width="480">
  </picture>
  <br>
  <em>Multi‑Strategy Trading Fleet — 24/7 on Binance Spot</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12+-blue?logo=python&logoColor=white">
  <img src="https://img.shields.io/badge/Binance-CCXT-F0B90B?logo=binance&logoColor=white">
  <img src="https://img.shields.io/badge/Status-Production-brightgreen">
  <img src="https://img.shields.io/badge/Bots-3+2-resilient">
  <img src="https://img.shields.io/badge/License-MIT-3da639">
</p>

---

## Fleet Topology

```
                          ┌──────────────────────────────────────┐
                          │           BINANCE SPOT               │
                          │    ADA/EUR  SOL/EUR  BTC/EUR …       │
                          └────────────┬──────────┬──────────────┘
                                       │          │
              ┌────────────────────────┼──────────┼──────────────────┐
              │                        │          │                  │
     ┌────────▼────────┐    ┌──────────▼──┐  ┌───▼──────────┐      │
     │     NUVOLA      │    │  MARCODG1   │  │     MC2      │      │
     │  (Cloud VPS)    │    │ (Cloud VPS) │  │  (On‑Prem)   │      │
     │                 │    │             │  │              │      │
     │  Stellatron ◄───┤    │ MarcoSOL ◄──┤  │ ORION ◄─────┤      │
     │  ADA grid       │    │ SOL reversal│  │ BTC/ETH/BNB  │      │
     │  +0.88€ profit  │    │ +0.10€      │  │              │      │
     │                 │    │             │  │ ◈ Denaro Mem │      │
     │  ─ legacy ─     │    │ ─ legacy ─  │  │   DB SQLite  │      │
     │  momentum, rsi… │    │ denaro_v3   │  │ ◈ Regime     │      │
     └─────────────────┘    └─────────────┘  │   Detector   │      │
                                              │ ◈ Optimizer  │      │
                                              │ ◈ Capital    │      │
                                              │   Allocator  │      │
                                              │              │      │
                                              │ ─ legacy ─   │      │
                                              │ squadra,     │      │
                                              │ legion…      │      │
                                              └──────────────┘      │
              └──────────────────────────────────────────────────────┘
```

### Servers

| Server  | Type         | IP / Host              | Role                     | Capital |
|---------|-------------|------------------------|--------------------------|---------|
| **nuvola** | Cloud VPS   | 87.106.3.15            | Stellatron (ADA grid)    | ~120€   |
| **MARCODG1** | Cloud VPS | 87.106.222.123         | MarcoSOL (SOL reversal)  | ~20€    |
| **mc2**     | On‑Prem     | 192.168.1.99:2222      | ORION + Memory System    | ~80€    |

---

## Active Bots

### 🤖 Stellatron — Adaptive Grid (nuvola)

Grid trading su ADA/EUR con auto‑compounding e switching automatico del pair.

| Parametro | Valore |
|-----------|--------|
| **Grid spacing** | 0.12–0.30% _(adattivo)_ |
| **Ordine base** | 5.50€ |
| **Grid levels** | 3–6 |
| **Compound** | fino a 1.8× |
| **Max invested** | 50€ |
| **Ciclo** | 30s check, 3min rebalance |

> **Stato**: 81 fills, +0.88€ cumulative profit. Parametri auto‑regolati dal Denaro Memory System in base a volatilità e win rate.

### 🔄 MarcoSOL — Reversal Cycle (MARCODG1)

Compra SOL in dip (-0.4%), vende in pump (+0.5%). Ciclo sell→buy→sell→buy.

| Parametro | Valore |
|-----------|--------|
| **Sell raise** | 0.32% _(adattivo)_ |
| **Buy drop** | −0.26% _(adattivo)_ |
| **Max buy** | 6.00€ |
| **Ciclo** | 5s check |

> **Stato**: 1 fill completo, +0.10€ profit. Spread dinamico calibrato su fill time medio.

### 🎯 ORION — Multi‑Asset Reversal (mc2)

Tre reversal indipendenti su BTC, ETH, BNB.

| Pair | Sell raise | Buy drop | Ordine |
|------|-----------|---------|--------|
| BTC/EUR | 0.4% | −0.3% | 0.00015 BTC |
| ETH/EUR | 0.4% | −0.3% | 0.003 ETH |
| BNB/EUR | 0.4% | −0.3% | 0.002 BNB |

> **Stato**: 300+ trades registrati. Supporta auto‑pausa su perdite consecutive (3+ loser → PAUSED).

---

## 🧠 Denaro Memory System

Sistema di auto‑apprendimento centralizzato su **mc2**. Ogni bot scrive trades nel DB, il sistema analizza e restituisce parametri ottimizzati.

```
┌──────────────────────────────────────────────────────────────────┐
│                        mc2 — MEMORY SYSTEM                       │
│                                                                  │
│  ┌────────────────┐    ┌──────────────┐    ┌──────────────────┐  │
│  │  memorize_     │───▶│  denaro_     │◀───│  regime_detector │  │
│  │  trades.py     │    │  memory.db   │    │  (ogni 5 min)    │  │
│  │  (ogni 1 min)  │    │  (SQLite)    │    └──────────────────┘  │
│  └────────────────┘    └──────┬───────┘                          │
│                               │                                  │
│                    ┌──────────▼──────────┐                       │
│                    │  strategy_optimizer │─── params_{bot}.json  │
│                    │    (ogni 30 min)    │─── via sync → bots    │
│                    └─────────────────────┘                       │
│                    ┌─────────────────────┐                       │
│                    │  capital_manager    │─── allocazione EUR    │
│                    │    (ogni 30 min)    │─── riserva 20€        │
│                    └─────────────────────┘                       │
│                                                                  │
│  orchestrator.py ← API endpoints su :8899                       │
│  └─ /api/regime          — regime corrente                      │
│  └─ /api/params/<bot>    — parametri ottimizzati                │
│  └─ /api/memory/stats    — performance trade per bot            │
│  └─ /api/memory/trades   — storico trades                       │
│  └─ /api/memory/summary  — riepilogo DB                         │
└──────────────────────────────────────────────────────────────────┘
```

### Componenti

| Modulo | Frequenza | Descrizione |
|--------|-----------|-------------|
| `memorize_trades.py` | 1 min | Sincronizza trades da Binance myTrades, calcola PnL FIFO |
| `regime_detector.py` | 5 min | Classifica mercato: trending / ranging / volatile / quiet |
| `strategy_optimizer.py` | 30 min | Calibra grid_spacing, spread, order_size per ogni bot |
| `capital_manager.py` | 30 min | Alloca EUR tra bot, tiene riserva 20€ |
| `orchestrator.py` | sempre su :8899 | API HTTP + risk management + circuit breaker |

### Esempio: ciclo di auto‑miglioramento

```
1. 🔄 memorize_trades.py → registra trade completato nel DB
2. 📊 regime_detector.py → "mercato quieto (vol=0.17%)"
3. ⚙️ strategy_optimizer.py → "riduci grid_spacing a 0.12%"
4. 📨 sync_dashboard.sh → copia params_stellatron.json su nuvola
5. 🤖 stellatron.py → carica nuovi parametri al prossimo refresh
```

---

## Project Structure

```
denaro/
│
├── stellatron.py           # Adaptive grid (ADA/EUR) — nuvola
├── marco_sol.py            # SOL reversal cycle — MARCODG1
├── orion.py                # Multi‑asset reversal — mc2
├── orchestrator.py         # Core HTTP API + risk mgmt — mc2 :8899
│
├── denaro_memory.py        # SQLite DB manager
├── memorize_trades.py      # Binance → DB sync (1 min)
├── regime_detector.py      # Market regime classifier (5 min)
├── strategy_optimizer.py   # Self‑optimizing params (30 min)
├── capital_manager.py      # Dynamic EUR allocation (30 min)
│
├── dashboard/              # Web dashboard
│   ├── index.html
│   └── public/
│
├── squadra/                # Legacy: Ares, Hermes, Apollo, Artemis
├── zabbix/                 # Zabbix monitoring configs
├── architecture/           # SOP docs
│
├── memory/                 # Daily logs
├── .env                    # Binance API keys (gitignored)
├── README.md
└── LICENSE
```

---

## Quick Start

```bash
# Clone
git clone https://github.com/grivetto/dollari.git
cd dollari

# Install
pip install ccxt python-dotenv

# API keys
echo "BINANCE_API_KEY=your_key" > .env
echo "BINANCE_API_SECRET=your_secret" >> .env

# Run a bot (example: Stellatron)
python3 stellatron.py

# Memory system (on mc2)
python3 denaro_memory.py          # init DB
python3 regime_detector.py        # manual regime detection
python3 strategy_optimizer.py     # manual optimization
```

### Cron (on mc2)

```
* * * * *   python3 memorize_trades.py
*/5 * * * * python3 regime_detector.py
*/30 * * * * python3 strategy_optimizer.py
*/30 * * * * python3 capital_manager.py
```

---

## Risk Management

| Guardia | Soglia | Azione |
|---------|--------|--------|
| **Liquidity Reserve** | 20€ EUR | Mai allocata ai bot |
| **Daily Loss Limit** | −3% | Pausa 30 min |
| **Max Drawdown** | −10% | Kill switch automatico |
| **Min Notional** | 5€ per ordine | Salta ordini sotto soglia |
| **Max Exposure** | 60% per bot | Limite allocazione |

---

## License

MIT — see [LICENSE](LICENSE).

<p align="center">
  <sub>Built with Python, CCXT, and too much espresso.</sub>
  <br>
  <sub>Sergio Grivetto · <a href="mailto:sergio@grivetto.eu">sergio@grivetto.eu</a></sub>
</p>
