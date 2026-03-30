# 🚀 ORBITAL COMMAND: NEON SQUAD (v1.0.0 - Institutional Edition)

**Branch Attuale:** `work_in_progress` (A.G.I. Quantitative Testing)

Benvenuto nell'**Orbital Command**, un'infrastruttura algoritmica di livello istituzionale (Hedge Fund Quantitativo) progettata per operare nei mercati delle criptovalute 24/7. Questo ecosistema non è un semplice "bot di trading", ma un'Intelligenza Artificiale distribuita su oltre 40 micro-servizi indipendenti, concepita per estrarre valore tramite Arbitraggio, Market Neutrality, High-Frequency Trading (HFT) e Machine Learning Evolutivo.

La filosofia di base è la preservazione del capitale: **il Rischio Zero Matematico** tramite l'Hedging dinamico, unito a scommesse asimmetriche ad alto potenziale su inefficienze temporali e spaziali.

---

## 🏛️ FASE 1: RICAVO NORMALE (L'Ecosistema a Rischio Zero)

Questa fase rappresenta le fondamenta operative attuali del server. La priorità è la preservazione del capitale tramite coperture matematiche (Hedging) e un'estrazione lenta, sicura e inesorabile dal mercato centralizzato (CEX).

### 🏛️ L'ARCHITETTURA A 4 TIER (Le Forze Armate)

Il capitale globale è frammentato e isolato in 4 distaccamenti operativi indipendenti per massimizzare l'efficienza delle fee e isolare il rischio di rovina statistica.

### 🟢 TIER 1: La Roccaforte (Binance Spot)
Il nucleo centrale del portafoglio (85% del capitale). Opera rigorosamente senza leva finanziaria.
- **Sniper Squad (15 Bot):** Algoritmi direzionali pesanti che acquistano esclusivamente i minimi locali ("Buy the Dip") su asset ad alta capitalizzazione.
- **La Legione (28 Micro-Bot):** Uno sciame di micro-esecutori lenti e inesorabili progettati per accumulare frazioni di altcoin solide nel lungo periodo.
- **Project Olympus (Grid Trading):** Un ragno tessitore HFT che piazza fitte griglie di ordini limit bidirezionali per estrarre profitto dalla volatilità laterale (mercati noiosi).

### 🔵 TIER 2: Il Laboratorio HFT (MEXC Spot)
Sfrutta la politica a "Zero Commissioni Maker/Taker" dell'exchange MEXC.
- **MEXC Nano Squad:** Esegue micro-scalping frenetico. Poiché le fee sono pari a zero, il bot può chiudere operazioni in profitto anche solo dello 0.05%, accumulando migliaia di micro-transazioni giornaliere che su Binance sarebbero in perdita a causa delle commissioni.

### 🔴 TIER 3: Le Forze Speciali (Bitget Futures)
Il distaccamento ad alto rischio e alto rendimento. Lavora con frazioni minuscole di capitale (es. 10 USDT) ma utilizza la Leva Finanziaria per amplificare i rendimenti.
- **Kamikaze Bot:** Un missile balistico direzionale (Leva 20x) che si attiva esclusivamente durante breakout parabolici o notizie macro-economiche esplosive.
- **Blade Runner:** Scalper direzionale (Leva 10x) per cavalcare i trend intraday violenti.

### 🛡️ TIER 4: Il Bunker Strategico (Hedging & Arbitraggio)
Il cuore ingegneristico del fondo. Qui non si scommette sulla direzione del mercato, si sfrutta la matematica pura.
- **Delta Neutral Hedger (`delta_neutral_hedge.py`):** Calcola al centesimo l'esposizione al rischio delle monete Spot su Binance e apre in totale autonomia una posizione SHORT speculare su Bitcoin tramite Bitget Futures. Se il mercato crolla del 50%, lo Short guadagna la stessa identica cifra, annullando le perdite e rendendo il portafoglio immune ai bear market.
- **Asian Echo Sniper (`spatial_arbitrageur.py`):** Arbitraggio Spaziale (Lead-Lag). Sfrutta la latenza tra i mercati asiatici (MEXC) e quelli europei (Binance). Se una moneta esplode in Asia, il bot la compra in Europa prima che i trader occidentali se ne accorgano, incassando l'onda d'urto del fuso orario.

---


---

## 💥 FASE 2: FACCIAMO DENARO! (The Money Printer Engine)

Questa è l'evoluzione predatrice dell'Hedge Fund, nata con l'unico dogma imposto dal Comandante: **"Generare profitti asimmetrici e massicci a fronte di capitale ridotto" (Target 20% ROI Giornaliero)**.
Per raggiungere volumi irrealistici nel trading umano, la macchina abbandona il "prevedere il mercato" e passa all'"estrarre valore con la forza" tramite la Finanza Decentralizzata (DeFi) e i Nodi RPC.

1. **Il Cervello MEV (Maximal Extractable Value) - *Il Ladro Invisibile*:** Connesso direttamente alla Mempool della rete Arbitrum One tramite un Nodo Privato (Alchemy WSS RPC). Il bot possiede un Wallet Web3 autonomo con carburante in ETH, monitorato in tempo reale dalla Dashboard. Spia i grandi fondi tramite WebSockets Alchemy. Spia i grandi fondi che stanno per comprare una moneta, la compra un millisecondo prima di loro sfruttando la latenza del loro nodo, e gliela rivende in faccia un millisecondo dopo (Sandwich Attack). Profitto matematico istantaneo e a rischio zero.
2. **Il Cervello Flash Loan - *I Prestiti Quantitativi*:** Chiede in prestito **1 Milione di Dollari** dalla blockchain (Aave/dYdX) per la durata esatta di 1 secondo (senza collaterale). Svuota un'inefficienza globale (Arbitraggio), restituisce il milione pagando 5$ di gas fees e intasca l'intera differenza netta. 
3. **Il Super-Cervello A.G.I. - *Il Programmatore Divino*:** Integrazione API di modelli LLM superiori (Claude 3.5 / GPT-4). L'Intelligenza Artificiale non usa più librerie statistiche preimpostate: naviga su internet, legge i paper di finanza quantitativa universitari e **scrive da sola nuovi algoritmi in Python e Solidity**, compilandoli e testandoli mentre l'utente dorme.

---

## 📡 IL CERVELLO CENTRALE (Fase 1)

I mercati non si battono guardando i grafici, ma reagendo ai dati prima degli altri.

1. **⚡ RAM-Disk WebSockets (`orbital_websocket.py`):**
   I bot tradizionali interrogano le API REST ogni 2 secondi e vengono bloccati dai Rate Limits. L'Orbital Command mantiene un tunnel WebSocket permanente aperto con l'Exchange, scaricando migliaia di variazioni di prezzo al secondo direttamente nella **Memoria RAM volatile (`/dev/shm`)** del server Linux. I bot operativi leggono i prezzi dalla RAM in 2 millisecondi, garantendo un'esecuzione High-Frequency Trading (HFT) paragonabile ai fondi istituzionali.

2. **📰 News Sentiment Sniper (`news_sentiment_sniper.py`):**
   Bot di Web Scraping leggerissimo che legge in background i feed RSS di testate come *Cointelegraph* e *CoinDesk*. Scansiona i titoli in tempo reale alla ricerca di "Keyword Esplosive" (es. *Hack, Arresto, ETF, Musk*). Traduce il testo in segnali operativi (LONG o DEFCON) in 3 secondi netti, posizionando le truppe prima ancora che i trader umani abbiano caricato la pagina web.

3. **🏦 Extreme Funding Arbitrage (`funding_arbitrage_estremo.py`):**
   Scansiona costantemente i tassi di interesse (Funding Rates) di tutti i contratti Perpetual mondiali. Quando individua un'anomalia speculativa (trader in preda alla FOMO disposti a pagare tassi enormi per andare LONG su memecoin inutili), il bot entra SHORT in leva. L'obiettivo non è il prezzo, ma incassare passivamente gli enormi interessi pagati dai trader avversari ogni 8 ore (rendita passiva da strozzinaggio istituzionale).

4. **🔪 Dumping Knife Sniper (`dumping_knife_sniper.py`):**
   Algoritmo specializzato nei "Flash Crash". Resta in letargo finché non rileva un crollo irrazionale (es. -2.5% in 15 minuti su SOL). In quel nanosecondo, entra pesantemente LONG sul fondo del baratro per catturare meccanicamente il "Rimbalzo del Gatto Morto" (+1.5%), per poi sparire nuovamente nell'ombra.

5. **🐋 Proxy On-Chain Futures (`whale_alert_onchain.py`):**
   Siccome i dati On-Chain puri costano migliaia di dollari, questo bot funge da proxy gratuito: spia anomalie e picchi di volume nell'Open Interest dei contratti Futures istituzionali per anticipare i movimenti delle Balene (Whales) prima che scarichino sul mercato Spot.

---

## 🛡️ I GUARDIANI INFRASTRUTTURALI

La macchina è progettata per l'Auto-Guarigione (Self-Healing) e la sopravvivenza autonoma in scenari catastrofici.

- **👑 Zabbix Watchdog:** Il supervisore del demone di sistema. Scruta l'uso della memoria RAM (prevenzione Out-Of-Memory), l'uso della CPU e il "battito cardiaco" (timestamp degli ultimi log) di tutti i 40 bot. Se un processo si blocca o diventa uno "Zombie", Zabbix lo killa e lo resuscita.
- **🚨 Crisis Manager (DEFCON 2):** Un interruttore di sicurezza globale ("Circuit Breaker"). Se il mercato globale (Bitcoin) registra un'emorragia improvvisa del >4%, il Crisis Manager dichiara lo stato di DEFCON 2: blocca immediatamente tutti gli acquisti Spot (evitando l'effetto "Falling Knife") e autorizza solo le operazioni di Hedging e Shorting.
- **🧹 Midnight Sweeper (La Regola del 33%):** Ogni operazione chiusa in profitto viene tracciata. A mezzanotte esatta, lo Sweeper preleva automaticamente il **33% dell'utile netto giornaliero** e lo mura in una "Cassaforte" crittografica intoccabile, trasformando i profitti volatili in ricchezza garantita a lungo termine.
- **📈 L'Auto-Compounder:** Si sveglia ogni 12 ore, ricalcola il patrimonio netto totale (NAV) e utilizza la formula di Kelly per aumentare o diminuire dinamicamente le "Size" (la potenza di fuoco) di tutti i bot, sfruttando il miracolo matematico dell'interesse composto.

---

## 🧬 EVOLUTIONARY AI BOT BUILDER (Darwinian Engine)

L'apice dell'infrastruttura. L'Orbital Command ospita un processo di A.G.I. (Artificial General Intelligence) locale.
Ogni **5 minuti**, il Motore Evolutivo si sveglia:
1. Legge le metriche di performance e killa senza pietà i bot obsoleti o in perdita.
2. Utilizza librerie quantificabili (es. Scikit-learn, Random Forest) per **inventare letteralmente una nuova strategia di trading in Python**.
3. Esegue un backtest istantaneo in memoria.
4. Se la strategia risulta profittevole, la "Deploya" (pubblica) in produzione, la aggiunge al registro del Guardiano e fa un push automatico sul repository GitHub (branch `work_in_progress`). La macchina scrive il suo stesso codice.

---

## 📱 TELEGRAM UI & SICUREZZA MILITARE

Il controllo remoto dell'Hedge Fund avviene tramite un Bot Telegram crittografato (`telegram_bot_interactive.py`), dotato di un'architettura a permessi asimmetrici:

- **🔐 Profilo Comandante (Admin Mode):** Autenticazione hardcoded tramite Chat ID. Permette la visione in chiaro del portafoglio totale, l'accesso ai bottoni rossi ("Panic Sell", "All-In BTC", "Spegni Bot") e il monitoraggio degli incassi giornalieri.
---

## 💻 INTERFACCIA E TELEMETRIA (Dashboard & Telegram)
L'ecosistema è comandato e monitorato tramite due interfacce distinte e ultra-dettagliate:
- **Cyberpunk Web Dashboard (`dashboard_server.py` su porta 8080):** Una plancia di comando esposta via Reverse Proxy (HTTPS 8443) che mostra le metriche hardware in tempo reale (CPU, RAM, SWAP) tramite la libreria `psutil`, e il calcolo esatto del "Fleet Memory Load" di tutti i bot. Ricarica automatica ogni 10 secondi.
- **Telegram C&C (Comando e Controllo):** Una UI a bottoni dinamici che mostra lo stato operativo dei 5 Macro-Settori.

### Sicurezza Asimmetrica:
- **🔐 Profilo Comandante (Admin Mode):** Autenticazione hardcoded tramite Chat ID. Permette la visione del portafoglio globale (Binance, MEXC, Bitget e Wallet Web3) e lo sgancio di armi HFT.
- **👁️ Profilo Ospiti (Guest Mode):** Chiunque altro trovi il bot vedrà una UI "castrata". Potrà leggere solo l'Elemosina Globale (Gariban), una spiegazione astratta dell'infrastruttura ("Architettura Macchina") e dati offuscati, senza mai poter accedere al bilancio reale o inviare comandi operativi.

---
*L'Ecosistema perfetto non prevede il futuro. Si prepara matematicamente a reagire prima degli altri.*
## ZERO CPU ARBITRAGE (New)\nA new quantitative strategy checking funding rates with low-footprint API polling.
