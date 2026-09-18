# 43 — L'insieme regge, la stagionalita' no (e due porte chiuse)

Data: 2026-09-18. Riproducibile: `tools/trend_ensemble.py`.

## 43.1 La domanda

Il fatto misurato in docs/39-40: la configurazione deployata sta quasi tutta in un
blocco su tre, e sul 4H solo 4/24 configurazioni reggono a fee spot. Ma **tutte e
24** hanno rendimento composto positivo sull'intero periodo. Quindi il problema non
e' "la config e' sbagliata": e' che ognuna e' episodica in momenti diversi.

Domanda: l'**insieme** delle configurazioni (equipesato, universo largo) e' robusto
anche quando le singole non lo sono? E lo e' la sola meta' long-only, cioe' l'unica
che un conto spot puo' davvero negoziare?

## 43.2 4H, universo largo — 28 simboli, 5181 barre, 5 blocchi da 1036

| | fee OKX 0.35% | fee Bybit 0.27% |
|---|---|---|
| **ensemble 24 config** | **+11.09% — 4/5 blocchi** | **+19.30% — 4/5 blocchi** |
| ensemble 12 long-only | +9.18% — 3/5 | +14.27% — 3/5 |
| config deployata (40/100) | +10.81% — 3/5 | +16.45% — 4/5 |
| pieno periodo, ensemble long-only | +15.87% media / +16.96% mediana | +21.86% / +22.65% |

Blocchi dell'ensemble a 0.27%: +5.59% +9.13% +4.06% **-2.80%** +2.35%.

**L'ensemble batte la singola configurazione**: 4 blocchi positivi su 5 a *entrambe*
le fee, mentre la config deployata ci arriva solo a quella piu' bassa. Ma il
guadagno di robustezza vive **tutto nella meta' short**, che un conto spot non puo'
negoziare: la meta' long-only resta a 3/5 e rende *meno* della config deployata
(+9.18% contro +10.81%). Nessun miglioramento negoziabile — ma finalmente si sa
*dove* sta la robustezza.

## 43.3 1D, universo largo — 47 simboli, 900 barre, 3 blocchi

| | fee OKX 0.35% | fee Bybit 0.27% |
|---|---|---|
| ensemble 24 config | +9.15% — 1/3 | +9.48% — 1/3 |
| ensemble 12 long-only | +8.82% — 1/3 | +9.06% — 1/3 |
| config deployata | +8.93% — 1/3 | +9.21% — 1/3 |

L'insieme **non cura** il giornaliero: 1 blocco su 3 a ogni fee, per tutte le
varianti. Il rendimento del giornaliero resta un episodio, e non e' un problema di
diversificazione tra configurazioni.

## 43.4 Stagionalita': sembrava una scoperta, era correlazione incrociata

Prima misura, sbagliata (t calcolato su tutte le barre come se fossero
indipendenti — 42.253 barre per 900 giorni, con 47 simboli che si muovono insieme):

| barra | 1D media bp | t gonfiato | 4H media bp | t gonfiato |
|---|---|---|---|---|
| mar | +40.85 | +6.92 | -4.16 | -0.80 |
| mer | -42.36 | -6.93 | +8.13 | +5.54 |
| gio | +5.62 | +0.90 | -8.92 | -6.02 |
| sab | -17.51 | -3.08 | +7.44 | +4.90 |
| dom | -38.33 | -6.07 | -7.13 | -5.32 |

Misura corretta (una osservazione per timestamp: media cross-sezionale, poi t sulla
serie risultante — 899 osservazioni per il 1D, 5181 per il 4H):

| barra | 1D media bp | **t onesto** | 4H media bp | **t onesto** |
|---|---|---|---|---|
| lun | -33.22 | -1.07 | +2.66 | +0.41 |
| mar | +40.85 | +1.46 | -4.16 | -0.80 |
| mer | -42.36 | -1.36 | +8.13 | +1.57 |
| gio | +5.62 | +0.18 | -8.87 | -1.81 |
| ven | +21.58 | +0.69 | +5.95 | +0.96 |
| sab | -17.51 | -0.70 | +7.44 | +1.91 |
| dom | -38.33 | -1.24 | -7.13 | -1.49 |

**Nessun effetto sopravvive**: il |t| massimo e' 1.91. Il "t=6.92" era la
correlazione tra i 47 simboli travestita da numerosita'. Porta chiusa.

Dato collaterale importante: sull'universo largo equipesato il rendimento medio per
barra e' **-9.02 bp** (t onesto -0.80) su 899 giorni. Il mercato, in questo
campione, **non e' stato un vento a favore**: il +20% del trend deployato e' stato
preso *contro* il mercato, non grazie ad esso.

## 43.5 Drift delle nuove quotazioni EUR

45 simboli con storia corta (<1500 barre), rendimento dopo la prima barra
disponibile: 30 barre -0.16% (t=-0.09), 60 barre +0.01%, 120 barre +3.64%
(t=+1.64). Su tutti i 77 simboli: -2.89% / -2.31% / +1.27%. Nessun effetto pulito
di quotazione. Porta chiusa.

## 43.6 Verdetto

Su spot-only, long-only, 0.5-0.8% di giro completo, con 2,8 anni di dati su 77
serie: **niente di nuovo passa il cancello**. Le uniche cose che passano restano il
trend (episodico) e la sua meta' short (non negoziabile senza derivati).

Il collo di bottiglia non e' la strategia, e' **lo strumento**: e' la meta' short —
shorteare, o pagare 7 volte meno — che porta l'ensemble a 4/5 blocchi. A queste
condizioni il rendimento negoziabile e' ~+15% in 2,8 anni su un paniere equipesato,
con la sua episodicita' intatta.

Prossimo passo, e non e' un altro pattern sui prezzi: **verificare se esiste un
venue accessibile dall'UE con derivati** (Bitget EU? Kraken EU futures?) prima di
scrivere un'altra riga di ricerca. Se non esiste, la conclusione onesta e' che a 109
EUR e questi costi non c'e' un edge accessibile, e la flotta va portata in regime di
sola osservazione invece di continuare a macinare fee.
