# 22 — Rischio e parametri con il capitale vero (round 18)

## 22.1 Il rischio: 2% resta l'ottimo, e il vincolo non morde piu'

Con il capitale reale (mc2 42.12, nuvola 24.83, marcodg1 42.04) e 7/6/6 bot:

| rischio | rend. EUR | CAGR | maxDD | Sharpe | rifiutati |
|---|---|---|---|---|---|
| 1.0% | +50.14 | 16.70% | 9.98% | **1.16** | 0 |
| 1.5% | +60.82 | 19.69% | 12.85% | 1.11 | 0 |
| **2.0% (deployato)** | +65.59 | 20.86% | 15.16% | 1.06 | 0 |
| 2.5% | **+66.46** | 20.95% | 17.11% | 1.00 | 0 |
| 3.0% | +64.99 | 20.35% | 18.89% | 0.94 | 0 |
| 4.0% | +55.36 | 17.34% | 21.72% | 0.80 | 0 |

Il massimo in euro e' a 2.5%, ma supera il 2% di **0.87 EUR su 2.4 anni** con uno
Sharpe peggiore (1.00 contro 1.06) e piu' drawdown. Il 2% deployato e' a 1.3% dal
massimo: **nessun cambio**.

Differenza rispetto al round 15: allora a rischio 6% c'erano decine di segnali
rifiutati. Ora **zero rifiuti fino al 4%**: il capitale e' salito a 109.6 EUR e il
vincolo di cassa non morde piu'.

## 22.2 I parametri: un falso miglioramento, scartato

Griglia di 81 set sui 19 asset (canale 20/40/60 x trail 2.5/3/4 x stop
1.5/2/2.5 x media 0/100/200). Il migliore sembrava il set aggressivo
**canale 20, trail 2.5, stop 2.0**:

    storia intera   +48.68%  ->  +67.47%   maxDD 15.16% -> 10.20%   Sharpe 1.06 -> 1.41

Sembrava un salto. **Tre prove indipendenti l'hanno smontato:**

- per-asset: vince su 15/19 (sembra solido);
- per-finestra: **perde in tutte le finestre recenti** — 18 mesi +4.40% contro
  +6.34%, 12 mesi +1.93% contro +5.13%, 9 mesi **-2.90%** contro +0.24%, 6 mesi
  +2.51% contro +3.15%;
- per-blocco: perde in 3 blocchi su 4.

Il vantaggio viene quasi tutto dal rally di fine 2024: il canale a 20 barre entra
prima e cattura meglio i trend forti, e paga piu' falsi breakout nei mercati
normali. **Scartato.** E' il terzo set "migliore" che non regge la prova di
robustezza in questa sessione (dopo il set B del round 15 e il 4H del round 17).

## 22.3 Il miglioramento che regge: trailing da 3.0 a 2.5

Tenendo fisso il resto (canale 40, stop 2.0), il solo trailing:

| trail | storia | 540b | 365b | 270b | 180b | media recenti |
|---|---|---|---|---|---|---|
| 2.00 | 44.80% | 8.93% | 3.15% | 0.94% | 3.28% | 3.32% |
| 2.25 | **57.01%** | 10.16% | 4.08% | 1.91% | 4.08% | 4.35% |
| **2.50** | 55.62% | 8.97% | 4.95% | 1.18% | 4.06% | **4.38%** |
| 2.75 | 52.60% | 6.17% | 4.01% | 1.43% | 3.80% | 3.48% |
| 3.00 | 48.68% | 6.34% | 5.13% | 0.24% | 3.15% | 3.67% |
| 3.25 | 48.28% | 4.05% | 4.11% | -0.81% | 2.75% | 2.62% |

- **vince su 14 asset su 19**;
- la regione **2.25-2.75 batte uniformemente 3.0**: non un punto isolato;
- storia +6.94 punti, media delle finestre recenti +0.71.

Si sceglie il **centro della regione (2.5)**, non il massimo (2.25): il centro di
una regione robusta e' la scelta che non dipende dal rumore. Deployato su tutti e
19 i bot, piu' il default della dataclass.

## 22.4 Cosa aspettarsi adesso (onesta')

| finestra | rend. | maxDD | Sharpe |
|---|---|---|---|
| tutta la storia (2.4 anni) | +48.68% | 15.16% | 1.06 |
| ~18 mesi | +6.34% | 15.93% | 0.42 |
| ~12 mesi | +5.13% | 6.29% | 0.61 |
| ~9 mesi | +0.24% | 8.56% | 0.11 |
| ~6 mesi | +3.15% | 6.36% | 0.81 |

Il +48.68% e' storia passata e contiene il rally 2024. Sul regime recente la
strategia rende **+5%/anno circa**, ed e' **positiva in ogni finestra** — cosa che
la versione a 15 asset non faceva. Il backtest dice ~+20%/anno, il presente dice
~+5%: la verita' forward sta probabilmente in mezzo, e dipende da quanto trend
offrono i mercati.

Su 109.58 EUR: ~5.5 EUR/anno nel regime recente, ~22 EUR/anno se tornasse il
regime del backtest.
