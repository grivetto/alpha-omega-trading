<div align="center">

# 💰 DENARO

### *La macchina che genera denaro — grid trading su OKX e Kraken, su 3 nodi, monitorata e verificata.*

[![Python](https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![CCXT](https://img.shields.io/badge/exchange-OKX%20%7C%20Kraken-5741D9?logo=bitcoin&logoColor=white)](https://github.com/ccxt/ccxt)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20systemd-FCC624?logo=linux&logoColor=black)](https://www.freedesktop.org/wiki/Software/systemd/)
[![License](https://img.shields.io/badge/license-Pubblico%20Dominio-black)](LICENSE)
[![Monitoring](https://img.shields.io/badge/monitoring-Zabbix%20%2B%20Web%20Dashboard-FF6F00)]()
[![Status](https://img.shields.io/badge/status-2%20NODI%20LIVE%20%7C%203%20BOTS%20LIVE-brightgreen)]()

**Grid trading consolidato su 3 bot live (2 nodi, sub-account OKX/Kraken dedicati) + paper trade con motore realistico, edge verificato dal backtest su dati reali.**

</div>

---

## 📌 Stato attuale (2026-09-07)

| Componente | Stato |
|---|---|
| **MARCODG1** (87.106.222.123) | ✅ **SOL/Kraken grid** (trend-live) + **SOL/Kraken grid** (Kraken) + **ADA/OKX** running + **SOL/DOGE/ETH OKX** in CB weekly loss + 5 paper bot 500€ |
| **nuvola** (87.106.3.15) | ✅ **SOL/Kraken trend-live** (conto principale) + paper DOGE feeder |
| **mc2** (locale, 100.87.24.42 CGNAT) | ✅ Zabbix server + reverse SSH tunnel verso MARCODG1 |
| Conto MAIN OKX | 🚫 **MAI usato per trading** — solo trasferimenti/appoggio (regola) |
| Paper trade 500€ (5×100€) | ✅ motore realistico: fee reali, min_notional, slippage, MTM, stop-loss |
| Ponte Hermes ⇄ DeepSeek | ✅ chat CLI (`dschat`) + canale web unico `:3080` + heartbeat Zabbix |
| Zabbix | ✅ monitoraggio completo + trigger autohealing (auto-heal disabilitato per sicurezza) |
| Dashboard web | ✅ https://mgrivett.ddns.net/dashboard/ |

**Capitale reale verificato: ~29.5 EUR totali** (Kraken ~26 EUR + OKX ~1.56 EUR). I 50€ in arrivo (25€ Kraken + 25€ OKX) saranno assorbiti dai bot live.

---

## 🏗️ Architettura

```
┌─────────────────────────────────────────────────────────────────┐
│                        DENARO — 2 NODI                          │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐                             │
│  │  MARCODG1    │  │   nuvola     │                             │
│  │ SOL/Kraken   │  │ SOL/Kraken   │                             │
│  │ grid (trend) │  │ trend-live   │                             │
│  │ + ADA/OKX    │  │ (conto main) │                             │
│  │ + paper 500€ │  │ + paper      │                             │
│  └──────┬───────┘  └──────┬───────┘                             │
│         │                 │                                     │
│  ┌──────▼─────────────────▼─────────────────┐                    │
│  │           denaro_node (motore unificato) │                    │
│  │  grid bilaterale: buy in calo, sell TP  │                    │
│  │  preflight anti-deadlock + sizing       │                    │
│  │  stop-loss + cooldown + safe-mode       │                    │
│  └──────┬─────────────────┬─────────────────┘                    │
│         │                 │                                        │
│  ┌──────▼──────┐   ┌───────▼──────┐                                │
│  │   mc2       │   │  Zabbix      │                                │
│  │ (CGNAT)     │   │  + Dashboard │                                │
│  │ reverse SSH │   │  HTTPS       │                                │
│  └─────────────┘   └──────────────┘                                │
```

---

## 🔧 Componenti Core

| Modulo | Descrizione |
|---|---|
| `denaro/domain/` | Layer dominio: grid policies, risk, regime, indicators |
| `denaro/application/` | Orchestration, portfolio, supervisor, safemode |
| `denaro/infrastructure/` | Exchange adapters (OKX/Kraken), market data, storage |
| `denaro/denaro_node.py` | Entry point unificato per tutti i nodi |
| `push_metrics.py` | Push metriche a Zabbix (trapper) — fixato auto-heal |
| `infra_aggregator.py` | Aggrega health da tutti i nodi su porta 8912 |
| `health_server_v33.py` | Health endpoint per nodo (porta 8911) |
| `config/*.yaml` | Config per nodo (node.yaml, node_paper.yaml, node_trend_live_kraken.yaml) |

---

## 📊 Monitoraggio & Alerting

- **Zabbix Server** su mc2 (Docker) → HTTPS via `https://mgrivett.ddns.net/`
- **Items chiave**: `bot.kraken.*`, `bot.trend_live.*`, `project.*`, `svc.denaro-*`
- **Trigger**: CB weekly loss, daily loss, preflight block, stale health, DeepSeek heartbeat
- **Auto-heal**: **DISABILITATO** (causava riavvii spurii su bot live con capitale reale)
- **Dashboard**: https://mgrivett.ddns.net/dashboard/ (nginx + Let's Encrypt)

---

## 🚀 Deploy & Operatività

### Prerequisiti
- Python 3.12+, `uv` o `venv`
- Chiavi API OKX/Kraken in `.env` (mai in repo)
- Docker + Docker Compose per Zabbix (su mc2)

### Avvio rapido (su MARCODG1)
```bash
# Clona
git clone git@github.com:grivetto/alpha-omega-trading.git
cd alpha-omega-trading

# Installa dipendenze
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Configura .env con chiavi API (mai committare!)
cp .env.example .env
# modifica .env con le tue chiavi

# Avvia bot live (es. su MARCODG1)
python -m denaro.denaro_node --config config/node.yaml

# Avvia paper trading
python -m denaro.denaro_node --config config/node_paper.yaml

# Avvia trend-live Kraken
python -m denaro.denaro_node --config config/node_trend_live_kraken.yaml
```

### Systemd services (produzione)
```bash
# Su MARCODG1
sudo cp systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now denaro-node denaro-node-paper denaro-node-trend-live

# Su nuvola
sudo systemctl enable --now denaro-node-nuvola denaro-health-nuvola

# Su mc2
sudo systemctl enable --now zabbix-* denaro-tunnel-reverse
```

---

## 🔐 Sicurezza & Chiavi

- **Mai committare chiavi API** — sono in `.env` (gitignored)
- Sub-account OKX dedicati per bot (EEA, trasferimenti interni)
- Chiavi Kraken separate per conto principale e sub-account
- Zabbix accesso solo via HTTPS + autenticazione

---

## 📈 Roadmap

- [ ] Validazione 60 giorni bot live Kraken (SOL grid + trend-live)
- [ ] Soglie promozione automatica: profit factor > 1.3, max DD < 15%, Sharpe > 0.8
- [ ] Iniezione graduale capitale: 50€ → 200€ → 500€ → 1000€
- [ ] Template Zabbix "Denaro Grid Bot" con grafici equity/PnL/volume
- [ ] Bot-as-a-service per terzi (gestione conto, fee su profitti)

---

## 📜 Licenza

**Pubblico Dominio.** Questo codice è libero: usalo, copialo, modificalo, vendilo. **Usa al meglio questa tecnologia.**

---

> *DENARO — dalla baracca alla macchina che genera denaro. Usa al meglio questa tecnologia.*
