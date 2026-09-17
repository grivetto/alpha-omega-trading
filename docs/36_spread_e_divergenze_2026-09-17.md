# 36 — Costi reali di esecuzione (spread) e chiusura delle divergenze (round 34)

## 36.1 Lo spread che il backtest non vede

Il backtest paga la fee (0.35%/lato) piu' uno slippage parametrico. Su un book
reale si compra all'**ask** e si vende al **bid**: ogni giro paga anche lo
SPREAD, e questo il backtest non lo vede. Misurato su OKX EEA il 2026-09-17
(mediana di 3 letture del ticker, `tools/trend_spread_reale.py`):

| asset | spread | asset | spread | asset | spread |
|---|---|---|---|---|---|
| MINA | 0.415% | CRV | 0.245% | SUI | 0.062% |
| ARB | 0.376% | ADA | 0.170% | LINK | 0.060% |
| DOT | 0.328% | AVAX | 0.166% | XRP | 0.044% |
| XLM | 0.294% | UNI | 0.134% | SOL | 0.034% |
| ALGO | 0.266% | DOGE | 0.084% | ETH | 0.013% |
|  |  | TRX | 0.072% | BTC | 0.008% |

Mediana **0.134%**, media 0.163%. Il simulatore e' stato esteso con una fee
efficace `fee + spread/2` per lato (`tools/trend_sim_spread.py`, **generato**
da quello validato; con spread vuoto riproduce `backtest_trend` **al bit**).

## 36.2 Quanto costa davvero

| configurazione | storia | 540b | 365b | 270b | 180b | maxDD | Sharpe |
|---|---|---|---|---|---|---|---|
| flotta 17, solo fee | +79.60% | +12.19% | +8.37% | +5.49% | +8.10% | 12.46% | 1.24 |
| **flotta 17, fee + spread** | **+78.31%** | **+11.73%** | **+8.10%** | **+5.20%** | **+7.96%** | 12.82% | **1.23** |
| solo liquidi (8) | +27.89% | +8.70% | +5.33% | +5.06% | +5.03% | 9.19% | 1.01 |
| solo illiquidi (9) | +91.54% | +5.37% | +5.81% | +2.90% | +7.21% | 12.48% | 1.18 |

Lo spread reale costa **1.29 punti su 2.4 anni** (0.27 sull'anno recente) e non
cambia lo Sharpe (1.24 -> 1.23). Per asset il danno va da -0.02% (BTC) a -1.35%
(XLM) **su tutta la storia**: e' un ordine di grandezza sotto l'edge di ciascun
asset.

Il taglio "solo liquidi" (spread <= 0.11%) e' la scoperta controintuitiva: rende
**+27.89%** contro il **+91.54%** degli "illiquidi" — cioe' gli asset con lo
spread piu' largo (XLM, CRV, ALGO, MINA) sono quelli che hanno pagato di piu',
nonostante il costo. **Nessun cambio di flotta giustificato dallo spread.**

## 36.3 Le ultime due divergenze live/backtest sono chiuse

**a) Il prezzo d'ingresso e' quello misurato.** Il backtest entra all'**open
della barra successiva** al segnale (disciplina anti look-ahead). La live fa la
stessa cosa: il segnale si valuta sulla CHIUSURA (`barre[-1]["c"]`), ma il
prezzo d'ingresso e' il prezzo CORRENTE al momento del tick (il primo prezzo dopo
il confine) + 0.05% di slip. Verificato leggendo `backtest_trend` e il
`simula` validato: entrambi usano la chiusura per decidere e l'apertura
successiva per eseguire. La distinzione conta: sui dati reali la differenza
mediana fra chiusura e apertura successiva e' **0.44%** (p90 2.76%), quindi
usare il prezzo sbagliato dei due sarebbe un errore grande.

**b) Il trigger sul tick non va spostato sulla candela.** Restava la differenza
fra la chiusura dell'ultimo tick (usata per il segnale) e la chiusura ufficiale
della candela. Quantificata: il tick e' entro ~30 secondi dal bordo (errore
atteso ~0.05-0.1% di prezzo) e l'ATR della barra dei tick e' quello costruito dal
processo. Spostare il trigger sulla candela ufficiale (disponibile fino a 60s
dopo il confine, per il refresh del canale OHLCV) sposterebbe l'INGRESSO di 60
secondi in avanti, cioe' introdurrebbe un errore dello stesso ordine e nel verso
peggiore (si entra piu' tardi di quanto misurato). Con la fee a 0.35% e lo spread
a 0.13%, un residuo di 0.05-0.1% non e' misurabile: **non si cambia**, e il
rischio di toccare il percorso che mette ordini reali non si prende per zero.

## 36.4 Integrita' dei dati

Verificato: le barre dei CSV di ricerca sono **contigue** (differenza esatta di
86.400.000 ms fra barre consecutive, nessun buco) su tutti e 52 i file. Le
"anomalie" segnalate da un primo controllo erano un errore di unita' di misura
dell'analisi, non dei dati.
