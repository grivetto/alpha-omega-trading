# 30 — Allargare l'universo peggiora, potarlo pure (round 30, 2026-09-17)

## 30.1 L'ipotesi da verificare

L'edge del trend e' **episodico**: il rendimento si concentra in pochi blocchi
(docs/18). Con 17 asset il campione di trend e' la fortuna di un trimestre; la
cura teorica sono **piu' scommesse indipendenti** (`tools/fetch_universe.py`).
I dati per farlo c'erano gia': `backtest_data/` contiene **52 asset EUR** con
almeno 750 barre (47 con almeno 900), 865 barre comuni.

Due domande, due protocolli:

1. **Piu' ampio e' meglio?** Insiemi definiti dalla **liquidita'** a 24h (criterio
   esogeno, nessuna scelta sui risultati): top 17/26/35/44/52 contro la flotta
   attuale. Capitali veri per conto (42.12 / 24.83 / 42.04), asset distribuiti a
   rotazione in ordine di liquidita', capitale CONDIVISO dentro il conto.
2. **Piu' stretto e' meglio?** La tabella per-asset mostra cinque asset della
   flotta (SUI, DOT, ADA, AVAX, CRV) negativi in **tutte** le finestre recenti.
   Toglierli sembra ovvio: e' il modo classico di overfittare. Protocollo
   out-of-sample: si sceglie sul **60% iniziale**, si giudica sul **40% finale**.

## 30.2 Piu' ampio e' peggio, monotonicamente

Rendimento del portafoglio (media dei 3 conti normalizzati), fee 0.35%/lato,
rischio 2%, trailing 2.5:

| universo | storia | 540b | 365b | 270b | 180b | Sharpe storia | maxDD storia |
|---|---|---|---|---|---|---|---|
| **flotta (17)** | **+79.60%** | **+12.19%** | **+8.37%** | **+5.49%** | **+8.10%** | **1.24** | 12.46% |
| top 17 | +53.91% | +8.07% | +4.16% | +2.56% | +3.59% | 1.03 | 14.16% |
| top 26 | +57.08% | +6.03% | +0.09% | +2.72% | +3.94% | 1.00 | 19.01% |
| top 35 | +49.54% | +2.12% | **-2.37%** | +1.93% | +3.14% | 0.89 | 22.86% |
| top 44 | +35.43% | **-5.36%** | **-8.48%** | -2.37% | -0.99% | 0.69 | 29.52% |
| top 52 | +30.37% | **-9.16%** | **-10.57%** | -3.30% | -1.20% | 0.61 | 32.97% |

Il rendimento **cala** e il drawdown **cresce** a ogni allargamento, in tutte le
finestre; da 44 asset in su il portafoglio diventa **negativo** su 4 finestre su
5. La ragione sta nella tabella per-asset: dei 35 asset fuori flotta, la
maggioranza e' negativa in **tutte** le finestre (FET -14.8%, INJ -13.2%, SHIB
-9.8%, FLR, LDO, APE, AXS, IMX, OP, ATOM, ICP...). Piu' asset non sono piu'
scommesse indipendenti: sono lo stesso mercato con piu' rumore e piu' costi.
**Nessun allargamento.**

La flotta attuale **batte anche il top 17 per liquidita'**: la selezione fatta
nei round precedenti (potatura e aggiunta di MINA/TRX/CRV) ha valore reale.

## 30.3 Potare per rendimento recente NON regge fuori campione

In campione (primo 60% della storia) 16 asset su 17 sono positivi: l'unico
negativo e' **MINA** (-0.8%).

Fuori campione (ultimo 40%):

| insieme | rend. | Sharpe | trade |
|---|---|---|---|
| flotta intera (17) | **+7.90%** | 0.79 | 33 |
| solo "tenuti" (16, senza MINA) | +5.12% | 0.54 | 32 |
| **solo lo scartato (MINA)** | **+24.29%** | **1.79** | 1 |

La potatura ha buttato via **il miglior asset fuori campione**. Il criterio "tieni
chi ha reso di piu' nel periodo precedente" non ha validita' predittiva su questo
orizzonte — l'alpha e' episodico e si sposta. **Nessuna potatura basata sul
rendimento recente.**

(Onesta': il +24.29% di MINA fuori campione e' **un** trade. Non e' una prova che
MINA sia forte: e' la prova che il criterio di selezione non sa distinguere.)

## 30.4 Cosa resta vero

Sull'asse universo la flotta di 17 asset con i parametri deployati e' gia' al
punto misurato: non si allarga (peggiora) e non si pota (peggiora fuori
campione). Con **zero segnali rifiutati** in ogni configurazione, il vincolo non
e' il numero di asset ma il **capitale**: 109.58 EUR rendono quello che rendono
(~+5-8%/anno sul regime recente), e la leva per guadagnare di piu' e' aggiungere
capitale o abbassare i costi (derivati), non cambiare l'universo.

Due ipotesi chiuse con dati, non con opinioni: e' esattamente il mandato
"deploy solo di edge misurato e robusto".

## 30.5 Strumenti aggiunti

- `tools/trend_universo_largo.py`: confronto flotta vs insiemi per liquidita',
  su storia e 4 finestre, capitale condiviso per conto.
- `tools/trend_potatura_oos.py`: protocollo di selezione in campione /
  validazione fuori campione, per non ripetere l'errore della potatura.
