# DENARO — Sistema di Trading Quantitativo Realistico

⚠️ **AVVISO**: Questo NON è un sistema "20% profitto giornaliero". Ha un target realistico di €4-7/giorno su ~€400 capitale.

## 🎯 Architecture

### NUVOLA (87.106.3.15) — Core Grid Trading
- **Grid Bot**: BTC/EUR grid con €90 investiti
- **6 livelli**: 3 buy sotto, 3 sell sopra
- **Target**: €3-5/giorno

### MC2 (93.43.252.114) — RSI Sniping
- **Rebound Sniper**: Entra su ipervenduto (RSI < 32)
- **Coppie**: ETH/BTC, SOL/BTC, BNB/BTC, AVAX/BTC, LINK/BTC
- **Target**: €0.50-2/giorno

## 📊 Monitoring Automatico

| Servizio | Frequenza | Descrizione |
|----------|-----------|-------------|
| **Health Check** | 15 min | Stato bot, API, risorse |
| **Infrastructure Audit** | 6 ore | Sicurezza, log, performance |
| **Cassaforte** | 23:59 giornaliero | Tracciamento profitto |
| **Git Backup** | Dopo ogni modifica | Codice versionato |

## 🚀 Quick Start

```bash
# Start Grid Bot (NUVOLA)
sudo systemctl start denaro-realistic-grid

# Check status
cd /home/sergio/.openclaw/workspace/denaro
source trading_bot_env/bin/activate
python3 health_check.py
```

## 📈 Dashboard

- URL: https://sgrivett.ddns.net:8443
- Telegram: @sergio_bot

## ⚙️ Configurazione

File `.env`:
```
BINANCE_API_KEY=xxx
BINANCE_API_SECRET=xxx
TELEGRAM_BOT_TOKEN=8715854678:xxx
TELEGRAM_CHAT_ID=8183973303
```

## 📝 Changelog

- 2026-04-03: Setup completo con €90 capitale
- Grid: 6 livelli attivi
- Monitor: Health + Audit + Cassaforte

---
**Nota**: Target giornaliero €4-7 = 1-1.75% — realistico e sostenibile.
