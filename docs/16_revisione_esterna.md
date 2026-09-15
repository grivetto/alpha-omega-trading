# Revisione esterna del codice — 2026-09-15

> Revisore: agente esterno, **nessuna conoscenza pregressa** del progetto.
> Domanda: *affiderei denaro reale a questo software?*
> **Verdetto: no, non nello stato attuale.**
> Istantanea: commit `c1ab002` + modifiche non committate.
> ⚠️ Il tree era in **editing concorrente** durante la revisione
> (`orchestrator.py` è passato da 988 a 1089 righe): alcuni difetti possono
> essere già in correzione. Le righe citate valgono per l'istantanea letta.

Questo documento è la **specifica di hardening**. Ogni voce è un difetto con
evidenza `file:riga`, impatto in produzione e correzione minima.

---

## Verdetto in tre punti

1. **L'accounting non è riconciliato con l'exchange**: il PnL usa prezzi
   teorici e, per gli ordini ricostruiti, un costo *inventato*. PnL, win rate,
   Sharpe e profit factor non misurano il risultato reale.
2. **Il modello multi-bot su conto condiviso è rotto per costruzione**:
   equity, free balance, circuit breaker e stop-loss sono per-bot mentre il
   conto è per-account. Il limite è dichiarato in `denaro_node.py:382-388` e
   mai risolto.
3. **I controlli di sicurezza sono di facciata**: il rate limiter centralizzato
   non è centralizzato, il resource supervisor non misura la RAM di sistema, il
   cancel di emergenza non funziona su OKX, i filtri di minimo possono
   disattivarsi in silenzio.

---

## CRITICO

| # | Difetto | Evidenza | Impatto |
|---|---|---|---|
| **C1** | Più bot sullo stesso conto: equity/free/risk condivisi ma gestiti per-bot | `denaro_node.py:382-392`, `orchestrator.py:142,302-303`, `portfolio.py:99-106,135-136` | Stop-loss e CB di un bot reagiscono alle perdite di un altro; due bot impegnano lo stesso free; la dashboard somma due volte lo stesso capitale (osservato: equity 23.5675 identica per DOGE e SOL). **Fix:** ledger per-bot o un bot per conto. |
| **C2** | Il rate limiter "centralizzato" non è centralizzato | `rate_limiter.py:83-86` | `register()` crea sempre un bucket nuovo: N bot → N budget → il limite effettivo è N volte quello configurato. **Fix:** riusare il bucket esistente. ✅ corretto |
| **C3** | `PaperExchange` non riserva il cash: `free` ignora gli ordini aperti | `paper.py:139-156,109` | Con N buy aperti i fill portano il cash sotto zero. Riscontro reale: `free=-22.9795 equity=197.8694` su MARCODG1. Il paper è la base della "parità live": maschera l'over-commitment. **Fix:** riservare il notional alla creazione. |
| **C4** | Il PnL non usa mai il prezzo di fill reale | `orchestrator.py:882-904` | `proceeds = amount * target * (1-fee)` con il prezzo *pianificato*: fill parziali o migliori non vengono mai visti. **Fix:** usare `order["average"]`/`cost` o `fetch_my_trades`. |
| **C5** | PnL fabbricato per gli ordini ricostruiti | `orchestrator.py:242-245` | Un sell senza journal riceve `entry_price = price*0.99`: un costo inventato genera profitto inventato. **Fix:** marcare `unreconciled`, non stimare. |
| **C6** | Il filtro di notional minimo è di fatto disattivato su OKX | `orchestrator.py:706-713`, `okx.py:250-258` | Verificato live: `DOGE/EUR limits.cost.min = null` → `min_notional = 0.0` → in `preflight` la condizione `if min_notional > 0` è saltata. È il bug B1 di `docs/10`, sopravvissuto come soft-fail. **Fix:** fallback a `amount.min * price`; niente 0.0 su errore. |
| **C7** | `_guard_equity` può restituire il capitale di config come "equity vera" | `orchestrator.py:527-582` | Con lettura fuori range il bot prosegue con `equity = cfg.capital`: drawdown, CB e stop-loss calcolati su un numero inventato e stabile. **Fix:** su equity inattendibile non tradare. |
| **C8** | Stop-loss: se la vendita fallisce il bot resta congelato e la posizione aperta | `orchestrator.py:275-278,719-720,811-816` | `stop_loss_triggered` e `trading_paused` vengono impostati **prima** della vendita: se `sell_market` solleva, ai tick successivi la guardia è falsa e la posizione resta non gestita per sempre. **Fix:** separare `stop_requested` da `stop_completed`. |
| **C9** | `stop_loss_triggered` persistito su file: un drawdown transitorio disarma il bot per sempre | `orchestrator.py:958` + `_load_state` | Nessun percorso di riarmo. **Fix:** legare il flag alla posizione o prevedere riarmo esplicito. |

---

## ALTO

| # | Difetto | Evidenza | Note |
|---|---|---|---|
| **A1** | Pydantic scarta in silenzio 16 chiavi di config per bot | `config.py:63-121` vs `denaro_node.py:113-132,192-199` | Verifica empirica: `0/16` chiavi superstiti su `node_nuvola.yaml`, `node.yaml`, `node_mc2.yaml`. Il bot `DOGE/EUR strategy=irmr` gira con **tutti i default hardcoded**. |
| **A2** | Strategia sconosciuta → fallback silenzioso a `GridPolicy` | `denaro_node.py:81-156` | `chandelier_trend_rider` in produzione è diventato una griglia (B11 di `docs/10`). **Fix:** `ValueError` su strategia non riconosciuta. |
| **A3** | `except TypeError` come controllo di flusso per le firme di `decide()` | `orchestrator.py:354-363` | Un `TypeError` interno alla policy la fa rieseguire con firma diversa. |
| **A4** | Un errore di `fetch_order` mantiene un ordine "aperto" per sempre | `orchestrator.py:843-851` | `_resolved_status` → `"open"` su qualunque eccezione: un fill non riconciliato blocca il ciclo in silenzio. |
| **A5** | `_process_fills` eseguito due volte per tick | `orchestrator.py:451,507` | Seconda `fetch_open_orders` per bot per tick. |
| **A6** | `sell_market`/`cancel_order` non invalidano la cache del balance | `okx.py:274-276`, `kraken.py:206-208` | Dopo uno stop-loss si leggono saldi pre-vendita per 15 s. |
| **A7** | Il rate limiter può essere aggirato | `okx.py:145-148`, `kraken.py:90-91` | Dopo l'attesa non riacquisisce il token. `AsyncTokenBucket` esiste ed è codice morto. |
| **A8** | Il cancel di emergenza non è supportato su OKX | `okx.py:287-288`, `denaro_node.py:417-421` | Verificato: `cancelAllOrders() is not supported yet`. **Il SafeMode di emergenza non cancella nulla.** |
| **A9** | Fee opzionale con default 0.0 per i bot live | `denaro_node.py:349` | Un bot live senza `fee` calcola PnL senza commissioni. |
| **A10** | Nessuna validazione `profit_target > 2×fee` | `grid.py:111-113` | Un TP sotto il costo di andata/ritorno è perdita garantita a ogni ciclo. |
| **A11** | Il sizing non copre la fee | `grid.py:282-296` | `amount = per_level/buy_price`: l'ultimo livello non è finanziabile (test già esistente). |
| **A12** | Il cap VaR si disattiva quando la VaR è 0 | `risk.py:211` | `capital*0.02/(var+1e-10)` → con var=0 il cap è 2e8×capitale. ✅ corretto |
| **A13** | Kelly su P&L assoluti invece che su rendimenti | `risk.py:171-194` | `b = avg_win/avg_loss` dipende dalla dimensione dei trade. |
| **A14** | Il compounding diluisce il drawdown e disarma il CB | `risk.py:287-299` | `initial_capital` è denominatore del clamp e delle baseline. |
| **A15** | Tre denominatori diversi per lo stesso rischio | `orchestrator.py:547-548`, `risk.py:79,102,112` | Un'unica fonte in `CoreState`. |
| **A16** | Il resource supervisor non misura la RAM di sistema | `supervisor.py:105` | `ram_used = rss_processo / ram_totale`: con soglia 0.85 non scatterà mai. Il "zero OOM" del README non è implementato. |
| **A17** | Due metriche di RAM con le stesse soglie | `safemode.py:22-28` vs `supervisor.py:105` | I due guardiani possono contraddirsi. |
| **A18** | `load_markets` fallito → tutti i minimi a 0.0 | `okx.py:98-106,250-258`, `kraken.py:185-193,215-223` | Rete instabile al boot → filtri disattivati (B1 di `docs/10`, versione fail-open). |
| **A19** | `fetch_total_equity` somma tutto il conto e salta in silenzio l'invalutabile | `okx.py:214-230`, `kraken.py:155-170` | Equity sottostimata senza traccia → drawdown gonfiato. |
| **A20** | Cache del balance a 15 s usata per decidere | `okx.py:192-200`, `kraken.py:133-141` | Sizing su saldi vecchi fino a 15 s: con più bot è l'over-commitment di C1. |
| **A21** | `preflight` verifica un livello, non la somma | `portfolio.py:152-155` | Il tick poteva piazzare fino a `levels` ordini oltre il free. ✅ corretto |
| **A22** | `total_available`/`locked` per-simbolo, il conto no | `portfolio.py:70-97`, `orchestrator.py:302-303` | Il fattore 0.85 genera capacità virtuale che, sommata tra bot, supera il cash. |
| **A23** | `PaperExchange.fetch_order` su id ignoto restituisce `closed` | `paper.py:178-179` | Interpretato come FILLED → PnL fantasma. |
| **A24** | `PaperExchange` non implementa `min_amount_for` | `denaro_node.py:86-87` | Il paper non è paritario col live: il suo unico scopo. |
| **A25** | `create_limit_order` su paper restituisce un ordine rifiutato con `id=""` contato come piazzato | `paper.py:149-151`, `orchestrator.py:416-428` | Un rifiuto incrementa `ladder_ok` e inquina lo stato. |
| **A26** | `_on_emergency` non verifica l'esito del cancel | `denaro_node.py:412-428` | Vedi A8. |

---

## MEDIO

| # | Difetto | Evidenza |
|---|---|---|
| **M1** | `AtomicFile` atomico ma non durevole (niente fsync) | `storage.py:29-33` ✅ corretto |
| **M2** | Journal senza rotazione, riletto interamente a ogni avvio | `storage.py:67-81` |
| **M3** | `__len__`/`__iter__` del journal leggono tutto il file | `storage.py:83-87` |
| **M4** | Due fonti di verità per lo stesso PnL (journal vs `risk_state`) | `orchestrator.py:214-227` vs `906` |
| **M5** | La scala di vendita non verifica il notional minimo | `grid.py:248-259` (Kraken `cost.min = 0,45 €`) |
| **M6** | Un buy sopra il mercato non è mai "stantio" | `grid.py:126-127` |
| **M7** | Nuovi livelli indicizzati sul conteggio, non sui livelli occupati | `grid.py:269-306` |
| **M8** | `_note_error` conserva solo il primo errore del tick, max 1 log/5 min | `orchestrator.py:511-525` |
| **M9** | `run()` inghiotte ogni eccezione senza backoff né escalation | `orchestrator.py:994-1003` (chiavi invalide → loop silenzioso per giorni) |
| **M10** | `start_all` salta i bot senza ritentare | `orchestrator.py:1069-1072` |
| **M11** | Nessun `try/finally` sul ciclo di vita del Node | `denaro_node.py:441-453` |
| **M12** | `interpolate` lascia `${VAR}` letterale se la variabile manca | `config.py:33` |
| **M13** | Lo schema consente segreti nel file di config | `config.py:118-120`, `denaro_node.py:202-204` |
| **M14** | Reset giornaliero/settimanale con `max()` sulla baseline | `risk.py:84,92` ✅ corretto |
| **M15** | Divisione per baseline potenzialmente nulla | `risk.py:102,112,123` ✅ corretto |
| **M16** | `sizing_multiplier = 2.0` dopo 5 vincite consecutive | `risk.py:160-163` |
| **M17** | Il limite di perdita giornaliero si allenta in bassa volatilità | `risk.py:16` |
| **M18** | `MomentumPolicy` calcola EMA/RSI su tick (30 s), non su tempo | `momentum.py:38-45,63-81` |
| **M19** | `rsi_confirm` configurabile ma ignorato | `momentum.py:34` vs `77` ✅ corretto |
| **M20** | Kraken classifica ogni `EOrder:*` come transitorio | `kraken.py:83-84` (anche "Insufficient funds" ritentato 3 volte nel tick) |
| **M21** | `fetch_total_equity` fa una `fetch_ticker` per asset, ignorando l'hub | `okx.py:214-230`, `kraken.py:155-170` |
| **M22** | Scrittura SQLite di emergenza sincrona nell'event loop | `denaro_node.py:422-426` |
| **M23** | `_read_metrics`, `_cooldown_s`, `_last_check` morti | `supervisor.py:56-57,86-96` |
| **M24** | Log di tick a INFO per ogni bot ogni 30 s | `orchestrator.py:334` (causa della crescita anomala dei log) |

---

## BASSO

| # | Difetto | Evidenza |
|---|---|---|
| **B1** | `min_amount` restituisce sempre 0.0 (trappola) | `okx.py:93-96`, `kraken.py:210-213` |
| **B2** | Tre moduli di strategia morti (~530 righe, 0 riferimenti) | `asymvol_anchor.py`, `cycle_phase_grid.py`, `flowgate_grid.py` ✅ rimossi |
| **B3** | Docstring del package non veritiera | `denaro/__init__.py:3-8` ✅ corretto |
| **B4** | Tre implementazioni dello stesso ciclo di trading | `engine_solo_v33.py`, `engine_paper.py`, `application/orchestrator.py` |
| **B5** | Due simulatori con semantiche divergenti | `paper.py` vs `backtest/sim.py` (il secondo vieta il cash negativo, il primo no) |
| **B6** | `AsyncTokenBucket`/`async_bucket` codice morto | `rate_limiter.py:61-74,91-93` (ed è la soluzione di A7) |
| **B7** | `GridPolicy.effective_capital` non usata da `decide()` | `grid.py:87-89` vs `283` |
| **B8** | Tutte le strategie condividono `GridDecision` | `grid.py:56-70` |
| **B9** | Nove `except Exception` muti nella telemetria | `infra_aggregator.py:248,403,405,414,416,434,470,487,489,566,737,747`, `serve_dashboard.py:183` |
| **B10** | 189 clausole `except` nel package, molte con `pass` | pattern sistematico: "degrada in silenzio" |

---

## Invarianti NON coperti dai test

Ognuno avrebbe intercettato i difetti indicati.

1. Due `BotTask` sullo stesso conto non possono impegnare più del free → C1, A20, A22
2. Due adapter dello stesso exchange condividono lo **stesso oggetto** bucket (`is`) → C2 ✅
3. Paper/live: con ordini aperti `free == cash − notional_buy` e `cash >= 0` → C3
4. Il PnL usa il prezzo di fill reale → C4, C5
5. Round-trip di config: ogni chiave YAML sopravvive a `load_node_config` → A1
6. Una `strategy` non riconosciuta fa fallire l'avvio → A2
7. Un `fetch_order` fallito non perde un fill → A4
8. Un `TypeError` interno alla policy non la fa rieseguire con firma diversa → A3
9. Stop-loss: se la vendita fallisce, il tick successivo ritenta → C8
10. Il flag di stop-loss non spegne il bot per sempre senza asset chiuso → C9
11. Equity inattendibile ⇒ nessun ordine nel tick → C7
12. Il supervisore misura la RAM di sistema (90% reale) → A16, A17
13. Il cap VaR esiste anche con `var_95_1h == 0` → A12 ✅
14. Kelly è invariante alla scala delle posizioni → A13
15. Il drawdown non si diluisce dopo il compounding → A14
16. La cache del balance è invalidata dopo `sell_market`/`cancel_order` → A6
17. Il rate limiter non è aggirabile → A7
18. Il percorso di emergenza cancella davvero gli ordini, anche su OKX → A8, A26
19. `min_notional` non nullo su OKX quando `limits.cost.min` è null → C6
20. Journal con N record: `read_all` a tempo/memoria limitati → M2, M3
21. Crash-consistency di `AtomicFile` → M1 ✅
22. Invariante contabile end-to-end: `equity_iniziale + realizzato + unrealized == equity_exchange` a ogni tick → C4, C5, M4
23. `preflight` con `levels` livelli: il totale non supera il free → A21 ✅
24. Un order id sconosciuto non produce PnL su paper → A23
25. `PaperExchange.min_amount_for` esiste e filtra → A24

---

## Ordine di priorità suggerito

**C1, C2, C3** (correttezza strutturale) → **C4, C5, C6** (accounting) →
**C7, C8, C9** (risk) → **A1, A2** (config silenziosa) → **A16** (supervisor) →
il resto.

---

## Stato delle correzioni (2026-09-15, sessione di hardening)

Corretti in questa sessione, nei moduli non interessati dall'editing concorrente:

| Difetto | File | Test di regressione |
|---|---|---|
| C2 | `denaro/infrastructure/rate_limiter.py` | `test_review_fixes.py::test_c2_*` |
| A21 | `denaro/application/portfolio.py` | `test_review_fixes.py::test_a21_*` |
| M1 | `denaro/infrastructure/storage.py` | `test_review_fixes.py::test_m1_*` |
| M19 | `denaro/domain/momentum.py` | `test_review_fixes.py::test_m19_*` |
| A12, M14, M15 | `denaro/domain/risk.py` | `test_review_fixes.py::test_a12_*, test_m14_*, test_m15_*` |
| B2 | rimossi 3 moduli morti | — |
| B3 | `denaro/__init__.py` | — |

Suite eseguita: **111 passed** (`test_review_fixes`, `test_rate_limiter`,
`test_risk_p2`, `test_domain`, `test_policies`, `test_preflight`,
`test_backtest`, `test_runtime_guards`, `test_circular`, `test_hurst`).

**Non ancora corretto**: tutto il blocco C1, C3–C9 e la maggior parte degli A,
perché i file coinvolti (`orchestrator.py`, `grid.py`, `types.py`,
`denaro_node.py`, `config.py`, `supervisor.py`, gli adapter) erano **in
editing da una sessione concorrente** durante questa revisione. Serve
serializzare: un solo scrittore per volta sul package.
