# 25 — Lo stop piu' largo non mitiga la gap (round 23)

## 25.1 L'ipotesi

La size e' rischio/(stop_mult*ATR): con uno stop piu' LARGO la posizione e' piu'
piccola a pari rischio, quindi una gap che salta lo stop dovrebbe colpire meno
capitale. A differenza del tetto per posizione — che mordeva solo gli asset a
volatilita' bassissima — questo cambia TUTTE le posizioni. Sembrava la
mitigazione giusta.

## 25.2 La misura

Simulatore con gap validato (generato dal sorgente di quello di riferimento).

| stop (ATR) | gap 0% | gap 2% | gap 5% | sopravvivenza a gap 5% |
|---|---|---|---|---|
| 1.5 | +69.24% / -8.76% | +47.59% / -14.32% | +19.15% / -24.91% | 28% |
| **2.0 (deployato)** | **+73.04%** / -7.16% | **+54.81%** / -10.29% | **+30.10%** / -17.84% | **41%** |
| 2.5 | +63.26% / -6.92% | +47.95% / -10.70% | +27.06% / -17.04% | 43% |
| 3.0 | +55.87% / -6.72% | +42.73% / -10.57% | +24.63% / -16.33% | 44% |
| 4.0 | +46.11% / -6.45% | +35.82% / -9.72% | +21.39% / -14.63% | 46% |
| 5.0 | +39.42% / -5.90% | +30.96% / -8.76% | +18.96% / -13.07% | 48% |

L'ipotesi e' **vera in parte**: allargando lo stop la quota di rendimento che
sopravvive alla gap sale (41% -> 48%) e il drawdown scende (-17.84% -> -13.07% a
gap 5%). Ma il rendimento assoluto scende molto di piu': a gap 5%, stop 2.0 da'
+30.10% e stop 5.0 da' +18.96%. **Si perdono piu' profitti di quanti danni si
evitino.**

E lo stop 2.0 deployato e' il migliore a OGNI livello di gap.

## 25.3 Lo Sharpe non dipende dallo stop

| stop (ATR) | Sharpe gap 0% | Sharpe gap 5% |
|---|---|---|
| 1.5 | 1.19 | 0.44 |
| **2.0** | **1.39** | 0.67 |
| 2.5 | 1.38 | 0.67 |
| 3.0 | 1.37 | 0.68 |
| 4.0 | 1.38 | 0.70 |
| 5.0 | 1.39 | 0.72 |

Da 2.0 a 5.0 lo Sharpe e' **praticamente piatto** (1.37-1.39) a gap zero. Solo
1.5 e' nettamente peggiore. E' un buon segno: la qualita' risk-adjusted della
strategia non dipende da questo parametro, quindi la configurazione e' robusta.
Sotto gap lo Sharpe migliora lievemente con stop piu' larghi (0.67 -> 0.72), ma
il rendimento assoluto peggiora di molto: non e' un buon affare.

## 25.4 Decisione

**Nessun cambio: stop 2.0 ATR, trail 2.5 ATR.** Confermato ottimo su rendimento
assoluto; lo Sharpe non distingue; e nessuna delle due mitigazioni provate (tetto
per posizione, stop piu' largo) riduce il rischio di gap senza pagarlo piu' caro
di quanto renda.

**Il rischio di gap e' strutturale** in questa famiglia di strategie e va
accettato e dimensionato, non ingegnerizzato via. Quello che si puo' fare — ed e'
gia' fatto — e' tenere il rischio per trade al 2% del capitale, cosi' anche il
caso peggiore misurato (+30% con drawdown 18%) resta sostenibile.
