# 32 — Momentum cross-sezionale: misurato e scartato (round 32, 2026-09-17)

## 32.1 Il motore che nessuno aveva mai usato

`denaro/research/eval.py` contiene da tempo `backtest_xsec` (e
`walk_forward_xsec`): momentum **cross-sezionale**, cioe' "quale sale piu' degli
altri?" invece di "questo sale?". Ribilanciamento raro, turnover basso, costi
proporzionali al turnover. `grep` su tutto il repo: **nessun tool e nessun doc
l'aveva mai usato**. Era l'unico motore di ricerca mai misurato su questi dati
oltre ai cinque del censimento del round 31.

Perche' valeva la pena: il trend ha un edge **episodico** e lascia il capitale
fermo per mesi; una strategia relativa, sempre investita nel paniere migliore,
userebbe proprio quel capitale. E' l'ipotesi piu' generosa che si potesse fare.

## 32.2 I numeri

Parametri di **default** del motore (lookback 180, k 5, ribilanciamento 42),
nessun tuning. Fee taker reale 0.35%/lato (`tools/xsec_studio.py`).

| universo | finestra | xsec | maxDD | Sharpe | buy&hold paniere |
|---|---|---|---|---|---|
| flotta (17) | storia | **-40.87%** | 81.65% | -0.13 | -18.56% |
| flotta (17) | 540b | **-51.56%** | 62.14% | -1.33 | -36.78% |
| flotta (17) | 365b | +19.35% | 28.36% | 1.00 | -53.67% |
| flotta (17) | 270b | +33.51% | 9.97% | 2.83 | -12.73% |
| 52 asset | storia | **-50.38%** | 81.78% | -0.27 | -60.25% |
| 52 asset | 540b | **-65.52%** | 71.63% | -1.63 | -58.57% |
| 52 asset | 365b | -15.06% | 33.93% | -0.36 | -65.45% |
| 52 asset | 270b | +10.09% | 20.54% | 1.00 | -26.39% |

Griglia di robustezza (27 set: lookback 90/180/270 x k 3/5/8 x ribilanciamento
21/42/63), quanti set sono positivi:

| universo | storia | 540b | 365b | 270b | 180b |
|---|---|---|---|---|---|
| flotta (17) | 6/27 | 1/27 | 21/27 | 17/18 | 9/9 |
| 52 asset | 1/27 | 0/27 | 5/27 | 13/18 | 8/9 |

## 32.3 Perche' si scarta

Il cross-sezionale e' **positivo solo nelle finestre recenti** (365/270/180) e
**fortemente negativo** sulla storia e sui 540 giorni, in entrambi gli universi.
Non e' un problema di parametri: sulla storia solo 6 set su 27 (flotta) e 1 su 27
(52 asset) sono positivi. E' la stessa natura episodica dell'edge, con un
drawdown molto peggiore (81% contro il 12.5% del portafoglio trend).

Nota di contesto che vale piu' della tabella: il **buy&hold** del paniere fa
-18.56% (flotta) e -60.25% (52 asset) sulla storia, -53.67% e -65.45% sul 365b.
Il mercato degli alt e' stato orso e laterale. Il trend non batte il mercato
"perche' sale": batte **perche' sta a cash quando non c'e' niente da seguire**, e
questo e' il suo valore misurato.

Verdetto per la regola dichiarata (alpha positivo in ogni finestra): **non
deployabile**. Il motore resta nel repo come strumento di ricerca, non come
candidato.

## 32.4 Stato del censimento

Sei motori di ricerca, un verdetto per ciascuno:

| motore | verdetto |
|---|---|
| trend | deployato (5/5 finestre positive) |
| pullback | solo ricerca (3/5) |
| xsec | scartato (negativo su storia e 540b) |
| grid | eliminato |
| momentum | eliminato |
| meanrev | eliminato (motore morto) |

Nove policy restano **senza alcun motore di backtest** e quindi non deployabili
(docs/31). Sui dati reali non esiste oggi, in questo repo, un secondo edge
misurato e robusto da affiancare al trend.
