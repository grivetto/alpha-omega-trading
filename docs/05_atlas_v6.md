# ATLAS v6 — Profitable Evolution (stato implementazione)

> Refactoring radicale richiesto (TODO utente) sui 4 requisiti vincolanti.
> Aggiornato: 2026-08-24.

## 1. Architettura Infrastrutturale — Data Feeder Centralizzato ZeroMQ ✅

**File**: `denaro/infrastructure/mc2_feeder.py` (feeder, gira su MC2),
`denaro/infrastructure/zmq_market_source.py` (subscriber, gira sui nodi).

- **MC2Feeder** (`systemd/denaro-feeder-mc2.service`, attivo su mc2):
  - 1 WS per exchange (ccxt.pro watch_ticker) + **fallback REST ticker 5s**
  - OHLCV 1h via **RAW API pubbliche** (OKX `publicGetMarketHistoryCandles`,
    Kraken `publicGetOHLC`) — bypassa il bug di ccxt 4.5.x su `fetch_ohlcv`
    (OKX ritorna 0 candle, Kraken fallisce il parsedTimeframe)
  - PUB ZeroMQ: `tcp://0.0.0.0:5557` (ticker), `tcp://0.0.0.0:5558` (ohlcv)
  - **Verificato live**: 30 ticker/15s (SOL/DOGE/XRP da OKX) + 10 OHLCV
- **ZMQMarketSource** (subscriber lato nodi): si connette al feeder, inietta
  prezzi negli handler dell'hub; `healthy()` con TTL 15s → se il feeder cade,
  il nodo degrada al proprio canale WS/REST locale (nessuna perdita di dati).
- **Beneficio**: le WS ridondanti per lo stesso exchange su piu' nodi vengono
  eliminate; OHLCV centralizzato alimenta il regime filter senza che ogni
  nodo fetchi le stesse candle.

## 2. Motore di Rischio — Anti-Deadlock Dynamic Capital Allocation ✅

**File**: `denaro/application/portfolio.py` + integrazione in
`denaro/application/orchestrator.py` (BotTask).

- `PortfolioManager.total_available()` = `free + locked_in_cancellable_buys × 0.85`
  (risolve il deadlock quando `free_balance == 0`: il capitale bloccato in
  ordini limit BUY cancellabili e' capitale virtualmente usabile, scontato).
- `preflight(symbol, min_notional, per_level, price)`:
  - blocca se ci sono **buy speculari** (prezzo > mercato → mai riempiti,
    capitale congelato) → li cancella via API prima di ri-piazzare
  - blocca se `min_notional > available` (capitale insufficiente persino per
    il livello minimo)
  - i livelli sotto il minimo vengono **filtrati dal caller** (semantica
    legacy: skip del livello, non stop globale)
- Il BotTask alimenta il portfolio con free + open orders gia' in mano
  (nessuna chiamata API extra) e usa `total_available` nel pre-flight.

## 3. Filtro Algoritmico di Regime — ADX + ATR Adaptive ✅

**File**: `denaro/domain/regime.py` (filtro) + `denaro/domain/adaptive.py`
(AdaptiveEngine, la strategia) + integrazione in `denaro/denaro_node.py`
(canale OHLCV 1h per bot adaptive) + `denaro/application/orchestrator.py`
(TradeOrchestrator.add_ohlcv_source).

- **RegimeFilter** (ADX Wilder 14, ATR% 14, EMA200 + pendenza, RSI 14):
  - `ADX < 25` → RANGE
  - `ADX > 30 e prezzo < EMA200` → TREND BEAR
  - `ADX > 30 e prezzo > EMA200` → TREND BULL
  - fallback `from_prices()` quando manca OHLCV (documentato: approssimato)
- **AdaptiveEngine** (Policy, stesso contratto GridPolicy):
  - **RANGE**: griglia con spread dinamico = `max(base, ATR × multiplier)`
  - **TREND BEAR**: i BUY vengono DISABILITATI (niente falling knife) e i buy
    residui cancellati — le posizioni esistenti escono con i TP
  - **TREND BULL**: scalper direzionale (una posizione, entry con slip) con
    **trailing take-profit agganciato all'ATR**
- **Verificato con dati reali** (OKX EEA, candle 1h): SOL ADX 18.2 range,
  ADA 10.9 range, DOGE 12.6 range, ETH 21.9 range — classificazione corretta
  con ATR% e EMA200.

## 4. Performance e Pulizia Codice ✅

- **LLM locale (Qwen)**: gia' assente nel codice Denaro (verificato con grep)
  → nessun modulo da rimuovere.
- **BALANCE_CACHE_TTL = 15** negli adapter OKX e Kraken: `fetch_balance`
  con cache 15s + `invalidate_balance()` dopo ordini/fill.
- **`__slots__`** nelle nuove classi: RegimeFilter, RegimeParams, Regime,
  AdaptiveParams, AdaptiveEngine, ExchangeFeeder, MC2Feeder, ZMQMarketSource,
  PortfolioManager, MomentumParams, MeanReversionParams.
- **Buffer circolari**: CircularBuffer (dominio) gia' presente; i nuovi storici
  usano `deque(maxlen=...)` (OHLCV 200, tick 200) — memoria sotto 512M
  (unit feeder ha `MemoryMax=512M`).

## Strategie disponibili (config `strategy:`)

| strategy | File | Comportamento |
|----------|------|---------------|
| `grid` (default) | `domain/grid.py` | griglia statica idempotente |
| `momentum` | `domain/momentum.py` | trend-following EMA fast/slow + RSI |
| `meanrev` | `domain/meanrev.py` | compra l'oversold (RSI), vende il ritorno |
| `adaptive` | `domain/adaptive.py` | regime ADX/ATR: range→grid, bear→blocca buy, bull→scalper |

## Test

- `denaro/tests/test_policies.py`: 10 test (momentum + meanrev)
- `denaro/tests/test_atlas_v6.py`: 12 test (regime + adaptive + portfolio)
- `denaro/tests/test_orchestrator.py`: +2 test stop-loss (priorita' sul CB)
- Suite completa: **137 test verdi**

## Deploy

- **mc2**: `denaro-feeder-mc2.service` ATTIVO (ticker+OHLCV verificati)
- **MARCODG1/nuvola**: package v6 copiato; il subscriber ZeroMQ e'
  opzionale (i nodi continuano a funzionare col MarketDataHub locale);
  l'integrazione ZMQ→hub e' pronta in `zmq_market_source.py`
- config `node.yaml`: paper DOGE/ETH + live DOGE/ETH con `strategy: adaptive`
