# 17 — Risultato della ricerca: nessun edge nelle strategie attuali

Data: 2026-09-17
Stato: **negativo, ma verificato**. Da leggere prima di riprovare qualsiasi
ottimizzazione di parametri sulle famiglie esistenti.

## Perche' questo documento

Un anno e mezzo di lavoro ha prodotto un conto che non cresce. La causa non
erano le strategie: era il **rig di misura**. Questo documento registra cosa e'
stato corretto, cosa e' stato misurato dopo la correzione, e perche' insistere
sui parametri delle famiglie esistenti e' tempo perso.

## 1. I quattro difetti del vecchio laboratorio

Tutti in `brain/strategy_lab.py`. Ognuno da solo basta a invalidare le conclusioni.

**a) Look-ahead nel backtest.** Si riempiva il buy con il `low` della barra e
il sell con l'`high` della **stessa** barra. Ogni candela con range maggiore di
`buy_distance + profit_target` chiudeva un ciclo completo garantito: il profitto
non veniva dal mercato, veniva dall'usare entrambi gli estremi della stessa
candela. Effetto misurato: la griglia DOGE su 2 anni passava da **+272%** a
**−54%**.

**b) Drawdown sbagliato.** `max(1 - e/peak)` con `peak` calcolato *dopo* il
ciclo, cioe' il picco finale. Non e' un drawdown. Su `[100,110,99,105,120]`
dava 17.50% invece di 10.00%.

**c) Sharpe su equity oraria.** Una griglia ha equity costante a tratti: i
rendimenti orari sono quasi tutti zeri esatti, `mean/std` esplode e
annualizzato produce valori tipo −12. Questo produceva il paradosso
"rendimento +12% con Sharpe −4.61". Lo Sharpe ora si calcola sui rendimenti
**giornalieri**.

**d) Fallback silenzioso.** `walk_forward_evaluate`, sotto le 350 barre,
restituiva un backtest singolo **senza segnalarlo**. Tutti i risultati in
`config/strategies/registry.json` erano backtest su 149-225 barre (6-9 giorni)
presentati come walk-forward. Nessuna voce aveva il campo `folds`.

## 2. Il rig corretto

`denaro/research/eval.py` (nuovo, versionato, con 12 test di regressione).

- Ordini piazzati sul **close** della barra e attivi dalla barra successiva
  (campo `attivo_da`); un sell nasce dal fill di un buy solo per la barra dopo.
- Drawdown sul **picco corrente**.
- Sharpe e Sortino sui rendimenti **giornalieri**.
- Walk-forward con motivo esplicito se i fold non sono possibili.
- **Gate out-of-sample**: >=3 fold, >=75% fold positivi, mediana OOS > 0,
  **mediana alpha > 0**, >=30 trade OOS.
- Confronto esplicito con il **buy-and-hold** sulla stessa finestra.

Dati: `deep_fetch.py` scarica 17.700 barre 1H (737 giorni) e ~6.000 barre 4H
per coppia — contro le ~200 barre usate prima. Paginazione vera di
`history-candles` con il parametro `after`.

## 3. Risultato: nessun candidato robusto

Matrice 5 coppie x 3 motori (grid, momentum, mean-reversion), 1H, walk-forward
con 9 fold. Nessuno passa il gate.

| coppia | motore | rendimento intero | mediana OOS | fold positivi |
|---|---|---|---|---|
| DOGE/EUR | grid | +61.52% | **−8.26%** | 11% |
| SOL/EUR | grid | +50.15% | −3.87% | 11% |
| XRP/EUR | grid | +74.38% | −8.15% | 0% |
| ETH/EUR | grid | +45.75% | −6.85% | 11% |
| ADA/EUR | grid | +23.18% | −8.09% | 11% |
| XRP/EUR | meanrev | −3.99% | +1.17% | 56% |
| DOGE/EUR | momentum | −97.59% | −26.13% | 0% |

La firma e' inequivocabile: **in-sample brillante, out-of-sample negativo**.
E' la definizione di overfitting, riprodotta su tutte le coppie.

Gli `alpha OOS` positivi (+20%…+67%) sono in gran parte **fittizi**: le
strategie battono il buy-and-hold restando *fuori* dal mercato nei ribassi,
non per un edge misurato.

## 4. Ipotesi strutturali testate e respinte

L'ipotesi era ragionevole: la griglia perde perche' compra nei ribassi e si
porta l'inventario. 70 configurazioni testate.

| variante | effetto misurato |
|---|---|
| stop loss 10% | riduce il drawdown (77% -> 11%) ma non crea edge |
| filtro EMA200 | **0% fold positivi**: peggio del baseline |
| filtro ADX + EMA | 0% fold positivi |
| target piu' ampio (3%) | fee/lordo scende (11% -> 7%) ma OOS resta negativo |
| timeframe 4H | peggiore: mediana OOS da −3% a −26% |

Il filtro di regime, in particolare, **non aiuta**: blocca i trade e riduce il
campione OOS sotto il minimo, peggiorando il risultato.

Una sola riga su 70 passa il gate (ETH grid 1H, 75% fold positivi) ma con
**alpha −2.50%**: perde contro il semplice buy-and-hold. Era un falso positivo
del gate, che infatti e' stato irrigidito richiedendo anche alpha positivo.

## 5. Conclusione

Le tre famiglie esistenti, **con qualunque parametro**, non hanno un edge
out-of-sample misurabile su 2 anni e 5 coppie. Continuare a ottimizzare i
parametri e' esattamente cio' che e' stato fatto per un anno e mezzo: piu'
prova di overfitting, non piu' rendimento.

Il passo successivo non e' un altro giro di tuning. E' cambiare la **fonte del
segnale**: le famiglie attuali gestiscono inventario, non prevedono nulla.
Le direzioni da esplorare, in ordine di credibilita' per un conto retail su
OKX EEA spot:

1. **Trend following con gestione del rischio per volatilita'** (trailing stop
   ATR, sizing inversamente proporzionale alla volatilita'). Il momentum
   testato era naif: target fisso, nessun trailing, size fissa.
2. **Verifica del costo maker/taker reale su OKX EEA**: se non c'e' ribate o
   credito maker, il market making e' strutturalmente in perdita e va scartato.
3. **Strategie di portafoglio** (momentum cross-sezionale su piu' asset,
   mean-reversion tra coppie correlate) che non dipendono dalla previsione di
   un singolo prezzo.

Ogni candidato va giudicato **solo** con `denaro/research/eval.py` e il suo gate.
Nessuna strategia va in live senza >=3 fold, >=75% fold positivi, mediana OOS
positiva e alpha positivo.


## 6. Le commissioni reali sono il DOPPIO di quelle usate (2026-09-17)

Verificato sui **fill reali** del conto, non sul config. Ogni fill, senza
eccezioni, e' tassato allo **0.2000%**:

    DOGE/EUR 2026-09-08 buy  notional 4.0002 fee 0.104484 DOGE -> 0.2000%
    DOGE/EUR 2026-09-08 sell notional 2.0386 fee 0.004077 EUR  -> 0.2000%
    SOL/EUR  2026-09-11 sell notional 2.0539 fee 0.004108 EUR  -> 0.2000%

Il conto e' `level: Lv1`, `maker: -0.002`, `taker: -0.0035`.
Il progetto usava `fee: 0.001` — **meta' del costo reale** — nei config, nei
backtest e nel PnL del bot.

Conseguenze misurate (griglia live, 2 anni, 1H):

| coppia | fee 0.10% (usata) | fee 0.20% (reale maker) | fee/lordo |
|---|---|---|---|
| SOL/EUR | +27.27% | **−5.73%** | 11.9% -> 25.3% |
| ETH/EUR | +27.37% | +21.93% | 10.6% -> 21.1% |
| DOGE/EUR | −6.42% | −7.19% | 14.7% -> 28.8% |
| XRP/EUR | −11.10% | −11.67% | 13.9% -> 27.2% |
| ADA/EUR | −10.80% | −11.17% | 35.8% -> 65.2% |

Il caso SOL e' il piu' grave: **il profitto era la fee sbagliata**. Con il costo
vero diventa negativo.

Effetti sul bot live:
- il PnL registrato e' ottimistico di ~0.2% per round trip;
- con centinaia di cicli questo e' una parte rilevante del capitale: sul bot
  DOGE di mc2, 159 cicli su ~8 EUR per livello sono ~2.5 EUR di fee non
  contabilizzate su un conto da 24 EUR;
- i guard di drawdown e daily-loss scattano in ritardo, perche' calcolati su
  un'equity gonfiata.

Correzione applicata: `fee: 0.002` in `node_mc2.yaml`,
`node_nuvola_trade.yaml`, `node_marcodg1_xrp.yaml`.

Nota sugli spread (misurati in contemporanea): DOGE 0.056%, SOL 0.023%,
XRP 0.035%. **Non sono lo spread il problema: sono le fee**, che con un round
trip maker costano 0.40% contro 0.02-0.06% di spread. Qualunque strategia che
faccia piu' di ~4 round trip al giorno paga piu' di fee che di spread.
