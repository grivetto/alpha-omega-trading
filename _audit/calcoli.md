# AUDIT ECONOMICO — tabelle calcolate

## A. Round-trip e break-even (taker/taker), capitale 52 EUR

| Venue / livello | Maker | Taker | Round-trip % | Break-even edge lordo/trade | Costo su 52 EUR | N. trade/anno a pareggio con edge 2% |
|---|---|---|---|---|---|---|
| OKX EEA spot, NO derivati (Regular = oggi) | 0.2% | 0.35% | 0.7000% | 0.7000% | 0.3640 EUR | 2.86 |
| OKX EEA spot, CON X-Perps (Regular) | 0.08% | 0.1% | 0.2000% | 0.2000% | 0.1040 EUR | 10.00 |
| OKX EEA swap taker (acctLv2 richiesto) | 0.02% | 0.05% | 0.1000% | 0.1000% | 0.0520 EUR | 20.00 |
| Bybit EU spot crypto VIP0 | 0.1% | 0.25% | 0.5000% | 0.5000% | 0.2600 EUR | 4.00 |
| Bybit EU fiat pair (USDC/EUR) VIP0 | 0.15% | 0.25% | 0.5000% | 0.5000% | 0.2600 EUR | 4.00 |
| Kraken stablecoin/FX (EUR/USDC) tier 0 | 0.2% | 0.2% | 0.4000% | 0.4000% | 0.2080 EUR | 5.00 |
| Kraken spot crypto Tier1 | 0.4% | 0.8% | 1.6000% | 1.6000% | 0.8320 EUR | 1.25 |
| Binance (non piu' disponibile per IT dal 2026-07-01) | n/d | n/d | n/d | n/d | n/d | n/d |

Nota: 'break-even edge lordo per trade' = 2xfee_taker, che e' anche il costo di
attraversare lo spread. Il valore 0.7778% di docs/39 somma 2x0.35 con lo spread mediano
0.0778%: e' un doppio conteggio (la fee taker GIA' paga lo spread). La misura corretta
e' 0.70%. Errore prudenziale (~11% di sovrastima), non cambia alcuna conclusione.

## B. Costo effettivo A GIRO COMPLETO, taker/taker

| Venue | fee/lato | round-trip (2x) | in EUR su 52 |
|---|---|---|---|
| OKX EEA spot oggi (NO derivati) | 0.350% | 0.7000% | 0.3640 |
| OKX EEA spot CON X-Perps aperti | 0.100% | 0.2000% | 0.1040 |
| OKX EEA swap taker (acctLv2) | 0.050% | 0.1000% | 0.0520 |
| OKX swap taker + funding 3g | 0.068% | 0.1360% | 0.0707 |
| Bybit EU spot taker VIP0 | 0.250% | 0.5000% | 0.2600 |
| Kraken EUR/USDC stabile taker | 0.200% | 0.4000% | 0.2080 |
| Kraken spot crypto Tier1 taker | 0.800% | 1.6000% | 0.8320 |

## C. Sensibilita' del trend giornaliero (params FISSI canale40/trail3/stop2, 19 asset)
Dati docs/17 §9.3 — gli unici tre punti realmente misurati:

| fee per lato | alpha cumulato | t |
|---|---|---|
| 0.00% | +34.98% | +4.51 |
| 0.20% | +12.33% | +1.73 |
| 0.35% | -1.97% | -0.30 |

Interpolazione lineare sui tre punti: alpha(f) = 34.54 + (-105.99)*f   [f in %]
  - f = 0.00%/lato -> alpha stimato +34.54%
  - f = 0.05%/lato -> alpha stimato +29.24%
  - f = 0.10%/lato -> alpha stimato +23.95%
  - f = 0.15%/lato -> alpha stimato +18.65%
  - f = 0.20%/lato -> alpha stimato +13.35%
  - f = 0.25%/lato -> alpha stimato +8.05%
  - f = 0.35%/lato -> alpha stimato -2.55%
  - break-even (alpha=0) a f = 0.326% per lato

CONFRONTO CON docs/17 §9.2 (campione CON selezione dei parametri per asset):
| fee/lato | TREND alpha | t |
|---|---|---|
| 0.00% | +104.13% | +3.92 |
| 0.05% | +95.59% | +3.68 |
| 0.10% | +86.73% | +3.40 |
| 0.20% | +72.72% | +2.99 |
| 0.35% | +54.43% | +2.41 |
A 0.10%/lato quella tabella da' t = 3.40, cioe' SOPRA la soglia di significativita' 2.
Ma la stessa pagina avverte che quei valori sono 'gonfiati dalla selezione dei
parametri per asset': la tabella a parametri FISSI (§9.3) ha solo 3 punti misurati
(0.00 / 0.20 / 0.35) e il punto a 0.10% non esiste. L'interpolazione e' una STIMA.


ATTENZIONE: interpolazione su 3 punti, non una misura. I punti a 0.05/0.10/0.15%/lato
NON sono stati simulati. Dichiarato come stima, non come fatto.

## D. Robustezza misurata (configurazioni robuste su 24) — docs/40 §40.1

| fee per lato | 4H (19 asset) | 4H largo (28) | 1D (19) | 1D largo (47) |
|---|---|---|---|---|
| 0.35% | 3 | 4 | 14 | 7 |
| 0.27% | 9 | 11 | 17 | 9 |
| 0.25% | 9 | 14 | 18 | 9 |
| 0.20% | 13 | 19 | 18 | 10 |
| 0.10% | 18 | 21 | 18 | 12 |
| 0.05% | 20 | 21 | 18 | 12 |

## E. Trade necessari per assorbire la fee (edge lordo per trade = R)

| edge lordo/trade | trade/anno a pareggio @0.35%/lato | @0.25%/lato | @0.20%/lato | @0.10%/lato | @0.05%/lato |
|---|---|---|---|---|---|
| 0.5% | 0.71 | 1.00 | 1.25 | 2.50 | 5.00 |
| 1.0% | 1.43 | 2.00 | 2.50 | 5.00 | 10.00 |
| 2.0% | 2.86 | 4.00 | 5.00 | 10.00 | 20.00 |
| 3.0% | 4.29 | 6.00 | 7.50 | 15.00 | 30.00 |
| 5.0% | 7.14 | 10.00 | 12.50 | 25.00 | 50.00 |

Frequenza misurata dal progetto: ~10 trade per asset in 2.5 anni = 4 trade/anno per asset (docs/17 §10).
Con 5 posizioni contemporanee su 1 conto: ~4 trade/anno per slot.