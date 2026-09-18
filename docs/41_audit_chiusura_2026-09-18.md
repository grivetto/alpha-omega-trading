# 41 — Audit di chiusura: l'obiettivo, con le prove (round 38)

## 41.1 L'obiettivo, in due meta'

"Riorganizzare completamente il repo git di alpha-omega-trading (branch, junk
tracciato, worktree, storia) **e poi** rendere il sistema Denaro realmente
redditizio: pipeline di ricerca multi-finestra/multi-coppia, eliminazione o
riprogettazione delle strategie con alpha negativo, verifica su dati di mercato
reali e deploy solo di edge misurato e robusto."

## 41.2 Meta' 1 — Repo riorganizzato (prove)

| prova | valore |
|---|---|
| branch | **1** (`main`) |
| worktree | **1 per macchina** (rimosso quello orfano `/tmp/ao-push-brain-* su MARCODG1) |
| tag | **22**, allineati su tutte e tre le macchine (il tag locale e' stato pushato) |
| storia | **428 commit**, 5 merge, nessuna riscrittura |
| file tracciati | **322** |
| file sospetti tracciati | **0** (nessun `.env`, `.pem`, `.key`, secret, `.bak`, `node_data`, `.pytmp`, `__pycache__`) |
| `.gitignore` | 130 righe: ignora dati di mercato, stato, health, backup, venv, segreti — verificato con `git check-ignore` dopo aver scoperto che un `.gitignore` vecchio (90 righe, CRLF) l'aveva sovrascritto su mc2 |
| working tree | **pulito su tutte e tre le macchine** |
| controllo permanente | **allarme repo sporco** in dashboard (HEAD + modifiche non committate per macchina, round 36) |
| dimensione | `.git` 12 MB |

## 41.3 Meta' 2 — Edge misurato e deployato (prove)

- **Pipeline di ricerca**: 64 tool in `tools/`, 40 documenti. Ogni decisione e'
  passata da finestre multiple, protocolli out-of-sample, fee reali; il
  simulatore a capitale condiviso e' **validato al bit** contro il motore di
  backtest (`tetto_capitale=False` riproduce `backtest_trend`).
- **Strategie con alpha negativo eliminate**: grid (0/5 finestre positive, 743
  giri), momentum (0/5, 2328 giri), meanrev (0 trade con i default); 9 policy
  senza alcun motore di backtest non sono deployabili. Il tutto **imposto dal
  codice** (`denaro/research/misurate.py` + guardia in `_build_bots`), non da
  una convenzione: in live parte solo chi ha una misura.
- **Verifica su dati di mercato reali**: fee taker 0.35% e maker 0.20% misurate
  sull'account; **spread bid/ask reale** per asset (mediana 0.134%, MINA 0.415%);
  **volumi reali** (partecipazione al volume); capitali reali (42.12 / 24.83 /
  42.04); **barre allineate all'exchange** (16:00 UTC) e **candela vera**
  dell'exchange al posto della barra dei tick.
- **Deploy**: 17 bot trend (mc2 7, nuvola 6, MARCODG1 4) su 109.58 EUR, canale 40
  + filtro EMA 100, stop 2 ATR, trailing 2.5 ATR, rischio 2%, uscita a mercato
  con **stop monitorato**, stop registrato **dal fill**.
- **13 ipotesi respinte** con i numeri (docs/30-40), fra cui allargamento
  dell'universo, potatura per rendimento, momentum cross-sezionale, piramide,
  4H a fee spot, migrazione di venue.

## 41.4 Cosa aspettarsi (tutto misurato)

| finestra | rendimento | maxDD | Sharpe |
|---|---|---|---|
| storia (2.4 anni) | +78.31% (spread reale incluso) | 12.8% | 1.23 |
| 12 mesi | **+8.10%** | 4.2% | 0.92 |
| 6 mesi | +7.96% | 4.1% | 1.80 |

Sul capitale vero: **~+8 EUR/anno** oggi; **~+80 EUR/anno** a 1.000 EUR;
**~+240 EUR/anno** a 3.000 EUR. Capacita': partecipazione al volume sotto l'1%
fino a ~1.000-3.000 EUR con questa flotta. Costi: maker **+0.9 EUR/anno**,
derivati **+1.8 EUR/anno** sui 109 EUR — e sul 4H i derivati portano le
configurazioni robuste da 3/24 a 20/24 (docs/39-40).

## 41.5 Cosa NON e' chiuso, e perche' non dipende dal lavoro

1. **Il primo trade reale**: evento di orologio, chiusura di barra alle 16:00
   UTC. Il verificatore e' pronto (`tools/trend_verifica_trade.py`): dice se il
   breakout e' avvenuto, se l'ordine e' stato registrato e se quantita', stop e
   slittamento corrispondono al modello misurato.
2. **Il capitale**: decisione dell'utente; e' l'unico moltiplicatore rimasto.
3. **`acctLv 2` (derivati)**: azione sull'account; sblocca il 4H.

## 41.6 Come riverificare tutto

    cd /home/sergio/alpha-omega-trading        # o /home/marco/... su MARCODG1

    # 1. il repo
    git log --oneline -1; git status --short; git worktree list; git tag | wc -l

    # 2. i test (336)
    /home/sergio/denaro/venv/bin/python -m pytest denaro/tests -q

    # 3. la strategia: dove siamo, quanto manca al segnale, cosa farebbe
    python3 tools/trend_monitor.py config/node_nuvola_trade.yaml
    python3 tools/trend_allineamento.py config/node_nuvola_trade.yaml
    python3 tools/trend_preflight.py config/node_nuvola_trade.yaml [--forza]

    # 4. il primo trade (dopo la chiusura delle 16:00 UTC)
    python3 tools/trend_verifica_trade.py config/node_nuvola_trade.yaml

    # 5. la flotta e gli allarmi
    https://web.grivetto.eu   ·   https://zab.grivetto.eu

## 41.7 Stato al momento dell'audit

`8c6f9ed` (piu' il commit di questo documento): **336 test verdi**, 17/17 bot
freschi, **0 errori**, 0 posizioni, dashboard a **0 problemi**, working tree
pulito su mc2, nuvola e MARCODG1.
