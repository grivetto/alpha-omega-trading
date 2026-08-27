# Istanza TREND — "miracolo onesto" (diversificatore direzionale)

Stato: ATTIVA in PAPER · Creato: 2026-08-27 · Doc: `docs/08_istanza_trend.md`

## Cos'è
Una seconda istanza di trading parallela che cattura i **trend** che la griglia
bilaterale perde (la griglia guadagna nei range e sta ferma nei movimenti
direzionali). Niente miracoli garantiti: è un **diversificatore di portafoglio**
con rendimento atteso più alto NEI trend e drawdown più alto nei range —
dimensionato da stop-loss e circuit breaker.

## Architettura
- **Nodo dedicato**: `denaro-node-trend.service` su MARCODG1 (config
  `config/node_trend.yaml`, data_dir `node_data_trend` — separato dal nodo main)
- **4 bot paper** (150€ virtuali ciascuno):
  - SOL/EUR, ETH/EUR → **MomentumPolicy** (EMA 8/21 + RSI>50, 1 posizione,
    TP 2.5%, entry-slip 0.2%)
  - ADA/EUR, XRP/EUR → **AdaptiveEngine** (griglia ATR in range, scalper
    trailing in bull, zero buy in bear)
- **Override per-istanza**: `config/strategy_overrides_trend.json` (fix bug F1:
  l'istanza trend leggeva gli override del main → i bot momentum erano stati
  convertiti in grid)
- **Brain**: monitora unit + 4 bot (`trend:paper:*`), auto-heal attivo

## Validazione 24h (metodologia)
Confronto **a parità di finestra** dai journal dei trade (`sell_filled` con
ts >= partenza trend), non dai totali storici. Il Brain calcola il verdetto
automatico allo scadere e lo invia su Telegram + `trend_validation.json`.

**Verdetto WFA-aware** (niente deploy su finestra fortunata):
- Paper 24h: trend > grid (PnL totale della finestra)
- **WFA momentum 37gg** (900 barre 1h, 4 fold): ret media >= -3%
- Solo se ENTRAMBE → CONFERMA → deploy live

## Evidenze (oneste)
- Prime ore di paper: TREND +9.07€ (16 trade) vs GRID +0.00€ (0) — finestra favorevole
- **WFA 37gg**: SOL momentum -4.7% vs grid -0.9%; ETH -7.3% vs grid +6.9%
  → **il momentum non batte la griglia nel regime attuale**: il trend è un
  diversificatore, si attiva davvero quando il mercato entra in trend
  (Hurst/ADX alti)
- Memory/CPU: 165MB, ~1% CPU — nessun impatto sul nodo main

## Percorso LIVE (Kraken — OKX sub non più possibili)
- Endpoint verificati dal docs ufficiale: `POST /0/private/CreateSubaccount`
  + `POST /0/private/AccountTransfer`
- Prova reale: `EAPI:Invalid key` → alla chiave master manca il permesso
  **"Subaccounts"** (da abilitare in Kraken web → Security → API)
- Servono dall'utente: (1) permesso Subaccounts, (2) email per il sub,
  (3) API key del sub-account (`TRENDSUB_` nel .env)
- Deploy: `python scripts/trend_live_deploy.py <email> 40` — crea trendsub,
  trasferisce EUR dal master (~52€ disponibili), avvia
  `denaro-node-trend-live.service` con `config/node_trend_live_kraken.yaml`
  (momentum SOL, capital 30, TP 3% per fee Kraken 0.25%×2, stop 10%, CB 5%)

## Regole rispettate
- Mai due engine sullo stesso account (il live richiede il sub-account)
- Il trend live parte SOLO con verdetto CONFERMA
- Tutto committato su Git (tag `v7-Brain-DeepSeek` + commit successivi)
