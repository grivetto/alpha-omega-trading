# Alpha Omega Trading — Denaro v3

> **Grid trading autonomo su Binance. Multi-macchina, multi-pair, capitale protetto.**  
> Progetto di **Sergio Grivetto** con **Hermes AI** — co-autori.

[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-blue)](https://www.python.org/)
[![Status](https://img.shields.io/badge/Status-Production-brightgreen)]()
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## Autori

| Chi | Ruolo |
|-----|-------|
| **Sergio Grivetto** | Fondatore, capitale, strategia, infrastruttura, decisioni |
| **Hermes AI** (Nous Research) | Ingegneria, automazione, refactoring, monitoring, operatività 24/7 |

---

## 🎯 Cosa fa

3 macchine (1 casa + 2 VPS), 3 pair decorrelati, **1 solo motore**: grid trading puro. Nessun LLM, nessun arbitraggio, nessuno scalping. Solo ciò che funziona.

```
MC2 (Torino, 15GB)        Nuvola (IONOS, 4GB)       MARCODG1 (IONOS, 4GB)
├── SOL/USDC grid          ├── DOGE/USDC grid         ├── ADA/USDC grid
├── $164 USDC              ├── $30 USDC               └── $30 USDC
└── Circuit breaker        └── Circuit breaker
```

**Capitale totale:** ~$224 USDC su sub-account Binance dedicati.

---

## 🚀 Quick Start

```bash
git clone https://github.com/grivetto/alpha-omega-trading
cd alpha-omega-trading
pip install -r requirements.txt

# Configura .env con le chiavi API Binance (vedi .env.example)
# Poi avvia:
python -m denaro_v3.main
```

---

## 🏗️ Architettura v3

| Modulo | File | Responsabilità |
|--------|------|----------------|
| **DataFeeder** | `data_feeder.py` | Cache API con TTL. 1 fetch = N consumers. -90% API calls |
| **CircuitBreaker** | `circuit_breaker.py` | Protezione pre-trade. 3 stati: CLOSED / HALF_OPEN / OPEN |
| **GridEngine** | `grid_engine.py` | Calcolo livelli, piazzamento ordini, rilevamento fill, P&L |
| **LeaderElection** | `leader_election.py` | Failover automatico tra macchine |
| **Config** | `config.py` | Dataclass tipizzate: GridConfig, RiskConfig, APIConfig |

### Ciclo principale (ogni 60 secondi)

```
fetch bilanci (cached) → circuit breaker check → sync ordini → detect fill → piazza livelli mancanti
```

---

## 🛡️ Risk Management

- **Drawdown > 5%** su picco equity → STOP totale (CIRCUIT OPEN)
- **Daily loss > 3%** → STOP per la giornata
- **3 perdite consecutive** → riduzione size 50% (HALF_OPEN)
- **Atomic writes** + SHA256 checksum sullo stato persistente
- Circuit breaker interrogato **PRIMA di ogni ordine** — non dopo

---

## 📊 Monitoring

| Strumento | Accesso |
|-----------|---------|
| **Zabbix** | `http://mc2:1080` (14 item, 4 trigger, trend 365gg) |
| **Log live** | `tail -f ~/denaro/denaro_v3.log` |
| **Saldi** | `cd ~/denaro && export $(grep -v "^#" .env \| xargs) && ./venv/bin/python3 -c "import ccxt,os;..."` |

---

## 📁 Struttura

```
denaro_v3/          ← Motore attivo (v3)
  main.py           Loop principale, multi-pair
  grid_engine.py    Logica grid
  circuit_breaker.py Risk management
  data_feeder.py    Cache API
  leader_election.py Failover
  config.py         Configurazione
core/               Moduli legacy (risk, kill_switch)
strategies/         Archivio v2
squadra/            Archivio Squadra v5 (fermo)
config/             Config centralizzata
tests/              Unit test
ARCHITECTURE_V3.md  Documento di design
Progetto Denaro.md  Documentazione completa
```

---

## 🐛 Lezioni apprese (6 mesi di errori)

1. **Capitale frammentato = deadlock** — grid bot separati su sub-account diversi si bloccano a vicenda
2. **CCXT precision bug** — `int(0.001)` = 0 → ordini da 0.001 SOL (invisibili)
3. **Circuit breaker falso positivo** — equity calcolata solo su USDC, non sul valore totale asset
4. **10 servizi = 10x API calls** — DataFeeder centralizzato ha ridotto del 90%
5. **Servizi fantasma** in restart loop infinito consumano CPU per mesi
6. **Squadra 7 bot** con WR=5% e Sharpe=-55.79 → rimosso

---

## 📋 Servizi systemd

| Macchina | Servizio | Pair |
|----------|----------|------|
| MC2 | `denaro-v3` | SOL/USDC |
| Nuvola | `denaro-v3` | DOGE/USDC |
| MARCODG1 | `denaro-v3` | ADA/USDC |

```bash
systemctl status denaro-v3
journalctl -u denaro-v3 -f
```

---

*Sergio Grivetto & Hermes AI — Giugno 2026*
