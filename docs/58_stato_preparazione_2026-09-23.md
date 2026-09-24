# 58 — Preparazione per i 1.000 EUR: cosa è pronto e cosa no

Data: 2026-09-23. Chiusura del lavoro su `docs/53`-`57`. Ogni affermazione qui è **verificata
eseguendo**, tranne dove dichiarato diversamente.

---

## 58.1 Cosa è cambiato

Dodici turni di lavoro sul percorso che muove i soldi. In sintesi:

| difetto | stato | prova |
|---|---|---|
| **R1** lo stop vendeva l'**intero saldo** dell'asset invece della size della posizione | **corretto** in entrambi i punti di vendita | 2 test |
| **R2** uno stop fallito **non veniva mai ritentato**, e il blocco dei nuovi ordini era aggirabile dall'esterno | **corretto**: retry + blocco ancorato allo stato persistito | 2 test |
| **R3a** il recupero da exchange **inventava** `entry_price = price*0.99` | **corretto**: dichiara il PnL non misurabile invece di fabbricarlo | 1 test |
| **Q4** i fill parziali **sparivano** dallo stato; una posizione chiusa con meno del richiesto era sovrastimata del **43%** | **corretto**: si contabilizza il `filled` reale | 3 test |
| **Q5** `EquityTracker` esisteva ed era usato **solo dai test**; la curva si azzerava a ogni riavvio | **collegato e persistito** | 3 test |
| **Q6** nessun cap di esposizione a livello di conto (17 bot, nessuno vede la somma) | **implementato e testato**, hook nel tick | 8 test |
| **R3b** ordini senza chiave di idempotenza | **aperto** — vive in `denaro/infrastructure/`, territorio Hermes | 1 test **rosso** |

Più un effetto collaterale utile: **il lint della CI è tornato verde**. Era rosso per un `f`
prefisso superfluo in `scripts/archive_stale_health.py:33` (F541), un errore preesistente che
`docs/53` aveva registrato.

## 58.2 I criteri di accettazione

`denaro/tests/test_rischi_capitale.py` (12) + `denaro/tests/test_exposure.py` (8):

```
19 passed, 1 failed
```

L'unico rosso è `test_R3_gli_adapter_offrono_una_chiave_di_idempotenza`: asserisce che
`create_limit_order` accetti una chiave d'ordine. Oggi accetta solo `symbol, side, amount, price`.

**Verificato anche**: `ruff check denaro scripts` → *All checks passed*. E il conteggio della
suite esistente è **identico al baseline** (38 failed / 17 passed / 30 errors: quei fallimenti
sono ambientali, permessi sulle temp dir della sandbox, non causati da queste modifiche).

## 58.3 Cosa NON è pronto

Da dire senza addolcire, perché riguarda denaro vero:

1. **R3b, la chiave di idempotenza.** Un crash fra l'invio dell'ordine e il salvataggio dello
   stato lascia **ordini vivi non tracciati**. È l'ultimo dei tre difetti che bloccano la
   riapertura del live, e la sua correzione tocca gli adapter.
2. **Il cap di esposizione non è attivo.** Il registro è pronto e testato, l'hook è nel tick, ma
   **nessuno lo costruisce**: l'iniezione va fatta in `denaro_node.py`. Il guardrail esiste, non
   è operativo.
3. **La persistenza della curva equity non è verificata su disco.** La logica di round-trip è
   testata; il percorso reale no, perché la sandbox nega la scrittura nelle temp dir. Segue riga
   per riga il pattern di `risk_state_path`, che in CI è testato — ma è "credibile", non "provato".
4. **Ledger per bot**: assente. Due bot sullo stesso conto condividono l'equity e si fermano a
   vicenda.
5. **Riconciliazione contro l'exchange**: solo parziale (`_riconcilia_posizione`).
6. **Il backtest a 0,10% per lato non è stato rifatto** (vedi §58.4): senza, non sappiamo se la
   strategia è profittevole, solo che lo era a fee zero.
7. **Nessuno ha ancora eseguito un trade reale** con questo motore.

## 58.4 La leva più grossa non è nel codice

`docs/57` ha verificato di prima mano che OKX EEA pubblica **due** tabelle di fee spot:

| | maker / taker |
|---|---|
| senza account derivati (X-Perps) | 0,200% / **0,350%** |
| **con** account X-Perps | 0,0800% / **0,1000%** |

e che gli X-Perps sono disponibili per **tutti e 30 i paesi EEA** (KYC + *appropriateness
assessment* MiFID). Il pedaggio per giro passerebbe da ~0,70% a ~0,20%, e **lo short diventerebbe
possibile** — cioè la metà robusta dell'edge, oggi non negoziabile.

L'ostacolo sembra **operativo, non regolamentare**: OKX blocca l'attivazione finché il conto ha
posizioni aperte, ordini non riempiti o **bot in esecuzione**. Il progetto ha una sell aperta dal
2026-09-11 (`.cm8.txt`) e 17 bot configurati.

**Prima di qualunque altra cosa**: leggere il messaggio esatto con cui OKX blocca l'attivazione.
Costa zero ed è la diagnosi.

## 58.5 Perché il live NON va riaperto adesso

Tre ragioni indipendenti:

1. **R3b è aperto**: la riapertura era subordinata a R1/R2/R3 chiusi con prove. Due su tre sono
   chiusi.
2. **La semantica dello stop su griglia/trend è indecisa**: la correzione R1 è giusta per i bot
   trend (che tracciano la posizione) ma per una griglia disabilita di fatto lo stop. Finché non
   si sceglie, il comportamento della flotta attuale è **ambiguo**.
3. **L'economia non è ri-verificata** a 0,10%/lato: oggi l'unica misura disponibile dice che a
   0,35% il daily trend è **-1,97%**. Riaprire prima di rifare quel conto significa operare in
   perdita attesa.

## 58.6 Il lavoro non committato, e la rete di sicurezza

**24 voci** in `git status`; `orchestrator.py` ha **+216 / -24 righe**. Tutto non committato.

Non ho committato perché `git fetch origin` **fallisce in questa sandbox**
(`ssh: couldn't create signal pipe, Win32 error 5`), e il tuo protocollo impone
*"PRIMA DI OGNI COMMIT: git fetch origin, poi git pull --rebase origin main"*. Preferisco un
commit mancante a un commit fuori protocollo.

Il lavoro è però protetto: `.pytmp/salvataggio_2026-09-23/` contiene copie **byte-identiche** dei
file critici, il diff esatto e i documenti — in una cartella **gitignorata**, quindi sopravvive a
un `git checkout -f`.

La riconciliazione è pronta e verificata: locale 5 commit indietro, 0 avanti; i 5 file che
bloccherebbero il `pull` sono **identici a origin** (per blob hash, riverificati).

## 58.7 Ordine di esecuzione per arrivare al live

1. **Leggere il messaggio di blocco X-Perps** (costo zero, sblocca fee e short).
2. **`git fetch` + riconciliazione + commit `[dsh]`** (mette in salvo il lavoro).
3. **Rifare il backtest a 0,10% taker / 0,08% maker**: è il numero che decide se vale la pena.
4. **R3b** negli adapter (serve Hermes o un'estensione dell'autorizzazione).
5. **Iniettare il cap nel nodo** e decidere la semantica griglia/trend.
6. **Go-live graduale** secondo `docs/56`: dry-run → un trade minimo forzato → flotta a dimensione
   minima → capitale pieno.

## 58.8 Le decisioni che restano al proprietario

| # | decisione | perché è tua |
|---|---|---|
| 1 | **sbloccare il fetch** / approvare la riconciliazione | git non è la flotta, ma è il tuo protocollo a due scrittori |
| 2 | **semantica griglia/trend** per lo stop (`sell_untracked_asset`?) | è semantica di trading sul tuo denaro |
| 3 | **R3b**: accordo con Hermes o estensione dell'autorizzazione | `infrastructure/` non è mio |
| 4 | **banco di prova o capitale vero** | con 1.000 €, +7%/anno fa 70 €: la dimensione non crea edge |
| 5 | **leggere il blocco X-Perps** e ripulire il conto (posizioni, ordini, bot) | sono azioni sul conto |
