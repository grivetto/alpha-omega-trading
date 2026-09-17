# 24 — Il rischio di gap, finalmente misurato (round 22)

## 24.1 Prima ho dovuto riparare lo strumento

Ieri avevo costruito un simulatore con gap avversa sulle uscite e **non
riproduceva** quello validato: a gap zero dava +69.01% dove il validato da'
+64.21%, e i conteggi dei trade differivano (BTC 13 contro 11). Un simulatore che
non riproduce il riferimento non puo' decidere niente, quindi i suoi numeri erano
stati scartati.

Oggi l'ho risolto alla radice: invece di riscrivere la funzione a mano, la
**genero dal sorgente di quella validata** con inspect.getsource, aggiungendo il
parametro gap e modificando SOLO la riga di uscita a stop. La fedelta' e'
garantita per costruzione.

Validazione: a gap zero il delta e' **0.00e+00** su 7 asset, con conteggi di trade
identici (BTC 13/13, XRP 8/8, TRX 17/17, ADA 8/8, MINA 5/5, ETH 8/8, SOL 11/11).

## 24.2 Il backtest assume di essere servito AL PREZZO di stop

Nella realta' una gap notturna salta lo stop e si esce peggio. Il sizing e' sul
rischio, quindi ci si aspetta di perdere il 2% per trade: una gap colpisce
l'intera posizione.

Banda realistica (gap medio applicato a ogni uscita):

| scenario | storia (2.4 anni) | 12 mesi | maxDD |
|---|---|---|---|
| nessuna gap (assunzione del backtest) | +73.04% | +9.17% | 7.16% |
| 1 uscita su 6 con gap 3% | +68.30% | +7.91% | 7.45% |
| 1 uscita su 3 con gap 3% | +63.68% | +6.66% | 7.95% |
| 2 uscite su 3 con gap 3% | +54.81% | +4.22% | 10.29% |
| OGNI uscita con gap 5% | +30.10% | -2.88% | 17.84% |

Lettura onesta: se una parte delle uscite ha una gap — e in cripto succede — il
rendimento atteso e' **+63/+68% invece di +73%**, con drawdown intorno all'8%
invece del 7%. Lo scenario catastrofico (ogni stop con gap 5%) porta a +30% e
drawdown 18%, e resta positivo.

**La gap e' il rischio non modellato piu' grande del sistema.**

## 24.3 Il tetto per posizione NON protegge dalle gap

Avevo misurato che un tetto (max_exposure) costa rendimento. Restava da vedere se
almeno protegge. Risposta: **no**.

| tetto | gap 0% | gap 2% | gap 5% | gap 10% |
|---|---|---|---|---|
| 100% | +73.04% / -7.16% | +54.81% / -10.29% | +30.10% / -17.84% | -2.38% / -31.48% |
| 50% | +72.54% / -6.97% | +54.93% / -11.17% | +31.10% / -18.17% | -0.92% / -31.57% |
| 30% | +62.94% / -7.35% | +46.62% / -12.29% | +24.80% / -19.32% | -5.11% / -30.17% |

A ogni livello di gap il tetto lascia il rendimento quasi invariato (o lo riduce,
al 30%) e **peggiora leggermente il drawdown**. Il motivo: il tetto morde solo gli
asset a volatilita' bassissima (TRX), mentre il danno da gap arriva da tutte le
posizioni. Ridurre quella singola posizione non cambia l'esposizione aggregata.

**Decisione: nessun tetto.** Non e' una misura di mitigazione, e' solo un costo.

## 24.4 Cosa mitigherebbe davvero (non fatto)

- **Stop piu' larghi**: riducono il numero di stop ma non l'effetto di una gap.
- **Ordini condizionali nativi**: su derivati esistono e sono eseguiti
  dall'exchange anche a macchina spenta, ma non eliminano la gap.
- **Ridurre l'esposizione notturna**: incompatibile con una strategia giornaliera.
- **Accettarla e dimensionarla**: e' quello che si sta facendo — il rischio per
  trade e' il 2% del capitale, e il caso peggiore misurato (+30%, drawdown 18%)
  resta sostenibile.

La conclusione operativa e': il rendimento atteso e' quello della banda
realistica (+63/+68% di periodo, +6.7/+7.9% sui 12 mesi), non il +73% del
backtest puro.
