# 33 — Piramide sul trend: misurata e scartata (round 33, 2026-09-17)

## 33.1 L'idea e la validazione

Aggiungere una **seconda unita'** quando la posizione e' gia' in profitto
(prezzo >= entry + p*ATR) e' la costruzione classica del trend following: si
lascia correre il vincitore invece di accontentarsi del primo breakout. Ha anche
un effetto pratico sul conto: usa la cassa libera nei trend forti, che oggi resta
ferma.

Il simulatore della piramide e' **generato** dal `simula` validato di
`trend_capacita.py` (`tools/trend_sim_piramide.py`, non modificabile a mano) e
con la piramide spenta riproduce `backtest_trend` **al bit** su tutti e 17 gli
asset: i numeri sotto sono confrontabili con quelli di produzione.

## 33.2 I numeri

Portafoglio a capitale condiviso, 3 conti reali, fee taker 0.35%, trail 2.5:

| variante | storia | 540b | 365b | 270b | 180b | maxDD storia | Sharpe storia |
|---|---|---|---|---|---|---|---|
| **base (1 unita')** | +79.60% | **+12.19%** | +8.37% | +5.49% | +8.10% | **12.46%** | **1.24** |
| piramide 0.5 ATR | +77.70% | +11.71% | +10.65% | +6.64% | +9.94% | 17.46% | 1.12 |
| piramide 1.0 ATR | **+82.12%** | +10.18% | +9.40% | +6.39% | +9.49% | 17.24% | 1.15 |
| piramide 1.5 ATR | +78.86% | +9.34% | +9.58% | +6.84% | +9.18% | 17.94% | 1.12 |
| piramide 1.0 ATR x3 | +75.53% | +6.29% | +7.79% | +5.23% | +9.14% | 20.06% | 1.05 |

## 33.3 Perche' si scarta

- **Lo Sharpe peggiora in ogni configurazione** (1.24 -> 1.05-1.15): piu'
  rendimento in euro, ma per unita' di rischio il sistema peggiora.
- Il **drawdown massimo sale del 38-61%** (12.46% -> 17.24-20.06%) per guadagnare
  1-1.5 punti nelle finestre recenti. E' il cambio peggiore possibile: si paga
  rischio certo per rendimento incerto.
- Sul 540b la piramide **perde** (+10.18% contro +12.19%) — cioe' non e' un
  miglioramento uniforme, e la regola della sessione richiede che lo sia.

Verdetto: **scartata**. Il trend deployato resta a una unita' e a trail 2.5.

## 33.4 Il programma di ricerca e' convergente: cosa e' stato provato

Con questo round le assi di variazione disponibili sullo spot con questi asset
sono state percorse tutte. Elenco delle ipotesi provate e dell'esito, per non
ripeterle:

| asse | prova | esito |
|---|---|---|
| ingresso | canale 20 (piu' aggressivo) | scartato (perde in tutte le finestre recenti) |
| ingresso | multi-orizzonte (20/40/80) | scartato |
| ingresso | pullback con ordini limite | piatto (3/5) |
| uscita | sweep trailing 2.0-3.25 | **adottato 2.5** (regione 2.25-2.75 robusta) |
| uscita | stop piu' larghi (gap) | scartato |
| rischio | tetto per posizione (max_exposure) | scartato |
| rischio | rischio per trade 1-4% | 2% resta l'ottimo in euro e Sharpe |
| orizzonte | barre 4H | scartato (le fee mangiano il segnale) |
| regime | filtri EMA/momentum su BTC | scartato |
| universo | allargare a 26/35/44/52 | scartato (peggiora monotonicamente) |
| universo | potare per rendimento recente | scartato (fallisce fuori campione) |
| famiglia | momentum cross-sezionale | scartato |
| posizione | piramide su vincitori | scartata (questo round) |
| costi | maker vs taker vs derivati | misurato: +0.9/+1.8 EUR/anno |

Nessuna di queste ha superato la regola "positivo in ogni finestra, migliore del
deployato". Questa non e' una sconfitta del metodo: e' il metodo che ha impedito
di mettere denaro su tredici idee che sembravano buone.

**Il vincolo del progetto non e' piu' la strategia: e' il capitale** (109.58 EUR,
~+5-8%/anno sul regime recente) e, in seconda battuta, i costi (derivati: +1.8
EUR/anno a questo capitale, proporzionali al capitale se questo cresce).
