# 📜 DENARO — Cronologia Completa delle Conversazioni

> Export per agent Hermes — Contesto storico del sistema di trading Denaro
> Data export: 2026-05-19
> Owner: Sergio Grivetto (sergio@grivetto.eu)

---

## 📋 Indice

1. [Fase 1: Analisi e Diagnosi (15 Maggio)](#fase-1)
2. [Fase 2: Deploy v4.0 e Migrazione EUR (15-16 Maggio)](#fase-2)
3. [Fase 3: Squadra Denaro Opportunistico (17-18 Maggio)](#fase-3)
4. [Fase 4: Grid Bot Fixes e Stabilizzazione (19 Maggio)](#fase-4)
5. [Fase 5: Audit Completo e GitHub (19 Maggio)](#fase-5)
6. [Decisioni Architetturali Chiave](#decisioni)
7. [Lezioni Imparate](#lezioni)
8. [Stato Attuale Sistema](#stato)

---

## Fase 1: Analisi e Diagnosi (15 Maggio) {#fase-1}

### Problema Iniziale
Sergio: *"Devi avviare in maniera approfondita una analisi del perché questo sistema: 1) non produce guadagni, 2) bot crashano o non caricano i dati corretti, 3) il sistema non ha ancora imparato dai suoi errori. Oramai è quasi 4 mesi che è in gioco e sino ad ora ha solo perso."*

### Cause Radici Identificate

**Causa #1: Account Binance MiCA — Solo EUR**
- Il 100% dei trade USDT falliva con errore `-2010`
- L'account Binance è MiCA (solo EUR)
- Il grid bot funzionava perché usava SOL/EUR
- Tutti gli altri bot erano condannati

**Causa #2: Sistema v4.0 Mai Deployato**
- `legion_manager_production.py` non era mai stato eseguito su mc2
- I bot legacy (alpha_strike_scalper, legion_*.py) giravano con bug noti
- Il sistema vero (AutoAdaptiveEngine, RiskManager, ExposureGuard) era fermo

**Causa #3: AutoAdaptiveEngine Mai Attivo**
- Il self-learning era scritto bene ma non aveva mai visto un trade
- `trade_history` vuota — non poteva imparare da dati che non aveva mai visto

### Fix Applicati
1. Conversione tutti gli asset in EUR (€225.43)
2. `SYMBOLS_WS` → 14 coppie EUR (btceur, etheur, xrpeur, soleur, dogeeur, bnbeur, adaeur, suieur, etceur, maticeur, ftmeur, unieur, zileur, wifeur)
3. `exchange_multi.py` → mappa aggiornata con EUR
4. `fetch_balance()` → solo EUR, rimosso USDT
5. `INITIAL_CAPITAL` aggiornato a 225.0€ (da 500€ fittizio)

---

## Fase 2: Deploy v4.0 e Migrazione EUR (15-16 Maggio) {#fase-2}

### Deploy su mc2
- `legion_manager_production.py` v4.0 avviato (PID 530866)
- 12 bot caricati, WebSocket connesso
- 0 trade eseguiti (attesa segnali)

### Problema Nuvola — Python 3.14
- `nuvola` crashava con `sqlite3.OperationalError: unable to open database file`
- Causato da Python 3.14.4 + concorrenza sqlite3 + lock del vecchio grid_bot
- Fix: riscrittura `trade_db.py` con Singleton Connection e `check_same_thread=False`

### Problema MARCODG1
- Deploy non completato
- File v4 presenti ma non avviati

### Parametri Chiave (per €225)
| Parametro | Valore |
|-----------|--------|
| PER_SYMBOL_MAX_EUR | 30€ |
| TP_ATR_MULT | 1.5 |
| SL_ATR_MULT | 0.75 |
| MIN_VOLUME_MULT | 1.0 |
| TRADING_HOURS | 6-22 UTC |
| SCALP_RSI_MAX | 55 |
| DIP_BUY_THRESHOLD | 0.15% |

---

## Fase 3: Squadra Denaro Opportunistico (17-18 Maggio) {#fase-3}

### Nascita della Squadra
Sergio: *"Facciamo funzionare ciò che abbiamo"*

**Bot creati:**
1. **Ares** — ETH/EUR, 5m, trend following
2. **Hermes** — SOL/EUR, 15m, RSI + MACD + Sentiment
3. **Apollo** — ETH/BTC, 1h, ratio mean-reversion (z-score)
4. **Artemis** — BTC/EUR, 1d, SMA50/200 crossover (long-only)

### Fix Applicati
- **Hermes**: Soglia BUY 0.5→0.3 (RSI=16.7 non comprava)
- **Nuvola**: risk_factor 0.20→0.60 (bloccato in STRONG_DOWN)
- **MARCODG1**: rimosso pause su STRONG_DOWN
- **Apollo**: z_entry 2.0→1.5 (mai raggiunto)
- **Kill-switch**: fix drawdown calc (usare total equity, non solo EUR free)

### Risultati
- Portfolio: peak 125€ → current 97.11€ → drawdown 22.31%
- Hermes IN POS su SOL/EUR entry 73.17€ (0.109 SOL)
- Grid Nuvola: 1 buy + 4 sell, 5.58€ invested
- Grid MARCODG1: 2 buy, 14€ invested

---

## Fase 4: Grid Bot Fixes e Stabilizzazione (19 Maggio) {#fase-4}

### Problemi Identificati
1. **WebSocket loop**: `ping_interval=20, ping_timeout=10` — timeout minore del ping_interval
2. **Ordini duplicati**: Nuvola e MARCODG1 piazzavano stessi ordini SOLEUR (stesso account Binance)
3. **Prezzi duplicati ADA**: `round(..., 2)` arrotondava tutti i livelli a 0.21 o 0.22
4. **MARCODG1 hostname**: funziona solo con `MARCODG1` (uppercase nel SSH config)

### Fix Applicati
1. **ping_timeout**: 10s→30s (entrambi i server)
2. **Separazione coppie**: Nuvola→SOL/EUR, MARCODG1→ADA/EUR
3. **Adaptive decimal precision**: 4 decimali per asset <1€, 6 per <0.1€
4. **Anti-duplicate order check**: verifica ordini esistenti prima di piazzare
5. **Config ADA**: 5 livelli, 10% range, base 6€, max 60€

### Stato Grid Dopo Fix
- SOL/EUR (Nuvola): 2 buy + 6 sell, prezzi distinti
- ADA/EUR (MARCODG1): 5 buy + 2 sell, prezzi distinti

---

## Fase 5: Audit Completo e GitHub (19 Maggio) {#fase-5}

### Audit Infrastruttura
**Servizi (tutti attivi):**
- `mc2`: denaro-squadra + denaro-dashboard ✓
- `nuvola`: denaro-grid (SOL/EUR) ✓
- `MARCODG1`: denaro-grid (ADA/EUR) ✓

**Chiavi API Binance:**
- Ogni server ha API key diverse nel `.env`
- MARCODG1: `BINANCE_SECRET_KEY` (il codice usa questa)
- Nuvola: `BINANCE_API_SECRET`
- mc2: `BINANCE_API_KEY`

### GitHub
- Branch `grivetto/dolari` creato e pushato
- README.md riscritto con architettura completa
- Licenza MIT aggiunta
- Contatti: sergio@grivetto.eu

---

## Decisioni Architetturali Chiave {#decisioni}

### 1. Systemd vs Tmux
**Decisione**: Preferire systemd a tmux per gestione servizi
- Auto-restart, log via journald, gestione centralizzata
- Convertire i bot da tmux a systemd quando possibile

### 2. Separazione Coppie Grid
**Decisione**: Nuvola→SOL/EUR, MARCODG1→ADA/EUR
- Entrambi i server usano la stessa API key Binance (stesso account)
- Non piazzare ordini sulla stessa coppia da entrambi

### 3. Risk Management
**Decisione**: RiskManager integrato nell'orchestrator
- Position sizing ATR-vol
- SL/TP: 1.5x/3x ATR
- Cost model: fee 0.1% + slippage 0.1%, round-trip ~0.4%
- Cost filter blocca profitto netto negativo

### 4. Precisione Adattiva
**Decisione**: Decimali dinamici per asset a basso prezzo
- Prezzo < 0.1€: 6 decimali
- Prezzo < 1.0€: 4 decimali
- Prezzo >= 1.0€: 2 decimali

### 5. Kill Switch
**Decisione**: Kill switch con drawdown protection
- Calcolato su total equity (non solo EUR free)
- Emergency position closing quando attivo

---

## Lezioni Imparate {#lezioni}

### 1. Account MiCA
Gli account Binance MiCA supportano solo coppie EUR. I trade USDT falliscono con errore -2010. **Sempre verificare il tipo di account prima di configurare i simboli.**

### 2. WebSocket Stability
Il `ping_timeout` deve essere SEMPRE maggiore del `ping_interval`. Altrimenti il timeout scade prima che arrivi il ping, causando disconnessioni continue.

### 3. Arrotondamento Prezzi
Usare `round(..., 2)` per asset come ADA (0.21€) causa la collisione di tutti i livelli grid. **Sempre adattare i decimali alla magnitudine del prezzo.**

### 4. Stesso Account, Server Multipli
Quando più server usano la stessa API key Binance, non possono piazzare ordini sulla stessa coppia. **Sempre separare le coppie per server.**

### 5. Git Repo
MARCODG1 non ha git repo. Nuvola sì. mc2 sì. **Mantenere il codice sincronizzato via SCP quando manca git.**

### 6. Log Strutturato
I bot non scrivono su file di log. Usare `journalctl` per systemd. **Configurare sempre un path di log dedicato.**

### 7. .env Format
Il file `.env` non può avere `import os` in testa se usato con systemd EnvironmentFile. I nomi delle variabili devono matchare tra `.env` e codice.

---

## Stato Attuale Sistema {#stato}

### Server

| Server | Ruolo | Servizi | Stato |
|--------|-------|---------|-------|
| mc2 | Squadra + Dashboard | denaro-squadra, denaro-dashboard | ✅ Attivo |
| Nuvola | Grid SOL/EUR | denaro-grid | ✅ Attivo |
| MARCODG1 | Grid ADA/EUR | denaro-grid | ✅ Attivo |

### Bot Squadra (mc2)

| Bot | Coppia | Timeframe | Strategia | Stato |
|-----|--------|-----------|-----------|-------|
| Ares | ETH/EUR | 5m | Trend following | ⚪ Waiting |
| Hermes | SOL/EUR | 15m | RSI+MACD+Sentiment | ⚪ Waiting |
| Apollo | ETH/BTC | 1h | Ratio z-score | ⚪ Waiting |
| Artemis | BTC/EUR | 1d | SMA50/200 | ⚪ Waiting |

### Grid Bot

| Server | Coppia | Ordini | Budget |
|--------|--------|--------|--------|
| Nuvola | SOL/EUR | 8 (2B+6S) | ~€52 + 0.45 SOL |
| MARCODG1 | ADA/EUR | 7 (5B+2S) | ~€46 + 51 ADA |

### Portfolio
- **Totale**: ~€227 EUR
- **EUR free**: ~€67
- **Investito**: ~€160 (grid + posizioni)

### File Chiave
```
denaro/
├── grid_bot_v3.py          # Grid bot (Nuvola + MARCODG1)
├── denaro_core.py          # Core API Binance
├── denaro_strategies.py    # Strategie grid
├── grid_config.json        # Config grid (per-server)
├── orchestrator.py         # Dashboard HTTP server (:8899) + RiskManager
├── trade_db.py             # SQLite (vault, trades, daily PnL)
├── squadra/                # Bot direzionali (mc2)
│   ├── ares_bot.py
│   ├── hermes_bot.py
│   ├── apollo_bot.py
│   ├── artemis_bot.py
│   ├── orchestrator.py     # SquadraOrchestrator
│   └── run_squadra.py      # Entry point
├── utils/
│   ├── indicators.py
│   ├── risk_engine.py
│   ├── exit_strategy.py
│   ├── entry_filters.py
│   └── sentiment.py
└── dashboard/              # UI web (:8899)
```

### Comandi Rapidi
```bash
# Stato servizi
ssh mc2   'sudo systemctl status denaro-squadra denaro-dashboard'
ssh nuvola 'sudo systemctl status denaro-grid'
ssh MARCODG1 'sudo systemctl status denaro-grid'

# Log
ssh mc2 'sudo journalctl -fu denaro-squadra'

# Riavvio
ssh mc2 'sudo systemctl restart denaro-squadra'
```

### Branches Git
- `grivetto/dolari` — production (systemd, risk management, README, LICENSE)
- `grivetto/money` — precedente (pulizia + systemd)
- `refactoring` — legacy
- `main` — stabile legacy

---

## 📬 Contatti

**Owner**: Sergio Grivetto
**Email**: sergio@grivetto.eu
**GitHub**: github.com/grivetto/denaro
