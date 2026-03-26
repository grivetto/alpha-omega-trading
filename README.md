# 🚀 ORBITAL COMMAND: NEON SQUAD
**Versione Attuale:** Alpha 0.99 (Pre-Beta)
*La release Beta 1.0 verrà rilasciata solo ed esclusivamente al raggiungimento e mantenimento stabile dell'obiettivo di 100€ di profitto netto giornaliero.*

## 👁️ L'INFRASTRUTTURA A 4 TIER (RISCHIO ASIMMETRICO)
La flotta è stata divisa in distaccamenti strategici per massimizzare la resa e frammentare il rischio:
- **TIER 1 (Squadra Alpha - Binance Spot):** La Roccaforte. Ospita la Sniper Squad e i 28 Legionari. Usa l'85% del capitale per comprare i dip e sfruttare l'interesse composto senza l'uso di leve finanziarie.
- **TIER 2 (Squadra Beta - MEXC Spot):** Il Laboratorio a Zero Commissioni. La `MEXC Nano Squad` opera su altissime frequenze per grattare millesimi di dollaro dai micro-movimenti del mercato senza pagare fee di transazione.
- **TIER 3 (Squadra Gamma - Bitget Futures):** Le Forze Speciali. Operano con un budget minuscolo (5% del capitale) su Leva 20x. Contiene il `Kamikaze Bot` (per i pump), il `Micro-Shorter` (per speculare sui crolli) e l'algoritmo `Pairs Trading Neutral` che genera profitti arbitrando la differenza di forza tra due monete contemporaneamente (es. LONG SOL, SHORT DOGE).
- **TIER 4 (Squadra Delta - Binance Order Flow):** Il Whale Front-Runner. Utilizza il Level 2 Order Book di Binance per scovare inefficienze (Imbalance > 3.5x tra Bids e Asks nei primi 10 livelli). Acquista istanti prima che un muro in acquisto ("Buy Wall") faccia esplodere il prezzo, scalpando un +0.2% netto in frazioni di secondo. Se il muro è "fake" (Spoofing), applica uno stop loss dinamico a -0.5% per protezione del capitale.

## 🎖️ IL GENERALE (Dynamic Capital Allocator)
A capo del Tier 1 è stato posto **IL GENERALE** (`il_generale.py`). Questo algoritmo si sveglia ogni ora per ispezionare il portafoglio:
- **Stop Loss Tattico:** Taglia le posizioni in forte perdita (<-5% in 24h) vendendole per salvare il capitale.
- **Moltiplicatore di Profitto:** Inietta budget extra (es. 30€) sulle monete in forte trend rialzista (>+5% in 24h) per massimizzare i profitti prima del picco.

## 🛡️ CHARLIE INFRASTRUCTURE (Zabbix Monitor & Dashboard)
La nuova architettura si regge su un guardiano supremo: **CHARLIE** (`zabbix_watchdog.py`). Questo demone in background scruta la memoria RAM, l'uso CPU e il battito cardiaco (ultimo log) di tutti i bot. Se un bot entra in stato *Zombie* (log bloccati per >600 secondi), CHARLIE lo killa e il `lite_guardian` lo riporta in vita. Questo, unito ai fix anti-memory-leak sulla Dashboard Web (che consumava 10 GB di Swap e ora è divisa in 4 pannelli operativi per i 4 Tier), garantisce un uptime eterno a consumo quasi zero.

## ⚙️ LA FABBRICA DEI BOT (Auto-Builder Cron)
Un processo isolato di intelligenza artificiale ("Auto-Builder Bot Factory") si sveglia ogni ora per analizzare il mercato, scrivere da zero un nuovo algoritmo Python su Binance Spot, integrarlo nel `lite_guardian` e testarlo in produzione. Questa fabbrica iterativa punta a trovare l'anomalia perfetta per raggiungere i 100€ giornalieri.

## 🔐 LA REGOLA D'ORO (Vault del 33%)
Nessun bot può accrescere a dismisura il capitale esposto. **Ogni singolo trade chiuso in profitto** da una qualsiasi delle intelligenze artificiali è tenuto per legge a dirottare il **33% dell'incasso netto verso il Vault** (Fondo Sicurezza Intoccabile). In più, la funzione **Elemosina Gariban** raccoglie i micro-resti in USDT e li protegge nello stesso fondo. A mezzanotte, il `midnight_sweeper.py` sigilla i profitti giornalieri.
