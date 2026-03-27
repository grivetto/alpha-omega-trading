# 🚀 ORBITAL COMMAND: NEON SQUAD
**Branch Attuale:** `work_in_progress` (A.G.I. Quantitative Testing)
*Questo branch ospita l'ecosistema algoritmico in evoluzione continua. Le strategie vengono testate, validate e promosse automaticamente dall'Intelligenza Artificiale isolata (Evolutionary Bot Builder).*

## 👁️ L'INFRASTRUTTURA A 4 TIER (HEDGE FUND MODE)
La flotta è stata divisa in distaccamenti strategici per massimizzare la resa e frammentare il rischio:
- **TIER 1 (Squadra Alpha - Binance Spot):** La Roccaforte. Ospita la Sniper Squad e i 28 Legionari. Usa capitale senza leva per comprare i dip e sfruttare l'interesse composto. Include il **Project Olympus** (Griglie HFT a spread ravvicinato per incassare dalla volatilità laterale).
- **TIER 2 (Squadra Beta - MEXC Spot):** Il Laboratorio a Zero Commissioni. La `MEXC Nano Squad` opera su altissime frequenze per grattare millesimi di dollaro dai micro-movimenti senza pagare fee.
- **TIER 3 (Squadra Gamma - Bitget Futures):** Le Forze Speciali. Operano con budget ridotto su Leva 10x/20x. Contiene il `Kamikaze Bot` (Momentum LONG), il `Micro-Shorter` (Speculazione Crolli) e il `Blade Runner` (Scalper Direzionale estremo).
- **TIER 4 (Squadra Delta - Market Neutral & Hedging):** Lo Scudo Assoluto.
  - `delta_neutral_hedge.py`: Calcola l'esposizione Spot su Binance e apre dinamicamente una posizione SHORT su Bitget Futures per bilanciare il portafoglio a Rischio Zero.
  - `spatial_arbitrageur.py`: Legge i prezzi tra Binance e MEXC e segnala inefficienze di prezzo (Risk-Free Arbitrage).

## 🧠 LA VISTA E LA VELOCITÀ (HFT & Dati Alternativi)
- **Il Cervello Condiviso (WebSockets):** Il demone `orbital_websocket.py` mantiene una connessione WSS permanente con Binance, scrivendo migliaia di prezzi al secondo su una **RAM-Disk locale (`/dev/shm`)**. I bot leggono dalla RAM in <5ms azzerando la latenza e i Rate Limits API.
- **La Vista On-Chain:** `whale_alert_onchain.py` fa da proxy analizzando i volumi anomali sui Futures per anticipare i movimenti delle Balene.
- **News Sentiment Sniper:** `news_sentiment_sniper.py` esegue scraping e parsing RSS in tempo reale di *Cointelegraph* e *CoinDesk*, analizzando i titoli per intercettare keyword esplosive (es. "Hack", "ETF", "Elon Musk") e ordinando ai bot di reagire in millisecondi.

## 🎖️ IL GENERALE E L'OTTIMIZZATORE
- **Il Generale:** Taglia le posizioni in forte perdita (Stop Loss Tattico) e inietta budget sulle monete in forte trend rialzista.
- **L'Auto-Compounder:** `auto_compounder.py` si sveglia ogni 12 ore, legge il capitale totale e applica la formula di Kelly per calcolare il Rischio (es. 2.5%), aumentando dinamicamente la size (potenza di fuoco) di tutti i bot.

## 🛡️ CHARLIE INFRASTRUCTURE E CRISIS MANAGER
La nuova architettura si regge su due guardiani:
- **ZABBIX Watchdog:** Scruta la memoria RAM, l'uso CPU e il battito cardiaco (ultimo log) di tutti i bot. Genera il `fleet_stats.json` per la Dashboard Web e riavvia i bot "Zombie".
- **CRISIS MANAGER (DEFCON 2):** `crisis_manager.py` monitora il crollo del benchmark globale (BTC). Se il mercato sanguina >4%, dichiara il DEFCON 2, **blocca gli acquisti Spot (No Falling Knives)**, sguinzaglia i bot Short e avverte il Comandante su Telegram.

## ⚙️ EVOLUTIONARY AI BOT BUILDER (Darwinian Engine)
Un processo di AGI (Artificial General Intelligence) si sveglia ogni **5 minuti**. Legge i log storici, elimina spietatamente i bot in perdita o che consumano troppa RAM, inventa una nuova strategia in Python (Machine Learning / Quant), la testa in RAM e se redditizia la deploya in produzione aggiungendola al Guardiano e aggiornando il repository GitHub in autonomia.

## 🔐 LA REGOLA D'ORO (Vault del 33%)
**Ogni singolo trade chiuso in profitto** da una qualsiasi intelligenza artificiale dirotta il **33% dell'incasso netto verso il Vault** (Fondo Sicurezza Intoccabile). A mezzanotte, il `midnight_sweeper.py` sigilla i profitti della giornata e azzera i contatori.
