# 40 — La scala dei costi: quanto vale ogni punto base (round 37)

Complemento a **docs/39** (che stabilisce che la migrazione a Bybit EU non si
giustifica). Qui c'e' solo cio' che docs/39 non quantifica: come si muove la
robustezza lungo la scala dei costi e quanto valgono i punti base in euro.

## 40.1 La scala (configurazioni robuste su 24)

| fee per lato | 4H (19 asset) | 4H largo (28) | 1D (19) | 1D largo (47) |
|---|---|---|---|---|
| 0.35% — OKX spot taker (deployato) | **3** | 4 | **14** | 7 |
| 0.27% — Bybit taker + spread (reale) | 9 | 11 | 17 | 9 |
| 0.25% — Bybit taker (listino) | 9 | 14 | 18 | 9 |
| 0.20% — maker | **13** | 19 | 18 | 10 |
| 0.10% — maker Bybit | 18 | 21 | 18 | 12 |
| 0.05% — derivati (acctLv 2) | **20** | 21 | 18 | 12 |

Due letture opposte, ed e' il punto:

- **sul giornaliero la fee e' quasi irrilevante**: da 0.35% a 0.05% le
  configurazioni robuste passano da 14 a 18 su 24. Il daily paga 0.70% di round
  trip su movimenti da diversi punti percentuali: il costo e' rumore.
- **sul 4H la fee e' tutto**: 3 -> 20 su 24 (0.35% -> 0.05%), monotona e ripida.
  La soglia sta fra 0.30% e 0.25%.

Quindi: il daily non ha bisogno di fee basse per funzionare, il 4H si'. Non e' un
problema di strategia, e' un problema di **dove** e **come** si esegue.

## 40.2 Quanto valgono in euro

Misurato al round 30 sui 109 EUR attuali, e proporzionale al capitale:

| leva | effetto sul rendimento | a 109 EUR | a 1.000 EUR | a 10.000 EUR |
|---|---|---|---|---|
| maker sull'ingresso (0.35 -> 0.20) | +0.9 punti/anno | +0.9 EUR | +8 EUR | +80 EUR |
| derivati taker (0.35 -> 0.05) | +1.8 punti/anno | +1.8 EUR | +16 EUR | +165 EUR |
| **derivati + 4H** | abilita 8x le occasioni | non misurabile a 109 EUR | da misurare | da misurare |

## 40.3 Cosa fare, in ordine

1. **Oggi**: nessun cambio. Il giornaliero a 0.35% e' robusto (14/24) e deployato.
2. **Passo a costo zero**: chiedere a OKX l'upgrade a `acctLv 2` (derivati). E'
   l'unica leva che cambia *quante occasioni* esistono, non solo quanto costano: a
   0.05%/lato il 4H passa da 3 a 20 configurazioni robuste.
3. **In alternativa**, senza cambiare venue ne' conto: ingressi **maker** sul
   daily. Guadagno piccolo ma certo (+0.9 EUR/anno sui 109 EUR) e porta il 4H a
   13/24, cioe' lo rende valutabile.
4. **Non** migrare a Bybit EU per la sola fee: 9/24 contro 3/24 non paga
   l'integrazione di una seconda venue (docs/39).
