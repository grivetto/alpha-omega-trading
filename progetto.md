# Progetto Denaro — Stato operativo verificato (2026-09-24)

Tre macchine, tre subaccount separati, tre strategie complementari.
Questo file riporta SOLO fatti riconciliati con l'exchange e con systemd.

## Architettura

| Nodo | Host | Subaccount OKX | Strategia | Asset | Stato |
|------|------|----------------|-----------|-------|-------|
| mc2 | locale | mc2sub1 | trend (ATR+EMA) | BTC ETH SOL XRP DOGE (+TRX CRV) | user service attivo |
| nuvola | 87.106.3.15 | nuvolasub1 | trend (ATR+EMA) | LINK AVAX DOT UNI SUI MINA | system service attivo |
| MARCODG1 | 87.106.222.123 | marcosub1 | trend (ATR+EMA) | ADA ARB XLM ALGO | system service attivo |

- Codice canonico: un solo repo `grivetto/alpha-omega-trading`, checkout in
  `/home/sergio/alpha-omega-trading` (mc2, nuvola) e `/home/marco/alpha-omega-trading` (MARCODG1).
- Nessun overlap di asset tra i tre conti: portafoglio diversificato, non tre
  volte la stessa scommessa.
- Chiavi: file `.env_<nodo>` in `config/`, permessi 600, MAI in git
  (.gitignore li esclude). Ogni bot usa SOLO le variabili del proprio prefisso
  (fix fail-closed del 2026-09-24: con `env_prefix` valorizzato nessun fallback
  su variabili generiche → isolamento subaccount garantito).

## Capitale riconciliato (API main + subaccount, 2026-09-24)

Riconciliazione integrale eseguita con chiave main (da MARCODG1, IP-bound):
- main account: 0.003 EUR + dust — funding account vuoto.
- Subaccount (mc2sub1, nuvolasub1, marcosub1, marcosol1, marcodoge1):
  funding = 0 per tutti; trading = dust (mc2sub1 SOL ~0.10 EUR, resto dust).
- TOTALE OKX: ~0.15 EUR. Il capitale (~67 EUR) presente al 19/09 non è più
  sui subaccount OKX: va depositato dal proprietario.

| Subaccount | Equity reale | Capital dichiarato nei config |
|------------|--------------|-------------------------------|
| mc2sub1 | ~0.10 EUR (SOL 0.000987) | 42.12 EUR/bot |
| nuvolasub1 | ~0.0003 EUR (dust) | 24.83 EUR/bot |
| marcosub1 | ~0.0001 EUR (dust) | 42.04 EUR/bot |
| main | ~0.003 EUR (dust) | — |

Conseguenza: la guardia "equity inattendibile → tick saltato" blocca ogni
ordine su tutti e tre i nodi. ZERO ordini live piazzati (verificato:
open_orders=0 su tutti i subaccount). Non è un incidente: è il fail-safe che
funziona. Per tradare servono depositi reali sui subaccount.

## Piano allocazione capitale (tre nodi, tre strategie)

Il capitale va distribuito **su tutti e tre i subaccount** in proporzione
al numero di bot e alla diversificazione degli asset. Esempio con 500 EUR
totali (adattabile all'importo reale versato):

| Nodo | Subaccount | Strategia | Bot | Asset | Capitale nodo | Capitale/bot |
|------|------------|-----------|-----|-------|---------------|--------------|
| mc2 | mc2sub1 | Trend ATR+EMA | 7 | BTC ETH SOL XRP DOGE TRX CRV | **200 EUR** | ~28.6 EUR |
| nuvola | nuvolasub1 | Trend ATR+EMA | 6 | LINK AVAX DOT UNI SUI MINA | **150 EUR** | ~25.0 EUR |
| MARCODG1 | marcosub1 | Trend ATR+EMA | 4 | ADA ARB XLM ALGO | **150 EUR** | ~37.5 EUR |

**Totale: 500 EUR** — zero overlap di asset (17 coppie uniche).

Regole operative:
- Ogni bot usa SOLO il budget del proprio subaccount e del proprio simbolo
  (isolamento garantito da `env_prefix` + fail-closed env()).
- Attivazione condizionata: equity reale ≥ capitale dichiarato nel config
  (altrimenti guardia "equity inattendibile" blocca i tick).
- Risk per trade: 2% del capitale del bot (config `risk_pct: 0.02`).
- Stop giornaliero: -3% equity nodo; max drawdown: -10% equity nodo.
- min_notional OKX: 1 EUR/ordine → capitale/bot deve essere ≥ ~20 EUR
  per avere margine su fee + slippage + distanza griglia.

Prossimo passo operativo: depositare i fondi sui tre subaccount secondo
l'allocazione scelta, poi verificare che i tick smettano di essere saltati
su tutti e tre i nodi (journalctl + health endpoint).

## Risorse

- Vault chiavi: `~/.denaro_vault/keys_master.env` — le chiavi OKX lì contenute
  risultano REVOCATE (50119) al 2026-09-24.
- Chiavi VIVE: `~/denaro_legacy/secrets/{main,mc2sub1,nuvolasub1,marcosub1}_okx.env`
  (rotazione 2026-09-19) — verificate con ccxt il 2026-09-24.
- Kraken: rimosso dal progetto (19/09/2026). Le chiavi Kraken non sono più usate.

## Servizi systemd

- mc2: `denaro-node-mc2.service` (user unit, enabled, linger=sergio=yes) +
  infra system services: aggregator :8912, dashboard :8913, exporter :9100,
  feeder, health :8911.
- nuvola: `denaro-node-nuvola-trade.service` (system unit, enabled).
- MARCODG1: `denaro-node-marcodg1-xrp.service` (system unit, enabled) +
  infra: health :8911, aggregator :8912, dashboard :8913, exporter :9100,
  Grafana, Prometheus, landing :8914.

## Monitoraggio Zabbix

Ogni host monitora il PROPRIO nodo tramite agent locale:

- mc2 (`/etc/zabbix/zabbix_agentd.d/denaro_grid.conf`):
  `denaro.mc2.active`, `denaro.health.status`, `denaro.health.equity`
- nuvola (`/etc/zabbix/zabbix_agentd.conf.d/denaro_grid_bot.conf`):
  `denaro.nuvola_trade.active`, `denaro.health.bots`, `denaro.health.age`
- MARCODG1 (`/etc/zabbix/zabbix_agentd.d/denaro_grid.conf`):
  `denaro.marcodg1_xrp.active`, `denaro.health.status`, `denaro.health.bots`

Elementi vecchi (denaro-v3, zabbix_status.py, denaro_metrics.py) rimossi.
La pulizia lato SERVER (host/item nel frontend Zabbix) richiede accesso
API/UI di Zabbix su MARCODG1 — da fare con le credenziali di Zabbix.

## Layer di ricerca advisory — TradingAgents (dal 2026-09-25)

- Submodule `tradingagents/` (TauricResearch, MIT) + venv isolato `.venv` +
  config `config/.env_tradingagents` (DeepSeek v4-flash + TypeSafe/JEV).
- Runner `tools/tradingagents_advisory.py` in modalità **log-only**: produce
  un rating di ricerca (Buy/Overweight/Hold/Underweight/Sell) per asset;
  NESSUN ordine, nessuna chiave exchange, nessuna influenza sulle strategie
  live. Output in `logs/tradingagents/` (gitignored).
- Cron giornaliero su mc2 (06:10): BTC+ETH → `logs/tradingagents/cron.log`.
  Costo misurato ~$0.04/run (~$2.5/mese per 2 asset).
- Caveat tecnico: usare model ID `deepseek-v4-flash` (non `deepseek-flash`),
  altrimenti lo structured output del framework si rompe — dettagli in
  `docs/62_tradingagents_2026-09-25.md`.
- Utilizzo previsto: confronto statistico rating advisory vs segnali trend
  live vs rendimenti forward, per valutare se alza l'expectancy.

## Prossimi passi (in ordine)

1. Riconciliazione capitale main→subaccount (API main da MARCODG1) e funding
   dei subaccount fino a min_notional (1 EUR/ordine) + capitale di lavoro.
2. Verifica dry-run end-to-end con capitale reale minimo su un solo subaccount.
3. Pulizia Zabbix lato server (rimuovere item/host obsoleti).
4. Migrazione servizi infra MARCODG1 da ~/denaro a ~/alpha-omega-trading:
   COMPLETATA il 2026-09-25 (unit su path canonici, tutte attive).
5. TradingAgents: dopo ~2 settimane di log advisory, valutare il valore
   aggiunto (rating vs segnali trend vs rendimenti forward). Se nullo,
   disattivare il cron (costo ~$2.5/mese).
