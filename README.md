# 🏦 Denaro — Automated Trading System

> *"Sopravvivenza → Protezione → Intelligenza → Professionalità"*

Sistema di trading automatico su Binance, distribuito su server dedicati con strategie multi-timeframe, grid trading adattivo e gestione production-grade via systemd.

## 🏗 Architettura

### Panoramica

```
┌─────────────────────────────────────────────────────────┐
│                    DENARO v3.3                          │
│              Automated Trading System                   │
├─────────────┬──────────────────┬────────────────────────┤
│   MC2       │     NUVOLA       │      MARCODG1          │
│  (On-Prem)  │   (Cloud VPS)    │    (Cloud VPS)         │
│             │                  │                        │
│ ┌─────────┐ │ ┌──────────────┐ │ ┌──────────────────┐  │
│ │ Squadra │ │ │  Grid Bot    │ │ │   Grid Bot       │  │
│ │ 4 bot   │ │ │  SOL/EUR     │ │ │   ADA/EUR        │  │
│ │         │ │ │              │ │ │                  │  │
│ │ Ares    │ │ │  Adaptive    │ │ │   Adaptive       │  │
│ │ Hermes  │ │ │  Volatility  │ │ │   Volatility     │  │
│ │ Apollo  │ │ │  Grid        │ │ │   Grid           │  │
│ │ Artemis │ │ │              │ │ │                  │  │
│ └─────────┘ │ └──────────────┘ │ └──────────────────┘  │
│ ┌─────────┐ │                  │                        │
│ │Dashboard│ │                  │                        │
│ │ :8899   │ │                  │                        │
│ └─────────┘ │                  │                        │
└─────────────┴──────────────────┴────────────────────────┘
```

### Flotta Server

#### MC2 — Cacciatore HFT Isolato
- **Host:** `mc2` (on-premise, Intel N150, 16GB RAM)
- **Ruolo:** Squadra di 4 bot direzionali + Dashboard
- **Porta:** 2222 (SSH), 8899 (Dashboard)
- **API Key:** BINANCE_API_KEY / BINANCE_API_SECRET

| Bot | Copia | Timeframe | Strategia |
|-----|-------|-----------|-----------|
| **Ares** | ETH/EUR | 5m | Trend following |
| **Hermes** | SOL/EUR | 15m | RSI + MACD + Sentiment |
| **Apollo** | ETH/BTC | 1h | Ratio mean-reversion (z-score) |
| **Artemis** | BTC/EUR | 1d | SMA50/200 crossover |

- **Servizio:** `denaro-squadra.service` (systemd, auto-restart)
- **Budget:** ~€228 portfolio, capital pooling dinamico
- **Risk Manager:** integrato con ATR-vol position sizing, SL/TP 1.5x/3x ATR
- **Cost Model:** fee 0.1% + slippage 0.1%, round-trip ~0.4%

#### Nuvola — Grid Trading SOL/EUR
- **Host:** `nuvola` (cloud VPS)
- **Ruolo:** Grid trading adattivo su SOL/EUR
- **API Key:** BINANCE_API_KEY / BINANCE_API_SECRET (condivisa con MARCODG1)

| Parametro | Valore |
|-----------|--------|
| Coppia | SOL/EUR |
| Livelli | 7 |
| Range | 2.5% |
| Profit | 0.5% |
| Base order | €10 |
| Max invested | €70 |

- **Servizio:** `denaro-grid.service` (systemd, auto-restart)
- **Strategia:** Adaptive volatility grid + martingale 1.12x

#### MARCODG1 — Grid Trading ADA/EUR
- **Host:** `MARCODG1` (cloud VPS)
- **Ruolo:** Grid trading adattivo su ADA/EUR
- **API Key:** BINANCE_API_KEY / BINANCE_SECRET_KEY (condivisa con Nuvola)

| Parametro | Valore |
|-----------|--------|
| Coppia | ADA/EUR |
| Livelli | 5 |
| Range | 10% |
| Profit | 0.8% |
| Base order | €6 |
| Max invested | €60 |

- **Servizio:** `denaro-grid.service` (systemd, auto-restart)
- **Strategia:** Adaptive volatility grid + martingale 1.15x

### Componenti Condivisi

```
denaro/
├── grid_bot_v3.py          # Grid bot (Nuvola + MARCODG1)
│   ├── init_grid()         # Inizializzazione livelli con precisione adattiva
│   ├── on_tick()           # Loop principale (5s)
│   ├── on_fill()           # Gestione fill ordini
│   └── trailing_stop_check() # Stop loss trailing
├── denaro_core.py          # Core API Binance (estende DenaroCore)
├── denaro_strategies.py    # Strategie grid
│   ├── AdaptiveTrendFilter # Filtro trend adattivo
│   ├── VolatilityGrid      # Calcolo spacing da ATR
│   └── MartingaleLite      # Position sizing progressivo
├── grid_config.json        # Config grid (per-server)
├── orchestrator.py         # Dashboard HTTP server (:8899) + RiskManager
│   ├── RiskManager         # Position sizing ATR-vol
│   ├── cost_model()        # Fee + slippage filter
│   └── kill-switch         # Drawdown protection
├── trade_db.py             # SQLite (vault, trades, daily PnL)
├── squadra/                # Bot direzionali (mc2)
│   ├── ares_bot.py
│   ├── hermes_bot.py
│   ├── apollo_bot.py
│   ├── artemis_bot.py
│   ├── orchestrator.py     # SquadraOrchestrator
│   └── run_squadra.py      # Entry point
├── utils/
│   ├── indicators.py       # RSI, MACD, ATR, SMA
│   ├── risk_engine.py      # Gestione rischio
│   ├── exit_strategy.py    # Strategie uscita
│   ├── entry_filters.py    # Filtri ingresso
│   └── sentiment.py        # Social sentiment engine
└── dashboard/              # UI web (:8899)
    ├── index.html
    ├── grid.html
    └── trades.html
```

### Ciclo di Funzionamento

```
┌──────────┐     ┌──────────┐     ┌──────────┐
│  Binance │────→│ WebSocket│────→│  on_tick │
│  Market  │     │  Stream  │     │  (5s)    │
└──────────┘     └──────────┘     └────┬─────┘
                                       │
                    ┌──────────────────┼──────────────────┐
                    ↓                  ↓                  ↓
              ┌──────────┐     ┌──────────┐     ┌──────────┐
              │  Grid    │     │  Trend   │     │  Risk    │
              │  Init    │     │  Check   │     │  Check   │
              └────┬─────┘     └────┬─────┘     └────┬─────┘
                   │                │                 │
                   ↓                ↓                 ↓
              ┌──────────┐     ┌──────────┐     ┌──────────┐
              │  Place   │     │  Entry   │     │  Kill    │
              │  Orders  │     │  Signal  │     │  Switch  │
              └──────────┘     └──────────┘     └──────────┘
```

### Sicurezza e Risk Management

- **Kill Switch:** drawdown protection con soglia configurabile
- **Stop Loss:** ATR-based, 1.5x ATR dal prezzo di entry
- **Take Profit:** ATR-based, 3x ATR dal prezzo di entry
- **Cost Filter:** blocca trade con profitto netto negativo (fee + slippage)
- **Anti-duplicate:** verifica ordini esistenti prima di piazzare
- **Precisione adattiva:** decimali dinamici per asset a basso prezzo (ADA: 4 dec)

## 📊 Dashboard

Servita da `orchestrator.py` su **porta 8899** (mc2):

```
http://mc2:8899
```

Mostra: vault status, bot attivi, PnL giornaliero, grafici prezzi, allocazione capitale.

## 🚀 Setup

```bash
# Clone
git clone git@github.com:grivetto/denaro.git
cd denaro

# Ambiente virtuale
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configurazione
cp .env.example .env
# Editare .env con le API keys Binance

# Avvio
python3 grid_bot_v3.py        # Grid bot
python3 squadra/run_squadra.py # Squadra bot
```

## 📋 Comandi Rapidi

```bash
# Stato servizi
ssh mc2   'sudo systemctl status denaro-squadra denaro-dashboard'
ssh nuvola 'sudo systemctl status denaro-grid'
ssh MARCODG1 'sudo systemctl status denaro-grid'

# Log in tempo reale
ssh mc2 'sudo journalctl -fu denaro-squadra'

# Riavvio servizio
ssh mc2 'sudo systemctl restart denaro-squadra'
```

## 📁 Branches

- `grivetto/dolari` — attuale (production, systemd, risk management)
- `grivetto/money` — precedente (pulizia + systemd)
- `refactoring` — legacy
- `main` — stabile legacy

## 📄 Licenza

MIT License — vedi [LICENSE](LICENSE)

## 📬 Contatti

**Owner:** Sergio Grivetto
**Email:** sergio@grivetto.eu
