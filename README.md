# 🚀 ORBITAL COMMAND: NEON SQUAD
**Versione Attuale:** Alpha 0.99 (Pre-Beta)
*La release Beta 1.0 verrà rilasciata solo ed esclusivamente al raggiungimento e mantenimento stabile dell'obiettivo di 100€ di profitto netto giornaliero.*

## 👨‍💻 Visione Strategica
Benvenuti nella nuova era del trading algoritmico. Il progetto è stato completamente rivoluzionato per risolvere i problemi di Out-Of-Memory (OOM) e i limiti delle API (Rate Limiting) che affliggevano le vecchie architetture basate su dataframes pesanti e polling continui.

La **NEON SQUAD** è una flotta di **9 Intelligenze Artificiali indipendenti**, progettata per estrarre profitto dai mercati crypto (Binance) con un impatto quasi nullo su RAM e CPU. Tutti i bot operano tramite **WebSockets** (dati in push) o timer asincroni a bassissima frequenza.

L'obiettivo giornaliero di sistema è fissato a **100€ netti**, protetto dalla regola aurea della "Cassaforte al 33%".

---

## 🛡️ La Regola della Cassaforte (Vault 33%)
Ogni singolo bot della flotta è programmato con un vincolo di sicurezza assoluto:
**Ad ogni trade chiuso in profitto, il 33% del guadagno netto viene immediatamente isolato in una "Cassaforte Virtuale" (`vault.json`).**
Nessun bot ha il permesso di usare i fondi presenti nella cassaforte per aprire nuove posizioni. Questo garantisce che una parte dei profitti venga sempre messa al riparo dal rischio di mercato.

---

## 🤖 L'Arsenale (Le 9 IA della Flotta)

### 1. 🎯 SNIPER SQUAD (Heavy Assault)
L'unità principale. Opera sulle monete ad alta capitalizzazione (SOL, BNB, ETH, AVAX, LINK, DOT, PEPE, DOGE).
*   **Strategia:** Cerca ipervenduti (RSI < 35) e momentum positivi, sparando colpi pesanti (fino a 1000€).
*   **Gestione Rischio:** *Perdite non ammesse in stop loss stretto*. Applica un Maximum Drawdown (MDD) del -10% per evitare il bag-holding, ma attende pazientemente il ritorno in profitto (Take profit dinamico a +0.4% / +0.2% con trailing).

### 2. 🤲 GARIBAN (L'Elemosiniere / Trapper)
Il bot opportunista per eccellenza, dedicato alle meme-coin (SHIB, DOGE, PEPE, FLOKI, ecc.).
*   **Strategia:** Piazza "trappole". Se rileva un crollo improvviso (>1% in 5 minuti), compra per soli 10€. Appena la moneta fa un microscopico rimbalzo del +0.10%, vende tutto e versa il 100% dell'elemosina nella Cassaforte.

### 3. 🧛 VAMPIRO (Grid BTC Laterale)
Il succhiasangue della volatilità di Bitcoin.
*   **Strategia:** Morde il mercato (BTCEUR) con micro-posizioni da 15€. Se il prezzo scende dello 0.15%, piazza un nuovo morso. Se sale dello 0.15%, drena il morso vendendo. Vive di pura lateralizzazione.

### 4. 🦴 SCIACALLO (Scavenger Meme Crash)
Il predatore del Panic Selling.
*   **Strategia:** Ascolta passivamente i volumi delle meme-coin. Se rileva uno scarico di mercato anomalo (es. 500 milioni di PEPE venduti in 1 minuto), entra a mercato sulle ceneri del crollo per rubare un tick di profitto sul rimbalzo tecnico.

### 5. 👻 PHANTOM (Book Maker Invisibile)
Il fantasma del book di Binance. Consumo RAM/CPU letteralmente a zero.
*   **Strategia:** Si sveglia ogni 2 minuti e piazza reti (Ordini LIMIT) al -2% del prezzo attuale. Se il mercato crolla e gli prende l'ordine, piazza automaticamente una vendita LIMIT al +2% e torna a dormire.

### 6. 🌊 TSUNAMI (Pump Rider)
Il surfista dei rialzi violenti.
*   **Strategia:** Osserva i grafici a 1 minuto. Se una candela verde esplode in rialzo oltre lo 0.8% in 60 secondi, entra a mercato in corsa con 50€ per cavalcare il "Pump", uscendo rapidamente al primo segno di cedimento.

### 7. 🐝 SCIAME (Hunter Swarm - Micro Dips)
L'attacco a sciame sincronizzato.
*   **Strategia:** 5 mini-bot da 20€ l'uno. Se il mercato fa una candela rossa improvvisa dello -0.5%, l'intero sciame attacca simultaneamente per comprare a sconto, vendendo su micro-profitti del +0.3%.

### 8. 🌑 DARKPOOL (Radar Arbitraggio Triangolare)
Cacciatore di glitch matematici sui mercati (EUR -> CRYPTO -> BTC -> EUR).
*   **Strategia:** Analizza i tassi di cambio incrociati. Se scopre un disallineamento superiore allo 0.3% (al netto delle fee), segnala la discrepanza per estrarre valore a rischio di mercato nullo.

### 9. 🌌 BLACKHOLE (Timing Globale)
Il predatore temporale.
*   **Strategia:** Dorme 24 ore su 24 e si attiva per 1 minuto solo in tre momenti esatti: l'apertura delle borse di Tokyo (01:00 UTC), Londra (08:00 UTC) e New York (14:30 UTC), per assorbire la volatilità scatenata dai volumi istituzionali.

---

## 🎛️ Centro di Comando

- **Lite Guardian 2.1:** Il gestore dei processi (Supervisor) che mantiene in vita tutti e 9 i bot, riavviandoli in caso di crash, ma assicurandosi che nessuno di essi superi i limiti di memoria.
- **Orbital Command Dashboard:** Interfaccia Web Cyberpunk (`https://sgrivett.ddns.net:8443`) con telemetria live da Binance, stato della flotta, progress bar dell'obiettivo dei 100€, log in stile terminale e chart generato dinamicamente con Matplotlib.
- **Telegram Bot (@Sergiotrdxbot):** Interfaccia mobile per Sergio. Permette di visualizzare lo stato delle squadre, richiedere la generazione al volo del grafico profitti (inviato come immagine PNG) e controllare i versamenti del Gariban.

---
*Architettura Zero-OOM sviluppata da Stella (AI Assistant) per Sergio Grivetto.*
