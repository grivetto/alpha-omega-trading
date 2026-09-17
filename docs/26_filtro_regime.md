# 26 — Filtro di regime: no (round 24)

## 26.1 L'idea

La strategia e' long-only. Un filtro che vieta nuovi ingressi quando il mercato
e' in trend ribassista — BTC sotto la sua media lunga, oppure BTC in perdita sul
mese — potrebbe evitare i falsi breakout nei mercati che scendono, cioe' proprio
il regime recente dove la strategia rende poco.

Variante generata dal sorgente del simulatore validato (stesso metodo del
simulatore con gap): a filtro assente il delta e' **0.00e+00** con 62 trade
identici.

## 26.2 La misura

| filtro | storia | maxDD | Sharpe | 12 mesi | 6 mesi |
|---|---|---|---|---|---|
| **nessuno** | +73.04% | 7.16% | 1.39 | **+9.17%** | +8.56% |
| BTC > EMA50 | +73.02% | 7.15% | 1.41 | +7.12% | +8.51% |
| BTC > EMA100 | +72.02% | 7.10% | 1.39 | +6.79% | +9.87% |
| BTC > EMA200 | +73.62% | 7.19% | 1.40 | +6.99% | +7.07% |
| BTC mom 30gg | +75.54% | **7.06%** | **1.43** | +7.52% | +7.00% |
| BTC mom 60gg | **+76.27%** | 7.38% | 1.41 | +6.25% | +9.29% |

Due filtri migliorano la storia lunga (mom60 +3.2 punti) e mom30 migliora anche
Sharpe e drawdown. **Ma peggiorano tutte le finestre recenti.**

## 26.3 La prova che decide

Dodici finestre scorrevoli, i tre candidati migliori contro il nessun filtro:

    mom30   batte 'nessuno' in  1/12 finestre
    mom60   batte 'nessuno' in  4/12 finestre
    ema100  batte 'nessuno' in  4/12 finestre

Il criterio e' battere in TUTTE. Nessuno ci si avvicina. Il guadagno sulla storia
lunga viene, di nuovo, dal rally 2024: il filtro lascia fuori i falsi breakout di
allora, non quelli di adesso.

**Decisione: nessun filtro.** La strategia senza filtro resta la migliore in 8-11
finestre su 12.

## 26.4 Una verifica che chiude un dubbio

Nel round 18 avevo annotato il sospetto che un riavvio potesse far PERDERE un
segnale, perche' la policy valuta solo al cambio di giornata. Rileggendo il
percorso, il sospetto era **infondato**:

- un nodo in funzione valuta la barra appena chiusa al cambio di giornata e entra
  al prezzo di quel momento, cioe' all'apertura della barra successiva — esattamente
  come il backtest;
- un riavvio a meta' barra imposta il periodo corrente e attende il PROSSIMO
  cambio: valutera' quella barra, cioe' la piu' recente, non una vecchia;
- l'unica perdita e' il segnale della chiusura avvenuta MENTRE il nodo era fermo,
  che e' inevitabile: non si puo' tradare a macchina spenta.

Non serve nessuna "recupero all'avvio", e sarebbe anzi peggiore: entrerebbe con
~22 ore di ritardo su un segnale vecchio.
