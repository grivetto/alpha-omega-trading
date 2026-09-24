# 53 — Scaletta per rendere produttivo il progetto Denaro

Data: 2026-09-23. Definizione di "produttivo" data dal proprietario:
**netto positivo verificato fuori campione, dopo fee e slippage, ripetibile.**

Metodo: quattro audit in sola lettura (economia/edge, storia delle decisioni, igiene del
repo, operazioni) più i documenti 17-52. Ogni voce porta la sua prova. **Niente qui è
stato eseguito o committato**: è una proposta, e le azioni sulla flotta vanno approvate
una per una.

> ⚠️ **Il live non va riaperto prima di aver chiuso la sezione 0.6.** L'audit statico ha
> trovato tre difetti del percorso di esecuzione che possono liquidare l'intero saldo di un
> conto, lasciare una posizione aperta senza stop, o duplicare un ordine. Non sono ipotesi:
> sono righe di `orchestrator.py` con il numero di riga accanto. Che la fase trend deployata
> abbia fatto **0 trade reali** (fatto 8) è coerente: quel percorso non è mai stato esercitato
> con denaro vero, e non è pronto per esserlo.

---

## 53.0 Lo stato di partenza, in nove fatti verificati

| # | fatto | prova |
|---|---|---|
| 1 | Il live è **fermo dal 2026-08-28** | `.deepseek/stella_to_hermes6.txt` |
| 2 | La scommessa da 42 € è **chiusa**, rientro ~in pari | `docs/49` §49.3 |
| 3 | Il capitale è **109,99 €** in EUR sul master OKX, liquido, decisione rinviata | `docs/49` §49.6 |
| 4 | La telemetria **mentiva**: dashboard +74,99 € contro ~-0,30 reali | `.cm8.txt` |
| 5 | L'equity veniva **sostituita con un valore inventato**: drawdown, circuit breaker e stop calcolati su un numero falso | `.cm7.txt` |
| 6 | L'alpha del trend è **+34,98% (t=4,51) a fee zero** e **-1,97% (t=-0,30) a 0,35%/lato** | `docs/17:436-438` |
| 7 | La copia locale del repo è **5 commit indietro** rispetto a origin/main | `git rev-list --left-right --count origin/main...HEAD` → `5 0` |
| 8 | La fase trend deployata ha fatto **0 trade reali** | `docs/37:85`, `docs/41:96` |
| 9 | I 17 bot trend puntano a **sub-account svuotati** il 22/09: i config non sono stati aggiornati | `docs/49` §49.6, `docs/48` §48.5, `config/node_*.yaml` |

I punti 4, 5 e 7 sono la ragione per cui questa scaletta comincia dalla verità e non
dalla strategia: **oggi il progetto non è in grado di misurare se stesso.**

---

## P0 — Verità misurabile

Senza questa fase ogni decisione successiva è fondata su numeri che possono essere falsi.

### 0.1 Riconciliare il repo con origin — *rischio: basso, procedura verificata*

- **Cosa**: la copia locale è 5 commit indietro. Cinque file esistono sia come locali non
  tracciati sia come versioni già committate sul remoto, ma sono **byte-identici** a
  origin (verificato per blob hash, non per hash di file: `.gitattributes` normalizza i
  fine-riga). Un `git pull` si bloccherebbe sulla sovrascrittura di file non tracciati.
- **Procedura sicura**, in quest'ordine:
  1. `git fetch origin`
  2. rimuovere **solo** i 5 file identici a origin: `docs/45`, `docs/46`, `docs/47`,
     `docs/48`, `tools/scommessa.py` (nessuna perdita: il contenuto è quello del remoto)
  3. `git pull --rebase origin main`
  4. aggiungere e committare i **3 documenti solo locali**: `docs/49`, `docs/51`,
     `docs/52` con prefisso `[dsh]`
  5. **mai** `git clean -fd docs/`: cancellerebbe i punti 4 di sopra, che sono l'unica copia
- **Prova**: `git hash-object --path=<file>` uguale a `git rev-parse origin/main:<file>` per
  tutti e cinque; `docs/49/51/52` assenti da origin.
- **Chi**: `[dsh]` (`docs/`, `tools/` sono suoi per `protocollo_git.md`).
- **Fatto quando**: `git status` non mostra più untracked in `docs/` e `git log origin/main`
  contiene i tre documenti.

### 0.2 Sbloccare il documento invisibile

- **Cosa**: `docs/50` è ingoiato da `.gitignore:77` (`docs/*moa*`): un documento reale del
  progetto non è versionabile e non lo sarà mai, in silenzio.
- **Come**: restringere la regola a ciò che si voleva davvero escludere (es. `docs/hermes-moa-*`),
  oppure rinominare il documento fuori dal pattern.
- **Prova**: `git check-ignore -v docs/50_hermes_moa_free_mc2_2026-09-23.md` →
  `.gitignore:77:docs/*moa*`.
- **Chi**: da concordare con Hermes (`.gitignore` è alla radice, non assegnato a nessuno dei due).

### 0.3 Applicare i commit preparati e mai applicati

- **Cosa**: `.cm7.txt` e `.cm8.txt` alla radice sono messaggi di commit pronti (telemetria
  onesta, equity non più inventata, live/paper separati) che non sono stati applicati.
  Il codice potrebbe essere già dentro, ma la storia no.
- **Prova**: presenza dei due file; `git log --oneline -25` non contiene quelle voci.
- **Fatto quando**: i due messaggi esistono come commit, o i file sono rimossi perché già
  rappresentati.

### 0.4 Una sola fonte di verità per equity e PnL, riconciliata contro l'exchange

- **Cosa**: due difetti distinti hanno prodotto numeri falsi (`.cm7`, `.cm8`): PnL paper
  sommato al reale, bot "stale" contati come attivi, equity fuori range sostituita con
  `cfg.capital`. La dashboard pubblica è la superficie che il proprietario legge.
- **Come**: un solo calcolo dei totali, live e paper separati, gli stale esclusi ed elencati;
  **equity grezza o tick saltato**, mai un sostituto; riconciliazione periodica contro
  `fetch_balance` dell'exchange, con lo scarto pubblicato.
- **Prova del bisogno**: `.cm7.txt` (migliaia di warning/giorno con `equity=12.0000` su
  `0.0005` reali), `.cm8.txt` (`node_total_pnl` 74,99 → 0,0).
- **Causa a livello di codice** (audit statico): `EquityTracker` (`domain/equity.py:37`), cioè
  la telemetria che dovrebbe essere la fonte autorevole, **è usata solo dai test**. Il percorso
  live pubblica invece `risk_state.perf` (`orchestrator.py:1231-1241`), che è esattamente la
  fonte per-trade che `equity.py:5-8` dichiara inaffidabile. Finché è così, questa non è una
  voce di dashboard: è un difetto di architettura.
- **Chi**: `[hermes]` (`denaro/infrastructure/`, servizi, dashboard).

### 0.5 Il primo trade reale: provare che il percorso di esecuzione funziona

- **Cosa**: la fase trend deployata ha fatto **0 trade reali** (`docs/37:85`, `docs/41:96`) e
  il primo trade reale non è mai stato verificato (`docs/41` §41.5, `docs/37` §37.7,
  `docs/28` §28.5, `docs/29` §29.4; il commit `d8cf5e0` parla di "un buy non riempito" senza
  esito documentato). **Non sappiamo se il percorso ordine→fill→stop funziona davvero.**
- **Come**: un singolo trade di dimensione minima, con verifica a valle di ordine inviato,
  fill, stop piazzato, slittamento e fee pagata — riusando `tools/verifica_trade` e il
  verificatore del primo trade (commit `5489d68`).
- **Fatto quando**: esiste un documento con ordine, fill, fee e slittamento misurati.
- **Chi**: `[dsh]` prepara la verifica, l'esecuzione è una decisione del proprietario.

### 0.6 I difetti del percorso live — *bloccano la riapertura*

Dall'audit statico di `denaro/` (`orchestrator.py`, percorso live `336-623`). Tre difetti
indipendenti, ognuno sufficiente a perdere denaro:

**R1 — Lo stop vende l'intero saldo dell'asset, non la size della posizione.**
`orchestrator.py:879-882` legge `amount` come saldo **libero** del base e vende quello
(`:891`), ignorando `state.posizione_aperta["amount"]` che pure è tracciato (`:1099-1101`).
Con due bot sullo stesso sub-account — configurazione ammessa come P0 in
`denaro_node.py:450-456` — o con asset detenuti a mano, **lo stop di un bot liquida a mercato
tutto l'asset del conto.**

**R2 — Dopo uno stop-loss il bot resta disarmato o bloccato.**
`_trigger_stop_loss` imposta `stop_loss_triggered=True` (`:941`) e `trading_paused=True`
(`:942`), ma il ramo di tick pretende `not stop_loss_triggered` (`:361-364`). Se
`sell_market` fallisce (`:1033-1038`) il flag non viene mai riazzerato: il commento "il retry
al prossimo tick lo risolverà" è **falso** e la posizione non si chiude. Peggio:
`trading_paused` non esiste in `BotState` (`:134`) e `_propagate_safemode` lo sovrascrive a
ogni cambio di livello RAM (`denaro_node.py:478`): quando il guardian torna `nominal` il bot
**riprende a piazzare ordini con lo stop-loss permanentemente disabilitato**, perché il flag
resta in `state.json` e nessuno lo azzera.

**R3 — Ordini senza idempotenza, stato salvato dopo il piazzamento.**
Zero occorrenze di `clientOrderId`/`clOrdId` in tutto `denaro/`. I buy partono a `:605-618` e
lo stato è persistito solo a `:623`: un crash tra i due lascia **ordini vivi non tracciati**.
Il recupero `_rebuild_from_exchange` (`:246-284`) **inventa** `entry_price = price*0.99` per
le sell (`:278`) e `level: 0` per i buy (`:271`), falsando PnL e invariante di griglia dopo
ogni riavvio. Correlato: l'`except TypeError` a `:445-449` riesegue `policy.decide` con la
firma legacy se il TypeError nasce **dentro** una policy ⇒ doppia esecuzione di codice
stateful.

**Mancanze collegate**, da chiudere nella stessa tornata: nessun `amount_to_precision` negli
adapter (`okx.py:83`, `kraken.py:63` usano solo `min_amount`/`min_notional`); nessuna
contabilizzazione dei **partial fill** (`filled`/`remaining` non usati in
`denaro/application/`: un ordine parzialmente eseguito e poi cancellato esce dallo stato a
`:1131`/`:1170` lasciando PnL e inventario divergenti); nessun ledger **per bot** (due bot
sullo stesso conto condividono l'equity e si fermano a vicenda); nessuna **curva equity
persistita** (Sharpe e drawdown onesti non sono calcolabili in produzione).

**Criteri di accettazione eseguibili** — `denaro/tests/test_rischi_capitale.py`: 6 test che
descrivono il comportamento voluto e che **oggi falliscono**. Verificati in esecuzione
(1,1 s, nessuna rete, nessun file: `make_bot` costruisce il `BotTask` senza
`state_path`/`journal_path`/`health_path`, quindi girano anche dove gli altri test di
integrazione non riescono per permessi sulle temp dir). Prove ottenute eseguendoli:

| test | evidenza |
|---|---|
| R1 monitorato | ha venduto `[1.0]` invece di `[0.25]` → **liquida l'intero conto** |
| R1 stop-loss di bot | idem: il difetto è in **due** punti di vendita, non uno |
| R2 retry | `assert 1 > 1` → il tick successivo non ritenta la chiusura |
| R2 flag in memoria | con un controllo che dimostra che il banco piazza davvero, il trattamento piazza 1 ordine **con lo stop attivo e persistito** |
| R3 prezzo d'ingresso | recuperato `99.0` da `price*0.99`: fabbricato, non misurato |
| R3 idempotenza | `create_limit_order` accetta solo `symbol, side, amount, price` |

**Correzioni proposte** (da applicare in `application/`, previo accordo con Hermes):

- **R1** — in entrambi i punti vendere la size tracciata, non il saldo:
  `amount = min(free_base, float(pos.get("amount") or 0.0))`. Se il libero è **minore** della
  size, vendere il disponibile e **scrivere lo scarto nel journal** (chiusura parziale),
  invece di vendere tutto in silenzio. Se `posizione_aperta` manca o è zero, **non vendere**:
  journal `stop_no_position` e uscire — meglio una posizione da riconciliare che un conto
  svuotato.
- **R2a** — sul fallimento della vendita ripristinare il flag, come già fa il guard di spread
  poche righe sopra (`:994`, `# riprova`): la funzione oggi gestisce correttamente un
  fallimento e scorrettamente l'altro. Il commento a `:1036-1038` va reso vero o rimosso.
- **R2b** — il blocco dei nuovi ordini non può dipendere da un flag in memoria: a `:498`
  bloccare su `self.trading_paused or self.state.stop_loss_triggered`, così un overwrite
  esterno di `trading_paused` non può riabilitare il trading con lo stop disabilitato.
- **R3a** — nel recupero marcare la sell come `entry_unknown: True` e **non** fabbricare il
  prezzo (`entry_price = None`). Un PnL che non si può misurare si segnala come non
  misurabile, non si inventa.
- **R3b** — aggiungere `client_order_id` a `create_limit_order` su tutti gli adapter, con una
  chiave deterministica da `(bot_key, level, side)`, così un riavvio riconosce l'ordine; e
  persistere l'id **appena** l'exchange lo restituisce, non a fine tick.

- **Fatto quando**: i 6 test di `denaro/tests/test_rischi_capitale.py` passano, e i test di
  integrazione del tick girano end-to-end senza `PermissionError`.
- **Nota**: l'audit ha potuto eseguire `pytest denaro/tests -q` → **63 failed, 270 passed,
  3 skipped, 50 errors**. Le cause visibili sono ambientali (permessi sulle temp dir della
  sandbox), quindi ~113 test restano **non verificati**, non necessariamente rotti.
  `ruff` dà 20 errori, tutti fuori da `denaro/` (che è pulito), **ma uno è nello scope della
  CI** (`scripts/archive_stale_health.py:33`, F541) ⇒ il job di lint è **rosso oggi**.

---

## P1 — Il cancello, eseguito davvero

### 1.1 Il cancello esiste già: renderlo un comando

- **Cosa**: `docs/47.2` definisce **6 prove** (lookahead, walk-forward, blocchi, costo +50%,
  Monte Carlo al 5° percentile, universo senza i migliori 3 asset) e il gate OOS è già
  codificato in `denaro/research/eval.py:1143-1155` (≥3 fold, ≥75% positivi, mediana OOS>0,
  ≥30 trade OOS, composto>0, alpha composto>0).
- **Problema**: è un insieme di funzioni dentro un file da 48 KB, invocato da decine di
  script diversi. Non è un comando unico, e quindi non è un cancello.
- **Come**: **una** entry point che prende un candidato e restituisce `passa`/`non passa`
  con le 6 prove in tabella e la prova che l'ha bocciato.
- **Fatto quando**: lo stesso candidato, rieseguito, dà lo stesso verdetto.

### 1.2 L'unico esperimento mai provato

- **Cosa**: trend a **volatilità targettizzata** con pesi consapevoli delle correlazioni su
  universo largo (`docs/47` §47.3, il punto di Carver). Dichiarato "l'unico non ancora
  provato" e mai misurato. Attacca direttamente l'episodicità di `docs/43`.
- **Perché proprio questo**: è l'unica idea in tutta la ricerca che non sia già stata
  bocciata coi numeri, e il suo bersaglio è il difetto misurato (il rendimento sta in 1
  blocco su 3).
- **Come**: misurato con il cancello di 1.1, sugli stessi dati (77 serie 4H, 56 serie 1D).
- **Fatto quando**: esiste un verdetto, **anche se è no** — un no coi numeri chiude la
  domanda e libera il progetto.

### 1.3 Fermare la ricerca una-tantum

- **Cosa**: `tools/` contiene ~65 script `trend_*.py` dello stesso giorno e `.pytmp/`
  centinaia di file; la ricerca si è frammentata in esperimenti non riproducibili.
- **Perché conta**: un risultato che non si può rieseguire non è un risultato, è un aneddoto.
- **Come**: consolidare ciò che serve in una pipeline versionata sotto `denaro/research/`;
  il resto si archivia dichiarandone l'esito nel documento che lo ha prodotto.
- **Chi**: `[dsh]` (`tools/`, `denaro/research/`).

---

## P2 — Economia: la leva che cambia il segno

Il vincolo singolo non è la strategia: è il **pedaggio per giro** (0,70% taker OKX EEA
Lv1, 0,778% effettivo con spread) **più l'assenza di uno strumento short**.

| prova | numero |
|---|---|
| Trend sul 4H variando **solo** la fee: 0,35% → 0,05% per lato | **3/24 → 20/24** config robuste |
| Trend sul 1D variando la fee | 14/24 → 18/24 (quasi insensibile) |
| Robustezza dell'ensemble: metà short vs metà long-only negoziabile | **4/5 blocchi vs 3/5** |
| Rendimento: ensemble vs config singola long-only | +9,18% vs +10,81% |

### 2.1 Accesso a short/derivati — la mossa a costo zero

- **Cosa**: `acctLv 2` su OKX (o un venue UE con derivati) rende negoziabile la metà
  robusta dell'edge. È **l'unica leva che cambia il segno del risultato** e non costa nulla.
- **Stato**: bloccata lato account (`docs/44` §44.3: OKX EEA resta `acctLv 1`, Bybit EU ha
  chiesto la MiFID II). Monitoraggio MiFID II Bybit EU aperto dal 18-09.
- **Azione**: verificare oggi lo stato del livello account e le condizioni d'accesso, e
  mettere la verifica in monitoraggio invece di lasciarla a una nota.
- **Rischio**: nullo finché non si opera. Va deciso **prima** di qualunque altra cosa in P1,
  perché se la leva si apre, la strategia da validare cambia (include lo short).

### 2.2 Fee

- **Cosa**: sul 4H la fee è l'unica variabile che conta; sul daily quasi no. Migrazione a
  Bybit EU **non giustificata** per il daily (+0,36 punti su 2,5 anni, `docs/39`).
- **Conclusione**: non è una strada da riaprire per il daily; diventa rilevante solo se si
  torna sul 4H, e solo insieme a 2.1.

### 2.3 La decisione sul capitale è del proprietario, e va presa

- **Cosa**: 109,99 € sul master. La matematica è spietata e va detta: **+7%/anno fa 7,7 €
  su 110 €** e 700 € su 10.000 € (`docs/17:627-641`). La capacità utile misurata è
  1.000-3.000 € (`docs/27-36`).
- **Le due opzioni, esplicite**:
  - **(a) banco di prova**: capitale simbolico, obiettivo = **dimostrare** il metodo OOS.
    A questa dimensione il risultato economico è irrilevante per costruzione.
  - **(b) capitale vero**: allora il primo lavoro non è la strategia ma la dimensione e la
    struttura di costo (2.1 + 2.2), perché sotto una soglia il trading non è economicamente
    sensato qualunque sia l'edge.
- **Perché è urgente**: finché la decisione è rinviata, ogni lavoro successivo è sospeso a
  un "ma con quanto?". È rinviata da `docs/48` §48.5 (6 giorni).
- **Chi**: il proprietario. Nessun agente può deciderlo.

---

## P3 — Operabilità

Fatti dall'audit SRE (sola lettura locale). Processi vivi, saldi e stato dei servizi **non**
sono verificabili dal repo e restano "dichiarati nei documenti".

### 3.1 Urgente — i config non sanno dov'è il denaro

- **Cosa**: i tre config live (`config/node_mc2.yaml`, `node_nuvola_trade.yaml`,
  `node_marcodg1_xrp.yaml`) descrivono 17 bot trend con capitale 109,58 € distribuito sui
  sub-account. Ma il 22/09 il capitale è stato spostato tutto sul **master** e i sub-account
  sono vuoti (`docs/49` §49.6); i config non sono stati aggiornati (`docs/48` §48.5).
- **Rischio concreto**: chiunque riavvii la flotta oggi la fa partire con un sizing calcolato
  su un capitale che non c'è. Alla prima riapertura del live il sistema opererebbe su una
  premessa falsa — lo stesso genere di errore che `docs/23` aveva già prodotto.
- **Come**: allineare i config alla realtà **prima** di qualunque riavvio, oppure dichiarare
  la flotta formalmente dismessa. Non può restare a metà.

### 3.2 Il resto, in ordine di rapporto valore/rischio

| # | voce | prova |
|---|---|---|
| 1 | `docs/45-52` e l'ops di `.pytmp/` **non sono in git**: i piani di rollback esistono solo su disco | `git ls-files docs` si ferma a `44`; `.gitignore:65` |
| 2 | **Tre auto-heal concorrenti** che si contendono le stesse unit | `zabbix_healer.sh`, `push_metrics._heal_remote`/`heal_if_stale`, `zabbix/denaro_heal.sh` |
| 3 | Unit su **root legacy** (`/home/*/denaro_node_app`) mentre i config vivono nel checkout | `systemd/denaro-node-{mc2,nuvola,paper,trend}.service`, `denaro-feeder-mc2.service` |
| 4 | Password Zabbix `Admin/zabbix` **hardcoded nel codice** (e duplicata, e come default in un healer) | `zabbix/push_metrics.py:19-21`, `tools/zabbix_push_metrics.py`, `zabbix_healer.sh:9` |
| 5 | L'health server di mc2 conosce **1 bot su 7** (`BOTS={"doge"}`) | `health_server_mc2.py` |
| 6 | Il drift check non copre le unit né i due config live di nuvola/MARCODG1 | `check_fleet_drift.sh` |
| 7 | Ledger **senza fee** → il PnL pubblicato è lordo | `docs/15` §3.8 |
| 8 | Quattro `.env` OKX, di cui uno revocato e uno legacy **con scope trade attivo** | `docs/15` §3.6 |
| 9 | Feeder ZMQ in ascolto su `0.0.0.0:5557/5558` e non monitorato | `mc2_feeder.py` |
| 10 | Nessun trigger su `tailscaled`, da cui dipende tutto il monitoraggio | `docs/51` §51.6.1 |
| 11 | `_progetto_denaro.md` è **obsoleto**: le sue unit `denaro-v3` non esistono tra i 22 `*.service` | confronto con `systemd/` |
| 12 | `.pytmp/` contiene script che piazzano ordini e **prelievi reali senza dry-run di default**, e non è in git (665 file, 487 `.py`) | `chiudi.py:22`, `liquidate.py:34`, `okx_rientro.py:136`, `passo_c.py:26` (`private_post_asset_withdrawal`) |
| 13 | Quattro versioni divergenti del percorso live (~1800 righe) più copie morte identiche ai moduli canonici | `.pytmp/orch_r26.py`, `orch_local.py`, `orch_branch.py`; `.pytmp/{grid,policy,sizing}.py` identici per MD5 |

### 3.3 Direzione

Un deploy ripetibile e reversibile con artefatto pinnato; **un solo** healer allineato alle
unit reali; una sola fonte di verità per i segreti per host, senza credenziali nel codice; un
monitoraggio che allerta su ciò che è fermo invece di mostrarlo soltanto.

---

## P4 — Coordinamento fra i due scrittori

- **Cosa**: il protocollo c'è già ed è scritto bene (`protocollo_git.md`: `fetch` +
  `pull --rebase` prima di ogni commit, mai push forzati, firma `[dsh]`/`[hermes]`,
  proprietà per percorsi). **Non viene applicato**: nessuno degli ultimi 25 commit porta
  la firma, e la copia locale è 5 commit indietro.
- **Problema di fiducia aperto**: le dichiarazioni di esecuzione di un agente sono risultate
  non verificabili, alcune false (`.deepseek/stella_to_hermes6.txt`). Regola già stabilita
  dall'altra parte e da mantenere: **si dichiara solo ciò che è accompagnato dall'output di
  un comando realmente eseguito**, e si verifica ogni output prima di usarlo.
- **Come**: applicare il protocollo esistente. Non serve scriverne un altro.

---

## 53.9 Ordine di esecuzione proposto

**Prima ondata — si può fare subito, rischio basso, sblocca tutto il resto**
1. `0.1` riconciliazione del repo (senza questa, ogni lavoro nuovo rischia di essere perso)
2. `0.2` + `0.3` documento invisibile e commit non applicati
3. `3.1` allineare i config alla realtà: i 17 bot oggi puntano a conti vuoti
4. `0.6` correggere R1/R2/R3: sono il prerequisito di qualunque riapertura del live
5. `2.1` verificare lo stato dell'accesso a short/derivati (costo zero, cambia il segno)
6. `1.1` il cancello come comando unico

**Seconda ondata — dopo la prima**
7. `1.2` l'esperimento di Carver sotto il cancello
8. `0.4` + `0.5` telemetria riconciliata e primo trade verificato
9. `1.3` consolidamento della ricerca

**In parallelo, decisione del proprietario**
10. `2.3` banco di prova o capitale vero

**Regola che vale fino a chiusura di 0.6**: la flotta resta ferma. Il live non si riapre per
verificare se i difetti sono reali — si chiudono i difetti, e poi si verifica.

---

*Nota di metodo*: la scaletta nasce da quattro audit in sola lettura — economia/edge, storia
delle decisioni, igiene del repo, operazioni, più l'analisi statica del percorso live — e
dall'incrocio con i documenti 17-52. Gli audit non hanno toccato la flotta: tutto ciò che
riguarda processi vivi, saldi e stato dei servizi resta "dichiarato", non verificato.
Nessun file è stato committato.

---

## 53.10 Cosa NON riproporre (già chiuso coi numeri)

Grid (alpha -7,48%, t=-4,64, **negativa anche a fee zero**), momentum (0/5, -78,89%),
meanrev (0 trade), pullback maker-only (-61,35%, t=-16,76), cross-sezionale (alpha -8,61%),
piramide, filtro di regime, tetto `max_exposure`, stop più larghi, set canale 20,
allargamento o potatura dell'universo, 4H a fee spot, migrazione a Bybit EU per le fee,
market making (spread 0,0778% contro fee maker 0,10-0,20%), statistica arbitrage, HFT,
pipeline ML, riscritture v4-v7/ATLAS/ShadowGrid, 20 wallet airdrop sullo stesso seed.
Prove: `docs/17`, `docs/21`, `docs/26`, `docs/30-33`, `docs/39`, `docs/43`, `docs/47` §47.1.

---

## 53.11 Le tre domande a cui il progetto non ha ancora risposto

1. Esiste, per un conto UE, un accesso a short/derivati (o fee ~0,05%/lato) che renda
   negoziabile la metà robusta dell'edge? (`docs/43` §43.6, `docs/44`, `docs/40` §40.3)
2. Il trend a volatilità targettizzata passa il cancello? (`docs/47` §47.3)
3. Cosa si fa dei 109,99 €? (`docs/48` §48.5 p.2, `docs/49` §49.6)

Le prime due sono le uniche domande di ricerca ancora aperte. La terza è una decisione, non
una domanda, e blocca la scala di tutto il resto.
