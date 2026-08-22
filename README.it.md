# ⚡ ALPHA-OMEGA TRADING — ATLAS

[![License: Unlicense](https://img.shields.io/badge/license-Unlicense-blue.svg)](http://unlicense.org/)
[![Python](https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![CCXT](https://img.shields.io/badge/exchange-CCXT%20Pro%20%2F%20Kraken%20%7C%20OKX-5741D9?logo=bitcoin&logoColor=white)](https://github.com/ccxt/ccxt)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20systemd-FCC624?logo=linux&logoColor=black)](https://www.freedesktop.org/wiki/Software/systemd/)
[![Status](https://img.shields.io/badge/status-LIVE-brightgreen)](https://github.com/grivetto/alpha-omega-trading)

> **ATLAS** è l'evoluzione modulare, asincrona e multi-exchange del sistema legacy **Denaro**. Stessi exchange, stesse credenziali, stessa filosofia — ricostruiti con architettura pulita, pattern di resilienza e risk management integrato.

---

## 🏗️ Cos'è ATLAS

ATLAS è un sistema di trading algoritmico distribuito scritto in Python 3.12 con `asyncio`. Sostituisce il codebase monolitico di Denaro con un'architettura modulare:

- **Multi-exchange**: Kraken e OKX Europe (EEA) via CCXT async + CCXT Pro (WebSocket)
- **Multi-nodo**: un'istanza per ogni nodo di trading (`nuvola`, `MARCODG1`)
- **Strategia a griglia**: ordini limit buy/sell attorno al prezzo medio
- **Resiliente**: timeout → retry con backoff esponenziale → classificazione degli errori non ritentabili
- **Risk-managed**: limiti di drawdown, perdita giornaliera, size delle posizioni, esposizione, correlazione + kill switch
- **Osservabile**: logging JSON, API HTTP di health/readiness

## 🧩 Architettura

```
atlas/
├── main.py                 # Entry point: ciclo di vita + dependency injection
├── core/
│   ├── config.py           # Pydantic settings + caricamento YAML con sostituzione ${VAR}
│   ├── events.py           # EventBus (pub/sub asincrono: tick, fill, eventi di rischio)
│   ├── lifecycle.py        # GracefulShutdown (gestione SIGINT/SIGTERM)
│   └── resilience.py       # decorator exchange_call: timeout → retry → circuit breaker
├── connector/
│   ├── interface.py        # classe astratta ExchangeConnector
│   ├── ccxt_adapter.py     # implementazione CCXT async (REST + WebSocket)
│   └── models.py           # Ticker, OrderBook, Balance
├── strategy/
│   └── engine.py           # GridStrategy + StrategyEngine (loop tick, dedup ordini aperti)
├── execution/
│   ├── router.py           # ExecutionRouter: pipeline di invio ordini
│   └── models.py           # OrderRequest, OrderResponse, CancelResponse
├── portfolio/
│   └── manager.py          # ExchangeRegistry + PortfolioManager (limiti di rischio, equity)
├── observability/
│   └── logging.py          # logging strutturato JSON
└── storage/                # persistenza dello stato
```

### Pipeline di esecuzione

```
Ticker → StrategyEngine (GridStrategy.on_tick)
       → ExecutionRouter.submit(OrderRequest)
       → CCXTAdapter.create_order (via exchange_call: timeout→retry→classify)
       → Exchange (Kraken / OKX EEA)
```

Il loop di strategia è limitato (massimo 1 segnale per simbolo ogni 60s) e deduplicato sugli ordini aperti: il bot non accumula mai ordini alla cieca.

## ⚙️ Configurazione

Tutta la configurazione vive in `config/` come YAML, con sostituzione `${VAR}` risolta da `.env`:

**`config/exchanges.yaml`** — credenziali e tuning degli exchange:

```yaml
exchanges:
  - name: kraken
    api_key: ${KRAKEN_API_KEY}
    api_secret: ${KRAKEN_API_SECRET}
    rate_limit_rps: 5.0
    rate_limit_burst: 10
  - name: okx
    api_key: ${OKX_API_KEY}
    api_secret: ${OKX_API_SECRET}
    passphrase: ${OKX_API_PASSPHRASE}
    extra:
      eea: true        # → forza l'hostname eea.okx.com (OKX Europe)
```

> ⚠️ **OKX Europe (EEA)**: il flag `extra.eea: true` è obbligatorio. Senza, il bot punta a `api.okx.com` e ogni chiamata autenticata fallisce con errore 50119/50111.

**`config/strategies.yaml`** — parametri di strategia:

```yaml
strategies:
  - strategy_id: grid_btc_eur
    class_path: atlas.strategy.engine.GridStrategy
    enabled: true
    symbols: ["BTC/EUR"]
    exchanges: ["kraken"]
    params:
      grid_levels: 3          # numero di livelli della griglia attorno al prezzo medio
      spread_pct: 0.005       # distanza tra i livelli (0.5%)
      per_level_pct: 0.10     # allocazione di equity per livello
      order_size: 0.00005     # size esplicita (sovrascrive per_level_pct)
      min_notional: 5.0       # valore minimo dell'ordine
```

**`.env`** — credenziali API (mai committate; vedi `.gitignore`).

## 🛡️ Risk Management

Limiti di default (`atlas/core/config.py`), applicati da `PortfolioManager`:

| Limite | Valore |
|--------|--------|
| Drawdown massimo del portafoglio | 20% |
| Perdita massima giornaliera | 5% |
| Size massima posizione | 25% dell'equity |
| Esposizione massima per valuta base | 30% |
| Esposizione massima per correlazione | 70% |
| Leva massima | 1.0 (solo spot) |

Le violazioni emettono `RiskEvent` sull'event bus e possono attivare il **kill switch**.

## 🔄 Compatibilità con Denaro

ATLAS è l'evoluzione diretta di **Denaro**: preserva ciò che funzionava e corregge ciò che non funzionava.

| Aspetto | Denaro (legacy) | ATLAS |
|---------|-----------------|-------|
| Codebase | Monolitico (`engine_solo.py`, `bot_v5.py`) | Pacchetto modulare `atlas/` |
| Accesso exchange | Chiamate CCXT dirette | CCXT async via `CCXTAdapter` + strato di resilienza |
| Strategia | Griglia hardcoded per bot | `GridStrategy` dichiarativa da YAML |
| Rischio | Sparso in check ad-hoc | `PortfolioManager` centrale con limiti rigidi |
| Osservabilità | File di log | Logging JSON + API HTTP `/health` + `/ready` |
| Resilienza | Assente | Timeout → retry → circuit breaker (`exchange_call`) |
| Configurazione | Costanti nel codice | YAML + `.env` con sostituzione `${VAR}` |

**Coesistenza**: entrambi i sistemi girano sugli stessi nodi ed exchange. Leggono **sezioni separate** dello stesso `.env` (chiavi Denaro vs chiavi ATLAS), usano unità systemd separate e non condividono mai lo stato degli ordini. I parametri della griglia Denaro si mappano direttamente sui parametri di `GridStrategy` (`grid_levels`, `spread_pct`, `per_level_pct`).

**Percorso di migrazione**: un bot a griglia Denaro si migra (1) scrivendo i suoi parametri in `config/strategies.yaml`, (2) aggiungendo la sua sezione di chiavi API in `.env`, (3) avviando `atlas-engine.service`.

## 🚀 Deployment

```bash
# 1. Dipendenze
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2. Configurazione
cp .env.example .env            # inserire le credenziali API
# modificare config/exchanges.yaml + config/strategies.yaml

# 3. Esecuzione (foreground)
.venv/bin/python -m atlas.main

# 4. Esecuzione come servizio (produzione)
sudo systemctl enable --now atlas-engine
sudo systemctl enable --now atlas-watchdog   # auto-healing
```

**`atlas-engine.service`** esegue il bot con `Restart=always`; **`atlas-watchdog.service`** riavvia il motore quando smette di rispondere.

### Health API

```
GET /health   → {"status": "healthy", "service": "atlas-engine", "exchanges": [...], "strategies": [...]}
GET /ready    → {"ready": true|false, "service": "atlas-engine"}
```

Il server di health si bind su `[::]:8080` (dual-stack IPv4/IPv6) così i nodi dietro CGNAT possono essere monitorati da remoto.

## 📊 Deployment attuale

| Nodo | Exchange | Coppie | Servizio |
|------|----------|--------|----------|
| `nuvola` | Kraken | BTC/EUR | atlas-engine + watchdog |
| `MARCODG1` | OKX (EEA) | ETH/EUR, SOL/EUR, XRP/EUR, DOGE/EUR | atlas-engine + watchdog |

## 🧠 Principi di design

1. **Code is law, profit is proof** — ogni decisione di trading è deterministica e auditabile.
2. **Protezione del capitale prima di tutto** — i limiti di rischio sono applicati nel percorso del codice, non su una lista di buoni propositi.
3. **La distribuzione è resilienza** — due nodi indipendenti, nessun punto singolo di guasto.
4. **Non sprecare nulla** — I/O asincrono, niente framework oltre a quelli usati, un processo per nodo.
5. **Mai fidarsi di credenziali nel codice** — i segreti vivono solo in `.env` (gitignored).

## 📄 Licenza

[The Unlicense](http://unlicense.org/) — pubblico dominio. Usalo, studialo, rompilo, miglioralo.
