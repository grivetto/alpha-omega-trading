# Denaro — analisi indipendente e validazione onesta (2026-09-11)

> Analisi read-only del sistema in produzione + nuovo harness di backtest che
> esegue **le policy reali** su **dati reali**, con fee, minimi di scambio e
> curva di equity **mark-to-market**.
> Nessun ordine è stato inviato; nessun file di produzione è stato modificato
> sulle macchine (le fix sono in locale, non deployate).

---

## 0. Verdetto in breve

1. **Il sistema non perde per la strategia: non opera.** Al 2026-09-11 entrambi
   i bot live su OKX hanno **0 buy aperti e 0 EUR liberi**: €23,57 di inventario
   interamente bloccato in 12 sell aperti (il più vecchio dal 08/09). L'unica
   attività è un **loop di 2 ordini dust rifiutati ogni 30 secondi per bot**,
   loggati come "piazzati".
2. **La causa è un bug di una riga**: gli adapter non chiamano `load_markets()`,
   quindi `min_amount_for()` e `min_notional()` restituiscono **0.0** e tutti i
   filtri di dimensione minima sono **disattivati in produzione**.
3. **La metrica che il progetto mostra non misura il rischio**: l'health riporta
   solo il PnL **realizzato** dei cicli chiusi ("100% win rate"). Il mark-to-market
   dell'inventario non è mai stato misurato: un bot che compra tutta la discesa
   appare "vincente" mentre il conto perde.
4. **Il backtest onesto ribalta la tesi del progetto**: su SOL/EUR, un anno di
   dati reali, la griglia **non batte il buy&hold in nessun regime** né in
   rendimento né in rendimento corretto per il rischio, e paga fee.
5. Realizzato complessivo reale del sistema dopo mesi: **≈ €0,38** (DOGE +0,033,
   SOL +0,131, XRP +0,220) su ~€50 di capitale.

---

## 1. Cosa è stato fatto

| Attività | Esito |
|---|---|
| Audit read-only delle 3 macchine (SSH) | servizi, processi, health, journal |
| Query read-only degli account OKX | saldi, ordini aperti, minimi di mercato |
| Replica del tick del bot sulle macchine | riprodotta la decisione reale della policy |
| Nuovo harness di backtest | `denaro/backtest/` — policy reali, dati reali, fee, minimi |
| Test dell'harness | 21 test (simulatore, parità, invarianti) |
| Backtest 90 giorni su tutte le config live | 10 run, 4 simboli, 2 exchange |
| Studio multi-regime 1 anno (SOL/EUR) | 4 finestre da 90 giorni |
| Fix dei difetti trovati (locale, non deployate) | adapter + logging, con test di regressione |

---

## 2. Stato reale del sistema (2026-09-11, 20:40 UTC)

### 2.1 Account OKX di mc2 (node `denaro-node-mc2`)

```
TOTAL: DOGE 262.946234 | SOL 0.044987 | EUR 0.380487
FREE : DOGE 0.0        | SOL 7.36e-07 | EUR 0.380487
OPEN ORDERS: 12   (DOGE/EUR sell x10, SOL/EUR sell x2)
  DOGE sell 25.8469 @ 0.07876   <-- DUPLICATO identico
  DOGE sell 25.8469 @ 0.07954
  SOL  sell 0.0225  @ 91.38 / 91.53
oldest order: 2026-09-08T03:21:49Z   (3 giorni)
```

Equity mark-to-market: ≈ €23,57. Equity "libera": €0,38.
Health dei bot: `buys: 0`, `sells: 10` (DOGE) / `2` (SOL), PnL +0,033 / +0,131.

I due bot **condividono lo stesso conto e riportano la stessa equity** (23.5675
per entrambi): chi legge la dashboard somma due volte lo stesso capitale.

### 2.2 Il loop di ordini impossibili

Journal di mc2, ogni ~30s, per entrambi i bot, da ore:

```
TICK DOGE/EUR: price=0.072910 free=0.3805 equity=23.5305
grid bilaterale DOGE/EUR: 2 sell ladder piazzati
TICK SOL/EUR: price=88.460000 free=0.3805 equity=23.5314
grid bilaterale SOL/EUR: 2 sell ladder piazzati
```

Replica read-only della decisione della policy vera (`GridPolicy.decide`) sui
dati correnti dell'account:

```
BOT DOGE/EUR  min_amount_for = 0.0   min_notional = 0.0
  free DOGE = 1.72e-07            open sell = 10
  decide() -> to_sell = [(9e-08, 0.074378), (9e-08, 0.075108)]
```

**2 ordini da 9e-08 DOGE (≈ 0,000000007 €) ogni tick**: l'exchange li rifiuta, il
bot li ritenta 2 volte ogni 30 s → **~5.760 tentativi di ordine autenticati al
giorno per bot**, senza che nessuno se ne accorga (il log dice "2 piazzati", e
`_last_error` viene azzerato a fine tick prima di finire in health).

### 2.3 Perché i filtri non filtrano

```
OKXAdapter.min_amount_for("DOGE/EUR") -> 0.0     # markets not loaded
dopo load_markets():  limits.amount.min = 10.0, precision 1e-06
```

`OKXAdapter.__init__` costruisce `ccxt.okx(...)` ma **non carica i mercati**;
`self.ex.market(symbol)` solleva `ExchangeError: markets not loaded`, e la
`except` restituisce `0.0`. Con `min_amount = 0.0` la condizione della policy
`(self.min_amount and amount < self.min_amount)` è **falsa per costruzione**:
il filtro non esiste. Ogni saldo dust (1e-07) diventa un "livello" valido.

### 2.4 Le altre macchine

- **nuvola**: nodo attivo con ETH/EUR + XRP/EUR, equity €25,58, 0 buy, 0 sell
  recenti, `free_quote` €5,47 (nessuna attività).
- **MARCODG1**: 3 nodi `denaro-node*` + `brain.main` + un aggregatore orfano in
  `/tmp/agg_new.py`; health `sol_kraken.json` **fermo al 24 agosto** mentre il
  processo è attivo (telemetria morta, non il bot).
- `denaro-node-trend.service` (paper) e `otf-trader.service` girano in parallelo.

---

## 3. Difetti trovati (con evidenza)

| # | Difetto | Evidenza | Impatto |
|---|---|---|---|
| B1 | Adapter senza `load_markets()`: minimi ordine = 0.0 | query live: `min_amount_for = 0.0` vs reale 10.0 | filtri disattivati, ordini dust |
| B2 | Ladder dust ritentato all'infinito, loggato come successo | journal ogni 30s + replica `decide()` | ~5.760 ordini falliti/giorno/bot |
| B3 | `_last_error` azzerato a fine tick | `orchestrator.py` (fix applicata) | errori invisibili in log e health |
| B4 | PnL solo realizzato, mai mark-to-market | health: "+0,033, 100% WR" con equity ferma | rischio invisibile, decisioni sbagliate |
| B5 | Sizing senza fee: `per_level` non copre `amount×prezzo×(1+fee)` | backtest: 63-4.218 ordini rifiutati per run | griglia incompleta + API sprecate |
| B6 | Circuit breaker su equity mark-to-market | 51-85% dei tick bloccati in mercato ribassista | il bot si spegne per settimane, restando esposto |
| B7 | Churn di cancellazioni | 262 cancel / 399 place (SOL 60d) | API + ordini fantasma |
| B8 | Entropia operativa | 3 macchine, 4+ nodi, brain, servizi duplicati, orfani | diagnosi difficile, capitale frammentato |

B1, B2, B3 sono stati **corretti in locale** (non deployati): vedi §6.

---

## 4. Evidenze dal backtest onesto

Metodo: barre 5m reali (OKX EEA), fee di config, `min_amount`/`min_notional`/
precision **reali del mercato**, ciclo identico a `BotTask.tick`, equity
mark-to-market, nessun round-trip regalato nella stessa barra, fill al prezzo
limite.

### 4.1 Le config in produzione (90 giorni)

| config | coppia | strategia | capitale | rendimento | buy&hold | **alpha** | maxDD | DD hold | Sharpe | cicli | WR cicli | rifiutati |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mc2 | DOGE/EUR | grid | €12 | **+0,94%** | +15,72% | **-14,78%** | 8,4% | 18,9% | 0,34 | 24 | 79% | 347 |
| mc2 | SOL/EUR | grid | €12 | **+11,92%** | +34,77% | **-22,85%** | 7,1% | 11,2% | 2,19 | 49 | 96% | 721 |
| paper | ADA/EUR | grid | €200 | +7,24% | +20,43% | -13,19% | 21,8% | — | 0,85 | 71 | 66% | 33 |
| paper | SOL/EUR | grid | €100 | +10,52% | +34,77% | -24,25% | 7,5% | — | 2,38 | 64 | 91% | 628 |
| paper | XRP/EUR | grid | €100 | **-3,77%** | +18,94% | **-22,71%** | 20,2% | 23,2% | -0,13 | 27 | 85% | 537 |
| paper | ETH/EUR | adaptive | €100 | +6,59% | +51,03% | -44,45% | 4,4% | — | 1,68 | 24 | 92% | 2.312 |
| paper | DOGE/EUR | adaptive | €100 | **-4,26%** | +15,72% | -19,98% | 11,5% | — | -0,51 | **0** | — | 4.218 |

Lettura: **l'alpha è negativa in tutte le config** (-13% … -44%). XRP chiude a
-3,77% con **win rate dei cicli dell'85%**: è esattamente l'illusione da cui
nasce la narrativa "100% WR".

### 4.2 Studio multi-regime — SOL/EUR, 4 finestre (1 anno)

| finestra | giorni | rendimento | buy&hold | alpha | maxDD | DD hold | Sharpe | Sharpe hold | tick bloccati (CB) |
|---|---|---|---|---|---|---|---|---|---|
| w0 (rialzo recente) | 60 | **+12,98%** | +34,77% | **-21,79%** | 6,7% | 11,2% | 3,02 | 3,58 | 0,2% |
| w1 (ribasso) | 90 | **-25,22%** | -24,18% | -1,03% | 34,7% | 38,4% | -1,85 | -1,35 | **82,7%** |
| w2 (ribasso) | 90 | **-25,51%** | -27,03% | +1,52% | 45,3% | 54,8% | -1,28 | -1,07 | **51,4%** |
| w3 (crash) | 90 | **-44,05%** | -46,85% | +2,79% | 45,9% | 50,8% | -2,33 | -2,36 | **85,1%** |

Lettura:

- **In salita** la griglia rinuncia a ~22 punti di rialzo.
- **In discesa** perde quasi quanto il mercato (+1,5 / +2,8 punti di "alpha"
  contro perdite del 25-44%) e il drawdown è simile: **non è una copertura**.
- Il piccolo vantaggio in ribasso arriva dal **circuit breaker che blocca il
  trading** per il 51-85% del tempo: la "protezione" è *non fare nulla*, mentre
  l'inventario resta comunque esposto al mercato.
- **Fee reali**: 0,24%-1,22% del capitale per finestra (≈1-5%/anno). Su €25 sono
  €0,25-1,00 all'anno di commissioni, contro **€0,38 di PnL realizzato in un anno**.

### 4.3 Il numero che mancava

Il sistema non ha mai misurato il rendimento sull'equity. L'harness lo fa, e il
risultato è che la strategia live è **dominata dal semplice buy&hold** su questi
asset in tutti i regimi testati. Non è una questione di parametri: è la natura
di una griglia spot con fee dello 0,1-0,26% per lato su asset che trendano.

---

## 5. Cosa è stato costruito: `denaro/backtest/`

| file | ruolo |
|---|---|
| `denaro/backtest/data.py` | download/pagina/cache OHLCV (OKX EEA, Kraken) + specifiche reali di mercato |
| `denaro/backtest/sim.py` | exchange simulato: fill sui limiti, path intrabar, fee, min_amount/min_notional, **free vs locked** (deadlock), mai saldi negativi |
| `denaro/backtest/runner.py` | replica del ciclo `BotTask.tick` (equity → stop-loss → CB → decide → preflight → place → fill) usando `PortfolioManager` e `RiskManager` del progetto |
| `denaro/backtest/metrics.py` | metriche oneste: equity MTM, maxDD, Sharpe, Calmar, realizzato vs non realizzato, fee drag, esposizione, **benchmark buy&hold** |
| `denaro/backtest/__main__.py` | CLI: singolo bot, interi node config, grid search, finestre storiche |
| `denaro/tests/test_backtest.py` | 14 test: fill, rifiuti, free/locked, identità contabile, nessun round-trip intrabar |
| `denaro/tests/test_runtime_guards.py` | 7 test di regressione delle fix runtime |

**Parità col live**: le policy sono costruite da `denaro.denaro_node.build_policy`
(la stessa factory della produzione) e il ciclo è quello di `BotTask.tick`:
il backtest non può divergere dal live per costruzione.

Comandi:

```bash
# una config live, 90 giorni
python -m denaro.backtest --config config/node_mc2.yaml --days 90 --timeframe 5m

# grid search ordinata per rendimento mark-to-market
python -m denaro.backtest --config config/node.yaml --bot SOL/EUR --days 90 \
  --sweep levels=2,3,5 --sweep profit-target=0.01,0.015,0.02

# studio multi-regime (finestra spostata indietro nel tempo)
python -m denaro.backtest --exchange okx --symbol SOL/EUR --days 90 \
  --end-days-ago 180 --capital 12 --cash 23.57 --json out.json
```

I dati sono in cache in `backtest_data/` (gitignorato): un run è riproducibile
anche offline.

---

## 6. Fix applicate

| fix | file | effetto |
|---|---|---|
| A | `denaro/infrastructure/exchanges/okx.py`, `kraken.py` | `_ensure_markets()` pigro: limiti e precision **reali** disponibili; `invalidate_balance()` dopo ogni ordine; i filtri di minimo tornano a funzionare → il ladder dust sparisce da solo |
| B | `denaro/application/orchestrator.py` | il log del ladder riporta gli ordini **realmente accettati**; i fallimenti diventano un WARNING (`_note_error`, max 1/5 min) e restano in health; `_last_error` non viene più azzerato prima della scrittura; un prezzo non disponibile **blocca la decisione** e viene segnalato invece di tickare su 0.0 |
| C | `denaro/infrastructure/market_data.py` | il client REST dell'hub carica i markets (`_ensure_rest_markets`, lazy): il fallback REST di `get_price` funziona → i bot non restano ciechi se il WebSocket cade (era la causa di `price=0.000000`) |
| D | `denaro/infrastructure/mc2_feeder.py` | `inspect.iscoroutinefunction` al posto di `asyncio.iscoroutinefunction` (deprecato, rimosso in 3.16) |

**Deployate il 2026-09-13** su mc2, MARCODG1 e nuvola (dettagli in §9), con
backup `*.bak-<timestamp>` accanto a ogni file e md5 verificato.

Verifica: **nessuna regressione** — A/B con `git stash` dei 3 file su 7 suite di
test: identico risultato (31 failed / 49 passed / 23 error **prima e dopo**; le
failure sono artefatti dell'ambiente sandbox che nega la scrittura nelle
directory temporanee, non del codice). I 21 test dell'harness e delle fix
passano: `python -m pytest denaro/tests/test_backtest.py denaro/tests/test_runtime_guards.py`.

Effetto atteso in produzione delle fix (nessun cambio di strategia):
- gli ordini dust non vengono più pianificati (minimo OKX DOGE = 10);
- se qualcosa viene rifiutato, lo si vede nel log e in health;
- il numero di chiamate API di ordine scende da ~5.760/giorno/bot a ~0.

---

## 7. Raccomandazioni (in ordine di rapporto valore/rischio)

1. **Deployare le fix A e B** (nessun cambio di strategia, solo correttezza) e
   verificare dopo 24h che `orders_placed` non cresca e che `error` in health sia vuoto.
2. **Misurare il mark-to-market anche in produzione**: aggiungere all'health
   `equity_mtm`, `unrealized_pnl`, `inventory_notional`. Senza questo, ogni
   decisione futura si basa sull'unica metrica che il progetto ha dimostrato
   essere ingannevole (win rate dei cicli chiusi).
3. **Decidere consapevolmente cosa deve fare il capitale**: i numeri dicono che
   con €25-50 la griglia non batte il buy&hold in nessun regime e paga fee.
   Le opzioni oneste sono: (a) HODL, (b) griglia solo come disciplina di
   accumulo accettando il sottoperformance, (c) nuova strategia **validata
   prima** con l'harness (gate: alpha ≥ 0 e maxDD accettabile su almeno 4
   finestre, incluso un mercato ribassista).
4. **Nessun cambio di parametri live senza un run dell'harness**: il progetto ha
   una storia di 7 riscritture in 8 settimane senza validazione. Ora esiste lo
   strumento; va messo nel flusso (es. script `scripts/validate.sh` in CI).
5. **Ridurre l'entropia**: 4 nodi, 2 motori, `brain`, aggregatori duplicati e un
   processo orfano in `/tmp`. Consolidare su 1 nodo + 1 conto, spegnere il resto.
6. **Liberare l'inventario bloccato**: 12 sell aperti da giorni con prezzi +2-8%
   sopra il mercato tengono fermo tutto il capitale. Decidere: lasciarli,
   cancellarli, o riprezzarli — ma decidere, non lasciare che un bot dust loop
   sia l'unica attività del sistema.

---

## 8. Riproducibilità

- Dati: `backtest_data/*.csv` (5m, 90 giorni, OKX EEA) — rigenerabili con `--refresh`.
- Risultati: `backtest_out/*.json` (mc2, paper, trend, 4 finestre regime).
- Un anno di finestre SOL/EUR: `regime_w0..w3.json`.
- Strumento di riconciliazione: `denaro/scripts/fleet_reconcile.sh` (dry-run di default).

---

## 9. Verifica esecuzione 2026-09-13 e correzioni applicate

### 9.1 Correzione all'analisi precedente

- **MARCODG1 e nuvola NON avevano processi orfani**: i 3 nodi di MARCODG1
  (`denaro-node-trend-live`, `-trend`, `-paper`) e i 2 di nuvola girano come
  unità di **sistema** (`/etc/systemd/system`), regolarmente gestite. L'errore
  era mio: avevo interrogato `systemctl --user`, che non li vede.

### 9.2 Nuovi difetti trovati (con evidenza)

| # | Difetto | Evidenza |
|---|---|---|
| B9 | **Ogni config su mc2 girava DUE volte**: unità di sistema *e* unità utente con lo **stesso nome**, WorkingDirectory e config **diverse** (`alpha-omega-trading`: capital 12 / sell 2 — `denaro_node_app`: capital 23 / levels 5 / sell 5 / distanza 0,3%), **stesso conto OKX**, stessi file health | `ps -eo pid,ppid,etime,cmd` + `/proc/PID/cgroup`: `system.slice/denaro-node-mc2.service` **e** `user@1000.service/app.slice/denaro-node-mc2.service` |
| B10 | **Bot ciechi con prezzo 0**: `MarketDataHub.get_price` usa il client REST creato senza `load_markets()` → `fetch_ticker(symbol)` fallisce → `price=0.0` → il bot ticka "running", `error:""` e non opera. Le istanze col WebSocket funzionante avevano prezzi reali: la cecità dipendeva dal **fallback REST rotto** | journal: `TICK XRP/EUR: price=0.000000 free=5.4713 equity=25.2811` ogni 30s |
| B11 | **Strategia fantasma**: `strategy: chandelier_trend_rider` in `config/node_trend_live_kraken.yaml` non esiste in `build_policy` → **fallback silenzioso a GridPolicy** (health: `"strategy": "grid"`). L'operatore crede di far girare un trend-follower con chandelier exit | `denaro/denaro_node.py:87-154` + health |
| B12 | **Chiavi OKX non valide su nuvola**: 4 bot live in loop di errore ogni 30s | `AuthenticationError: okx Invalid OK-ACCESS-KEY, code 50111` |
| B13 | **Stop-loss con drawdown 93,5% e 54%** mai emersi in alcuna metrica (il PnL conta solo i cicli chiusi in TP) | journal: `stop_loss drawdown 0.9352 equity 1.8617` e `stop_loss drawdown 0.5406 equity 3.4` |
| B14 | **52 ore senza un singolo fill**: saldi identici byte per byte e 12 ordini immutati | `DOGE 262.946234 / SOL 0.044987 / EUR 0.380487` invariati dal 11/09; ultimo riempimento 2026-09-11T14:34Z |

### 9.3 Azioni eseguite (con verifica)

1. **Riconciliazione mc2** (`fleet_reconcile.sh --apply`): fermate e disabilitate
   le due unità **utente** duplicate → resta **una sola istanza per config**
   (verificato: 3 processi, 3 config, tutte unità di sistema).
2. **Deploy delle fix A–D** su **mc2, MARCODG1 e nuvola** (5 file per host), con
   backup `*.bak-<timestamp>` accanto a ogni file e **md5 verificato**.
3. **Restart** dei nodi (`denaro-node-mc2`, `-nuvola`, `-trend`, `-trend-live`,
   `-paper`) + `daemon-reload` su nuvola.
4. **Verifica post-deploy**:
   - `okx: 4640 mercati caricati` (mc2), `kraken: 1449 mercati caricati` (MARCODG1),
     `hub: markets REST caricati (4640 / 1449 simboli)`;
   - prezzi reali nei tick (`price=87.40`, `price=0.073000`, `price=1.169150`);
   - **nessun** più `grid bilaterale ... sell ladder piazzati`: il loop di ordini
     dust (~5.760 tentativi/giorno/bot) è **cessato**;
   - i bot restano correttamente inerti dove il capitale non basta
     (`PRE-FLIGHT BLOCK: per_level 4.1000 > free reale 3.6467` su Kraken).
5. **Nota di trasparenza**: il deploy ha portato con sé, dall'HEAD del repo, anche
   la fix `e4e6155` (fill dei buy processati **prima** del preflight — 3 righe in
   `orchestrator.py`). È l'**unica** differenza oltre alle mie modifiche
   (verificato con `git diff 951d537 581cc96`).

### 9.4 Stato finale (2026-09-13 21:15 UTC)

| Host | Nodi attivi | Fix | Cosa fa adesso |
|---|---|---|---|
| mc2 | `denaro-node-mc2`, `-nuvola`, `-trend` (1 istanza ciascuno) | OK | tick con prezzi reali, nessun ordine (free €0,38 < per_level €4) |
| MARCODG1 | `-trend-live`, `-trend`, `-paper` | OK | Kraken bloccato dal preflight (free €3,65 < per_level €4,10) |
| nuvola | `-nuvola`, `-trend` | OK | 4 bot OKX in errore: **chiavi non valide (50111)** |

### 9.5 Aperti (richiedono una decisione, non codice)

1. **nuvola**: chiavi OKX non valide → rigenerarle o disabilitare i 4 bot.
2. **mc2**: 12 sell aperti (il più vecchio dell'08/09) e €0,38 liberi → decidere
   se cancellare o riprezzare e ricostituire la liquidità.
3. **MARCODG1**: per_level (€4,10) > free (€3,65) → allineare capitale e livelli
   al saldo reale, altrimenti la griglia non parte.
4. **chandelier_trend_rider**: o si integra in `build_policy`, o si cambia la
   config: oggi è un grid travestito.
5. **Telemetria mark-to-market** in health (`equity_mtm`, `unrealized_pnl`):
   senza, gli stop-loss al 93,5% restano invisibili.

---

*Revisione: 2026-09-13. Le cifre provengono da dati di mercato reali e dagli
account di produzione; le azioni di §9.3 sono state eseguite e verificate.*
