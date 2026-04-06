# DENARO — Sistema di Trading Quantitativo — **BETA 01**

⚠️ **AVVISO IMPORTANTE**: Questo NON è un sistema di trading "magico".
È un sistema **realistico**, trasparente e open-source con target dichiarati.
**Nessuna leva, solo spot.** Obiettivo: €3-8/giorno su ~€400 capitale.

---

## 🏗️ Architecture

### NUVOLA (87.106.3.15) — Core Trading + Monitor
| Bot | File | Descrizione |
|-----|------|-------------|
| **Grid Bot V2** | `grid_bot_v2.py` | Grid ETH/EUR 5 livelli, spacing 0.5%, tracking fill, ribilanciamento, kill switch |
| **DCA Bot** | `dca_bot.py` | Accumulo BTC: €5 ogni 2h, vendita a +1.0% o stop -3% |
| **Monitor H24** | `monitor/monitor.py` | Auto-healing: controlla tutti i bot ogni 5min su Nuvola e MC2 |
| **Telegram Bot** | `telegram_bot_interactive.py` | Controller via Telegram (@Sergiotrdxbot) |
| **Hermes Chat Bot** | `hermes_chat_bot.py` | Bot chat per Stella/Hermes |
| **Dashboard V3** | `dashboard_v3_unified.py` | Dashboard completa con bilancio reale e stato bot |

### MC2 (93.43.252.114) — Sniper & Trend
| Bot | File | Descrizione |
|-----|------|-------------|
| **Sniper V2** | `rebound_sniper_v2.py` | RSI < 40 su 6 pairs EUR (ETH/SOL/AVAX/DOT/LINK/DOGE), TP 1%, budget €70/trade, max 4 pos |
| **Trend Follower** | `trend_following_bot.py` | EMA 9/21 crossover su ETH/EUR e SOL/EUR, TP +3%, SL -5% |
| **Status Server** | `mc2_status_server.py` | HTTP server port 8080 — dashboard monitoring completa |

---

## 💰 Strategie

### Grid Bot V2 (Motore Principale — €200 allocati)
- **Pair**: ETH/EUR
- **Config**: 5 livelli (2 buy + 2 sell), spacing 0.5%, ordini €35
- **Funzionamento**: Compra ETH quando scende, vende quando sale. Ogni ciclo genera profit ~€0.15-0.30
- **Safety**: Kill switch se ETH drop >15% in 24h
- **Log**: `/tmp/grid_v2.log`

### Sniper V2 (MC2 — Opportunistico)
- **Pairs**: ETH/EUR, SOL/EUR, AVAX/EUR, DOT/EUR, LINK/EUR, DOGE/EUR
- **Trigger**: RSI < 40 (5 min timeframe)
- **Exit**: TP +1.0% | SL -4%
- **Budget**: €70/trade | Max 4 posizioni | Cooldown 5 min dopo vendita

### Trend Follower (MC2 — Trend forti)
- **Pairs**: ETH/EUR, SOL/EUR
- **Segnale**: EMA 9 > EMA 21 (conferma 2 periodi)
- **Exit**: TP +3% | SL -5% | Reverse trend

### DCA Bot (NUVOLA — Accumulo)
- **Pair**: BTC/EUR
- **Buy**: €5 ogni 2 ore fino a max €30 BTC
- **Exit**: TP +1.5% | SL -3%

---

## 📊 Monitoring H24

Il sistema `monitor/monitor.py` gira ogni **5 minuti** tramite cron e:
- ✅ Controlla se ogni bot è attivo su Nuvola e MC2
- ✅ Riavvia automaticamente i bot caduti
- ✅ Monitora RAM, connettività MC2, accesso dashboard
- ✅ Salva log in `monitor/monitor.log` e stato in `monitor/state.json`

**Dashboard:**
- **Nuvola**: `https://sgrivett.ddns.net:8443` — Portafoglio completo, ordini aperti
- **MC2**: `https://mgrivett.ddns.net` — Status bot, RSI auto-repair log

---

## 🚀 Quick Start

```bash
# Nuvola — Grid Bot
cd /home/sergio/.openclaw/workspace/denaro
nohup trading_bot_env/bin/python3 grid_bot_v2.py >> /tmp/grid_v2.log 2>&1 &

# MC2 — Sniper V2
ssh -p 2222 sergio@93.43.252.114 "cd ~/denaro && nohup venv/bin/python3 rebound_sniper_v2.py > /dev/null 2>&1 &"
```

---

## ⚠️ Sicurezza
- Chiavi API in `.env` (NEVER committato)
- SSH key auth per MC2
- Solo trading Spot — NO futures, NO leverage
- Budget per bot configurato per limitare esposizione

---

## 📜 Cronologia Versioni
| Versione | Data | Note |
|----------|------|------|
| **Beta 01** | 06 Apr 2026 | Grid V2 (spacing 0.5%, 5 livelli), Sniper EUR pairs (RSI 40), Trend Follower EMA, DCA Bot, Monitor H24, Dashboard unificata |
| V3 Initial | 05 Apr 2026 | Chiusura old system, apertura nuovo |
