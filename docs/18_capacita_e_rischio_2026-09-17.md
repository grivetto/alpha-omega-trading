# 18 — Capacita', rischio e costo reale (2026-09-17)

Ricerca del round 15. Domanda: il sistema e' davvero redditizio, e si puo'
migliorare **senza** cambiare strategia?

## 18.1 Il costo reale e' taker, non maker

`exchange.fetch_trading_fee('BTC/EUR')` sull'account in produzione:
livello **Lv1**, **maker 0.20%**, **taker 0.35%**.

L'ingresso e' un limite a `mercato x (1 + 0.0005)` — sopra il mercato,
quindi **crossa lo spread** — e l'uscita e' a mercato. Sono **entrambi taker**:
il round trip reale e' **0.70%**, non 0.40% come assumeva il rig.

Misurato (`tools/trend_studio.py`, 19 asset, 865 barre):

| fee per lato | rendimento 2% rischio |
|---|---|
| 0.20% (maker) | +20.45% |
| 0.35% (taker reale) | +19.82% |

**L'edge sopravvive**: la strategia trada ~7 volte per asset in 2.4 anni, quindi
il costo incide per 0.6 punti su 2.4 anni. Il sospetto "le fee si mangiano
tutto" e' falso per QUESTA famiglia (era vero per grid e momentum, che tradano
centinaia di volte).

## 18.2 Il rendimento e' un EPISODIO, non un flusso

Storia spezzata in blocchi non sovrapposti (`tools/trend_oos.py`):

    3 blocchi: +20.33%   -0.55%   +0.25%
    4 blocchi: +31.56%   -0.56%   -0.23%   +0.43%
    5 blocchi: -0.72%  -0.11%  -0.49%  +0.16%  +0.67%

Tutto il rendimento sta in **un blocco** (il rally di fine 2024, barre ~173-288).
Sulle finestre ancorate OOS (ultimo 30/40/50% della storia) la strategia e'
**piatta**: -0.16%, +0.43%, +0.34%.

Griglia di **81 set di parametri** su finestre recenti:

| finestra | mediano | set positivi |
|---|---|---|
| tutta la storia | +13.75% | 60/81 (74%) |
| ultimi 18 mesi | +0.23% | 45/81 (56%) |
| ultimi 12 mesi | +0.17% | 58/81 (72%) |
| ultimi 8 mesi | +0.47% | 64/81 (79%) |
| ultimi 6 mesi | +0.72% | 48/54 (89%) |

L'edge **non e' morto** (sui 6 mesi l'89% dei set e' positivo) ma rende
**+0.2%/+0.7%**: rumore. Il trend following paga a episodi, e l'episodio
recente non c'e' stato.

## 18.3 A vs B: il rig per-simbolo sbaglia la classifica

Un set candidato B (canale 20, trail 4.0, stop 1.5) batteva il deployato A
(canale 40, trail 3.0, stop 2.0) su **14 asset su 19** nella storia intera
(differenza media +11.77%, **t=+2.66**) e vinceva ogni finestra della griglia.

Sembrava un miglioramento. **Era un artefatto.**

Il rig da' a ogni simbolo il proprio capitale pieno. In produzione i 5 asset di
un conto **condividono 24.83 EUR**: quando 3 posizioni sono aperte la quarta
viene dimensionata sul cash rimasto. B usa posizioni piu' grandi (stop piu'
stretto -> size maggiore a pari rischio), quindi sotto il vincolo reale sta
peggio.

## 18.4 Il simulatore a capitale CONDIVISO

`tools/trend_capacita.py` simula i 3 conti reali con la cassa condivisa,
riproducendo la logica di `backtest_trend` e il `budget = min(capitale, cash)`
della `Policy._available` in produzione.

**Validazione**: con capitale 1.0 e un solo asset il simulatore riproduce
`backtest_trend` **al bit** — 15 asset su 15, delta 0.00000. Senza questa prova
non sarebbe credibile.

Nota trovata durante la validazione: `backtest_trend` dimensiona sul cash
**cresciuto** (compone la size), la produzione la ancora al capitale configurato.
Su un conto che cresce le due cose divergono.

## 18.5 La frontiera: il rischio 2% e' GIA' l'ottimo

Simulatore validato, 3 conti x 24.83 EUR, 5 asset ciascuno:

| rischio | rendimento | CAGR | maxDD | Sharpe | rifiutati |
|---|---|---|---|---|---|
| 1.0% | 26.54% | 11.19% | 10.86% | **0.86** | 0 |
| 1.5% | 32.46% | 13.50% | 13.84% | 0.83 | 0 |
| **2.0%** | **34.90%** | **14.44%** | 16.85% | 0.79 | 0 |
| 3.0% | 32.56% | 13.54% | 22.13% | 0.68 | 0 |
| 4.0% | 25.64% | 10.83% | 26.01% | 0.55 | 0 |
| 6.0% | 7.71% | 3.41% | 27.65% | 0.26 | 22 |
| 8.0% | -7.05% | -3.24% | 34.24% | 0.01 | 89 |

**Alzare il rischio per trade RIDUCE il rendimento.** Da 6% in su il conto non
riesce piu' a finanziare le posizioni: 22 segnali rifiutati, poi 89, e il
risultato crolla. La configurazione deployata e' il **punto di massimo
rendimento** della frontiera vincolata.

## 18.6 Il vincolo e' una FRAZIONE, non una cifra

| capitale/conto | rischio 2% | rischio 6% |
|---|---|---|
| 25 EUR | 34.90% | 7.71% (22 rifiutati) |
| 250 EUR | 33.68% | 5.24% (22 rifiutati) |
| 1000 EUR | 32.50% | 4.53% (24 rifiutati) |

I rifiuti sono **costanti** al variare del capitale: il vincolo e' il numero di
posizioni contemporanee x la loro frazione, non l'importo. **Piu' capitale non
sblocca piu' rischio**: il rendimento percentuale e' lo stesso, cambia solo la
cifra in euro.

## 18.7 Decisione

**Nessun cambio di configurazione.** Il set deployato (canale 40, trail 3.0,
stop 2.0, rischio 2%) e' il massimo rendimento della frontiera misurata con il
vincolo reale; B perde su rendimento, drawdown e Sharpe a ogni livello di
rischio. Cambiare sarebbe overfitting su un rig che ignora la cassa.

## 18.8 Cosa significa per il denaro

Backtest della configurazione deployata sui 2.4 anni trascorsi: **+26 EUR** su
74.5 EUR di capitale totale. Ma quel numero e' dominato dal rally di fine 2024:
la finestra recente e' piatta. **L'aspettativa forward e' bassa.**

Il collo di bottiglia non e' piu' la strategia (corretta, robusta, Sharpe ~0.8)
ne' la configurazione (all'ottimo vincolato): e' **il capitale**, e il fatto che
il trend paga a episodi rari. Con 74.5 EUR un episodio favorevole vale decine di
euro, non migliaia.
