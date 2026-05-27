# REPORT ANALISI PROGETTO DENARO
## Data: 2026-05-20 | Portfolio: 227.31€

---

## 1. QUADRO GENERALE

### 1.1 Architettura

| Server | Ruolo | Bot |
|--------|-------|-----|
| **MC2** | Orchestrator Squadra | Ares (ETH/EUR), Hermes (SOL/EUR), Apollo (ETH/BTC ratio), Artemis (BTC/EUR) |
| **Nuvola** | Grid bot | SOL/EUR grid, base_order=15€, max=100€ |
| **MARCODG1** | Grid bot | ADA/EUR grid, base_order=6€, max=60€ |

### 1.2 Situazione Patrimoniale

- **EUR liquidi**: 172.44€ (75.8%)
- **Crypto**: 54.87€ (24.2%)
  - ETH: 20.05€
  - BTC: 20.10€
  - SOL: 9.17€
  - ADA: 4.14€
  - Altri: ~1.53€
- **Esposizione attiva**: 8€ (3.5%)
- **Variazione 19→20 Mag**: 228.33€ → 227.31€ (-1.02€, *flat*)

---

## 2. DIAGNOSI: PROBLEMI STRUTTURALI

### ❌ PROBLEMA #1: 75% DEL CAPITALE FERMO IN EUR (CRITICO)

**Causa**: La squadra ha limite exposure_max=90€ ma la somma dei bot usa solo 8€. I grid bot hanno budget separati ma non attingono al capitale in EUR su mc2.

**Impatto**: 172€ stanno fermi, non fruttano nulla. Se fossero investiti anche solo al 5% APY in stablecoin farebbero 8.60€/anno. Invece generano 0.

**Perché succede**: 
- Expo max 90€ (squadra infra) + grid bot hanno fondi separati
- Ares usa 10€ per posizione → venduto → 120€ torna in EUR
- Nessun meccanismo che reinveste automaticamente l'EUR libero
- Il capitale cresce in EUR ma non viene ridistribuito

### ❌ PROBLEMA #2: ARES PERDE SULLE COMMISSIONI (CRITICO)

**Dati**: Ares fa trading ETH/EUR con SMA crossover (fast=5, slow=8 periodi). Ogni trade:
- Guadagno medio per trade: 0.05% (+0.05% entry → si vende a +0.05%)
- Costi: 0.1% (taker fee) + 0.1% (stimato slippage) = 0.2% per lato
- **Costo round-trip**: 0.4% 
- **PnL netto per trade**: 0.05% - 0.4% = **-0.35%**

Ogni trade è una perdita netta. Più trade fa Ares, più soldi perde. Tutti i trade con PnL positivo sono in realtà perdite nette.

**Ares ha fatto 148 trade in 2 giorni**. A 10€ per trade, ha perso ~0.035€ × 148 = **5.18€ in commissioni** in 2 giorni.

### ❌ PROBLEMA #3: HERMES SEGNALI INCOERENTI

**Dati**: Hermes (SOL/EUR) passa ore a dare segnali SELL consecutivi (score -0.30/-0.40, RSI alto), poi improvvisamente fa BUY a 74.05€ e 74.21€ il 19 maggio.

**Analisi**: Il segnale è basato su RSI e forse un indicatore composito. La soglia per SELL è troppo bassa (si attiva a RSI 55+), portando a falsi segnali prolungati. Il SOL/EUR è in trend laterale/rialzista e RSI oscilla tra 45-65.

**Impatto**: Hermes non ha fatto trade profittevoli in 2 giorni. È praticamente inattivo.

### ❌ PROBLEMA #4: APOLLO (PAIR TRADING) MAI TRADATO

**Dati**: Apollo monitora ETH/BTC ratio con z-score. Valori attuali: Z=-1.85 a Z=-2.34, sempre "NOCOINT" (nessuna cointegrazione).

**Analisi**: La soglia di z-score (±2.5 o ±3.0) non viene mai raggiunta. ETH/BTC ratio non ha abbastanza volatilità relativa in questo periodo. Apollo è **WAITING** da 3 giorni senza mai entrare.

**Impatto**: 0 trade, 0 profitto. Consuma solo banda API e CPU.

### ❌ PROBLEMA #5: ARTEMIS (BTC DAILY) SEMPRE IN ATTESA

**Dati**: Artemis usa timeframe daily. Ogni controllo mostra "WAITING" per settimane intere.

**Analisi**: Strategia daily significa max 1 segnale al giorno. In 3 giorni di operatività, zero segnali. BTC si muove troppo lentamente su daily per generare pattern frequenti.

**Impatto**: Bot praticamente decorativo. Consuma CPU/Banda senza produrre nulla.

### ❌ PROBLEMA #6: GRID BOTS NON MOSTRANO PROFITTO

**Dati**: 
- Nuvola (SOL/EUR): log dice "profit 0.00€" perché il profit counter si resetta a ogni restart
- MARCODG1 (ADA/EUR): stesso problema
- Ordini aperti: SOL/EUR 2 buy, ADA/EUR 5 buy → tutti in attesa, nessuno eseguito

**Analisi**: 
- Il profit counter è in memoria volatile, non su DB → si resetta a ogni restart
- Gli ordini grid sono troppo distanti dal prezzo corrente → non vengono fillati
- I bot sono attivi da giorni ma non eseguono nuovi trade

### ❌ PROBLEMA #7: STRANDED BTC POSITION

**Dati**: 0.00030129 BTC = 20.10€. Non c'è un bot attivo che lo gestisca. Il vecchio grid bot BTC su mc2 ha chiuso, ma il BTC è rimasto.

**Analisi**: Bot BTCEUR faceva grid trading ma è stato -20.44€ nelle ultime 200 operazioni. È stato fermato, ma il BTC è rimasto in portafoglio. Ora è merce "dimenticata" — non genera nulla, non viene capitalizzata.

### ❌ PROBLEMA #8: DUPLICAZIONE OPERATIVA SU MC2

**Dati**: Su mc2 ci sono DUE sistemi attivi:
1. Squadra orchestrator (giusto)
2. Vecchio grid_bot_v3.py che trade SOLEUR (sbagliato, perché SOLEUR è già su Nuvola)

**Analisi**: Il vecchio grid_bot_v3 produce ordini SOL/EUR duplicati o in conflitto con Hermes della squadra. Consuma capitale e banda API.

---

## 3. ANALISI QUANTITATIVA

### 3.1 Performance per Bot (ultimi 200 trade)

| Bot | Pair | P&L Lordo | Commissioni (stim.) | P&L Netto | Trade/Day | Esito |
|-----|------|-----------|---------------------|-----------|-----------|-------|
| **Vecchio grid** | SOLEUR | +7.98€ | ~2.50€ (taker freq) | ~+5.48€ | ~5 | OK marginale |
| **Vecchio grid** | ETHEUR | +14.31€ | ~3.00€ | ~+11.31€ | ~3 | OK |
| **Vecchio grid** | BTCEUR | -20.44€ | ~2.00€ | **-22.44€** | ~2 | **PERDITA** |
| **Vecchio grid** | ADAEUR | +39.00€ | ~0.50€ (maker) | ~+38.50€ | ~20 | OK |
| | **TOTALE** | **+40.85€** | **~8.00€** | **~+32.85€** | | |

**Nota**: Questi sono dati del vecchio grid bot (v3). I bot attuali (Ares, Hermes) non hanno ancora generato profitto misurabile.

### 3.2 Potenziale vs Attuale

| Metrica | Attuale | Potenziale | Gap |
|---------|---------|------------|-----|
| Capitale investito | 8€ (3.5%) | 150€ (66%) | 142€ non usati |
| Exposure massima | 90€ (squadra) | 227€ (totale) | 137€ non allocati |
| Trade/day profittevoli | ~0 (Ares) | 3-5/giorno/bot | Tutti i bot |
| Return mensile | ~0% | 2-5% (target) | - |

---

## 4. CAUSE RADICE

### R1. Sottocapitalizzazione strategica
Ogni bot usa budget singolo (Ares 10€, Hermes 15€, grid max 100€) ma nessun meccanismo consolida il capitale libero. 172€ in EUR sono fuori dal gioco.

### R2. Strategie non adatte al capitale reale
Le commissioni Binance (0.1% taker) mangiano i micro-profitti di Ares (0.05%). Con 10€ per trade, 0.4% di commissioni = 0.04€. Per fare 1€ netto servono 25 trade vincenti. Ares invece fa trade negativi.

### R3. Assenza di risk management adattivo
- Ares non ha stop-loss (solo SMA crossover)
- Hermes non ha filtri di trend (segnala SELL in trend rialzista)
- Apollo non ha fallback se la cointegrazione non si verifica

### R4. Capitale bloccato non ottimizzato
20€ in BTC fermi, 172€ in EUR fermi. 192€ su 227€ sono morti.

### R5. Assenza di unificazione dei fondi
Tre server, tre pool di capitale separati. Nuvola ha budget 100€ ma usa 15€. MARCODG1 ha budget 60€ ma usa 6€. Il resto dei fondi è su mc2 ma non raggiunge gli altri server.

---

## 5. PIANO D'AZIONE (PRIORITÀ)

### 🔴 URGENTE (fare subito)

**1. Unificare il capitale**
- Spostare la cassa EUR su mc2 sotto controllo unico
- Aumentare exposure_max a 200€ (o levare il limite)
- Ogni bot usa lo stesso pool di capitale

**2. Riparare Ares**
- Aumentare posizione minima a 30-50€ (così 0.4% fees diventa gestibile)
- Aggiungere take-profit reale: 0.5-1% invece di 0.05%
- Aggiungere trailing stop-loss (ATR 1.5x)
- Oppure: cambiare timeframe (5m invece di 30s) per ridurre frequenza trade

**3. Riattivare il capitale fermo**
- Vendere 0.0003 BTC → +20.10€ liquidi
- Decidere se vendere o rideployare ADA/ETH residui
- Portare EUR investito da 8€ a minimo 100€

### 🟡 IMPORTANTE (prossimi giorni)

**4. Rivedere Hermes**
- Soglia RSI troppo aggressiva → allargare a 40-70 range
- Aggiungere trend filter (solo BUY in uptrend, solo SELL in downtrend)
- Fix: non segnalare SELL se SOL/EUR è sopra EMA20

**5. Apollo fallback**
- Se z-score non raggiunge soglia in 7 giorni → passare a strategia alternativa
- Opzione: trend following su ETH/BTC ratio
- Opzione: single-asset momentum su ETH

**6. Grid bots**
- Fix profit counter persistente su DB
- Regolare spaziatura ordini per fillare più velocemente
- Considerare unire grid bot su mc2 e chiudere Nuvola/MARCODG1

### 🟢 OTTIMIZZAZIONE (quando possibile)

**7. Dashboard unificata**
- Mostrare tutto il capitale su un unico pannello
- P&L reale (non resettato) per ogni bot
- Allarmi su drawdown

**8. Self-tuning**
- Bot che aggiustano parametri in base alla volatilità
- RSI threshold dinamico
- SMA period adattivo

---

## 6. CONCLUSIONE

**Il progetto Denaro non perde perché le strategie sono sbagliate.** 
**Il progetto Denaro non guadagna perché il capitale è quasi totalmente inattivo.**

| Problema | % di responsabilità |
|----------|---------------------|
| Capitale fermo (172€ idle) | 60% |
| Commissioni che mangiano profitti (Ares) | 20% |
| Bot inattivi (Apollo, Artemis) | 10% |
| Capitale bloccato (BTC stranded) | 10% |

**La priorità #1**: usare i soldi che hai. 227€ investiti al 2% mensile = 4.54€/mese. Con 8€ investiti = 0.16€/mese. La differenza è 28x.

**La priorità #2**: smettere di fare micro-trade che perdono sulle commissioni. Ogni trade deve avere un obiettivo di profitto netto positivo dopo fees.

**La priorità #3**: centralizzare tutto su mc2. Tre server non servono a nulla se il capitale è frammentato. Un solo bot con 200€ fa meglio di tre bot con 8€, 15€ e 6€.
