# Denaro v3 — Documento di Architettura Riveduta

> **Data:** 23 Giugno 2026  
> **Autore:** Hermes Agent (su richiesta di Sergio Grivetto)  
> **Status:** In attesa di approvazione  

---

## 📉 1. Analisi spietata dei 3 errori principali

### Errore #1 — Frammentazione del capitale e deadlock sistematico

**Cosa è successo:** €200 distribuiti su 3 sub-account (MC2 $83, Nuvola $28, MARCODG1 $93) con grid bot indipendenti su coppie diverse. Ogni bot riceve una fetta di capitale così piccola che qualsiasi ordine blocca TUTTA la liquidità disponibile. Il grid non può piazzare nuovi livelli perché il free balance è zero.

**Dati concreti:**
- MARCODG1: 481 ADA bloccati in un ordine SELL da settimane. Free USDC = $0.002 → 0 livelli grid attivi. Necessario intervento manuale per cancellare l'ordine.
- MC2: DUE grid bot (main.py + mc2_bot.py) in competizione sullo stesso pair SOL/USDC. mc2_bot piazza ordini → main.py vede free=$0.10 → 0 livelli.
- Squadra: 7 bot su MARCODG1 tentano di tradare coppie EUR ma il sub-account ha ZERO EUR. Tutti gli ordini falliscono con NOTIONAL filter.

**Costo stimato:** 6+ settimane di capitale inattivo o bloccato. Centinaia di chiamate API sprecate su ordini che non possono essere eseguiti per mancanza di fondi.

**Root cause tecnica:** I bot leggono `free` balance per calcolare l'allocazione grid, ma il capitale è in `locked` (ordini aperti). Nessun meccanismo di "total available = free + locked in cancellable orders". Nessun controllo pre-volo: il bot non verifica se può effettivamente tradare PRIMA di entrare nel loop.

---

### Errore #2 — Chiamate API massive senza ROI

**Cosa è successo:** Ogni bot esegue il proprio ciclo indipendente di fetch OHLCV, balance, open orders, ticker — moltiplicato per 7 bot Squadra + 3 grid + arb + gariban = ~40-50 richieste API per ciclo. Con cicli di 60 secondi, sono **60.000+ chiamate API al giorno** tra tutti i servizi.

**Dove il sangue è stato versato:**
- **LLM Optimizer (denaro-v2):** 30 secondi di inferenza su qwen3.5:4b per ogni coppia (SOL, ADA), risultato: `conf=0.30, action=hold` nel 100% dei casi osservati. Zero decisioni utili. CPU del PC di casa saturata per nulla.
- **Squadra (7 bot × N pairs):** Ogni bot fetcha OHLCV, balance, open orders indipendentemente. Moltiplicato per self-improve loop (Artemis tenta parametri fuori range e fallisce). WR=5%, Sharpe=-55.79: sta letteralmente pagando Binance per perdere soldi.
- **Nessun caching:** OHLCV identici rifetchati da ogni bot separatamente. Balance fetchato ad ogni ciclo anche se non ci sono stati trade.
- **API calls duplicate:** MC2 aveva DUE grid bot che fetchavano entrambi OHLCV, balance, e ticker per SOL/USDC.

**Costo stimato:** Al rate limit Binance (1200 pesi/minuto), il sistema attuale consuma ~800-1000 pesi/minuto solo per query ridondanti. Ogni superamento del rate limit = blocco temporaneo di TUTTI i bot.

**Root cause tecnica:** Architettura a silos — ogni bot è un'isola che si porta dietro il proprio stack di API calls. Manca un layer di caching condiviso e un data feeder centralizzato.

---

### Errore #3 — Assenza di risk management unificato e azionabile

**Cosa è successo:** Esistono 4 livelli di kill-switch (teorici) ma nella pratica:
- Il kill-switch di Squadra scrive su `bot_lock.json` con checksum SHA256 — ma il file non viene MAI letto dagli altri bot.
- Ogni bot ha la propria logica di stop-loss, dimensionamento, drawdown — parametri diversi, nessuna coordinazione.
- Nessun meccanismo cross-machine: MC2 non sa cosa fa MARCODG1, e viceversa.
- Il profit sharing è in dry-run da sempre perché la master key non ha permessi Universal Transfer.
- **Nessuno stop-loss è mai scattato** nonostante WR=5% su Squadra — significa che i bot continuano a tradare in perdita senza che il kill-switch li fermi.

**Dati concreti:**
- Squadra: WR=5.0%, Sharpe=-55.79, 769 dust asset, €63.75 equity. Nessun intervento automatico.
- MARCODG1 grid: capitale bloccato per settimane senza alert.
- MC2: servizi fantasma in restart loop (ollama 21,853 restart, flash-crash 4,656) — zero monitoring fino all'audit di oggi.

**Costo stimato:** Perdita continua e silenziosa. Impossibile da quantificare senza log storici dei trade.

**Root cause tecnica:** Il kill-switch esiste nel codice ma non è connesso ai bot reali. I bot non leggono lo stato globale. Manca un "circuit breaker" centralizzato che TUTTI i bot devono interrogare prima di ogni trade.

---

## 🏗️ 2. Nuova architettura proposta

### Principio fondante: UN solo processo decisionale per l'intero capitale

```
                        ┌─────────────────────────────┐
                        │     Denaro Engine v3         │
                        │     (unico processo)         │
                        └─────────────┬───────────────┘
                                      │
              ┌───────────────────────┼───────────────────────┐
              │                       │                       │
    ┌─────────▼─────────┐   ┌────────▼────────┐   ┌─────────▼─────────┐
    │   DataFeeder      │   │  RiskEngine      │   │  StrategyEngine   │
    │   (cache + API)   │   │  (global state)  │   │  (1 strategia)    │
    └─────────┬─────────┘   └────────┬────────┘   └─────────┬─────────┘
              │                       │                       │
    ┌─────────▼─────────┐   ┌────────▼────────┐   ┌─────────▼─────────┐
    │ Cache locale (60s) │   │ Circuit Breaker │   │ Grid SOL/USDC     │
    │ 1 fetch = N consumers│  │ Global P&L      │   │ (unica strategia) │
    └───────────────────┘   │ Max Drawdown 3%  │   └───────────────────┘
                            │ Daily Loss Limit │
                            └──────────────────┘
```

### Cosa cambia radicalmente:

| Componente | v2 (attuale) | v3 (proposta) |
|-----------|-------------|---------------|
| **Motore decisionale** | 10 servizi indipendenti, ognuno col proprio loop | 1 processo, 1 loop, 1 strategia |
| **Capitale** | Frammentato su 3 macchine, 4 sub-account | **Consolidato su 1 sub-account principale** |
| **Strategia** | Grid + Arb + Gariban + Squadra (7 bot) + LLM | **Solo Grid Trading** (provata, funzionante) |
| **API calls** | ~800-1000 pesi/min (ridondanti) | **~50-80 pesi/min** (cache + feeder unico) |
| **Risk** | 4 kill-switch non connessi | **Circuit breaker centralizzato pre-trade** |
| **LLM** | Inferenza su ogni coppia ogni ciclo | **Solo regime detection** (1 chiamata/ora) |
| **Deployment** | 3 macchine con configurazioni divergenti | **1 macchina principale (MC2)**, Nuvola/MARCODG1 come backup freddi |
| **Balance check** | fetch_balance() ad ogni ciclo | **Cache 60s + invalidation solo dopo trade eseguito** |

---

### Il DataFeeder — cuore dell'ottimizzazione API

Un singolo modulo che fetcha TUTTI i dati necessari UNA volta per ciclo:

```python
class DataFeeder:
    """Fetch once, serve many. Cache con TTL configurabile."""
    
    def __init__(self, exchange):
        self._cache = {}
        self._ttl = {
            'balance': 60,      # 1 minuto
            'ohlcv': 60,        # 1 minuto  
            'ticker': 30,       # 30 secondi
            'open_orders': 15,  # 15 secondi (dopo trade)
        }
    
    def get_balance(self) -> dict:
        """Ritorna cached o fetcha. Invalida solo dopo trade."""
        ...
    
    def get_ohlcv(self, symbol: str, timeframe: str) -> list:
        """OHLCV cached. Una fetch serve grid + indicatori."""
        ...
```

**Impatto:** Da ~50 chiamate API/ ciclo a ~5 chiamate API/ciclo (-90%).

### Il Circuit Breaker — protezione capitale reale

```python
class CircuitBreaker:
    """Interrogato PRIMA di ogni trade. Se aperto, NESSUNA operazione."""
    
    STATE_CLOSED = 'closed'      # Trading allowed
    STATE_OPEN = 'open'          # ALL trading BLOCKED
    STATE_HALF_OPEN = 'half'     # Reduced size only
    
    def check(self, symbol: str, side: str, amount: float) -> bool:
        # 1. Daily P&L < -3% ? → OPEN (stop totale)
        # 2. Consecutive losses >= 3 ? → HALF_OPEN (size -50%)
        # 3. Total drawdown > 5% ? → OPEN
        # 4. Free balance < min_notional * grid_levels ? → OPEN
        
    def record_trade(self, trade: Trade):
        # Aggiorna P&L cumulativo, consecutive losses, peak equity
```

**Impatto:** Non si piazza MAI un ordine senza passare dal circuito. Il capitale è protetto a livello di core.

---

### Perché SOLO Grid Trading?

1. **Grid è l'unica strategia che ha funzionato**: MC2 grid ha piazzato ordini reali. Arb ha spread positivi ma marginali (+0.02%). Gariban non ha mai eseguito un trade. Squadra ha perso soldi.
2. **Semplicità = profittabilità**: Una strategia, un loop, niente interferenze tra bot.
3. **Capitale consolidato**: $200 su UNICO sub-account → abbastanza per 4-5 livelli grid su SOL/USDC con $40-50 per livello.

---

## 📋 3. Piano d'azione step-by-step

### Fase 0 — Spegnere ciò che perde soldi (SUBITO, oggi)

| Step | Azione | Comando |
|------|--------|---------|
| 0.1 | **Fermare Squadra** su MARCODG1 | `ssh marco@MARCODG1 'sudo systemctl stop squadra && sudo systemctl disable squadra'` |
| 0.2 | **Fermare Gariban** su MC2 (mai eseguito trade) | `ssh sergio@mc2 'sudo systemctl stop denaro-gariban && sudo systemctl disable denaro-gariban'` |
| 0.3 | **Fermare LLM v2** su MC2 (solo hold, inutile) | `ssh sergio@mc2 'sudo systemctl stop denaro-v2 && sudo systemctl disable denaro-v2'` |
| 0.4 | **Fermare Arb** su MC2 (spread irrisori) | `ssh sergio@mc2 'sudo systemctl stop denaro-mc2-arb && sudo systemctl disable denaro-mc2-arb'` |
| 0.5 | **Fermare grid Nuvola** (capitale da consolidare) | `ssh sergio@nuvola 'sudo systemctl stop denaro-nuvola denaro-nuvola-stella denaro-dashboard && sudo systemctl disable denaro-nuvola denaro-nuvola-stella denaro-dashboard'` |
| 0.6 | **Fermare grid MARCODG1** (capitale da consolidare) | `ssh marco@MARCODG1 'sudo systemctl stop denaro-marcodg1 denaro-marcodg1-grid && sudo systemctl disable denaro-marcodg1 denaro-marcodg1-grid'` |

**Risultato atteso:** 0 chiamate API. Sistema fermo. Capitale da consolidare.

### Fase 1 — Consolidare capitale su MC2 (manuale, Sergio)

| Step | Azione |
|------|--------|
| 1.1 | Cancellare TUTTI gli ordini aperti su Nuvola (SOL/USDC) e MARCODG1 (ADA/USDC) |
| 1.2 | Vendere 481 ADA su MARCODG1 → ottenere ~$73 USDC |
| 1.3 | Vendere 0.089 SOL su Nuvola → ottenere ~$6 USDC |
| 1.4 | Trasferire TUTTO il capitale (via Universal Transfer) a **mc2orion** |
| 1.5 | Capitale totale atteso su MC2: ~$204 USDC + 0.987 SOL ≈ **$270** |

### Fase 2 — Scrivere il nuovo engine (sviluppo locale)

| Step | File | Cosa fa |
|------|------|---------|
| 2.1 | `denaro_v3/__init__.py` | Package init |
| 2.2 | `denaro_v3/config.py` | Configurazione centralizzata (pair, livelli, risk) |
| 2.3 | `denaro_v3/data_feeder.py` | Cache OHLCV/balance/ticker con TTL |
| 2.4 | `denaro_v3/circuit_breaker.py` | Risk pre-trade: P&L, drawdown, consecutive losses |
| 2.5 | `denaro_v3/grid_engine.py` | Grid trading puro: calcolo livelli, piazzamento ordini |
| 2.6 | `denaro_v3/main.py` | Loop principale: fetch → risk check → grid → sleep |
| 2.7 | `tests/test_circuit_breaker.py` | Unit test del circuit breaker |
| 2.8 | `tests/test_grid_engine.py` | Unit test del grid engine |
| 2.9 | `tests/test_data_feeder.py` | Unit test del data feeder con mock |

### Fase 3 — Deploy e test (su MC2)

| Step | Azione |
|------|--------|
| 3.1 | Deployare `denaro_v3/` su MC2: `scp -r denaro_v3/ sergio@mc2:~/denaro/denaro_v3/` |
| 3.2 | Avviare in **paper trading mode** (simulazione ordini, no API reali) |
| 3.3 | Verificare 24 ore di funzionamento senza errori |
| 3.4 | Avviare con capitale reale **ridotto**: solo $50 USDC, 2 livelli grid |
| 3.5 | Dopo 48 ore senza problemi: attivare capitale pieno |

### Fase 4 — Pulizia codebase

| Step | Azione |
|------|--------|
| 4.1 | Archiviare TUTTO il codice v2 in branch `legacy-v2` |
| 4.2 | `main` branch = solo v3 |
| 4.3 | Rimuovere: `squadra/`, `strategies/` (vecchie), `trading_engine_v2/`, `arb_bot.py`, `gariban_beggar.py`, `stella_grid.py`, `services/`, file monitor sparsi |
| 4.4 | Mantenere solo: `denaro_v3/`, `core/` (risk, kill_switch riutilizzabili), `config/`, `tests/` |

---

## ⚡ Riepilogo: da 10 servizi a 1

| | v2 (prima) | v3 (dopo) |
|---|-----------|-----------|
| Servizi attivi | 10 | **1** (denaro-v3) |
| Macchine | 3 | **1** (MC2) |
| Strategie | 5 (grid, arb, gariban, squadra, LLM) | **1** (grid) |
| API calls/min | ~800-1000 pesi | **~50-80 pesi** |
| Capitale per strategia | $28-93 frammentato | **$270 concentrato** |
| Risk management | 4 kill-switch scollegati | **1 circuit breaker pre-trade** |
| LLM | Ogni 60s, sempre hold | **1/h per regime detection** |

---

> **Conferma ricezione e priorità comprese. In attesa di approvazione per procedere con la Fase 0 (spegnimento immediato) o con la scrittura del codice v3.**
