# 🏦 Denaro — Distributed Trading System

Sistema di trading distribuito su 3 server, unico conto Binance. Combina grid trading classico con una squadra di bot opportunistici.

## 📡 Architettura

```
┌──────────────────────────────────────────────────┐
│                   Binance API                     │
│         (unico conto, 3 API key diverse)          │
└────────┬──────────────┬──────────────┬────────────┘
         │              │              │
    ┌────▼────┐    ┌────▼────┐    ┌────▼────┐
    │   mc2   │    │ Nuvola  │    │MARCODG1 │
    │ Squadra │    │Grid SOL │    │Grid ADA │
    └────┬────┘    └────┬────┘    └────┬────┘
         │              │              │
         └──────────────┴──────────────┘
                    │
              ┌─────▼──────┐
              │  Dashboard │
              │ (nuvola)   │
              └────────────┘
```

### 📍 Server

| Server | Ruolo | Bot attivi |
|--------|-------|------------|
| **mc2** | Orchestratore | Squadra Opportunistica (Ares, Hermes, Apollo) |
| **Nuvola** | Grid | Grid SOL/EUR v3 |
| **MARCODG1** | Grid | Grid ADAEUR v3 |

## 🤖 Bot attivi

### Squadra Opportunistica (mc2)
Tre bot coordinati dall'orchestratore, budget 80€ max:

| Bot | Strumento | Strategia | Base |
|-----|-----------|-----------|------|
| **Ares** | ETH/EUR | Trend following | 10€ |
| **Hermes** | SOL/EUR | Sentiment (RSI+volume) | 8€ |
| **Apollo** | ETH/BTC | Mean reversion ratio | 8€ |

Ogni bot opera in autonomia, l'orchestratore gestisce risk management centralizzato e kill switch a -5% drawdown.

### Grid Bots
Due grid bot classici su coppie separate:

- **SOL/EUR** (Nuvola): Grid 3 livelli, base 5€
- **ADAEUR** (MARCODG1): Grid 3 livelli, base 7€×3

## 📊 Monitoraggio

- Dashboard live: https://sgrivett.ddns.net/denaro/
- Dati aggiornati ogni 5 min via `collect_all.sh`
- Watchdog automatico ogni 5 min (riavvia bot se crashano)

## 🛠 Struttura directory

```
denaro/
├── squadra/                    # Squadra Opportunistica
│   ├── ares_bot.py            # Trend ETH/EUR
│   ├── hermes_bot.py          # Sentiment SOL/EUR
│   ├── apollo_bot.py          # Ratio ETH/BTC
│   ├── orchestrator.py        # Coordinatore
│   ├── core.py                # Modello e DB
│   ├── run_squadra.py         # Entry point
│   ├── config/                # Configurazioni JSON
│   └── squadra_watchdog.sh    # Watchdog tmux
├── grid_bot_v3.py             # Grid bot template
├── dashboard/                 # Frontend dashboard
├── architecture/              # Procedure operative
├── utils/                     # Moduli condivisi
├── collect_all.sh             # Raccolta dati dashboard
├── collect_dashboard_*.py     # Collector per server
├── sync_dashboard.sh          # Sync su web server
└── dashboard_server.py        # Server HTTP locale
```

## 🚀 Avvio rapido

```bash
# Squadra (mc2)
cd ~/denaro && python3 squadra/run_squadra.py

# Grid bot (Nuvola / MARCODG1)
cd ~/denaro && screen -dmS grid_bot venv/bin/python3 grid_bot_v3.py
```

I watchdog si occupano di mantenere i bot in esecuzione.
