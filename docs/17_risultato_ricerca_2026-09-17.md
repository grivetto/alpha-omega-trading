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


## 7. Trend following con rischio per volatilita' (round 2, 2026-09-17)

Motore nuovo: `backtest_trend` in `denaro/research/eval.py`.
Differenze sostanziali dal momentum naif che perdeva −77..−98%:

- ingresso sul breakout del massimo delle ultime N barre (canale Donchian),
  non su un incrocio di medie;
- uscita con **trailing stop a k*ATR**, non con un target fisso;
- **size calcolata sul rischio**: qty = equity*risk / (stop_mult*ATR), quindi
  la posizione si stringe quando la volatilita' sale. Sul momentum la size era
  fissa.

### 7.1 Asset per asset: nessuno passa il gate

Su 4H e 1D, 5 coppie, fee reali 0.20%: nessun candidato singolo passa il gate
(fold positivi >=75%). Ma il profilo e' molto migliore del grid: drawdown
18-37% invece di 75%, fee/lordo 8-26% invece di 25-65%, e **alpha OOS positivo
in tutti e 10 i casi** (+19%..+190%).

Il trend following e' a coda grossa: pochi periodi molto positivi e molti
piccoli negativi. La percentuale di fold positivi e' quindi una statistica
povera per questa famiglia — XRP 4H ha il 56% di fold positivi ma un
rendimento composto OOS di +93%.

### 7.2 Portafoglio: la misura corretta

`walk_forward_portafoglio`: **un solo set di parametri per tutti i simboli**,
scelto sul train AGGREGATO e valutato sul test AGGREGATO. Cinque ottimizzazioni
indipendenti su cinque asset sono cinque occasioni di overfittare; una sola e'
una sola. E' anche cio' che si puo' fare davvero in live.

Portafoglio 4H, 5 asset equal-weight, 9 fold:

| metrica | valore |
|---|---|
| rendimento composto OOS | **+47.93%** |
| buy&hold equal-weight sugli stessi periodi | +14.90% |
| **alpha composto** | **+33.03%** |
| peggior fold | **−5.65%** |
| fold positivi | 56% |
| sharpe sui fold | 1.07 |
| composto escludendo il fold migliore | +4.37% |

### 7.3 Robustezza

| prova | comp | senza fold migliore | alpha | peggior fold |
|---|---|---|---|---|
| train 500 / test 250 (20 fold) | +3.85% | −9.07% | +21.75% | −6.45% |
| train 750 / test 375 (12 fold) | +58.26% | +12.90% | +82.26% | −5.04% |
| train 1000 / test 500 (9 fold) | +47.93% | +4.37% | +33.03% | −5.65% |
| train 1500 / test 750 (5 fold) | +2.55% | −14.68% | +60.72% | −6.75% |
| train 2000 / test 1000 (3 fold) | +0.47% | −12.92% | +67.93% | −11.72% |
| senza SOL/EUR | +62.31% | +9.60% | +33.67% | −5.62% |
| senza DOGE/EUR | +24.00% | +7.69% | +11.94% | −5.39% |
| senza XRP/EUR | +35.95% | +1.41% | +81.46% | −5.71% |
| senza ETH/EUR | +60.20% | +6.74% | +48.68% | −6.65% |
| senza ADA/EUR | +50.25% | +10.34% | +17.94% | −6.28% |
| fee taker 0.35%/lato | +41.80% | +1.18% | +26.89% | −6.11% |

**Cosa regge:** l'alpha e' positivo in TUTTE le 11 configurazioni (+11.9%..+82.3%).
Il leave-one-out non crolla: nessun singolo asset trascina. Regge anche alla fee
taker peggiore. Il peggior fold resta sempre tra −5% e −12%.

**Cosa non regge:** il rendimento ASSOLUTO dipende molto dalla finestra
(+0.47%..+58.26%) e in 4 configurazioni su 5 diventa negativo togliendo il fold
migliore. La percentuale di fold positivi e' 20-56%, sotto qualsiasi soglia
ragionevole.

### 7.4 Lettura onesta

Il trend following 4H su portafoglio ha un **edge relativo reale e robusto**
(batte il buy-and-hold in modo consistente, con downside contenuto) ma un
**rendimento assoluto debole e instabile**: circa in pareggio.

Il motivo sta nei dati, non nella strategia: il buy-and-hold equal-weight ha
reso **da −18% a −67%** sui periodi di test. Era un **mercato orso**. Una
strategia long-only su spot ha un tetto strutturale in un orso: puo' perdere
meno, non guadagnare.

Conseguenza operativa: sostituire le strategie live attuali (grid, momentum,
mean-reversion, tutte con alpha NEGATIVO e drawdown 60-99%) con il portafoglio
trend e' un miglioramento netto anche se il rendimento atteso resta modesto.
Per guadagnare davvero in un orso servirebbe la capacita' di stare short
(swap/futures), che e' una decisione di rischio, non di codice.


### 7.5 Correzione: i numeri di 7.2 e 7.3 erano sottostimati

Il motore trend aveva un difetto: il cap di esposizione calcolava la size
massima affondabile con una stima FISSA di slippage (0.0005) mentre lo slippage
vero dipende dal notional (k*sqrt(notional/volume)). Quando la size calcolata
sul rischio si avvicinava al limite di capitale, il costo risultava maggiore
del cash disponibile e l'ordine veniva **rifiutato invece che ridotto**: trade
validi persi in silenzio. Corretto con uno scaling a due passaggi (calcolo il
costo vero e riduco la size).

I numeri di 7.2 e 7.3 vanno quindi sostituiti. Ricalcolo con il motore corretto:

| metrica | valore bacato | **valore corretto** |
|---|---|---|
| rendimento composto OOS 4H | +47.93% | **+44.75%** |
| buy&hold equal-weight | +14.90% | +14.90% |
| alpha composto | +33.03% | **+29.85%** |
| peggior fold | −5.65% | **−6.15%** |
| fold positivi | 56% | **44%** |
| sharpe sui fold | 1.07 | **0.99** |
| composto senza il fold migliore | +4.37% | **+1.23%** |

Robustezza ricalcolata (l'alpha regge in TUTTE le 11 configurazioni):

| prova | comp | senza fold migliore | alpha | peggior fold |
|---|---|---|---|---|
| train 500 / test 250 (20 fold) | +8.44% | −4.41% | +26.35% | −7.40% |
| train 750 / test 375 (12 fold) | +54.89% | +8.95% | +78.89% | −8.45% |
| train 1000 / test 500 (9 fold) | +44.75% | +1.23% | +29.85% | −6.15% |
| train 1500 / test 750 (5 fold) | +6.69% | −12.60% | +64.86% | −6.88% |
| train 2000 / test 1000 (3 fold) | +2.80% | −12.72% | +70.26% | −12.74% |
| senza SOL/EUR | +56.89% | +4.54% | +28.25% | −5.62% |
| senza DOGE/EUR | +50.16% | +1.68% | +38.10% | −5.87% |
| senza XRP/EUR | +40.91% | +0.09% | +86.42% | −5.71% |
| senza ETH/EUR | +58.78% | +10.04% | +47.25% | −6.65% |
| senza ADA/EUR | +33.61% | +6.46% | **+1.31%** | −6.28% |
| fee taker 0.35%/lato | +40.07% | +6.86% | +25.16% | −6.11% |

Le conclusioni di 7.4 restano valide, con una precisazione: l'alpha e' positivo
ovunque ma in un caso (senza ADA) scende a +1.31%, quindi non e' indistruttibile.
Il rendimento assoluto resta debole e dipendente dalla finestra, e togliendo il
fold migliore e' positivo solo in 2 configurazioni su 5.

**Nota di metodo**: questa correzione e' esattamente il motivo per cui il rig
esiste. I numeri bacati erano plausibili e la conclusione qualitativa non
cambiava; senza il test che ha fallito non me ne sarei accorto. E' lo stesso
tipo di errore che ha reso inutilizzabili un anno e mezzo di risultati.

### 7.6 Conclusione del round 2

Il trend following con rischio per volatilita', valutato su un portafoglio con
UN SOLO set di parametri per 5 asset:

- **batte il buy-and-hold in modo consistente**: alpha positivo in tutte le 11
  configurazioni di robustezza, regge al leave-one-out, regge alla fee taker;
- **non guadagna in modo affidabile in assoluto**: circa in pareggio, con forte
  dipendenza dalla finestra;
- il motivo e' nel mercato: il buy-and-hold equal-weight ha reso da −18% a −67%
  sui periodi di test. Era un orso, e una strategia long-only su spot in un orso
  puo' perdere meno, non guadagnare.

Sul piano operativo: le strategie live attuali (grid su DOGE, momentum su SOL,
mean-reversion su XRP) hanno alpha NEGATIVO e drawdown 60-99%. Sostituirle con
il portafoglio trend e' un miglioramento netto anche se il rendimento atteso
resta modesto. Per guadagnare davvero in un orso servirebbe la capacita' di
stare short (swap/futures): e' una decisione di rischio, non di codice.


## 8. Round 3 — L'alpha non c'e', e la griglia live e' provata dannosa

### 8.1 L'universo ampio uccide il risultato del round 2

Ipotesi: il trend following e' a coda grossa, quindi con piu' asset la legge dei
grandi numeri avrebbe stabilizzato il rendimento. Smentita.

| universo | comp OOS | senza fold migliore | peggior fold | fold positivi |
|---|---|---|---|---|
| 5 asset | +44.75% | +1.23% | −6.15% | 44% |
| 19 asset | **+3.93%** | **−34.47%** | **−15.08%** | **12%** |

Con 19 asset invece di 5, **gli stessi parametri** producono +3.93% invece di
+44.75%, e senza il fold migliore −34.47%. Il risultato del round 2 era quindi
**fortuna nella scelta degli asset** (SOL, XRP, DOGE, ETH, ADA erano quelli con
i trend piu' forti), non un effetto robusto. Leave-one-out sul 19 asset: togliere
BTC, ETH, XRP o SOL lascia +1.90%..+6.46%, cioe' nulla.

### 8.2 Alpha di Jensen: era beta, non abilita'

Una strategia long-only che sta fuori dal mercato gran parte del tempo batte il
buy-and-hold in un mercato che scende **senza avere alcun edge**: e' solo beta
piu' basso. La misura corretta e' la regressione:

    r_strategia = alpha + beta * r_buyhold

| campione | n | beta | alpha | t(alpha) | R2 |
|---|---|---|---|---|---|
| trend 5 asset (fold OOS) | 9 | +0.28 | +2.11% | +1.41 | 0.93 |
| trend 19 asset (fold OOS) | 8 | +0.37 | +0.36% | +0.09 | 0.79 |
| trend 5 asset (per asset) | 5 | +0.21 | +24.30% | +4.70 | 0.62 |
| trend 19 asset (per asset) | 19 | +0.10 | +12.33% | +1.73 | 0.06 |
| **grid ottimizzato (per asset)** | 18 | +0.09 | **−7.48%** | **−4.64** | 0.52 |

Lettura:

- **Il trend following non ha alpha.** R2 = 0.79..0.93: i suoi rendimenti sono
  spiegati per l'80-93% dal beta di mercato. L'alpha e' +0.36%..+2.11% con
  t <= 1.41, statisticamente indistinguibile da zero. Il caso "5 asset per
  asset" (+24.30%, t=4.70) ha n=5: con 3 gradi di liberta' il t-stat non e'
  credibile.
- **La griglia live ha alpha significativamente NEGATIVO**: −7.48% con
  t = −4.64 su 18 osservazioni. Ed e' la versione OTTIMIZZATA in-sample per
  ogni asset, quindi ottimisticamente distorta. La griglia che gira su mc2,
  nuvola e MARCODG1 distrugge valore in modo statisticamente solido.

### 8.3 Stato dell'obiettivo

Dopo tre round di misura rigorosa:

- **grid / momentum / mean-reversion**: nessun alpha, e per la grid alpha
  significativamente negativo (t = −4.64);
- **trend following con rischio per volatilita'**: alpha non significativo
  (+0.36%..+2.11%, t <= 1.41) e risultato dipendente dalla selezione degli
  asset;
- **nessuna strategia con alpha positivo statisticamente significativo** e'
  stata trovata.

Il rig di misura e' pero' ora affidabile (17 test di regressione) e le
conclusioni sono falsificabili. Le direzioni non ancora esplorate:

1. **Verificare se OKX EEA consente lo short** (swap/futures): e' l'unica leva
   che cambierebbe il segno in un mercato orso, ma introduce leva e
   liquidazione — decisione di rischio, non di codice.
2. **Smaltire le strategie live con alpha negativo** invece di continuare a
   farle girare mentre si cerca un edge.
3. **Esplorare fonti di rendimento non direzionali**: funding rate, basis,
   market making (ma la fee maker 0.20% rende il market making strutturalmente
   in perdita: lo spread e' 0.02-0.06%, la fee 0.20%).
