# 54 — Dimensionamento per 1000 EUR: la quota per bot, il rischio aggregato, la soglia minima

Data: 2026-09-23. Prosegue `docs/53` (§3.1 e §2.3). Obiettivo dato dal proprietario:
**preparare il sistema a operare con 1000 EUR di capitale reale.**

Due strumenti nuovi, entrambi di sola lettura e rieseguibili:

- `tools/audit_capitale_config.py` — verifica se il `capital:` di ogni bot è la **quota** del
  conto o l'**intero** conto.
- `tools/misura_stop_atr.py` — misura la distanza di stop reale (2 ATR giornaliero) con la
  stessa `atr_wilder` che usa la produzione, e ne deriva la size della posizione.

---

## 54.1 Il difetto: ogni bot dichiara l'intero conto, non la sua quota

`tools/audit_capitale_config.py` legge tutti i `config/node_*.yaml` (29 bot su 10 file). Sui
quattro config dove tutti i bot portano lo stesso valore — cioè dove il totale del conto è
inequivocabile — il risultato è:

| config | bot | capitale dichiarato | conto reale | quota corretta | fattore |
|---|---|---|---|---|---|
| `node_mc2.yaml` | 7 | 294,84 | 42,12 | **6,02** | 7,0× |
| `node_nuvola_trade.yaml` | 6 | 148,98 | 24,83 | **4,14** | 6,0× |
| `node_marcodg1_xrp.yaml` | 4 | 168,16 | 42,04 | **10,51** | 4,0× |
| `node_trend.yaml` | 4 | 600,00 | 150,00 | **37,50** | 4,0× |
| **totale** | **21** | **1.211,98** | **258,99** | — | — |

Il totale dei 10 config è 1.888,18 € dichiarati contro 672,49 € di conti stimati (2,8×).

**Perché conta, e non è cosmetica.** `capital` alimenta il sizing: con `risk_pct = 0.02`, ogni
bot rischia il 2% del valore che crede di avere. Se ogni bot crede di avere l'intero conto, la
somma dei rischi non è il 2%: è `N × 2%`.

| macchina | bot | rischio aggregato dichiarato | rischio corretto |
|---|---|---|---|
| mc2 | 7 | **14%** del conto | 2% |
| nuvola | 6 | **12%** | 2% |
| MARCODG1 | 4 | **8%** | 2% |
| node_trend | 4 | **8%** | 2% |

Questo si somma al difetto già noto di `docs/23` (config non allineati dopo lo spostamento del
capitale, `docs/49`) e lo peggiora: **non è solo che i config sono vecchi, è che la quota per
bot non è mai stata divisa.**

## 54.2 La distanza di stop, misurata

La size della posizione è `rischio_eur / distanza_stop`, e lo stop è 2 ATR: senza misurare
l'ATR, ogni cifra è un'ipotesi. `tools/misura_stop_atr.py` aggrega le candle locali a 1D e usa
`denaro.domain.indicators.atr_wilder` (la stessa funzione di ricerca e produzione, così non
esistono due ATR):

| simbolo | giorni | ATR% mediano | stop (2 ATR) | size a 58,82 €/bot | × minimo |
|---|---|---|---|---|---|
| SOL/EUR | 91 | 7,34% | **14,69%** | 8,01 € | 8,0× |
| ADA/EUR | 91 | 5,84% | 11,68% | 10,08 € | 10,1× |
| XRP/EUR | 91 | 3,88% | 7,76% | 15,15 € | 15,2× |
| ETH/EUR | 91 | 3,70% | 7,40% | 15,89 € | 15,9× |
| DOGE/EUR | 61 | 3,48% | 6,96% | 16,91 € | 16,9× |

**Limite dichiarato**: campione locale a 5m (~90 giorni, 5 simboli) aggregato a 1D. La strategia
è misurata su 1D e 2,5 anni su 19 asset. Serve per la **scala** delle size, non è un backtest.
Per gli altri 12 simboli servono le candle 1D da OKX: è una lettura, non l'ho fatta.

## 54.3 Il dimensionamento per 1000 EUR

Con la quota **uguale per bot** (la ricerca misura un edge di *portafoglio* equipesato, quindi
peso uguale per asset è la scelta fedele al metodo):

| voce | valore |
|---|---|
| capitale | 1.000 € |
| bot | 17 (uno per asset: 7 mc2, 6 nuvola, 4 MARCODG1) |
| **quota per bot** | **58,82 €** |
| rischio per trade | 2% di 58,82 = **1,18 €** |
| size della posizione | **8–17 €** secondo l'asset (mediana 15,15 €) |
| margine sul `min_notional` (1,0 €) | **8–17×** |
| se tutti e 17 fossero in posizione | 258 € impegnati (**26%** del capitale) |
| rischio aggregato massimo | 20,00 € = **2,0% del capitale** |

Per macchina: mc2 **411,76 €** (7 bot), nuvola **352,94 €** (6), MARCODG1 **235,29 €** (4).
Questo *non* è l'attuale ripartizione (39% / 23% / 39%): il capitale è sul master e va
**distribuito ai sub-account**, che è un'azione sulla flotta da approvare.

## 54.4 La soglia minima di capitale — perché 110 € non bastavano

Dalla formula `size = (cap_bot × 2%) / stop`, con `min_notional` = 1,0 €:

| capitale | per bot | size su SOL (stop 14,69%) | esito |
|---|---|---|---|
| **110 €** (oggi) | 6,47 € | **0,88 €** | **sotto il minimo: l'ordine verrebbe rifiutato** |
| 125 € | 7,35 € | 1,00 € | pari al minimo, nessun margine |
| 375 € | 22,06 € | 3,00 € | 3× il minimo, margine prudente |
| **1.000 €** | **58,82 €** | **8,01 €** | **8× il minimo** |

Quindi: **soglia dura ≈ 125 €**, **raccomandato ≥ 375 €**, e 1.000 € dà 8–17× il minimo su
tutti gli asset. Questo è il senso in cui i 1.000 € contano: **non creano edge, rendono la
flotta eseguibile.** La fee è una percentuale (0,778% per giro): è *invariante alla scala*,
quindi nessuna dimensione di capitale migliora il rapporto costo/rendimento — quello lo
cambiano solo il tier fee e lo short (`docs/53` §2.1-2.2).

## 54.5 Precondizioni prima che questa configurazione vada live

1. **R1/R2/R3 chiusi con prove** (`docs/53` §0.6, `denaro/tests/test_rischi_capitale.py`).
   R1 è *specificamente* bloccante per questo layout: mettere più bot sullo stesso sub-account
   è esattamente la configurazione in cui lo stop di un bot liquida tutto l'asset del conto.
2. **Quota per bot applicata** in tutti i config (la patch la applica chi possiede `config/`:
   il tool stampa i valori, non scrive).
3. **Capitale distribuito** dal master ai sub-account secondo la ripartizione di §54.3.
4. **Cap di esposizione globale**: oggi non esiste. Con 17 bot il massimo teorico è 258 €
   (26%), ma nessun componente lo verifica: serve un limite esplicito sul totale impegnato.
5. **`min_notional` confermato dalla sede** per ogni pair: nel config è 1,0 €, non è misurato
   dall'exchange.

## 54.6 Domande aperte

- La flotta copre **17** asset, la ricerca misurava su **19**: quali due mancano, e perché.
- La ripartizione per macchina cambia (§54.3): va confermata prima di spostare capitale.
- Il venue (`docs/53` §2.1): con fee a 0,35%/lato e senza short, questa configurazione è
  dimensionata bene ed economicamente in perdita. Il dimensionamento non risolve quel punto.
