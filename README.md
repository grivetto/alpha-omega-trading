# 🚀 Progetto Alpha-Fleet: Trading Engine Automativo v2.1

## 👨‍💻 Visione Strategica
Alpha-Fleet è un ecosistema di trading algoritmico multi-bot progettato per operare in sinergia sui mercati delle criptovalute (Binance e Crypto.com). Il sistema è strutturato per massimizzare il profitto attraverso la diversificazione delle strategie, riducendo al contempo il rischio operativo grazie a un'intelligenza centrale di coordinamento.

---

## 🏗️ Architettura del Sistema (I 3 Livelli)

### 1. Master Control Layer (Cervello Centrale)
*   **Neural Commander**: Un bot decisionale che analizza la volatilità del mercato h24. Non esegue trade direttamente, ma modifica i parametri (es. ampiezza griglia, soglie di ingresso) di tutti gli altri bot in base al regime di mercato individuato (Laterale vs Volatile).
*   **Fleet Reporter**: Aggregatore di log che monitora la salute di ogni servizio e popola la dashboard web in tempo reale.

### 2. Execution Layer (Le Squadre d'Attacco)
*   **Squadra ALPHA (Smart Grid BTC)**: Gestisce il capitale principale (Core) su Bitcoin. Utilizza una strategia a griglia (20+ livelli) per catturare micro-oscillazioni. Compra basso e vende alto sistematicamente ad ogni variazione dello 0.3% - 0.5%.
*   **Squadra BRAVO (Scalp ETH)**: Specializzata su Ethereum. Entra in gioco quando il Commander rileva trend solidi, operando con acquisti e vendite veloci.
*   **Squadra CHARLIE (SOL Interceptor)**: Un bot ad alta frequenza focalizzato su Solana (SOL). Cerca profitti rapidi dello 0.8% sfruttando l'alta volatilità dell'asset.

### 3. Intelligence Layer (I Radar)
*   **Whale Monitor**: Scansiona il book di Binance alla ricerca di ordini istituzionali (sopra i 0.5 BTC). Fornisce segnali di "pompaggio" o "dump" imminente.
*   **Sentinel Trend**: Analizza un paniere di 5 monete (BTC, ETH, SOL, BNB, ADA) rilevando spike improvvisi di volume che indicano l'inizio di un breakout.
*   **Arbitrage Sentinel**: Monitora costantemente la differenza di prezzo tra Binance e Crypto.com per identificare opportunità di guadagno prive di rischio direzionale.

---

## 📊 Parametri Tecnici Correnti
- **Capitale Operativo**: ~€360.00 (distribuito tra BTC, SOL e Liquidità).
- **Target Profit Medio**: +0.8% per operazione di scalp.
- **Sicurezza**: Trailing Stop Loss dinamico e sistema anti-spam per le notifiche di profitto (Cooldown 1h).
- **Infrastruttura**: Servizi systemd su Linux gestiti tramite OpenClaw Engine.

---

## 🔗 Accesso al Centro di Comando
- **Dashboard Live (HTTPS)**: `https://sgrivett.ddns.net:8443`
- **Controllo Mobile**: Bot Telegram Interattivo (@Sergiotrdxbot) con permessi granulari (Admin vs Guest).

---
*Progetto sviluppato da Stella (AI Assistant) per Sergio Grivetto.*
