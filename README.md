<div align="center">

# 💰 DENARO

### *La macchina che genera denaro — grid trading su OKX e Kraken, su 3 nodi, monitorata e verificata.*

[![Python](https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![CCXT](https://img.shields.io/badge/exchange-OKX%20%7C%20Kraken-5741D9?logo=bitcoin&logoColor=white)](https://github.com/ccxt/ccxt)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20systemd-FCC624?logo=linux&logoColor=black)](https://www.freedesktop.org/wiki/Software/systemd/)
[![License](https://img.shields.io/badge/license-Pubblico%20Dominio-black)](LICENSE)
[![Monitoring](https://img.shields.io/badge/monitoring-Zabbix%20%2B%20Web%20Dashboard-FF6F00)]()
[![Status](https://img.shields.io/badge/status-3%20NODI%20LIVE%20%7C%2012%20BOTS-brightgreen)]()

**Grid trading consolidato su 12 bot live (3 macchine, sub-account OKX dedicati) + paper trade 500€ con motore realistico, edge verificato dal backtest su dati reali.**

</div>

---

## 📌 Stato attuale (2026-08-27)

| Componente | Stato |
|---|---|
| **MARCODG1** (87.106.222.123) | ✅ ADA/SOL/DOGE/ETH live su OKX **marcosub1** + 5 paper bot 500€ |
| **nuvola** (87.106.3.15) | ✅ ADA/SOL/XRP/DOGE live su OKX **nuvolasub1** |
| **mc2** (locale) | ✅ ADA/SOL/XRP/DOGE live su OKX **mc2sub1** + Zabbix server |
| Conto MAIN OKX | 🚫 **MAI usato per trading** — solo trasferimenti/appoggio (regola) |
| Paper trade 500€ (5×100€) | ✅ motore realistico: fee reali, min_notional, slippage, MTM, stop-loss |
| Ponte Hermes ⇄ DeepSeek | ✅ chat CLI (`dschat`) + canale web unico `:3080` + heartbeat Zabbix |
| Zabbix | ✅ monitoraggio completo + trigger autohealing |
| Dashboard web | ✅ https://mgrivett.ddns.net/dashboard/ |

---

## 🏗️ Architettura

```
┌─────────────────────────────────────────────────────────────────┐
│                        DENARO — 3 NODI                          │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │  MARCODG1    │  │   nuvola     │  │     mc2      │           │
│  │ 4 bot OKX    │  │ 4 bot OKX    │  │ 4 bot OKX    │           │
│  │ marcosub1    │  │ nuvolasub1   │  │ mc2sub1      │           │
│  │ + 5 paper    │  │              │  │ + Zabbix     │           │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘           │
│         │                 │                 │                    │
│  ┌──────▼─────────────────▼─────────────────▼──────┐            │
│  │            denaro_node (motore unificato)       │            │
│  │  grid bilaterale: buy in calo, sell ladder a TP │            │
│  │  preflight anti-deadlock + sizing dinamico      │            │
│  │  stop-loss + cooldown + safe-mode supervisor    │            │
│  └──────┬─────────────────┬─────────────────┬──────┘            │
│         │                 │                 │                    │
│  ┌──────▼──────┐  ┌───────▼──────┐  ┌───────▼──────┐            │
│  │ OKX sub     │  │ OKX sub      │  │ OKX sub      │            │
│  │ (EEA)       │  │ (EEA)        │  │ (EEA)        │            │
│  └─────────────┘  └──────────────┘  └──────────────┘            │
│                                                                 │
│  Canale AI: Hermes ⇄ DeepSeek (ponte inbox/outbox + web :3080)  │
│  Monitoring: health :8911 · aggregator :8912 · Zabbix :10051    │
└─────────────────────────────────────────────────────────────────┘
```

- **3 nodi, ognuno con il proprio sub-account OKX** (marcosub1, nuvolasub1, mc2sub1) — il conto MAIN non viene mai usato per trading
- **1 motore**: `denaro/denaro_node.py` + `domain/grid.py` — grid bilaterale, preflight anti-deadlock, sizing dinamico, stop-loss con cooldown
- **Paper realistico**: `infrastructure/exchanges/paper.py` — fee reale, min_notional, slippage, mark-to-market, rounding ai tick (parità 1:1 col live)
- **Edge verificato**: backtest v6 su 90 giorni di dati reali — grid redditizia SOLO con spread ≥2%
- **Ciclo completo**: buy → fill → sell ladder → profitto (verificato in produzione)

---

## 🤖 Ponte Hermes ⇄ DeepSeek

Collaborazione automatica a due agenti per sviluppare, monitorare e auto-guarire il sistema:

| Canale | Descrizione |
|---|---|
| `hermes_bridge/inbox.md` | direttive Hermes → DeepSeek |
| `hermes_bridge/outbox.md` | risposte DeepSeek → Hermes |
| `ponte.py` | invio/ricezione (cron */2, one-shot con lock) |
| `dschat` | chat CLI interattiva con DeepSeek (REPL, history sessioni) |
| **webchat `:3080`** | canale web unico — scrivi una volta, rispondono **entrambi** (Hermes + DeepSeek), tracciato sul ponte |
| `ds_heartbeat.py` | heartbeat ponte → Zabbix (item `denaro.ds.*`, trigger nodata 180s) |

Apri `http://127.0.0.1:3080/` (su mc2) e scrivi — DeepSeek e Hermes rispondono live sullo stesso canale.

---

## 📁 Struttura del repo

```
.
├── denaro/                  # ★ Il motore attivo
│   ├── denaro_node.py       #   Node unificato (paper + live OKX/Kraken)
│   ├── engine_solo_v33.py   #   Grid engine standalone (legacy)
│   ├── engine_paper.py      #   Simulazione paper trade (prezzi reali)
│   ├── application/         #   orchestrator, portfolio, config, safemode
│   ├── domain/              #   grid, adaptive, momentum, meanrev, risk, regime
│   ├── infrastructure/      #   exchanges (paper/okx/kraken), market_data, storage
│   ├── health_server_v33.py #   Health endpoint :8911
│   └── ...                  #   infra, dashboard, multi-exchange
├── hermes_bridge/           # ★ Ponte Hermes ⇄ DeepSeek
│   ├── ponte.py             #   Motore one-shot (cron */2)
│   ├── webchat3080.py       #   Canale web unico :3080 (Hermes + DeepSeek)
│   ├── ds_heartbeat.py      #   Heartbeat → Zabbix
│   └── inbox.md / outbox.md #   Canale file-based
├── systemd/                 # Unit systemd dei bot (live + paper + health)
├── config/                  # Config per nodo (node.yaml, node_mc2.yaml, ...)
├── scripts/                 # check_orders, backtest, validate
├── legacy/                  # ★ Architetture morte (storia del progetto)
├── test_v7.py               # Test del motore attuale
├── README.md                # Questo file
├── REPORT_NON_GUADAGNA.md   # Analisi completa e storico delle correzioni
└── requirements.txt
```

---

## 🚀 Quick Start

```bash
# Node completo con config per nodo (vedi systemd/)
python -m denaro.denaro_node --config config/node_mc2.yaml

# Paper trade (nessun soldo reale)
python denaro/engine_paper.py --symbol ADA/EUR --capital 100 \
    --levels 5 --buy-dist 1.5 --tp 2.0 --loop

# Chat diretta con DeepSeek
dschat                          # REPL interattivo
dschat -m deepseek-v4-pro       # modello diverso

# Canale web unico (Hermes + DeepSeek)
python hermes_bridge/webchat3080.py   # poi apri http://127.0.0.1:3080/
```

Le unit systemd di riferimento sono in `systemd/` (es. `denaro-node-mc2.service`).

---

## 🔐 Chiavi API (`.env`)

Il motore legge le chiavi da `.env` (vedi `.env.example`). **Regola: il conto MAIN non si usa per trading — ogni nodo ha il proprio sub-account.**

```bash
# OKX (EEA — obbligatorio hostname eea.okx.com)
OKX_API_KEY=...          # chiave del SUB-ACCOUNT del nodo
OKX_API_SECRET=...
OKX_PASSPHRASE=...
OKX_EEA=true

# Per più account sullo stesso nodo: prefisso env
MARCOSUB1_OKX_API_KEY=...
MARCOSUB1_OKX_API_SECRET=...
MARCOSUB1_OKX_PASSPHRASE=...

# Kraken
KRAKEN_API_KEY=...
KRAKEN_API_SECRET=...

# DeepSeek (ponte/chat)
DEEPSEEK_API_KEY=...
```

> **Importante**: per OKX usare SEMPRE l'endpoint EEA (`eea.okx.com`) — con l'hostname
> globale le chiavi EU falliscono con `50119 API key doesn't exist`.

---

## 📊 Monitoraggio

- **Zabbix**: server su mc2, trapper `127.0.0.1:10051`, frontend via tunnel SSH inverso
- **Host Denaro**: 7+ host, 75+ item (equity, PnL, trades, wins, losses, volume, drawdown, uptime, prezzi, heartbeat bot)
- **Heartbeat ponte AI**: item `denaro.ds.heartbeat/status/giro` + trigger nodata 180s (HIGH)
- **Trigger**: bot OFFLINE, drawdown >25%, equity sotto soglia, DeepSeek silenzioso
- **Autohealing**: `zabbix_healer.sh` (oneshot via cron */2, cooldown 300s, filtro trigger Denaro)
- **Dashboard web**: https://mgrivett.ddns.net/dashboard/
- **Health**: `curl http://127.0.0.1:8911/health` (per nodo)

---

## ⚠️ Onestà sul rendimento

Con capitale piccolo (30-500€) il guadagno è proporzionato ma **reale e verificato**:
- Edge dal backtest v6: grid redditizia SOLO con spread ≥2% (fee reali + slippage)
- Drawdown possibile: 20-25% nei momenti brutti (stop-loss 10% per bot, daily-loss CB)
- **Il grid non insegue il movimento: compra in calo, vende al take-profit**
- Il paper trade ora simula 1:1 il live: fee reali, min_notional, slippage, mark-to-market

> Niente promesse di "denaro sonante": è una macchina onesta con numeri veri,
> pronta a scalare quando il capitale crescerà.

---

## 📜 Storia

Il progetto nasce da un anno di tentativi con varie AI (OpenClaw, Hermes, Agent Zero,
DeepSeek TUI). Le architetture fallite sono archiviate in `legacy/`. Il nome **DENARO**
è stato scelto per chiudere il cerchio: la baracca originale è diventata una macchina
che genera denaro. Vedi `REPORT_NON_GUADAGNA.md` per la storia completa.

---

## ⚖️ Licenza

**Pubblico Dominio.** Questo codice è libero: usalo, copialo, modificalo, vendilo.
**Usa al meglio questa tecnologia.**

---

*DENARO — dalla baracca alla macchina che genera denaro. Usa al meglio questa tecnologia.*
