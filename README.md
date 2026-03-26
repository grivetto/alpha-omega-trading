# 🚀 ORBITAL COMMAND: NEON SQUAD
**Versione Attuale:** Alpha 0.99 (Pre-Beta)
*La release Beta 1.0 verrà rilasciata solo ed esclusivamente al raggiungimento e mantenimento stabile dell'obiettivo di 100€ di profitto netto giornaliero.*

## 👁️ L'INFRASTRUTTURA A 3 TIER + WHALE WATCHER (RISCHIO ASIMMETRICO)
La flotta è stata divisa in distaccamenti per massimizzare la resa e frammentare il rischio:
- **TIER 1 (Squadra Alpha - Binance Spot):** La Roccaforte. Ospita la Sniper Squad e i 28 Legionari. Usa l'85% del capitale per comprare i dip e sfruttare l'interesse composto senza l'uso di leve finanziarie.
- **TIER 2 (Squadra Beta - MEXC Spot):** Il Laboratorio a Zero Commissioni. La `MEXC Nano Squad` opera su altissime frequenze per grattare millesimi di dollaro dai micro-movimenti del mercato senza pagare fee di transazione.
- **TIER 3 (Squadra Gamma - Bitget Futures):** Le Forze Speciali. Operano con un budget minuscolo (5% del capitale) su Leva 20x. Contiene il `Kamikaze Bot` (per i pump), il `Micro-Shorter` (per speculare sui crolli) e il nuovissimo algoritmo `Pairs Trading Neutral` che genera profitti arbitrando la differenza di forza tra due monete contemporaneamente.
- **TIER 4 (Squadra Delta - Binance Order Flow):** Il Whale Front-Runner. Utilizza il Level 2 Order Book di Binance per scovare inefficienze (Imbalance > 3.5x tra Bids e Asks nei primi 10 livelli). Acquista istanti prima che un muro in acquisto ("Buy Wall") faccia esplodere il prezzo, scalpando un +0.2% netto in frazioni di secondo. Se il muro è "fake" (Spoofing), applica uno stop loss dinamico a -0.5% per protezione del capitale.

## 🛡️ CHARLIE INFRASTRUCTURE (Zabbix Monitor & Dashboard)
La nuova architettura si regge su un guardiano supremo: **CHARLIE** (`zabbix_watchdog.py`). Questo demone in background scruta la memoria RAM, l'uso CPU e il battito cardiaco (ultimo log) di tutti i bot. Se un bot entra in stato *Zombie*, CHARLIE lo killa e il `lite_guardian` lo riporta in vita. Questo, unito ai recenti fix anti-memory-leak sulla Dashboard Web (che consumava 10 GB di Swap caricando i vecchi file di log), garantisce un uptime eterno a consumo quasi zero.

## ⚔️ LA LEGIONE E L'EFFETTO SCIAME (40+ BOTS ONLINE)
Invece di avere un singolo mega-algoritmo Pandas-TA (che divorava RAM), la "Neon Squad" ha frazionato la mente operativa in micro-servizi Python isolati che comunicano tra loro, pesando 0.2% CPU e 20MB di RAM ciascuno.

## 🔐 LA REGOLA D'ORO (Vault del 33%)
Nessun bot può accrescere a dismisura il capitale esposto. **Ogni singolo trade chiuso in profitto** da una qualsiasi delle 40 intelligenze è tenuto per legge a dirottare il **33% dell'incasso netto verso il Vault** (Fondo Sicurezza Intoccabile). 
In più, la funzione **Elemosina Gariban** raccoglie i micro-resti in USDT da ogni chiusura e li protegge nello stesso fondo.
