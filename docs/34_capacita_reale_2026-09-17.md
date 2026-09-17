# 34 — Fin dove regge l'edge se il capitale cresce (round 33, 2026-09-17)

## 34.1 Lo slippage parametrico dice "fino a 100.000 EUR"

Il simulatore modella l'impatto (k*sqrt(notional/volume)). Scalando il capitale
dei 3 conti in proporzione, stessa flotta, rischio 2%, fee taker 0.35%
(`tools/trend_scala_capitale.py`):

| capitale | storia | 365b | Sharpe storia | maxDD storia | 365b in EUR |
|---|---|---|---|---|---|
| 109 EUR (oggi) | +79.60% | +8.37% | 1.24 | 12.46% | 9 EUR |
| 250 EUR | +79.09% | +8.24% | 1.24 | 12.59% | 21 EUR |
| 500 EUR | +78.51% | +8.07% | 1.23 | 12.74% | 40 EUR |
| 1.000 EUR | +77.88% | +7.90% | 1.22 | 12.91% | 79 EUR |
| 2.500 EUR | +76.91% | +7.56% | 1.21 | 13.25% | 189 EUR |
| 10.000 EUR | +75.46% | +7.10% | 1.19 | 13.81% | 710 EUR |
| 100.000 EUR | +73.38% | +6.48% | 1.17 | 14.42% | 6.478 EUR |

Il rendimento percentuale e' quasi INVARIANTE: da 109 EUR a 100.000 EUR perde 6
punti sulla storia (2.4 anni) e 0.6 punti/anno sul presente. Se ci si fermasse
qui, la risposta sarebbe "il capitale e' gratis".

## 34.2 Il vincolo vero e' la LIQUIDITA' delle coppie EUR

Il modello di slippage e' parametrico e ottimista. Il limite reale si misura in
**partecipazione al volume**: nozionale tipico della posizione diviso volume
medio giornaliero dell'asset. Su OKX EEA le coppie EUR sono sottili.

| asset | volume/gg | part. a 1.000 EUR | a 10.000 EUR | a 100.000 EUR |
|---|---|---|---|---|
| MINA | 7.014 EUR | 0.57% | **5.67%** | **56.7%** |
| ALGO | 13.800 EUR | 0.42% | **4.16%** | **41.6%** |
| TRX | 66.931 EUR | 0.36% | **3.65%** | **36.4%** |
| AVAX | 24.423 EUR | 0.32% | **3.15%** | **31.5%** |
| CRV | 25.997 EUR | 0.17% | 1.67% | 16.7% |
| XLM | 43.463 EUR | 0.14% | 1.40% | 14.0% |
| ARB | 46.367 EUR | 0.08% | 0.79% | 7.9% |
| DOT | 153.526 EUR | 0.04% | 0.35% | 3.5% |

## 34.3 La risposta onesta: 1.000-3.000 EUR, non 100.000

- **fino a ~1.000 EUR** totali: partecipazione sotto lo 0.6% su tutti e 17 gli
  asset. L'edge misurato vale tale e quale (~+7.9%/anno sul regime recente).
- **1.000-3.000 EUR**: MINA, ALGO, TRX e AVAX vanno sopra l'1% del volume
  giornaliero. Lo slippage reale diventa visibile; o si accetta, o si tolgono
  quei quattro (misurato: toglierli costa rendimento, docs/30).
- **oltre ~3.000 EUR**: servono solo i nomi liquidi (BTC, ETH, SOL, XRP, LINK,
  DOT, DOGE, ADA...). A 10.000 EUR su 8-10 asset liquidi la partecipazione resta
  sotto il 3%: e' la configurazione sensata per un conto a 5 cifre.
- **100.000 EUR**: con questa flotta non e' fattibile (MINA sarebbe il 57% del
  volume giornaliero). Servirebbero i derivati e i pair USDT.

## 34.4 Cosa fare, in ordine

1. **Nessuna modifica alla flotta**: a 109 EUR la partecipazione massima e' lo
   0.57% (MINA). Il sistema attuale e' gia' al punto misurato.
2. **Primo euro di capitale in piu': su nuvola** (24.83 EUR, 6 bot) — e' il conto
   con meno capitale per bot. Portarlo a ~42 EUR uniforma la flotta.
3. **Fino a ~1.000 EUR** si sale senza cambiare niente: 5-8 EUR/anno per 100 EUR
   investiti sul regime recente, drawdown atteso 12-15%.
4. **Oltre 1.000 EUR**: prima di aggiungere, togliere MINA/ALGO/TRX/AVAX *solo
   se la misura lo conferma* (finora togliere per rendimento recente ha sempre
   peggiorato fuori campione). In alternativa, accettare slippage piu' alto su
   quei quattro e tenerli.
5. **Oltre 3.000 EUR**: passare ai nomi liquidi o ai derivati (fee 0.05%: +1.8
   EUR/anno ogni 109 EUR, quindi ~+165 EUR/anno a 10.000 EUR).

Il messaggio per il conto reale: **questo sistema non ha bisogno di piu'
strategie, ha bisogno di capitale**, e la quantita' utile sta fra 1.000 e 3.000
EUR con l'universo attuale.
