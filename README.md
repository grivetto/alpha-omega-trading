<div align="center">

# 💰 DENARO

### *La macchina che genera denaro — grid trading su OKX e Kraken, monitorata e verificata.*

[![Python](https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![CCXT](https://img.shields.io/badge/exchange-OKX%20%7C%20Kraken-5741D9?logo=bitcoin&logoColor=white)](https://github.com/ccxt/ccxt)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20systemd-FCC624?logo=linux&logoColor=black)](https://www.freedesktop.org/wiki/Software/systemd/)
[![Monitoring](https://img.shields.io/badge/monitoring-Zabbix%20%2B%20Web%20Dashboard-FF6F00)]()

**Grid trading consolidato su 3 bot live + paper trade 500€, con edge verificato dal backtest su dati reali.**

</div>

---

## 📌 Stato attuale

| Componente | Stato |
|---|---|
| Bot SOL/EUR (OKX main) | ✅ operativo — primo profitto reale, 100% win rate |
| Bot ADA/EUR (OKX marcosub1) | ✅ operativo — grid attivo |
| Bot SOL/EUR (Kraken nuvola) | ✅ operativo |
| Paper trade 500€ (ADA/SOL/XRP) | ✅ simulazione con prezzi reali |
| Zabbix (7 host, 75 item, trigger) | ✅ monitoraggio completo |
| Dashboard web | ✅ https://mgrivett.ddns.net/dashboard/ |

---

## 🏗️ Architettura

```
┌─────────────────────────────────────────────────────────────────┐
│                        DENARO — MARCODG1                         │
│  (87.106.222.123 — nodo principale)                              │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │ Bot SOL/EUR  │  │ Bot ADA/EUR  │  │ Paper ADA    │           │
│  │ (OKX main)   │  │ (marcosub1)  │  │ Paper SOL    │           │
│  │              │  │              │  │ Paper XRP    │           │
│  └──────┬───────┘  └──────┬───────┘  └──────────────┘           │
│         │                 │                                      │
│  ┌──────┴─────────────────┴──────┐                               │
│  │   engine_solo_v33 / engine_paper  │                           │
│  │   (grid: compra in calo, sell a TP)│                          │
│  └──────┬─────────────────┬──────┘                               │
│         │                 │                                      │
│  ┌──────▼──────┐  ┌───────▼──────┐                               │
│  │ OKX (EEA)   │  │   Kraken     │◄── nuvola (bot SOL/EUR)      │
│  └─────────────┘  └──────────────┘                               │
│                                                                  │
│  Monitoring: health server :8911 · aggregator :8912 · Zabbix     │
└─────────────────────────────────────────────────────────────────┘
          │                    │
          ▼                    ▼
   ┌───────────┐         ┌───────────┐
   │ mc2       │         │ nuvola    │
   │ Zabbix    │         │ bot Kraken│
   │ server    │         │           │
   └───────────┘         └───────────┘
```

- **3 nodi**: MARCODG1 (trading OKX + paper), nuvola (trading Kraken), mc2 (Zabbix server)
- **1 motore**: `denaro/engine_solo_v33.py` — grid con 3 livelli, TP 2%, capitale effettivo
- **Edge verificato**: backtest su 90 giorni di dati reali (ADA +11%, SOL +5%, XRP +7.7%)
- **Ciclo completo**: buy → fill → sell → profitto (verificato in produzione)

---

## 📁 Struttura del repo

```
.
├── denaro/                  # ★ Il motore attivo
│   ├── engine_solo_v33.py   #   Grid engine (OKX/Kraken, health file)
│   ├── engine_paper.py      #   Simulazione paper trade (prezzi reali)
│   ├── infra_aggregator.py  #   API aggregata (snapshot cache)
│   ├── infra_snapshot.py    #   Generatore snapshot (cron)
│   ├── health_server_v33.py #   Health endpoint
│   ├── dashboard_infra.html #   Dashboard web cyberpunk
│   ├── okx_engine.py        #   OKX EEA adapter
│   ├── multi_exchange.py    #   Multi-exchange adapter
│   └── ...                  #   core, risk, regime, indicators
├── systemd/                 # Unit systemd dei bot (live + paper)
├── config/                  # Fleet e strategy config
├── legacy/                  # ★ Architetture morte (storia del progetto)
│   ├── alpha_omega/         #   Vecchio motore fleet
│   ├── airdrop-farm/        #   Progetto airdrop abbandonato
│   ├── neo/                 #   Prototipo async
│   ├── tests/               #   Test delle architetture legacy
│   └── ...                  #   Motori vecchi (kraken, mexc, bybit)
├── test_v7.py               # Test del motore attuale
├── README.md                # Questo file
├── REPORT_NON_GUADAGNA.md   # Analisi completa e storico delle correzioni
└── requirements.txt
```

---

## 🚀 Quick Start

```bash
# Bot live su OKX (es. SOL/EUR)
python denaro/engine_solo_v33.py --exchange okx --symbol SOL/EUR \
    --capital 100 --profit-target 1.5 --buy-distance 1.0 --grid-levels 3 --loop

# Paper trade (nessun soldo reale)
python denaro/engine_paper.py --symbol ADA/EUR --capital 300 \
    --levels 3 --buy-dist 1.5 --tp 2.0 --loop

# Dry-run (mostra cosa verrebbe piazzato, senza ordini)
python denaro/engine_solo_v33.py --exchange okx --symbol ADA/EUR --capital 100
```

Le unit systemd di riferimento sono in `systemd/` (es. `solo-engine-v33-marcodg1.service`).

---

## 🔐 Chiavi API (`.env`)

Il motore legge le chiavi da `.env` (vedi `.env.example`):

```bash
# OKX (EEA — obbligatorio hostname eea.okx.com)
OKX_API_KEY=...
OKX_API_SECRET=...
OKX_PASSPHRASE=...
OKX_EEA=true

# Kraken
KRAKEN_API_KEY=...
KRAKEN_API_SECRET=...
```

> **Importante**: per OKX usare SEMPRE l'endpoint EEA (`eea.okx.com`) — con l'hostname
> globale le chiavi EU falliscono con `50119 API key doesn't exist`.

---

## 📊 Monitoraggio

- **Zabbix**: server su mc2, frontend HTTPS su MARCODG1 (tunnel SSH inverso)
- **Host Denaro**: 7 host, 75 item (equity, PnL, trades, wins, losses, volume, drawdown, uptime, prezzi)
- **Trigger**: bot OFFLINE, drawdown >25%, equity < 50€
- **Dashboard web**: https://mgrivett.ddns.net/dashboard/
- **Health**: `curl http://127.0.0.1:8911/health` (MARCODG1)

---

## ⚠️ Onestà sul rendimento

Con capitale piccolo (30-55€) il guadagno è proporzionato ma **reale e verificato**:
- Edge dal backtest: ~8-15% annuo netto in condizioni favorevoli
- Drawdown possibile: 20-25% nei momenti brutti (il capitale oscilla)
- **Il grid non insegue il movimento: compra in calo, vende al take-profit**

> Niente promesse di "denaro sonante": è una macchina onesta con numeri veri,
> pronta a scalare quando il capitale crescerà.

---

## 📜 Storia

Il progetto nasce da un anno di tentativi con varie AI (OpenClaw, Hermes, Agent Zero,
DeepSeek TUI). Le architetture fallite sono archiviate in `legacy/`. Il nome **DENARO**
è stato scelto per chiudere il cerchio: la baracca originale è diventata una macchina
che genera denaro. Vedi `REPORT_NON_GUADAGNA.md` per la storia completa.

---

*DENARO — dalla baracca alla macchina che genera denaro.*
