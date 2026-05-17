# 🧪 Denaro — Lab History

Storia completa del progetto Denaro, dalle origini all'ultimo refactoring.

---

## 2026-03-21 | Crypto.com API & Primo Setup

- Configurazione API Crypto.com (autenticazione HMAC)
- Debug errori 401 Client Error
- Setup `advanced_quant_bot.py` su Binance (SOL/EUR)
- Budget iniziale: ~€49

## 2026-03-22 | Espansione Flotta & Orbital Strike

- Creati 4 nuovi bot specializzati: `centurion_reversion_squad.py`, `liquidator_prime.py`, `oscillator_counter_unit.py`, `forced_profit_unit.py`
- Fleet Guardian (`fleet_guardian.py`) — demone di monitoraggio con riavvio automatico
- **Progetto Orbital Strike** — concept di geo-arbitraggio con nodi satellite a Tokyo, NY, Londra
- Switch strategico: liquidato 20% DOGE e AVAX per liberare €70, reinvestiti su SOL/ETH
- Bot scalper SOL/EUR attivo: 4 operazioni notturne, +1.1% netto

## 2026-03-22 | Operazione d'Urto

- Liquidati ADA e DOGE bloccati, liberati ~€120
- Forzati acquisti su SOL, ETH, BNB in iper-venduto
- Riavviato `war_machine.py` in ZERO PRISONERS MODE
- Dashboard web su `sgrivett.ddns.net:8443` risolta (sync con `fleet_monitor_service.py`)
- 18 unità di caccia ONLINE

## 2026-04-22 | Debug Alpha Strike & Legion Amnesia

- Identificato **loop infinito** in `ALPHA_STRIKE.log` (752 MB): tentativi di vendita con saldo insufficiente
- Trovato **bug di amnesia** nei bot `legion_*`: posizioni salvate solo in variabili locali, perse al riavvio
- Fix: persistenza su file JSON + sincronizzazione forzata con Binance all'avvio
- Raccomandato di spegnere tutti i bot `legion_*` singoli e usare solo `legion_manager_production.py`
- Server `MARCODG1` non raggiungibile (timeout SSH)

## 2026-05-12 | Prima Analisi del Sistema

- Analisi su 3 server: **mc2**, **nuvola** (87.106.3.15), **MARCODG1**
- Scoperta struttura massiva su mc2: decine di bot, log multi-GB
- Nuvola irraggiungibile (host key changed → MITM warning)
- Server MARCODG1 (user `marco`): setup più semplice, `denaro_ultimate.py`
- Analisi interrotta — nessuna conclusione

## 2026-05-14 | Nuvola Back Online, Test Avvio

- Riconnessione riuscita a Nuvola (192.168.1.117)
- Bot della Squadra in esecuzione da 3gg: Ares fà 0 trades, Apollo e Artemis idem
- Installato python3-dotenv su mc2. Verificato orario sincronizzato con NTP.
- **Test di startup** `squadra/test_startup.py` → OK (coinpaprika API, SQLite DB connettività)
- Propenso a: fermare tutto, fixare connesione Binance, accendere solo 2 bot, monitorare per 24h

## 2026-05-15 | Full Refactoring & Configurazione Finale

- **Squadra consolidata** su mc2: Ares (ETH/EUR trend 1m), Hermes (SOL/EUR RSI 1m), Apollo (ETH/BTC ratio 1h), Artemis (BTC/EUR SMA 1d)
- Configurati via `squadra/config/squadra.json` + file JSON per bot
- Orchestrator (`run_squadra.py`) — entry point unico
- Esecuzione via **tmux** (`squadra_bot`), watchdog via cron ogni 5 min
- Budget finale: **€125.58 EUR**
- Legion DECOMMISSIONED. MARCODG1 spento. Solo Squadra (mc2) + Grid Nuvola attivi.
- Branch `refactoring` creato su `github.com/grivetto/money`

## 2026-05-16 | Remote Access & Binance Config

- Configurato Hermes Agent per accesso remoto via Hermes Desktop
- Test e verifica chiavi API Binance (test_mode)
- Tutti i bot funzionanti in test_mode

## 2026-05-17 | Social Sentiment Engine (v3.2) & Cleanup Massivo

### Sentiment Engine (`utils/sentiment.py`)

- **Fear & Greed Index** (alternative.me) — OK, API gratuita
- **X/Twitter search** — OAuth 1.0a configurato via `requests_oauthlib`. Utente `@sgrivett` autenticato, ma crediti gratuiti esauriti (402 CreditsDepleted). Codice pronto, blocca il tier gratuito.
- **Crypto news fallback** (CoinPaprika + CryptoCompare) — funzionante
- Integrato in Hermes con peso 0.15 (15%), refresh ogni 10 cicli

### Hermes Bot v3.2

- Multi-timeframe context (1m + 1h)
- MACD + divergenze
- Social sentiment engine integrato
- Config in `hermes.json` con flag `enabled`/`weight`/`interval_cycles`

### Cleanup Repository

- Rimossi 849 file spazzatura da `dashboard/` (node_modules, Hermes Agent build artifacts, plugin-sdk, 207 MB)
- Rimosse vecchie strategie zombie (concept_gen_*.py, boot_concepts.py)
- Rimosso AGENTS.md (filosofia AI obsoleta), IDENTITY.md, HEARTBEAT.md, project_orbital_strike.md
- Rimosso ANALYSIS_AND_RECOMMENDATIONS.md (analisi di sistema datata)
- Rimosso `pronto_bot/` (WhatsApp bot non afferente al progetto)
- Rimosso `memory/` (log giornalieri AI)
- Aggiornato .gitignore (aggiunto `.x_creds.json`)
- README riscritto con stato attuale

### Linea di Concetto

Ripristinata nel README dopo cancellazione accidentale:

```
Sopravvivenza → Protezione → Intelligenza → Professionalità
```

E il ciclo autonomo: `TRADING → ANALISI → OTTIMIZZAZIONE → RIDEPLOY`

---

## Stato Attuale (2026-05-17)

| Server | IP | Ruolo | Stato |
|--------|-----|-------|-------|
| **mc2** | 192.168.1.116 | Squadra (4 bot) + Orchestrator | ✅ |
| **Nuvola** | 192.168.1.117 | Grid bot legacy | ✅ |
| **MARCODG1** | 192.168.1.120 | Decommissionato | ❌ |
| **Legion** | — | Decommissionato | ❌ |

### Bot Attivi (mc2)

| Nome | Simbolo | Timeframe | Strategia |
|------|---------|-----------|-----------|
| **Ares** | ETH/EUR | 1m | Trend following |
| **Hermes** | SOL/EUR | 1m | RSI + MACD + Social Sentiment v3.2 |
| **Apollo** | ETH/BTC | 1h | Ratio mean-reversion |
| **Artemis** | BTC/EUR | 1d | SMA50/200 crossover |

### Budget

€125.58 EUR su Binance.

### Repository

`git@github.com:grivetto/money.git` — branch `refactoring`

---

*"Sopravvivenza → Protezione → Intelligenza → Professionalità"*
