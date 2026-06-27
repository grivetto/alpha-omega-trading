# Alpha Omega Trading — Denaro v6

> **Trading autonomo su Binance. Circuit breaker, WebSocket, State Engine, 3 strategie.**  
> Progetto di **Sergio Grivetto** con **Hermes AI** — co-autori.

[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-blue)](https://www.python.org/)
[![Status](https://img.shields.io/badge/Status-LIVE-brightgreen)]()
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## Autori

| Chi | Ruolo |
|-----|-------|
| **Sergio Grivetto** | Fondatore, capitale, strategia, infrastruttura, decisioni |
| **Hermes AI** (Nous Research) | Ingegneria, automazione, refactoring, monitoring, operatività 24/7 |

---

## Cosa fa

**1 macchina, 1 processo, 3 strategie con protezione capitale integrata.** Circuit breaker blocca tutto se il drawdown supera la soglia — nessun trade passa senza risk check.

```
MC2 (Torino, Intel N150, 15GB RAM)
└── denaro-v6 (SOL/USDC + ADA/USDC + DOGE/USDC)
    ├── Circuit Breaker (CLOSED → HALF_OPEN → OPEN)
    ├── State Engine (BULL / BEAR / SIDEWAYS)
    ├── WebSocket Engine (prezzi real-time, zero API rate burn)
    ├── Scalper (ATR spike, -0.8% drop → +0.4% TP / -2% SL)
    ├── Whale Tracker (order book imbalance >3:1 → +0.8% TP / -1.5% SL)
    └── Momentum Reactor (2 tick +1% pump → +1.5% TP / -2% SL)
```

**Capitale totale:** ~$251 USDC su sub-account Binance `mc2orion`.

---

## Quick Start

```bash
git clone https://github.com/grivetto/alpha-omega-trading
cd alpha-omega-trading
pip install requests websocket-client

# Configura .env con BINANCE_API_KEY e BINANCE_API_SECRET
cp .env.example .env
nano .env

# Test dry-run (Ctrl+C per uscire)
python denaro_v6/main.py
```

---

## Architettura v6

Un solo file: `denaro_v6/main.py` (330 righe). Sync, zero async, dipendenze minime.

| Componente | Preso da | Funzione |
|-----------|----------|----------|
| **CircuitBreaker** | v3 | Protezione pre-trade. 3 stati: CLOSED / HALF_OPEN / OPEN. Drawdown, loss consecutive, persistenza |
| **WSEngine** | v5 | WebSocket Binance per prezzi real-time (~100ms). Thread daemon, riconsessione automatica |
| **StateEngine** | v5 | Classifica mercato: BULL (>+5% 20d), BEAR (<-5%), SIDEWAYS. Adatta strategie |
| **Scalper** | v5 | Entry su ATR spike (-0.8% da local high), TP +0.4%, SL -2%, max hold 120s |
| **WhaleTracker** | v5 | Order book imbalance >3:1, TP +0.8%, SL -1.5%, max hold 180s |
| **MomentumReactor** | v5 | 2 pump consecutivi >+1%, TP +1.5%, SL -2%, max hold 600s |

### Ciclo principale (ogni 0.5 secondi)

```
WS price update → equity calc → CB check → run strategie (solo se CB CLOSED) → sleep 0.5s
```

---

## Risk Management

- **Drawdown > 5%** su picco equity → STOP totale (CIRCUIT OPEN)
- **Daily loss > 3%** → STOP per la giornata
- **3 perdite consecutive** → riduzione size 50% (HALF_OPEN)
- **Circuit breaker interrogato PRIMA di ogni ordine** — se OPEN, nessun trade
- **Orphan cleanup** all'avvio: cancella tutti gli ordini aperti prima di iniziare
- **SIGTERM** graceful shutdown con cancel ordini

---

## Monitoring

| Strumento | Accesso |
|-----------|---------|
| **Zabbix** | `http://mc2:1080` (item + trigger, trend 365gg) |
| **Log live** | `journalctl -u denaro-v6 -f` |
| **Saldi** | `ssh sergio@mc2 'cd ~/denaro && ./venv/bin/python3 tools/check_balance.py'` |

---

## Struttura Repo

```
denaro_v6/              ← Motore attivo (v6)
  main.py               Unico file: engine, CB, strategie, loop
  config/
    v6_config.json      Configurazione

denaro_v5/              ← Archivio v5 WAR (sostituito da v6)
denaro_v3/              ← Archivio v3 Grid
tools/                  ← Script operativi (check_balance, cancel_all, sell_asset, universal_transfer)
tests/                  ← Unit test (v3)
```

---

## Servizi systemd (MC2)

| Servizio | Stato | File |
|----------|-------|------|
| `denaro-v6` | **ACTIVE** | Guerra unificata v6 |
| `denaro-war` | DISABLED | Sostituito da v6 |
| `denaro-v3` | DISABLED | Sostituito da WAR v5, poi v6 |

```bash
systemctl status denaro-v6
journalctl -u denaro-v6 -f
```

---

## Versioni

| Versione | Periodo | Strategia | Stato |
|----------|---------|-----------|-------|
| v2 Squadra | Feb-Giu 2026 | Multi-bot, LLM, arbitraggio | ARCHIVIATO (branch `legacy-v2`) |
| v3 Grid | 23-27 Giu 2026 | Grid trading puro, multi-macchina | FERMO |
| v5 WAR | 27 Giu 2026 | Scalp + Whale + News, sync | SOSTITUITO |
| **v6 Unified** | **27 Giu 2026 →** | **CB + WS + Stato + 3 strat in un file** | **LIVE** |

---

## Lezioni apprese (6 mesi di errori)

1. **Capitale frammentato = deadlock** — grid bot separati su sub-account diversi si bloccano a vicenda
2. **CCXT precision bug** — `int(0.001)` = 0 → ordini da 0.001 SOL (invisibili)
3. **Circuit breaker essenziale** — senza CB, un mercato bear distrugge il capitale
4. **WebSocket > REST** — 7s → 0.5s per ciclo, 14x più veloce, zero API rate burn
5. **Un file, non 20** — meno codice = meno bug. v6 è 330 righe contro le migliaia di v2/v3
6. **Sync > Async** per trading — niente event loop, niente deadlock, shutdown pulito

---

*Sergio Grivetto & Hermes AI — Giugno 2026*
