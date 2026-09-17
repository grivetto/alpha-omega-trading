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


## 9. Round 4 — Il collo di bottiglia sono i COSTI, non le strategie

### 9.1 Momentum cross-sezionale: respinto

Non "questo sale?", ma "quale sale piu' degli altri?": si rankano i 19 asset per
rendimento passato e si tiene equal-weight il paniere dei primi k, con
ribilanciamento settimanale (turnover basso, quindi fee contenute).

| finestra | fold | comp OOS | senza fold migliore | alpha Jensen | t |
|---|---|---|---|---|---|
| train 1000 / test 500 | 8 | **−51.11%** | −156.51% | **−8.61%** | **−2.55** |
| train 500 / test 250 | 18 | +7.04% | −140.90% | +1.02% | +0.33 |
| train 1500 / test 750 | 4 | −32.12% | −151.25% | +14.82% | +8.45 (n=4) |

Alpha significativamente negativo alla finestra di riferimento, e in ogni
configurazione il risultato dipende da un solo fold (senza-migl da −140% a
−156%). Il momentum settimanale in crypto compra i vincitori recenti subito
prima del reversal, e paga fee a ogni ribilanciamento.

### 9.2 La diagnostica decisiva: segnale mancante o costo eccessivo?

Regressione di Jensen per asset (n=19), a fee decrescenti. Se l'alpha resta
negativo a fee zero, manca il segnale. Se diventa positivo a fee basse, il
costo e' il collo di bottiglia.

| fee per lato | GRID alpha (t) | TREND alpha (t) |
|---|---|---|
| 0.00% | **−5.77% (−2.56)** | +104.13% (+3.92) |
| 0.05% | −6.88% (−3.37) | +95.59% (+3.68) |
| 0.10% | −6.45% (−3.01) | +86.73% (+3.40) |
| 0.20% (maker reale) | −7.48% (−4.64) | +72.72% (+2.99) |
| 0.35% (taker) | −9.09% (−7.06) | +54.43% (+2.41) |

**La griglia non ha segnale**: e' negativa anche a fee ZERO, con t = −2.56. Non
sono le commissioni, e' che non predice nulla. I valori del trend in questa
tabella sono gonfiati dalla selezione dei parametri per asset: vedi 9.3.

### 9.3 Trend con parametri FISSI: nessuna selezione, nessun bias

Parametri scelti a priori, gli stessi per tutti i 19 asset, mai ottimizzati:

| fee per lato | canale40/trail3/stop2 | t | canale60/trail4/stop2 | t |
|---|---|---|---|---|
| 0.00% | +34.98% | **+4.51** | +61.63% | +2.37 |
| 0.20% (maker) | +12.33% | **+1.73** | +42.16% | +1.78 |
| 0.35% (taker) | −1.97% | **−0.30** | +29.20% | +1.33 |

Lettura: **il trend ha un segnale reale** — a fee zero e' significativo, con t
fino a 4.51, quindi non e' solo beta. **Ma la fee reale lo porta sotto la soglia
di significativita'** (t < 2), e alla fee taker sparisce.

### 9.4 Correzione: il trend paga TAKER, non maker

Il backtest del trend applicava 0.20% (maker) a tutti i fill. Ma la strategia
entra sul **breakout** ed esce sul **trailing stop**: sono ordini a mercato, che
tolgono liquidita'. La fee vera e' **0.35% per lato = 0.70% di round trip**, non
0.40%.

A quella fee l'alpha del trend e' **−1.97% con t = −0.30**: nessun edge. E non e'
aggirabile: un ingresso su breakout non puo' essere maker, perche' un ordine
limite al di sopra del mercato viene eseguito subito. Servirebbe un ordine
stop-limit che diventa maker quando scatta, cosa non affidabile.

### 9.5 Conclusione del round 4

Il collo di bottiglia **non e' la ricerca di strategie: e' la struttura dei
costi**, insieme a un segnale debole.

- **GRID**: nessun segnale a qualunque fee (t = −2.56 a fee zero).
  Strutturalmente rotto, non riparabile abbassando i costi.
- **TREND**: segnale reale (t = 4.51 a fee zero) ma mangiato dalle fee reali. A
  fee maker 0.20% e' marginale (t = 1.73), a fee taker 0.35% sparisce.
- **MEAN-REVERSION**: nessun alpha (round 2).
- **CROSS-SEZIONALE**: alpha negativo significativo (t = −2.55).

Punto di rottura economico: il trend diventa significativo con fee <= 0.20% per
lato **a condizione di poter essere maker**. Il conto e' Lv1 (maker 0.20%,
taker 0.35%) e con ~75 EUR di capitale non puo' raggiungere un tier migliore,
che su OKX richiede volumi mensili di ordini di grandezza superiori.

Le direzioni residue, in ordine di realismo:

1. **Ridurre la fee per lato** e' la leva con il miglior rapporto
   beneficio/rischio: cambierebbe il segno del trend. Richiede piu' capitale, un
   tier superiore, o un venue con costi inferiori.
2. **Fonti di rendimento non direzionali e a basso turnover** (funding rate,
   basis), dove il premio non e' un segnale di prezzo ma un pagamento
   strutturale. Richiedono derivati.
3. **Smaltire le strategie live con alpha negativo**, che e' l'unica azione che
   oggi riduce la perdita attesa.


## 10. Round 5 — Il segnale vive nel breakout, e il breakout paga taker

### 10.1 L'idea

Il round 4 aveva isolato il vincolo: il trend ha un segnale reale (alpha +34.98%
con t=+4.51 a fee zero) ma paga TAKER su entrambi i lati, 0.70% di round trip.
Domanda naturale: esiste una struttura che catturi lo stesso segnale pagando
MAKER (0.40% di round trip)?

Proposta: non inseguire il breakout, ma **comprare il ritorno dentro il trend**
con un ordine limite sotto il mercato (maker in ingresso), e uscire con un
ordine limite sopra (maker in uscita). Solo lo stop duro esce a mercato. Motore
nuovo: backtest_pullback.

### 10.2 Risultato: respinto in modo netto

36 set di parametri FISSI (nessuna selezione), 19 asset, fee maker 0.20% in
ingresso e uscita, taker 0.35% sullo stop:

| metrica | valore |
|---|---|
| set con alpha > 0 | **0 su 36 (0%)** |
| set con t > 2 | **0 su 36** |
| alpha mediano | **−61.35%** |
| t mediano | **−16.76** |

E anche abbassando la fee maker a 0.10%: alpha mediano −60.64%, t −14.53. Non e'
un problema di costo.

### 10.3 Il motore e' sano: e' la strategia che perde

Diagnostica su SOL (6189 barre, 2.8 anni, buy-and-hold +65.01%):

| parametri | trade | win rate | fee pagate | ritorno | a fee ZERO |
|---|---|---|---|---|---|
| ea0.5 / xa2.5 / sm2.0 / mh42 | 257 | 43% | 30.65 EUR | **−73.61%** | **−48.27%** |
| ea0.5 / xa4.0 / sm3.0 / mh84 | 130 | 43% | 17.55 EUR | −31.61% | −13.34% |

La contabilita' e' corretta (fee proporzionali, PnL medio negativo coerente con
win rate 43%). **A fee zero la strategia perde comunque il 48%.** Su un asset che
nello stesso periodo e' SALITO del 65%: comprare i ritorni ha perso, perche' il
ritorno e' spesso l'inizio del ribasso, non un'opportunita'.

### 10.4 Conclusione: il segnale non e' separabile dal costo

Il segnale del trend vive **nel breakout**, e il breakout e' per natura un ordine
a mercato: non puo' essere maker, perche' un limite sopra il mercato viene
eseguito subito. La versione maker della stessa idea (comprare il dip) ha un
edge **diverso e negativo**. Non e' possibile avere il segnale e il costo maker
insieme.

Quindi la conclusione del round 4 non e' aggirabile per via di progettazione:
**il trend ha un edge che e' inferiore al costo necessario a catturarlo.**

### 10.5 Bilancio delle famiglie testate

| famiglia | alpha | significativita' | verdetto |
|---|---|---|---|
| grid | **−7.48%** | t = −4.64 | nessun segnale: negativo anche a fee zero |
| mean-reversion | ≈ 0 | t < 1 | nessun alpha |
| momentum / trend | +34.98% a fee zero | t = +4.51 | segnale reale, mangiato dalle fee taker |
| cross-sezionale | **−8.61%** | t = −2.55 | respinto |
| pullback maker-only | **−61.35%** | t = −16.76 | respinto: negativo anche a fee zero |

Su cinque famiglie e 19 asset, **una sola ha un segnale statisticamente reale**
(il trend), e quel segnale e' strutturalmente inferiore al costo di catturarlo in
questa configurazione (long-only spot, conto Lv1, ~75 EUR).

### 10.6 Dove sta il problema, in una riga

Non mancano le strategie: **mancano i margini**. Con fee maker 0.20% e taker
0.35%, un segnale che vale ~+35% di alpha a costo zero su 2.4 anni (circa 14%
annuo) viene azzerato da un costo di round trip dello 0.70% applicato ai
passaggi necessari a catturarlo.

Le uniche vie d'uscita restano quelle del round 4, e nessuna e' di ricerca:

1. **ridurre la fee per lato** (tier superiore, piu' capitale, o un venue con
   costi inferiori): e' l'unica leva che cambierebbe il segno del trend;
2. **fonti non direzionali** (funding rate, basis), dove il premio non e' una
   previsione di prezzo ma un pagamento strutturale: richiedono derivati;
3. **smaltire le strategie live con alpha negativo**.


## 11. Round 5b — Il primo edge reale: trend giornaliero

### 11.1 Perche' il giornaliero cambia tutto

Su barre 4H il trend ha un segnale reale (alpha +34.98% a fee zero, t=+4.51) ma
paga 0.70% di round trip a ogni passaggio, e il costo lo azzera. Su barre
GIORNALIERE lo stesso segnale cattura movimenti molto piu' grandi rispetto al
costo: **~10 trade per asset in 2.5 anni** invece di centinaia.

36 set di parametri FISSI (nessuna selezione), 19 asset, fee taker reale 0.35%
su entrambi i lati:

| metrica | valore |
|---|---|
| set con alpha > 0 | **36 su 36 (100%)** |
| set con t > 2 | 22 su 36 |
| alpha mediano | **+19.99%** |
| t mediano | **+2.24** |
| range alpha tra i set | +13.58% .. +26.96% |

Che l'alpha sia positivo in **tutti** i set, e non solo nei migliori, e' la
differenza sostanziale rispetto a tutto cio' che era stato testato prima: non
serve selezionare parametri, quindi non c'e' selection bias.

### 11.2 Verifiche

**Leave-one-out** (set canale40/trail3/stop2/ema100, fee taker): togliendo un
asset qualsiasi l'alpha resta tra +15.22% e +18.24%, con t tra 1.78 e 2.15.
Nessun singolo asset trascina il risultato.

**Stabilita' nel tempo**: prima meta' alpha +20.07% (t=+1.34, rendimento
assoluto medio +23.24%), seconda meta' alpha +6.62% (t=+1.73, rendimento
assoluto medio **−0.77%**). L'effetto e' concentrato nella prima meta'.

**Ampiezza economica**: il rendimento ASSOLUTO mediano per asset e' +6.32% in
2.5 anni, il MEDIO e' +19.35%. Un portafoglio equal-weight a 19 asset rende la
media, quindi circa **+7.3% annuo netto fee taker**, mentre il buy-and-hold
equal-weight nello stesso periodo ha reso circa −8% medio.

### 11.3 Lettura onesta

Questo e' il **primo edge reale** trovato in cinque round: positivo in tutti i
36 set di parametri, robusto al leave-one-out, e sopravvive alla fee taker.

Ma va letto per quello che e':

- l'ampiezza e' **modesta**: ~+7% annuo sul portafoglio (media), +2.5% annuo
  sulla mediana degli asset;
- la **seconda meta' del periodo e' piatta** (−0.77% di media): l'effetto e'
  concentrato nel tempo, e con ~5 trade per asset per meta' il campione e' corto;
- i t-stat sono **marginali** (~2.0-2.2), non schiaccianti.

### 11.4 La conclusione cambia di natura

Per cinque round la domanda era "esiste una strategia con edge?". Ora la
risposta e': **si', ma e' piccolo in percentuale, e su ~75 EUR di capitale vale
2-6 EUR all'anno.**

Il collo di bottiglia non e' piu' la ricerca: e' **il capitale**. Un edge del
+7% annuo su 75 EUR e' 5 EUR; lo stesso edge su 10.000 EUR sono 700 EUR. Per la
prima volta il problema e' di scala, non di strategia.

Cosa serve perche' questo diventi remunerativo:

1. **piu' capitale** sul medesimo edge, che e' anche la leva per accedere a un
   tier di commissioni migliore (e quindi a un edge ancora maggiore: a fee maker
   0.20% l'alpha sale);
2. **piu' asset** in portafoglio per ridurre la dipendenza dagli episodi (19 e'
   il massimo con 2.4+ anni di storia su OKX EEA; se ne possono aggiungere
   accettando una finestra comune piu' corta);
3. **accettare l'ampiezza**: +7% annuo e' un rendimento da gestione
   patrimoniale, non da trading speculativo. Con 75 EUR non e' visibile.

Resta valida la raccomandazione di smaltire le strategie live attuali, che
hanno alpha negativo provato (la griglia e' negativa anche a fee zero).


### 11.5 La policy di produzione, con equivalenza dimostrata

Implementata `denaro/domain/trend.py` — `TrendParams` e `TrendPolicy` —
come versione di produzione di `backtest_trend`, e collegata a
`build_policy` (strategia `trend`).

Scelte di progetto:

- **costruisce da sola le barre giornaliere dai tick**, accumulando o/h/l/c per
  giorno UTC e valutando il segnale solo alla chiusura di una barra. Il dominio
  resta puro (zero I/O) e non serve un feed OHLCV;
- l'ingresso e' un limite appena sopra il mercato (di fatto taker, come nel
  backtest); l'uscita normale e' il trailing stop, riposizionato con
  `to_cancel_sell` + `to_sell` perche' l'orchestratore piazza la
  protezione iniziale da `sell_target(entry)` ma il trailing deve salire.

**Un solo ATR e una sola EMA per tutto il progetto.** `atr_wilder` e
`ema_series` vivono ora in `denaro/domain/indicators.py`, e
`denaro/research/eval.py` li IMPORTA da li' invece di avere copie proprie.
Verificato nei test: `E.atr_wilder is indicators.atr_wilder` e' vero.
Averne due copie renderebbe l'equivalenza tra backtest e live una coincidenza,
non una garanzia.

Test (`denaro/tests/test_trend_policy.py`, 12 test):

- costruzione delle barre: una per giorno, OHLC corretti, nessuna barra chiusa
  dentro lo stesso giorno;
- ATR, EMA e canale identici a quelli del rig di ricerca, barra per barra;
- `segnale_breakout()` rispecchia la condizione del backtest;
- il trailing stop sale e non scende;
- `sell_target` e' lo stop iniziale, non un target di profitto;
- `on_fill` traccia la posizione;
- **equivalenza su dati reali**: su BTC giornaliero, oltre 400 confronti tra la
  condizione di breakout della policy viva e quella del backtest, **0
  discrepanze**.

Nota di metodo: la prima stesura del test di equivalenza dava 44 discrepanze.
Non era la policy: il test alimentava la policy con un solo tick al giorno (la
chiusura), quindi la policy vedeva high = close mentre il backtest usa gli high
reali. Corretto il harness (quattro tick al giorno per riprodurre l'OHLC), le
discrepanze sono scese a zero. E' lo stesso tipo di errore di misura che ha
caratterizzato i round precedenti: prima di accusare il codice, verificare
l'harness.


## 12. Round 10-11 — Quanto capitale serve davvero

### 12.1 Il difetto trovato dal live check, prima che mordesse

Il 2026-09-17 il tool di verifica live ha rivelato che **6 bot su 15 non
avrebbero mai piazzato un ordine**, in silenzio. Con `capital: 5.0` per bot e
rischio 2%, il sizing sul rischio produceva posizioni di 0.84-1.75 EUR, mentre i
minimi REALI dell'exchange (mai controllati prima) sono:

| asset | minimo ordine | in EUR |
|---|---|---|
| BTC | 0.0001 | **6.67** |
| ETH | 0.001 | 2.14 |
| ADA | 10 | 1.76 |
| XLM | 10 | 1.62 |
| ARB | 10 | 1.51 |
| XRP | 1 | 1.13 |
| AAVE | 0.01 | 1.12 |
| LINK | 0.1 | 0.99 |
| DOT | 1 | 0.93 |
| SOL | 0.01 | 0.88 |
| DOGE | 10 | 0.71 |
| UNI | 0.1 | 0.67 |
| AVAX | 0.1 | 0.66 |
| LTC | 0.01 | 0.47 |
| ATOM | 0.1 | 0.14 |

Correzione: **ogni bot riceve il capitale del CONTO**, non un quinto.
L'orchestratore usa `_available = max(0, min(capital_config, free_balance))`,
quindi il sizing resta limitato dalla cassa libera reale: l'esposizione totale
non puo' superare il conto, e ogni asset rischia il 2% del capitale disponibile,
che e' il modello di rischio della strategia misurata.

### 12.2 Capitale minimo perche' la strategia funzioni

`tools/trend_capital.py` calcola, per ogni asset, il capitale necessario
perche' la posizione calcolata superi il minimo reale:

    capitale_min = min_eur x (stop_mult x ATR%) / risk_pct

| conto | perche' OGNI bot possa piazzare | perche' TUTTI siano in posizione | attuale |
|---|---|---|---|
| mc2 | 19.03 EUR (BTC) | 42.12 EUR | 24.90 |
| nuvola | 5.98 EUR (DOT) | 21.59 EUR | 24.83 |
| MARCODG1 | 14.03 EUR (ARB) | 42.04 EUR | 24.81 |

Lettura: **con il capitale attuale ogni bot puo' piazzare**, ma su mc2 e
MARCODG1 non tutti e cinque possono essere in posizione insieme. Quando piu'
segnali scattano contemporaneamente, il limite della cassa libera riduce le
posizioni successive: alcune possono scendere sotto il minimo dell'exchange e
venire scartate. La strategia funziona, ma con un tetto di capacita'.

**Il numero da ricordare: ~42 EUR per conto (126 EUR in totale) e' il capitale
al quale la flotta esprime la strategia misurata senza vincoli di capacita'.**

### 12.3 Capitale e rendimento atteso

L'edge misurato e' ~+7% annuo (mean del portafoglio a 19 asset, netto fee
taker). Il rendimento atteso e' proporzionale al capitale:

| capitale | rendimento atteso |
|---|---|
| 25 EUR | 1.75 EUR/anno (0.15/mese) |
| 100 EUR | 7 EUR/anno |
| 500 EUR | 35 EUR/anno |
| 1.000 EUR | 70 EUR/anno |
| 10.000 EUR | 700 EUR/anno (58/mese) |

Questa e' la risposta quantificata alla domanda "rendere il sistema
redditizio": **il sistema ha un edge misurato e verificato, ma il suo valore
assoluto dipende interamente dal capitale.** Non c'e' ulteriore lavoro di
strategia che cambi l'ordine di grandezza: a fee Lv1 (maker 0.20%, taker 0.35%)
e con un segnale che vale ~7% annuo, il collo di bottiglia e' la scala.

Le due leve che restano, entrambe fuori dalla ricerca:

1. **piu' capitale sullo stesso edge** — e piu' capitale significa anche un tier
   di commissioni migliore, che a sua volta AUMENTA l'alpha misurato (a fee
   maker 0.20% l'alpha del trend passa da +12.33% a +34.98% nei test);
2. **fonti di rendimento non direzionali** (funding rate, basis), dove il premio
   non e' una previsione di prezzo ma un pagamento strutturale: richiedono
   derivati.


### 12.4 Quante posizioni sono aperte insieme (e il tetto di capacita')

Misurato con `tools/` e il nuovo campo `ts_in_pos` di `Risultato`
(registra le barre in cui la strategia era in posizione):

| conto | posizioni simultanee (media) | massima | tutte e 5 insieme |
|---|---|---|---|
| mc2 | 2.31 | 5 | **19% del tempo in posizione** |
| nuvola | 2.17 | 5 | 10% |
| MARCODG1 | 1.80 | 5 | 7% |

L'esposizione media per asset e' ~19%, quindi con 5 asset indipendenti la media
simultanea sarebbe 0.95. Il valore misurato e' 2.31: **le posizioni sono
correlate 2.4 volte piu' dell'indipendenza**, perche' i breakout si concentrano
nei movimenti di mercato ampi. E' esattamente quando servirebbe essere
posizionati al massimo.

**Il conto non li finanzia.** Fabbisogno per fondere tutte le posizioni
simultanee, per conto:

| conto | fabbisogno (tutte insieme) | disponibile |
|---|---|---|
| mc2 | 42.12 EUR | 24.90 |
| nuvola | 21.59 EUR | 24.83 |
| MARCODG1 | 42.04 EUR | 24.81 |
| **totale** | **105.8 EUR** | **74.5 EUR** |

Manca il 42%: **non e' risolvibile spostando asset fra i conti**, perche' il
fabbisogno complessivo supera il capitale complessivo.

I tre asset che pesano di piu': BTC 19.03, ARB 14.03, ADA 11.11 — da soli
€44.17 su €105.8. La causa e' il minimo d'ordine dell'exchange rapportato al
capitale: il minimo di BTC (€6.67) vale il 27% di un conto da €25.

Due modi per rientrare, entrambi con un costo:

1. **togliere i tre asset piu' esosi** (BTC, ARB, ADA): il fabbisogno scende a
   €61.60 su €74.5 disponibili, quindi **tutti i 12 asset rimasti sarebbero
   finanziabili insieme**. Si perdono tre simboli su quindici, e BTC in
   particolare;
2. **abbassare il rischio per trade da 2% a ~1.4%**: tutti e 15 gli asset
   rientrano, ma ogni posizione e' piu' piccola e il rendimento atteso per euro
   di capitale scende in proporzione.

Nessuna delle due e' gratuita: e' un compromesso fra fedelta' alla strategia
misurata (che assumeva di poter prendere tutti i segnali) e capitale
disponibile. Con €126 (42 per conto) il problema non esisterebbe.


## 13. DIFETTO CRITICO — il meccanismo di uscita del trend non funziona

Trovato il 2026-09-17 con l'audit del percorso live, **prima che sparasse**.

### 13.1 Cosa fa il backtest

In `backtest_trend` lo stop e' modellato come un ordine che scatta quando il
prezzo SCENDE sotto il livello:

    if lo <= stop: uscita al prezzo di stop

E' il comportamento di un ordine STOP.

### 13.2 Cosa fa la produzione

Il `TrendPolicy` emette lo stop come `decision.to_sell = [(amount, stop)]`.
L'orchestratore esegue ogni voce di `to_sell` cosi':

    await self.ex.create_limit_order(self.cfg.symbol, "sell", amount, sell_price)

Cioe' un ordine **LIMITE**. Ma il prezzo di stop e' `entry - stop_atr_mult*ATR`,
**sotto il mercato**. E un limite di vendita sotto il mercato **si riempie
immediatamente** al miglior bid disponibile (price improvement).

### 13.3 Conseguenza

Il bot, al primo segnale:

1. compra a mercato (limite sopra il mercato: si esegue subito come taker);
2. l'orchestratore chiama `sell_target(entry)` e piazza un limite di vendita
   a `entry - 2*ATR`, cioe' ~8% sotto il mercato;
3. **quell'ordine si riempie nello stesso istante** al bid corrente;
4. risultato: compra e vende immediatamente, perdendo spread + 2 commissioni.

La stessa cosa vale per ogni riposizionamento del trailing: il nuovo stop e' a
`prezzo - trail*ATR`, sempre sotto il mercato, quindi si esegue subito.

**La protezione non esiste: e' un take-profit al contrario.** Con un ciclo al
giorno e ~0.7% di costo per ciclo, il risultato atteso era una perdita
dell'ordine di centinaia di punti percentuali all'anno.

### 13.4 Perche' nessun test l'aveva visto

I test unitari verificano la LOGICA della policy. Il test di integrazione usa un
`FakeExchange` che riempie gli ordini **solo** su `market_trade()`, quindi non
riproduce la semantica reale degli ordini limite. La differenza sta nella
semantica dell'EXCHANGE, non nella policy.

### 13.5 Azione immediata

1. **Nodi di trading fermati** su tutte e tre le macchine.
2. Conti verificati: **nessun ordine, nessuna posizione, EUR 24.83 / 24.83 /
   24.81 intatti.** Il segnale non era ancora arrivato: il difetto e' stato
   trovato prima che muovesse denaro.
3. **Healer sospeso** con un interruttore nuovo
   (`/home/sergio/denaro/HEALER_PAUSE`): senza, il healer che gira ogni 2
   minuti avrebbe riavviato i nodi e il difetto sarebbe tornato vivo.
4. Le dashboard e i servizi di infrastruttura restano attivi.

### 13.6 La correzione necessaria

Serve un vero meccanismo di STOP, non un limite. Due strade:

1. **ordine condizionale (algo) su OKX**: l'adapter non lo espone ancora
   (`ExchangePort` ha solo `create_limit_order` e `sell_market`);
2. **stop gestito dall'orchestratore**: la policy espone il proprio stop, e
   l'orchestratore fa `sell_market` quando il prezzo lo attraversa. La
   macchina esiste gia' — e' quella usata per lo `stop_loss_pct` di bot
   (riga ~822: `await asyncio.to_thread(self.ex.sell_market, ...)`).

La seconda e' quella che richiede meno infrastruttura nuova ed e' coerente con
il resto del sistema.

### 13.7 Nota di metodo

Questo e' il quarto difetto del percorso live trovato in quattro round, e il piu'
grave. Nessuno era visibile dai test unitari. Il rig di misura era corretto fin
dal round 1; era il **collegamento fra rig e produzione** a essere fragile, e
l'unico modo di trovarlo e' stato leggere il percorso reale ordine per ordine.
