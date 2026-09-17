# 40 — Fee reali delle due venue: la migrazione si giustifica? NO

Data: 2026-09-18. Ricerca riproducibile: `tools/trend_4h_venue.py`.
Versione breve con la lista delle azioni: docs/39_fee_e_venue_2026-09-17.md.
Qui il dettaglio: numeri per blocco, universo largo, difetti di codice trovati.

## 40.1 La domanda, posta in modo da poter ricevere un no

Bybit EU costa meno di OKX EEA sulle fee spot misurate sull'account:

| | maker | taker | spread mediano alt | round trip taker effettivo |
|---|---|---|---|---|
| OKX EEA | 0.200% | 0.350% | 0.0778% | 0.778% |
| Bybit EU | 0.100% | 0.250% | 0.1183% | 0.618% |

Bybit e' ~21% piu' economica a giro completo, non 2.4 volte. Il test che poteva
giustificare una migrazione era uno solo: **il 4H diventa robusto a 0.25%/lato?**
Docs/20 aveva stabilito che sul 4H il verdetto della griglia passa da 3/24 a 20/24
cambiando SOLO la fee. Se a 0.25%/lato il 4H fosse diventato robusto, valevano il
trasloco di 17 bot e le chiavi nuove. Non lo e'.

## 40.2 Criterio (identico a tools/trend_4h_griglia.py)

4 canali (20/40/60/80) x 3 EMA (50/100/200) x 2 (long-only, long/short) = 24
configurazioni. Serie divisa in blocchi uguali; "robusta" = rendimento composto
positivo in almeno (blocchi-1) blocchi. "pieno" = rendimento sull'intera serie con
la configurazione deployata (canale 40, EMA 100, long-only).

## 40.3 4H — 19 asset del documento 20, 5181 barre, 5 blocchi da 1036

| fee per lato | robuste | comp. mediano | pieno media | pieno mediana |
|---|---|---|---|---|
| OKX spot taker 0.35% **[deployato]** | **3/24** | +8.74% | +17.31% | +6.40% |
| OKX spot maker 0.20% | 13/24 | +24.24% | +30.06% | +20.25% |
| Bybit EU taker 0.25% | **9/24** | +18.80% | +25.65% | +17.34% |
| Bybit EU taker +spread 0.27% **[reale]** | **9/24** | +16.64% | +23.93% | +16.20% |
| Bybit EU maker 0.10% *[non ottenibile]* | 18/24 | +35.69% | +39.41% | +26.53% |
| OKX swap taker 0.05% *[acctLv2, assente]* | 20/24 | +41.35% | +44.36% | +31.27% |

La riga OKX taker riproduce esattamente i 3/24 di docs/20 e la riga swap i 20/24:
il rigore di misura e' confermato.

## 40.4 4H — universo largo, 28 asset, 5181 barre, 5 blocchi

| fee per lato | robuste | comp. mediano | pieno media | pieno mediana |
|---|---|---|---|---|
| OKX spot taker 0.35% **[deployato]** | **4/24** | +10.69% | +16.92% | +5.81% |
| OKX spot maker 0.20% | 19/24 | +27.30% | +29.50% | +18.25% |
| Bybit EU taker 0.25% | **14/24** | +22.09% | +25.15% | +14.39% |
| Bybit EU taker +spread 0.27% **[reale]** | **11/24** | +19.92% | +23.45% | +12.89% |
| Bybit EU maker 0.10% *[non ottenibile]* | 21/24 | +38.09% | +38.69% | +26.22% |
| OKX swap taker 0.05% *[acctLv2, assente]* | 21/24 | +43.69% | +43.56% | +29.67% |

Qui la migrazione si vede: 4/24 -> 14/24 senza spread, 11/24 con lo spread reale.
E' un miglioramento vero (circa 3x) e non e' un caso: la fee pesa sui breakout 4H,
dove il rapporto segnale/costo e' molto piu' basso che sul giornaliero. Ma 11/24
**non e' robustezza**: e' una minoranza che diventa maggioranza solo se allo spread
non si paga nulla. La soglia che rende il 4H davvero affidabile e' 0.10%/lato,
cioe' maker — e un breakout che compra il massimo del canale con lo stop trailing
che esce in market e' **taker per costruzione**. Il maker qui non e' un'ipotesi
prudente, e' un'ipotesi impossibile. (La famiglia "maker-only" e' gia' stata
misurata a -61.35%, t=-16.76, docs/17 10.5.)

## 40.5 Il giornaliero, cioe' quello che gira davvero — 911 barre, 3 blocchi

| fee per lato | robuste | comp. mediano | pieno media | pieno mediana |
|---|---|---|---|---|
| OKX spot taker 0.35% **[deployato]** | 14/24 | +17.23% | +19.90% | +6.75% |
| OKX spot maker 0.20% | 18/24 | +17.66% | +20.59% | +7.14% |
| Bybit EU taker 0.25% | 18/24 | +17.51% | +20.36% | +7.01% |
| Bybit EU taker +spread 0.27% **[reale]** | 17/24 | +17.46% | +20.26% | +6.96% |
| Bybit EU maker 0.10% *[non ottenibile]* | 18/24 | +18.06% | +21.05% | +7.41% |
| OKX swap taker 0.05% *[acctLv2, assente]* | 18/24 | +18.25% | +21.28% | +7.54% |

**La fee e' irrilevante sul giornaliero.** Da 0.35% a 0.05%/lato — sette volte il
costo — il rendimento pieno passa da +19.90% a +21.28%: 1.4 punti su 2.5 anni. Da
OKX a Bybit: +0.36 punti. Non e' un motivo per spostare nulla.

### Universo largo, 47 asset, 900 barre, 3 blocchi

| fee per lato | robuste | comp. mediano | pieno media | pieno mediana |
|---|---|---|---|---|
| OKX spot taker 0.35% **[deployato]** | 7/24 | +8.65% | +9.84% | +2.44% |
| Bybit EU taker 0.25% | 9/24 | +8.85% | +10.18% | +2.82% |
| Bybit EU taker +spread 0.27% **[reale]** | 9/24 | +8.80% | +10.11% | +2.76% |
| Bybit EU maker 0.10% *[non ottenibile]* | 12/24 | +9.39% | +10.69% | +3.25% |
| OKX swap taker 0.05% *[acctLv2, assente]* | 12/24 | +9.66% | +10.86% | +3.40% |

Allargare da 18 a 47 asset fa SCENDERE la mediana del pieno da +6.75% a +2.44% e le
configurazioni robuste da 14/24 a 7/24. Il campione delle 19 era un campione
fortunato: l'universo largo e' il verdetto onesto.

## 40.6 Il vero problema, che la fee non tocca

Blocchi del giornaliero, configurazione deployata, fee reale Bybit 0.27%/lato:

| blocco | media | mediana | positivi |
|---|---|---|---|
| 1 | **+11.84%** | +3.87% | 35/46 |
| 2 | -1.74% | -2.46% | 10/46 |
| 3 | -0.62% | -2.11% | 12/46 |

**Tutto il rendimento e' nel blocco 1.** Gli altri due sono negativi. Cambiare venue
non sposta un euro di questo: e' la stessa serie di prezzi. Lo stesso vale sul 4H,
dove il blocco 4 e' negativo a ogni livello di fee (-6.07% a 0.35%, -5.36% a 0.27%).

Questo conferma con una misura indipendente il docs/18 18.2 (rendimento episodico) e
dice dove va il prossimo lavoro: **piu' scommesse indipendenti, non fee piu' basse**.
Con 19-47 asset e 5 posizioni per conto il campione resta la fortuna di un
trimestre; il numero di configurazioni robuste SALE con l'universo largo (4/24 ->
14/24 sul 4H), che e' l'unico segnale positivo di tutta questa misura.

## 40.7 Verdetto

1. **Non migrare per le fee.** Sul timeframe deployato la differenza e' +0.36 punti
   su 2.5 anni; sul 4H migliora (4/24 -> 11/24 con spread) ma resta una minoranza.
   Non vale il trasloco di 17 bot, le chiavi nuove e il rischio di esecuzione.
2. **Bybit EU non offre derivati** (0 mercati swap, verificato sul conto): non
   sblocca l'unica leva che rende il 4H robusto (0.05%/lato -> 20-21/24), cioe'
   acctLv2 su OKX. Il vero collo di bottiglia resta l'accesso ai derivati.
3. **Il maker a 0.10% non e' una via d'uscita**: il breakout entra e il trailing
   stop esce in market. La famiglia maker-only e' gia' misurata a -61.35%.
4. **La fee non e' il problema.** Il rendimento del giornaliero sta in un blocco su
   tre, e sul campione largo le configurazioni robuste sono 7/24. La leva e' la
   larghezza dell'universo e il numero di scommesse indipendenti.

## 40.8 Due difetti di codice trovati e corretti mentre si misurava

`tools/fetch_universe.py` aveva DUE difetti che si mascheravano a vicenda:

1. passava il timeframe `1D`/`4H` maiuscolo a ccxt, che vuole `1d`/`4h`:
   `fetch_ohlcv` sollevava "timeframe unit D is not supported" per OGNI simbolo,
   il fetcher saltava tutto e usciva comunque con "FATTO: 0 file";
2. senza `params={'type': 'HistoryCandles'}` ccxt/OKX rispondono dal solo endpoint
   `/market/candles`, che si ferma a **1440 barre**: il 4H veniva troncato a 240
   giorni contro i 2.8 anni (6190 barre) gia' presenti su disco.

Il secondo era il piu' insidioso: le griglie allineano tutti i simboli alla serie
**piu' corta**, quindi UN solo simbolo scaricato male avrebbe accorciato l'intero
universo senza dire niente. Verificato: con HistoryCandles BTC/EUR 4H torna 6190
barre (2023-11-21 -> 2026-09-17), identico al file esistente.

Corrette anche due trappole nella griglia di misura: le configurazioni il cui
warm-up (EMA 200) e' piu' lungo del blocco non fanno NESSUN trade e venivano contate
come "composto 0.00%" (8 delle 24 sparivano dal conteggio e la mediana crollava a
0.00% per un artefatto); e il giornaliero non puo' essere misurato su 5 blocchi da
182 barre. Ora le configurazioni non testabili sono escluse dal denominatore e
dichiarate, e il giornaliero si misura su 3 blocchi.

Dati scaricati: `backtest_data/uni_*_4H.csv` (77 file) e `backtest_data/dl_*_1D.csv`
(56 file). Il taglio "largo ma corto" (>=1000 barre su 4H = 1030) e' dichiarato NON
utilizzabile: blocchi da 206 barre con EMA fino a 200 non dicono nulla. Non e' un no,
e' una misura che non esiste ancora.
