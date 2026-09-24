# 59 — Architettura obiettivo: tre macchine, tre strategie complementari, tre sub-account

Data: 2026-09-25. Direttiva del proprietario (25/09): *«tre macchine, tre strategie diverse e
complementari, 3 sub-account su OKX»*, con scalabilità a 9/12/24/n mila.

Questo documento è la **specifica** di quell'architettura. Ogni numero che decide un cancello è
misurato o citato da una fonte primaria; dove non lo è, è dichiarato come stima.

---

## 59.1 Il fatto che cambia la diagnosi (correzione di un errore interno)

`docs/17` §9.3 riporta, per il trend giornaliero a parametri fissi, tre punti misurati:

| fee per lato | alpha cumulato (2,4 anni) | t |
|---|---|---|
| 0,00% | **+34,98%** | **+4,51** |
| 0,20% (maker) | +12,33% | +1,73 |
| **0,35% (taker, oggi)** | **−1,97%** | **−0,30** |

**L'errore da correggere**: quel −1,97% è un **alpha cumulato su 2,4 anni**, non un rendimento
giornaliero. Riportato "al giorno" (−1,97%/giorno) descriverebbe un conto azzerato in poche
settimane: il progetto non osserva nulla del genere. La lettura corretta è:

> A costo zero il segnale **esiste ed è significativo** (t = +4,51 su 2,4 anni: non è beta).
> A 0,35% per lato è **indistinguibile da zero** (t = −0,30). Non è una strategia che sanguina:
> è una strategia **che il pedaggio cancella**.

Conseguenza operativa: non si "guarisce" la strategia. Si abbassa il pedaggio, oppure si sceglie
una famiglia il cui rapporto edge/frequenza sopravvive al pedaggio attuale.

---

## 59.2 Il pedaggio, misurato (fonte: pagine ufficiali OKX EEA, `_audit/`)

OKX EEA pubblica **due** tabelle spot. La differenza non è il tier VIP: è **se il conto ha aperto
i derivati (X-Perps)**.

| conto | maker | taker | round-trip | break-even edge lordo/trade |
|---|---|---|---|---|
| OKX EEA **senza** derivati (oggi, `acctLv 1`) | 0,200% | **0,350%** | **0,700%** | **0,70%** |
| OKX EEA **con** X-Perps | 0,080% | **0,100%** | **0,200%** | 0,20% |
| OKX swap (serve `acctLv 2`) | 0,020% | 0,050% | 0,100% | 0,10% |

Il salto da 0,35% a 0,10% taker **non richiede volume né capitale**: richiede l'apertura di un conto
derivati (KYC + *appropriateness assessment* MiFID). L'attivazione è bloccata finché il conto ha
**posizioni aperte, ordini non riempiti o bot in esecuzione** — quindi è una procedura da fare
conto per conto, in stato pulito.

**Altre venue, verificate:** Bybit EU (spot crypto 0,10/0,25; coppie fiat 0,15/0,25 — accetta
l'Italia, ma **zero swap**, quindi non sblocca la frequenza); Kraken (EUR/USDC 0,20/0,20 —
simmetrico e adatto al maker, ma il volume su quella coppia non sale di tier e il maker 0,00%
richiede $10M); **Binance è fuori**: servizio spot sospeso per l'Italia dal 1° luglio 2026.
Non c'è una terza venue equivalente a OKX per un residente italiano: **la flotta resta su OKX**.

### La leva economica vera non sono i costi: è la frequenza

Trade/anno a pareggio, in funzione dell'edge lordo per trade:

| edge lordo/trade | @0,35%/lato (oggi) | @0,10%/lato (con X-Perps) |
|---|---|---|
| 0,5% | 0,71 | 2,50 |
| 1,0% | 1,43 | 5,00 |
| 2,0% | 2,86 | 10,00 |
| 5,0% | 7,14 | 25,00 |

La frequenza misurata del trend giornaliero è **~4 trade/anno per asset**. A 0,35% e con un edge
di 2% per trade il budget è **2,86 trade/anno**: il sistema è sopra il tetto, ed è esattamente
ciò che dice t = −0,30. A 0,10% lo stesso edge ne sostiene **10**, e questo sblocca non solo il
giornaliero ma il **4H** (che ha circa 8 volte le occasioni).

### Cosa non cambia con la fee (misurato, `docs/40` §40.1)

Robustezza = configurazioni con rendimento composto positivo in almeno (blocchi−1) blocchi, su 24.

| fee/lato | 4H (19 asset) | 1D (19 asset) |
|---|---|---|
| 0,35% — OKX oggi | **3/24** | **14/24** |
| 0,10% | 18/24 | 18/24 |
| 0,05% | 20/24 | 18/24 |

Il **giornaliero** è quasi insensibile alla fee (14 → 18 su 24) e resta la configurazione
*migliore* anche al pedaggio attuale. Il **4H** è dominato dalla fee: sotto 0,30% per lato non è
valutabile. Il suo problema strutturale resta, ed è misurato in `docs/39` §39.6: tutto il
rendimento del giornaliero sta nel blocco 1 (+11,84%), i blocchi 2 e 3 sono negativi (−1,74%,
−0,62%).

---

## 59.3 L'architettura richiesta: tre nodi, tre strategie, tre conti

```
                    ┌──────────────────────────────────────────────┐
                    │  GOVERNATORE DI PORTAFOGLIO (rischio 2%)     │
                    │  unica fonte del budget di rischio aggregato │
                    └───────┬───────────────┬──────────────┬───────┘
                            │               │              │
        ┌───────────────────▼──┐  ┌─────────▼────────┐  ┌──▼──────────────────┐
        │ NODO A — nuvola      │  │ NODO B — mc2     │  │ NODO C — MARCODG1   │
        │ strategia: TREND 1D  │  │ strategia: GRID  │  │ strategia: 4H       │
        │ edge misurato        │  │ ADATTIVA         │  │ (cancello fee)      │
        │ sub OKX: nuvolasub1  │  │ sub OKX: mc2sub1 │  │ sub OKX: marcosub1  │
        └──────────────────────┘  └──────────────────┘  └─────────────────────┘
              capitale            capitale            capitale
              isolato             isolato             isolato
```

Tre regole non negoziabili:

1. **Un conto per strategia.** Nessun bot condivide un sub-account con una strategia diversa:
   è la configurazione che ha già prodotto il difetto di rischio aggregato al 14% (§59.4).
2. **Il rischio è di portafoglio, non di bot.** Il budget 2% è del **capitale totale**, non di
   ogni strategia. Nessun nodo può spendere più della propria quota.
3. **Nessuna strategia entra in produzione senza il cancello** (`docs/47`): expectancy netta
   out-of-sample positiva **ai costi reali del conto su cui gira**.

### Assegnazione delle famiglie e criterio di ammissione

| nodo | famiglia | stato del cancello | criterio di ammissione |
|---|---|---|---|
| **A — nuvola** | trend giornaliero, canale 40 / EMA 100 / trailing 2,5 ATR | **misurato**: t = +4,51 a costo zero, 14/24 robuste a 0,35% | nessun requisito di fee: può girare **oggi** |
| **B — mc2** | grid adattiva: spaziatura della griglia derivata da volatilità realizzata e ATR, con vincolo `spaziatura ≥ 3 × round-trip` | **da misurare** | il vincolo si autoimpone: se la volatilità non paga il pedaggio, la griglia **non si apre** |
| **C — MARCODG1** | momento/breakout 4H, cross-sezionale su 19-28 asset | **sbloccato solo a fee < 0,30%** | richiede X-Perps aperti: 3/24 → 18/24 |

Il nodo B è la risposta alla tua direttiva «da statico a predittivo»: la griglia non è una scala
fissa di livelli, è una **funzione della volatilità misurata**, e la sua ampiezza minima è imposta
dall'economia (pedaggio), non da un parametro scelto a mano.

Il nodo C è la riserva di frequenza: con 8× le occasioni del giornaliero è la fonte naturale di
crescita composta, **ma solo dopo** l'apertura degli X-Perps. Prima di allora resta in **dry-run**,
che è un uso legittimo del nodo (produce la serie di confronto) e non costa capitale.

---

## 59.4 Il rischio: 2% del capitale, e come si fa a rispettarlo davvero

`tools/audit_capitale_config.py` (eseguito oggi) misura:

```
config                             bot  dichiarato  conto stim.  quota giusta  fattore
node_mc2.yaml                        7      294.84        42.12          6.02     7.0x
node_nuvola_trade.yaml               6      148.98        24.83          4.14     6.0x
node_marcodg1_xrp.yaml               4      168.16        42.04         10.51     4.0x
TOTALE                              29     1888.18       672.49         23.19     2.8x
```

**Sette bot che dichiarano ciascuno l'intero conto rischiano il 14% del conto, non il 2%.** La
quota corretta è `totale / N`. Con l'architettura a un conto per strategia il fattore torna a 1×,
e sopra i tre nodi sta il governatore con il budget unico.

### Il budget 2%: cosa significa in euro

| capitale sul conto | budget di rischio 2% | rischio per trade (es. 1% della quota) |
|---|---|---|
| 0,15 EUR (oggi, dust) | 0,003 EUR | sotto qualunque minimo d'ordine |
| 52 EUR (somma dei 5 conti) | 1,04 EUR | 0,52 EUR |
| 1.000 EUR (obiettivo dichiarato) | **20 EUR** | 10 EUR |

Questo è il secondo fatto da dire senza addolcire: **con 0,15 EUR non esiste nessun ordine
possibile** — il minimo per trade su OKX è di ordini di grandezza superiore. Le tre linee di
difesa da costruire sono quindi:

1. **stato NON FINANZIATO esplicito** (difetto chiuso in questo giro): il nodo dichiara di non
   essere in grado di operare invece di saltare i tick in silenzio;
2. **cap di esposizione a livello di conto** (`domain/exposure.py`, già scritto e testato: va
   iniettato nel nodo);
3. **governatore di portafoglio**: la somma dei rischi dei tre nodi letta da un unico registro,
   con kill-switch giornaliero −3% e drawdown massimo −10% già fissati nel mandato
   (`MANDATO_RISCHIO.md`).

---

## 59.5 I quattro pilastri di resilienza ("zero-touch")

| pilastro | stato di partenza | lavoro |
|---|---|---|
| **Idempotenza** | assente: nessun `clientOrderId` in tutto `denaro/` | chiave su ogni invio, registrata **prima** dell'ordine; riconciliazione al riavvio (R3b) |
| **Riconciliazione** | parziale (`_riconcilia_posizione`) | all'avvio: saldi, ordini aperti, posizioni contro lo stato persistito; un ordine orfano viene **adottato**, non ignorato |
| **Telemetria onesta** | curva equity collegata (Q5), ma i servizi di telemetria sono **in auto-restart/failed** su entrambe le macchine | riparare aggregator/exporter/prometheus/watchdog; badge stale su ogni serie (`docs/55`) |
| **Degradazione controllata** | guard di equity, circuit breaker, guard di spread esistono | stati espliciti e transizioni a una-riga-per-cambio: `ok` / `sottocapitalizzato` / `non_finanziato` / `illeggibile` |

---

## 59.6 Scalabilità 3 → 9 → 12 → 24 → n

La struttura è la stessa a ogni scala: **un nodo = una strategia = un conto**. Ciò che cambia non
è il numero di strategie per macchina, è il **numero di nodi**. A 9/12/24 "strategie" la lettura
corretta è: *n nodi indipendenti*, ciascuno con la propria chiave, il proprio conto, la propria
famiglia, e un budget di rischio che il governatore ripartisce.

Perché non "n strategie sullo stesso conto": l'esperimento è già stato fatto e ha prodotto il
14% di rischio aggregato, i due bot che si fermano a vicenda sull'equity condivisa, e uno stop
che liquidava il saldo di un altro bot (R1). **L'isolamento per conto non è un'opinione
architetturale: è la correzione di tre difetti già osservati.**

---

## 59.7 Ordine di esecuzione (cosa faccio, in che sequenza)

1. **In corso ora** — chiusura R3b (idempotenza) e stato **NON FINANZIATO** + iniezione del cap
   di esposizione nel nodo. Sono i tre difetti che impediscono di chiamare "professionale" il
   motore che muove i soldi.
2. **Poi** — riparazione dei servizi di telemetria sui due nodi (aggregator, exporter, prometheus,
   watchdog): senza telemetria vera non si distingue un guadagno da un artefatto.
3. **Poi** — riallocazione dei tre nodi secondo §59.3, con **un conto per strategia** e quote di
   capitale corrette (`totale/N`), non il capitale dell'intero conto su ogni bot.
4. **Poi** — il cancello sul nodo C: mettere **un** conto in stato pulito e chiedere l'apertura
   degli X-Perps. È l'unica azione che sblocca la frequenza, non tocca il deploy ed è reversibile.
5. **Infine** — la decisione sul capitale. Il software è pronto quando il punto 1 è chiuso con
   prove e il punto 3 gira in dry-run senza divergenze; **il capitale è la variabile che decide
   se il progetto guadagna o collauda**, e i numeri per decidere sono in §59.4.

---

## 59.8 Il muro da dire chiaro

Guadagno ≈ Σ (edge_per_trade − costi) × frequenza × capitale × (1 − errori_operativi).

Su questo conto, oggi: capitale ≈ 0,15 EUR → il prodotto è zero qualunque cosa faccia il codice.
A 52 EUR con il pedaggio attuale, il trend giornaliero ha ~4 occasioni/anno per asset e serve un
edge di 0,70% solo per cominciare: il tetto annuo misurato dal progetto è di **pochi euro**.
Le due leve che moltiplicano davvero sono **abbassare il pedaggio** (0,70% → 0,20% per giro,
cioè la frequenza sostenibile ×3,5) e **alzare la frequenza** (4H: 8× le occasioni, sbloccato
dalla stessa azione). Nessuna delle due è codice: la prima è un assessment, la seconda è la
conseguenza della prima. Il codice serve a non perdere per colpa nostra, ed è la parte su cui
sto lavorando adesso.

---

## 59.9 Fonti

- Fee EEA OKX (due tabelle, per apertura derivati): `_audit/www.okx.com_en-eu_help_what-are-the-new-trading-fees-for-eea-users.txt`
- X-Perps EEA: requisiti KYC/assessment e vincolo "posizioni, ordini e bot devono essere fermi":
  `_audit/www.okx.com_en-eu_help_okx-x-perps-eea-regional-availability-eligibility.txt`
- Bybit EU (spot e coppie fiat): `_audit/www.bybit.eu_en-EU_help-center_article_Trading-Fee-Structure.txt`
- Kraken (spot, stablecoin/FX, xStocks, LP program): `_audit/www.kraken.com_features_fee-schedule.txt`
- Strumenti OKX EEA via API pubblica: 1.415 spot, 272 con quote EUR, 492 swap (nessuno in EUR)
- Misure interne del progetto: `docs/17`, `docs/20`, `docs/39`, `docs/40`, `docs/47`, `docs/53`-`docs/58`
