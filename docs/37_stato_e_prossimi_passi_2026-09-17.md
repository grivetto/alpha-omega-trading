# 37 — Stato del progetto e cosa fare adesso (round 35, 2026-09-17)

Documento di consegna: cosa gira, cosa e' stato dimostrato, cosa resta.

## 37.1 Cosa e' deployato ADESSO

| voce | valore |
|---|---|
| strategia | trend following giornaliero: breakout canale 40 + filtro EMA 100 |
| uscita | trailing stop 2.5 ATR, **stop monitorato** (chiusura a mercato) |
| size | sul rischio: 2% del capitale per trade, stop 2 ATR, tetto 100% esposizione |
| bot | **17**, uno per asset: mc2 7, nuvola 6, MARCODG1 4 |
| capitale | 109.58 EUR (42.12 / 24.83 / 42.04) |
| fee pagata | taker spot 0.35%/lato; spread reale mediano 0.134% |
| barre | giornaliere OKX EEA, chiuse alle **16:00 UTC** (allineate al millisecondo) |

Prima valutazione del segnale: **chiusura delle 16:00 UTC** (18:00 CEST).

## 37.2 Cosa e' stato dimostrato (e cosa respinto)

Tutto su dati di mercato reali (52 asset, 865 barre comuni), stessa fee, finestre
multiple, simulatore a capitale condiviso **validato al bit** contro il motore di
backtest. Ipotesi provate e respinte, per non ripeterle: canale 20, ingressi
multi-orizzonte, pullback, 4H, filtri di regime, tetto per posizione, stop piu'
larghi, allargamento dell'universo (26/35/44/52 asset, peggiora
monotonicamente), potatura per rendimento recente (fallisce fuori campione),
momentum cross-sezionale, piramide sui vincitori (Sharpe peggiore ovunque).
Strategie eliminate dal codice: grid, momentum, meanrev (docs/31).

Adottato: trailing 2.5 (regione 2.25-2.75), universo 17 con MINA/TRX/CRV,
allineamento delle barre, stop dal fill.

## 37.3 I numeri da aspettarsi

| finestra | rendimento portafoglio | maxDD | Sharpe |
|---|---|---|---|
| storia (2.4 anni) | +78.31% (con spread reale) | 12.8% | 1.23 |
| ~18 mesi | +11.73% | 12.9% | 0.78 |
| ~12 mesi | **+8.10%** | 4.2% | 0.92 |
| ~9 mesi | +5.20% | 5.3% | 0.78 |
| ~6 mesi | +7.96% | 4.1% | 1.80 |

Sul capitale vero: **~+8 EUR/anno** sul regime recente, con drawdown atteso
12-15% (cioe' -13/-16 EUR nel caso peggiore osservato). Il +78% della storia
contiene il rally 2024: l'aspettativa forward onesta e' **+5-8%/anno**.

**Capacita'**: rendimento percentuale quasi invariante fino a ~3.000 EUR; sopra,
MINA/ALGO/TRX/AVAX superano l'1% del volume giornaliero. Il primo euro in piu'
va su **nuvola** (24.83 EUR, 6 bot: il conto piu' stretto).

## 37.4 I guardrail attivi

1. **Mandato strategie** (`denaro/research/misurate.py` + guardia nel Node): in
   live parte solo una strategia con alpha misurato. Le eliminate e le nove
   policy senza backtest non possono girare.
2. **Barre allineate all'exchange** (16:00 UTC, non mezzanotte): live = backtest.
3. **Candela vera**: ogni 60s lo storico e' sostituito dalle candele chiuse
   dell'exchange, cosi' canale/ATR non derivano dalle barre parziali dei tick.
4. **Stop dal fill**: la posizione nasce con lo stop a 2 ATR registrato subito;
   un ripristino senza stop lo riancora (non lo allarga a 2.5).
5. **Aggregator robusto**: una ssh per host + ultima lettura buona; le card non
   spariscono piu' per un timeout.
6. **Paper separato**: le strategie eliminate girano solo in paper, mai su conti
   reali (nessun bot live le usa).

## 37.5 Come verificare (comandi pronti)

    # quanto manca al segnale, per ogni bot
    python3 tools/trend_monitor.py config/node_nuvola_trade.yaml
    # confine barre e prossima chiusura
    python3 tools/trend_allineamento.py config/node_mc2.yaml
    # cosa farebbe al prossimo confine (nessun ordine)
    python3 tools/trend_preflight.py config/node_nuvola_trade.yaml [--forza]
    # stato reale: health, ordini, saldo
    python3 tools/trend_live_check.py config/node_mc2.yaml
    # dashboard e Zabbix
    https://web.grivetto.eu   ·   https://zab.grivetto.eu

## 37.6 Stato tecnico

- Repo: un solo branch (`main`), **1 worktree** per macchina, 22 tag allineati,
  **zero** file sospetti tracciati (nessun segreto, stato, backup, venv), working
  tree pulito su tutte e tre le macchine.
- Test: **331 verdi** (l'ultimo giro ne ha aggiunti 4 sullo stop iniziale).
- Flotta: 17/17 bot freschi, 0 errori, 0 posizioni, dashboard a 0 problemi.

## 37.7 Cosa resta, in ordine di importanza

1. **Il primo trade reale**: evento di orologio (chiusura 16:00 UTC). Candidato
   piu' vicino: **UNI**, sopra il canale. Va verificato con
   `trend_live_check.py`: il notional deve corrispondere al preflight e lo stop
   deve stare a entry - 2 ATR.
2. **Capitale**: e' l'unico vero moltiplicatore. 1.000 EUR rendono ~80 EUR/anno,
   3.000 EUR ~240 EUR/anno con questa flotta e questi costi.
3. **Derivati** (serve l'upgrade del conto OKX a `acctLv 2`): fee 0.05%/lato
   invece di 0.35% -> circa +1.8 EUR/anno ogni 109 EUR investiti, e sblocca il
   4H che sullo spot non paga le fee (docs/16-17).
