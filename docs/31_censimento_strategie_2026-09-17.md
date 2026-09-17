# 31 — Censimento delle strategie: chi ha alpha, chi no (round 31, 2026-09-17)

## 31.1 Perche' un censimento

Il repo contiene **13 policy** nel dominio, ma solo **5** hanno un motore di
backtest in `denaro/research/eval.py`. Il mandato dice "eliminare o riprogettare
le strategie con alpha negativo": per farlo servono numeri sulla **stessa
finestra**, sugli **stessi asset** e alla **stessa fee reale**, non impressioni.

Metodo, senza tuning e senza fortuna: 17 asset della flotta in produzione,
capitale 1.0 per asset (rendimento percentuale puro), fee taker reale **0.35%
per lato** per i motori a mercato, 5 finestre (storia, 540, 365, 270, 180
barre). `backtest_pullback` gira con i SUOI default (maker 0.20% + taker 0.35%
sullo stop): e' il motivo per cui esiste.
(`tools/strategie_censimento.py`)

## 31.2 I numeri

Rendimento **medio** sui 17 asset:

| motore | storia | 540b | 365b | 270b | 180b | finestre positive | verdetto |
|---|---|---|---|---|---|---|---|
| **trend** | **+13.08%** | **+0.87%** | **+0.06%** | **+0.31%** | **+0.96%** | **5/5** | deployato |
| pullback | -4.19% | +0.01% | +0.67% | +1.19% | 0.00% | 3/5 | solo ricerca |
| grid | -58.08% | -43.67% | -50.75% | -26.26% | -4.67% | 0/5 | **eliminata** |
| momentum | -78.89% | -56.73% | -37.73% | -35.19% | -21.40% | 0/5 | **eliminata** |
| meanrev | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0/5 | **eliminata** |

Note oneste:

- i numeri sono con i **default dei motori** (nessun tuning): servono a dire se
  una strategia ha un edge intrinseco, non a fare la classifica dei parametri;
- `grid` e `momentum` fanno **743** e **2328** giri sui 17 asset in 2.4 anni. A
  0.70% di round trip la fee da sola vale molte volte il capitale: il segnale
  puo' anche esistere (docs/17 lo misura a fee zero), ma su spot a fee taker e'
  il **costo** a decidere il risultato. Non e' un problema di parametri;
- `meanrev` con i default non fa **nemmeno un trade**: e' codice morto travestito
  da strategia.

## 31.3 Le policy senza una misura

Nove policy esistono nel dominio e **non hanno alcun motore di backtest**:
`adaptive`, `adaptive_vol_grid`, `irmr`, `vagr`, `mincapture_grid`,
`flowgate_grid`, `cycle_phase_grid`, `asymvol_anchor`, `circular`. Per il
mandato questo basta: **senza misura non si deploya**. (E' anche la risposta
secca al "un anno e mezzo": la strategia che girava in live era scelta per
intuizione, non per misura.)

## 31.4 Il mandato diventa codice

`denaro/research/misurate.py` contiene il registro delle misure
(`MISURATE`, `ELIMINATE`, `NON_MISURATE`) e la funzione
`puo_girare_live(strategia, modalita)`. Il Node la consulta in `_build_bots`:
in modalita' **paper** tutto e' ammesso (e' il banco di prova), in **live** un
bot con una strategia eliminata o mai misurata **non parte** e viene scritto un
`log.error` esplicito con il motivo e il riferimento alla misura.

Verifica:

- **323 test verdi** (6 nuovi in `denaro/tests/test_mandato.py`: trend ammesso,
  paper sempre ammesso, eliminate rifiutate, policy senza motore rifiutate,
  ignote rifiutate, e copertura completa del dispatch del Node);
- sui **17 bot live configurati** (7 mc2, 6 nuvola, 4 MARCODG1): **17 ammessi, 0
  bloccati**; i tre nodi sono ripartiti e registrano 7/6/4 bot senza alcun
  `BLOCCATO` nei log;
- commit `1c3b78d` su mc2, nuvola e MARCODG1.

## 31.5 Cosa cambia per l'obiettivo

Prima di questo round il progetto aveva **una** strategia con alpha misurato e
positivo (trend) e **dodici** senza misura alle spalle, con la porta aperta:
bastava un `enabled: true` e un `mode: okx` in un config per mettere denaro su
un'idea mai verificata. Ora quella porta e' chiusa da una regola eseguibile e
testata.

Resta aperto, e va detto: l'edge di trend e' **piccolo** (+13.08% di media
per-asset sulla storia, +0.06/+0.96% sulle finestre recenti, che sul capitale
vero significa dell'ordine di +5-8%/anno) e **episodico**. Il vincolo del
progetto non e' piu' "quale strategia", e' **quanto capitale**.
