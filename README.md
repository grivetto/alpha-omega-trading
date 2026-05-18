# 🏦 Denaro — Automated Trading System

Bot trading automatici per Binance, eseguiti su server dedicati con strategie multi-timeframe e gestione systemd.

```
Sopravvivenza → Protezione → Intelligenza → Professionalità
```

## 🔬 Linea di Concetto

Denaro è nato come collezione di bot sparsi, poi evoluto in un sistema a ciclo chiuso:

1. **Sopravvivenza** — non perdere capitale. Circuit breaker, adaptive sizing, self-healing.
2. **Protezione** — capital preservation come priority #1. Risk engine, stop-loss sistematici.
3. **Intelligenza** — auto-apprendimento. Sentiment engine, optimizer volatilità, feedback loop.
4. **Professionalità** — infrastruttura production-grade. systemd, watchdog, monitoring, log strutturati.

### Ciclo Autonomo

```
TRADING → ANALISI → OTTIMIZZAZIONE → RIDEPLOY
```

> *Il tempo è letteralmente denaro. L obiettivo è posizionare nodi sentinella accanto ai server delle borse per intercettare l evento e agire prima che il resto del mondo se ne accorga.* — Progetto Orbital Strike (visione futura)

## Stato Attuale — v3.3

Gestito via **systemd** su tutti i server. Nessun tmux.

### mc2 (192.168.1.116) — Squadra (4 bot)

| Bot | Simbolo | Timeframe | Strategia |
|-----|---------|-----------|-----------|
| **Ares** | ETH/EUR | 1m | Trend following |
| **Hermes** | SOL/EUR | 1m | RSI + MACD + Social Sentiment |
| **Apollo** | ETH/BTC | 1h | Ratio mean-reversion |
| **Artemis** | BTC/EUR | 1d | SMA50/200 crossover |

- Systemd: denaro-squadra.service — auto-restart, log via journald
- Budget base: €125.58 EUR (capital pooling dinamico fino a 15%)

### Nuvola (192.168.1.117) — Grid Bot

| Bot | Simbolo | Strategia |
|-----|---------|-----------|
| **GridBot** | SOL/EUR | Grid adaptive + volatility tiers |

- Systemd: denaro-grid.service
- Usa denaro_core.py + denaro_strategies.py (condivisi con squadra)

### MARCODG1 (192.168.1.120) — Grid Bot

| Bot | Simbolo | Strategia |
|-----|---------|-----------|
| **GridBot** | ADA/EUR | Grid adaptive |

- Systemd: denaro-grid.service
- API key Binance da ripristinare

## Dashboard

Servita da orchestrator.py su porta 8899 (mc2) con UI in dashboard/.

```
http://mc2:8899
https://sgrivett.ddns.net/denaro/  (se proxy HTTPS configurato)
```

## Struttura del Repository

```
denaro/
  squadra/                  Bot squadra (4 bot su mc2)
    hermes_bot.py           Hermes v3.3 con sentiment
    ares_bot.py             Ares trend follower
    apollo_bot.py           Apollo ETH/BTC ratio
    artemis_bot.py          Artemis SMA crossover
    core.py                 Core Binance API + save_bot_state
    orchestrator.py         SquadraOrchestrator
    run_squadra.py          Entry point
    strategies/             Strategie per bot
    config/                 Config JSON
  utils/
    indicators.py           Indicatori tecnici
    risk_engine.py          Gestione rischio
    exit_strategy.py        Strategie di uscita
    entry_filters.py        Filtri di ingresso
    sentiment.py            Social sentiment engine
  dashboard/
    index.html              Dashboard live
    grid.html               Grid view
    trades.html             Trade history
    public/                 Dati JSON
  orchestrator.py           Dashboard HTTP server (:8899) + DenaroCore
  trade_db.py               SQLite DB (vault, trades, daily PnL)
  grid_bot_v3.py            Grid bot condiviso (Nuvola + MARCODG1)
  denaro_core.py            Core condiviso grid
  denaro_strategies.py      Strategie grid
  grid_config.json          Config grid
  collect_dashboard_data.py  Data collector
  ...
  requirements.txt
```

## Comandi Rapidi

```
# Stato servizi
ssh mc2   'sudo systemctl status denaro-squadra denaro-dashboard'
ssh nuvola 'sudo systemctl status denaro-grid'

# Log in tempo reale
ssh mc2 'sudo journalctl -fu denaro-squadra'

# Riavvio servizio
ssh mc2 'sudo systemctl restart denaro-squadra'

# Test sentiment
python3 -c "from utils.sentiment import SentimentEngine; print(SentimentEngine().analyze('BTC'))"
```

## Branches
- grivetto/money — attuale (pulizia + systemd)
- refactoring — precedente
- main — stabile legacy
