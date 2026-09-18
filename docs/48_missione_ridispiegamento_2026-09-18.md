# 48 — Missione: ridispiegamento di Denaro a standard istituzionale

Data: 2026-09-18. Mandato del proprietario.

## 48.1 Il mandato

Ridispiegamento completo e pulito del progetto, che ha 18 mesi di vita. Denaro deve
funzionare a standard professionale: consolidare il software, coprire i costi di
infrastruttura, dare prestazioni affidabili. Eliminare i colli di bottiglia legacy e
le euristiche da retail, e ricostruire adottando le metodologie dei riferimenti
verificati: QuantStart, Robot Wealth, Quantpedia, Carver, Hummingbot, LEAN,
Lopez de Prado.

## 48.2 Cosa i numeri hanno GIA' escluso (e va detto prima di costruire)

Il mandato chiede market making (Avellaneda-Stoikov / Hummingbot V2) e stat-arb.
Prima di scrivere una riga di codice, queste due sono misurate:

- **Market making: impossibile sui nostri venue.** Spread mediano degli alt:
  OKX **0,0778%**, Bybit **0,1183%**. Fee maker: OKX **0,20%**, Bybit **0,10%** per
  lato. Fornire liquidita' **costa piu' di quanto rende**: non e' un'opinione, e' una
  sottrazione. Avellaneda-Stoikov ottimizza il quoting, non cambia il segno del conto.
- **Statistical arbitrage**: richiede derivati o short. OKX EEA e' acctLv 1 (spot),
  Bybit EU ha 0 swap. Su spot-only long-only lo stat-arb diventa momentum
  cross-sectional, gia' misurato: **-8,61%** (docs/17).
- **Grid/DCA**: **-7,48%** (docs/17).

Quindi "regime-adaptive" ha senso solo come **scelta tra cio' che sopravvive ai
costi**, e oggi il sopravvissuto misurato e' il trend, che e' episodico (1 blocco su
3 sul giornaliero). Questo non indebolisce il mandato: lo rende eseguibile. Il
mandato chiede rigore, e il primo atto di rigore e' non costruire cose che perdono.

## 48.3 Architettura: una macchina, un cancello, zero legacy

- **Un processo per strategia.** Non una flotta di unit systemd, non un aggregatore
  che tiene insieme quattordici servizi. Se un componente non serve a decidere o
  eseguire, non esiste.
- **Un solo cancello di promozione.** Nessuna strategia va in produzione senza
  passarlo. Il cancello e' codice, non una linea guida.
- **Stato in SQLite**, non in file sparsi per gli home. Una fonte di verita'.
- **Config-driven**: la stessa logica gira in backtest e in live con lo stesso codice.
- **Circuit breaker hard**: limiti che non si possono aggirare per configurazione.
- **Telemetria come output**, non come infrastruttura da mantenere.

## 48.4 Fasi, con criterio di accettazione

| fase | cosa | criterio di accettazione |
|---|---|---|
| **P0** | Fondamenta: repo, config, SQLite, logging strutturato, cancello | il cancello respinge un candidato costruito apposta per fallire |
| **P1** | Rig unificato backtest/live, dati point-in-time, costi reali | lo stesso input produce lo stesso output in backtest e in dry-run |
| **P2** | Risk manager: rischio per trade, budget di portafoglio, circuit breaker, kill switch | un limite violato ferma il sistema e lo dichiara |
| **P3** | Connettori OKX/Bybit + esecuzione con idempotenza e verifica on-chain | un ordine duplicato e' impossibile per costruzione |
| **P4** | Telemetria e dashboard su web.grivetto.eu | una metrica falsa si vede come falsa (stale, no-data) |
| **P5** | Dry-run prolungato, poi capitale reale | 30 giorni di dry-run senza divergenze inspiegate |

Nessuna fase si chiude senza il suo criterio. Il cancello (P0) viene **prima** di
qualsiasi strategia, perche' e' quello che impedisce di ricreare la baracca.

## 48.5 Cosa serve dal proprietario

1. **web.grivetto.eu**: dove gira, quali metriche vuole vedere, come si autentica.
   Oggi la dashboard e' interna su MARCODG1; questo e' un bersaglio nuovo.
2. **Decisione sui 67 EUR ancora in trading** e sul nodo di mc2 che gira su un conto
   vuoto: li fermo o li tengo come banco di prova?
3. **Tetto di capitale e mandato di rischio** scritti (loss massima accettabile,
   orizzonte, obiettivo).

## 48.6 La regola che tiene su tutto

Nessuna strategia in produzione senza cancello. Nessuna eccezione, nemmeno per una
che "funziona bene". E' l'unica cosa che separa un sistema da una baracca.
