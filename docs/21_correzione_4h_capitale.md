# 21 — Correzione: il 4H sotto il vincolo di cassa REALE

Round 17. Il round 16 aveva annunciato che il trend su barre 4H con le fee dei
derivati triplicava il rendimento. **Quella misura dava a ogni simbolo il proprio
capitale pieno.** Messo nel simulatore a capitale CONDIVISO — lo stesso che nel
round 15 aveva ribaltato il confronto fra i set di parametri — il vantaggio si
riduce molto e, su base risk-adjusted, si INVERTE. Questa e' la misura corretta.

## 21.1 Perche' il 4H e' molto piu' esigente di cassa

La size e' rischio / (stop_mult x ATR). Su barre 4H l'ATR e' circa 2.4 volte piu'
piccolo che sul giornaliero, a parita' di volatilita' del mercato: la stessa
volatilita' distribuita su barre piu' corte. Quindi a pari rischio la posizione
diventa ~2.4 volte piu' GRANDE.

Sul giornaliero una posizione impegnava ~17% del conto: cinque entravano tutte.
Sul 4H ne impegna ~41%: **due riempiono il conto**. Con 24.83 EUR per conto, il
vincolo smette di essere teorico.

## 21.2 I numeri veri (3 conti da 24.83 EUR, capitale condiviso, 5 asset)

| configurazione | fee | rischio | rend. | CAGR | maxDD | Sharpe | rifiutati |
|---|---|---|---|---|---|---|---|
| GIORNALIERO (deployato) | spot | 0.5% | +16.12% | 6.97% | 6.66% | **0.87** | 0 |
| GIORNALIERO (deployato) | spot | 1.0% | +26.54% | 11.19% | 10.86% | **0.86** | 0 |
| GIORNALIERO (deployato) | spot | 2.0% | +34.90% | 14.44% | 16.85% | 0.79 | 0 |
| 4H pari-barre | spot | 0.5% | +10.05% | 3.99% | 16.84% | 0.20 | 7 |
| 4H pari-barre | spot | 2.0% | **-8.18%** | -3.43% | 37.86% | -0.02 | 160 |
| 4H pari-barre | swap | 0.5% | +36.83% | 13.68% | 10.64% | 0.64 | 7 |
| 4H pari-barre | swap | 1.0% | +51.84% | 18.62% | 16.89% | 0.54 | 25 |
| 4H pari-barre | swap | 2.0% | +62.83% | 22.05% | 22.38% | 0.45 | 124 |
| 4H canale-240 | swap | 1.0% | +22.70% | 9.66% | 6.59% | 0.46 | 5 |

## 21.3 Cosa resta vero e cosa no

**Resta vero:** a fee spot il 4H e' da buttare. +10.05% a 0.5% di rischio contro
+16.12% del giornaliero, Sharpe 0.20 contro 0.87, e a 2% di rischio diventa
NEGATIVO. La conclusione del round 16 sul costo come fattore decisivo regge.

**Resta vero:** con le fee dei derivati il 4H rende di PIU' in assoluto. A pari
drawdown (16.9%): 4H a 1% rischio fa CAGR 18.62%, il giornaliero a 2% fa 14.44%.
Circa **+4 punti di CAGR**, non il triplo.

**NON e' vero** che il 4H sia una configurazione migliore. Lo Sharpe e' 0.45-0.64
contro 0.79-0.87: a parita' di rischio rende meno. E il vincolo di cassa morde
davvero: a 2% di rischio **124-160 segnali su oltre 2000 non sono finanziabili**,
cioe' la strategia non riesce a prendere i trade che il backtest per-simbolo
contava.

## 21.4 Conclusione

La configurazione **deployata e' la migliore su base risk-adjusted** fra tutte
quelle misurate: Sharpe 0.79-0.87 e zero segnali rifiutati, perche' le posizioni
da ~17% entrano tutte e cinque.

Il 4H a fee derivate e' un'opzione di **rendimento assoluto** (+4 punti di CAGR a
pari drawdown) a costo di uno Sharpe sensibilmente peggiore e di dover scartare
una parte dei segnali. Non e' un salto di qualita' e non giustifica da solo il
cambiamento di modalita' dell'account: se si fa, va fatto per il rendimento
assoluto, sapendo cosa si paga.

**Lezione di metodo**, la stessa del round 15: il rig per-simbolo sovrastima
sistematicamente le configurazioni con posizioni grandi, perche' ignora che il
capitale e' finito. Ogni confronto va rifatto nel simulatore a capitale condiviso
prima di concludere qualsiasi cosa.
