# 🏦 Denaro — Automated Trading System

Bot trading automatici per Binance, eseguiti su server dedicati con strategie multi-timeframe.

```
Sopravvivenza → Protezione → Intelligenza → Professionalità
```

## 🔬 Linea di Concetto

Denaro è nato come collezione di bot sparsi, poi evoluto in un sistema a ciclo chiuso:

1. **Sopravvivenza** — non perdere capitale. Circuit breaker, adaptive sizing, self-healing.
2. **Protezione** — capital preservation come priority #1. Risk engine, stop-loss sistematici.
3. **Intelligenza** — auto-apprendimento. Sentiment engine, optimizer volatilità, feedback loop.
4. **Professionalità** — infrastruttura production-grade. systemd, tmux, watchdog, monitoring.

### Ciclo Autonomo

```
TRADING → ANALISI → OTTIMIZZAZIONE → RIDEPLOY
```

> *"Il tempo è letteralmente denaro. L'obiettivo è posizionare nodi sentinella accanto ai server delle borse per intercettare l'evento e agire prima che il resto del mondo se ne accorga."* — Progetto Orbital Strike (visione futura)

## Stato Attuale — v3.2

Squadra attiva su **mc2** (192.168.1.116). Budget totale: **€125.58 EUR**.

| Bot | Simbolo | Timeframe | Strategia |
|-----|---------|-----------|-----------|
| **Ares** | ETH/EUR | 1m | Trend following |
| **Hermes** | SOL/EUR | 1m | RSI + MACD + Social Sentiment |
| **Apollo** | ETH/BTC | 1h | Ratio mean-reversion |
| **Artemis** | BTC/EUR | 1d | SMA50/200 crossover |

### Esecuzione
- Tmux session `squadra_bot` su mc2 (192.168.1.116)
- Watchdog Cron via `collect_all.sh` ogni 5 minuti
- `test_mode` flag in `squadra/config/squadra.json` per dry-run

### Sentiment Engine (Nuovo in v3.2)
Integrato in Hermes con peso 0.15 (15%) via `utils/sentiment.py`:
- **Fear & Greed Index** — funzionante, API gratuita
- **X/Twitter search** — OAuth 1.0a configurato, crediti Free tier esauriti
- **Crypto news (CoinPaprika + CryptoCompare)** — fallback funzionante

## Struttura

```
denaro/
├── squadra/                  # Bot squadra (attivi)
│   ├── hermes_bot.py         # Hermes v3.2 con sentiment
│   ├── ares_bot.py           # Ares trend follower
│   ├── apollo_bot.py         # Apollo ETH/BTC ratio
│   ├── artemis_bot.py        # Artemis SMA crossover
│   ├── core.py               # Core Binance API
│   ├── orchestrator.py       # Orchestratore multi-bot
│   ├── run_squadra.py        # Entry point squadra
│   ├── strategies/           # Strategie per bot
│   └── config/               # Config per bot
├── utils/
│   ├── indicators.py         # Indicatori tecnici
│   ├── risk_engine.py        # Gestione rischio
│   ├── exit_strategy.py      # Strategies di uscita
│   ├── entry_filters.py      # Filtri di ingresso
│   └── sentiment.py          # Social sentiment engine
├── dashboard/
│   ├── index.html            # Dashboard live
│   ├── grid.html             # Grid view
│   ├── trades.html           # Trade history view
│   └── public/               # Dati JSON
├── dashboard_server.py       # Server dashboard
├── grid_bot_v3.py            # Legacy grid bot (non attivo)
├── collect_dashboard_*.py    # Data collectors
└── collect_all.sh            # Watchdog script
```

## Server

| Server | IP | Stato | Ruolo |
|--------|-------|-------|-------|
| **mc2** | 192.168.1.116 | ✅ Attivo | Squadra (4 bot) |
| **Nuvola** | 192.168.1.117 | ✅ Attivo | Grid bot legacy |
| **MARCODG1** | 192.168.1.120 | ❌ Decommissionato | — |

## Dashboard live
https://sgrivett.ddns.net/denaro/

## Comandi Rapidi

```bash
# Avviare squadra
cd ~/denaro && python3 squadra/run_squadra.py

# Test startup
python3 squadra/test_startup.py

# Collettore dati
python3 collect_dashboard_data.py

# Sentiment test (singolo simbolo)
python3 -c "from utils.sentiment import SentimentEngine; print(SentimentEngine().analyze('BTC'))"
```

## Branches
- `refactoring` — sviluppo attuale (versione pulita)
- `main` — stabile precedente
