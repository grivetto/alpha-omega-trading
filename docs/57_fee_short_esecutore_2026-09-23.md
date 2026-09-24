# 57 — Fee, short ed esecutore: cosa ho verificato (e cosa cambia)

Data: 2026-09-23. Risposta alla richiesta del proprietario: *"cercami fee più basse, lo short, e
un esecutore provato"*. Fonti ufficiali consultate direttamente; tutto ciò che non ho potuto
verificare è marcato come tale.

**Sintesi in una riga**: le prime due voci si risolvono con **una sola azione** — aprire l'account
derivati su OKX EEA — e il blocco che le tiene chiuse sembra **operativo, non regolamentare**.

---

## 57.1 Fee più basse: il numero era giusto ma incompleto

`docs/20`/`docs/39` usano **0,20% maker / 0,35% taker** come fee OKX EEA. Verificato: è corretto,
ma è **la tabella di chi NON ha aperto l'account derivati**. OKX EEA ne pubblica due.

Fonte: [Spot Fees comparison: X-Perps account vs Regular account](https://www.okx.com/en-eu/help/eea-xperp-spot-trading-fees-comparison)
(pubblicato 18 mag 2026), letto direttamente.

| tier | **senza** X-Perps: maker / taker | **con** X-Perps: maker / taker |
|---|---|---|
| Regular (0 €, 0 volume) | 0,200% / **0,350%** | 0,0800% / **0,1000%** |
| VIP1 | 0,100% / 0,200% | 0,0675% / 0,0800% |
| VIP4 | 0,075% / 0,100% | 0,0300% / 0,0450% |

**Conseguenza**: un retail italiano con 0 € di asset e 0 € di volume passa da **0,35% a 0,10% per
lato** semplicemente aprendo l'account derivati. Costo per giro: da ~0,70% a ~0,20%.

E non serve volume: il tier Regular della tabella "con X-Perps" copre già 0–100.000 € di asset e
0–1.000.000 € di volume/30g. Per ottenere lo stesso **senza** derivati servirebbe VIP4, cioè
**1.000.001 € di volume in 30 giorni** — circa 1.000 volte un conto da 1.000 € al mese.

**Cosa questo cambia per la strategia**: `docs/17` misura l'alpha a **+34,98% con fee zero** e
**−1,97% a 0,35%/lato**. Se il pedaggio scende a 0,10%/lato, quel risultato **cambia segno**. La
stima lineare (≈36,95 punti per 0,739%/giro → ≈10 punti a 0,20%/giro) dà **≈ +25%**, ma è
un'estrapolazione: **va rifatto il backtest a 0,10% taker / 0,08% maker**, non stimato. Finché
quel backtest non esiste, la conclusione "non profittevole" in `docs/39`/`docs/40` è **basata su
una tabella che non è l'unica disponibile**.

## 57.2 Short: esiste, ed è la stessa azione

Gli **X-Perps** sono i derivati perpetui di OKX EEA. Fonte:
[Who can access X-Perps?](https://www.okx.com/en-eu/help/okx-x-perps-eea-regional-availability-eligibility)
(pubblicato 15 apr 2026, aggiornato 4 set 2026):

- servono **KYC** + **appropriateness assessment** (requisito MiFID) + nessuna restrizione sul conto;
- l'assessment classifica retail o professional, ma **l'offerta di prodotto è identica** per
  entrambi;
- **tutti e 30 i paesi EEA sono supportati**, ma l'attivazione può variare per paese per tempi di
  rollout e requisiti di conformità;
- l'entità che li offre è **OKX Europe Markets Limited**, autorizzata e regolata dalla MFSA sotto
  l'Investment Services Act (la parte MiFID), distinta da OKX Europe Limited che è MiCA.

Quindi `docs/44` §44.2 ("oggi, sui due venue della flotta, lo short non esiste") **è superato**:
lo short esiste su OKX EEA, ed è la stessa porta d'ingresso delle fee basse.

## 57.3 Il blocco sembra operativo, e il progetto lo ha già toccato con mano

La stessa pagina ufficiale dice, testualmente:

> *"Activating X-Perps or switching your account mode can be blocked while your account still
> holds activity tied to its current setup. The most common examples are **open positions, open
> orders that haven't been filled, and trading bots that are still running**: close the
> positions, cancel the orders, and stop the bots, and then try again."*

E il progetto ha **tre indizi indipendenti** che combaciano:

1. `docs/44` §44.2 registra che l'upgrade è *"la richiesta che il proprietario non riesce a
   ottenere"*.
2. `.cm8.txt` registra *"una sell SOL@90,89 aperta dal 2026-09-11 che blocca tutto il SOL"*.
3. `docs/54` §54.1 mostra **17 bot configurati** come attivi.

**Ipotesi, verificabile in pochi minuti**: l'attivazione X-Perps è bloccata non da un rifiuto
regolamentare ma dallo **stato del conto** — posizioni, ordini aperti o bot in esecuzione. Va
verificata leggendo il messaggio esatto che la piattaforma mostra al momento del blocco: la
pagina dice che quel messaggio identifica l'elemento mancante, e che il supporto non può
completare o saltare quei passi.

**Azione proposta, in ordine di costo**:
1. leggere il messaggio di blocco (è la diagnosi, non un'ipotesi);
2. chiudere posizioni, cancellare ordini aperti (compresa la sell rimasta dal 11/09) e fermare i
   bot;
3. rifare l'attivazione;
4. completare l'appropriateness assessment.

Tutto quanto sopra **non l'ho eseguito**: sono azioni sul conto, che richiedono la tua
approvazione una per una.

## 57.4 Cosa NON ho verificato (e va verificato)

- **Fee degli X-Perps stessi** (taker/maker sui perpetui e **funding**): la tabella di §57.1 è
  sulle fee **spot**. Chi fa short paga un listino diverso più il funding. `docs/20` misura il
  funding a 0,0040%/8h ≈ 0,036% su tre giorni, ma su dati vecchi: **da rimisurare**.
- **Disponibilità specifica per l'Italia**: la pagina dice che è per-paese; va letta dalla
  piattaforma, non dedotta.
- **Bybit EU e Kraken**: il subagent non ha potuto verificarli (Bybit risponde 403 al fetch
  automatico; il fee-schedule di Kraken è renderizzato lato client). **Non confermo né smentisco**
  la nota 0,10/0,25 di `docs/39`.
- **Spread tipico dei pair EUR**: la cifra 0,078% che circola nei documenti **non è documentata**
  da nessuna fonte ufficiale. OKX documenta solo lo spread *massimo* su Buy/Sell/Convert (1,00%) e
  dichiara che sull'order book, con ordine limite, *"you pay the trading fee for your fee tier,
  and no spread"*. Va **misurato dall'order book**, non assunto.

## 57.5 Esecutore provato: freqtrade, verificato leggendo il codice

Verifica indipendente (non marketing) contro i requisiti Q1-Q6 di `docs/55`:

| requisito | freqtrade |
|---|---|
| Q1 uscita sulla posizione | **risolto**: `_safe_exit_amount` usa la size della posizione e solleva eccezione se il saldo non basta; lo stop è ricreato con `amount=trade.amount` |
| Q2 stop che ritenta | **risolto**: `create_stoploss_order` gestisce `InsufficientFunds` e `InvalidOrder`, e `manage_trade_stoploss_orders` ricrea lo stop quando la sede lo mostra cancellato |
| Q3 idempotenza | **parziale**: nessun `clientOrderId`; mitigato da ordini persistiti su DB e riconciliazione all'avvio |
| Q4 fill parziali | **risolto**: `handle_cancel_enter/exit`, `safe_filled`/`safe_remaining`; caveat: il backtest assume fill completi |
| Q5 curva equity | ledger SQLite (Trade + Order, colonna `strategy`, `available_capital`); metriche ricostruibili |
| Q6 cap di conto | `available_capital` per più bot sullo stesso conto, ma **con leva la doc dice un solo bot per conto** |

Altro verificato: short con `trading_mode: futures` + `can_short=True` (Binance, Bitget, Bybit,
Gate, Hyperliquid, Kraken, OKX); `freqtrade lookahead-analysis` esiste e fa backtest concatenati
contro riesecuzioni slice-per-slice; il trailing ATR custom è **esempio ufficiale** della
documentazione (`custom_stoploss` + `stoploss_from_absolute` + `ta.ATR`); dry-run documentato
(wallet simulato, slippage massimo 5%, stop assunti come riempiti, **ordini aperti persistiti
"con l'assunzione che non siano stati riempiti mentre eri offline"**). Port: la logica di segnale
diventa una classe da ~150-250 righe; il motore da 1.400 righe si butta.

Maturità: 54.723 stelle, 401 contributor, ultima release **2026.8 del 31/08/2026**.

### Gli altri candidati, verificati sul sorgente

- **jesse — squalificato.** Live e paper trading **non sono open source**: la documentazione
  ufficiale ([docs.jesse.trade/docs/livetrade](https://docs.jesse.trade/docs/livetrade)) parla di
  *"an official plugin"* con *"access ... limited to those with an active license"*
  (`jesse install-live` + `LICENSE_API_TOKEN`). Conferma dal repository: `jesse/modes/live.py`
  risponde **404** e `jesse/exchanges/__init__.py` esporta **solo** `Sandbox`, nessun connettore
  reale. Quindi Q2, Q3, Q4, Q5 e la fedeltà del paper **non sono verificabili**: stanno in un
  binario chiuso. Per un conto reale significa un audit impossibile → **da non adottare**.
- **hummingbot — parziale, e non per questa strategia.** Lo stop-loss **non è un ordine a riposo
  sulla sede**: è una barriera pollata nel loop (`control_stop_loss()` in
  `position_executor.py`), con **retry esplicito** (`max_retries = 10`) e uscita dimensionata sulla
  posizione (`amount_to_close = open_filled_amount - close_filled_amount`) → **Q1 e Q2 coperti**.
  Ma il trailing stop è in **percentuale di PnL**, non in ATR, e la documentazione del paper-trade
  **non contiene nessuna affermazione di fedeltà** al live. Per noi significa **esprimere una
  strategia diversa** (Q7 di `docs/55`): la misura non si trasferisce.
- **nautilus_trader — il più solido, e il più caro.** Costruito attorno a ciò che a freqtrade
  manca: `ClientOrderId` + `use_uuid_client_order_ids` (**Q3 risolto**), e riconciliazione
  all'avvio **fail-closed** — *"Unresolved reports prevent actors and strategies from starting"*
  (`docs/concepts/execution/reconciliation.md`). Per Q2 ha un market-exit manager opt-in con
  `market_exit_max_attempts=100`, `market_exit_reduce_only=true` e blocco esplicito di ogni ordine
  non reduce-only con `MARKET_EXIT_IN_PROGRESS`. Fill parziali con `OrderFilled`/`OrderFillVoided`
  (**Q4**), curva equity e Sharpe persistiti **solo con cache Redis/Postgres** (**Q5 condizionato**),
  ATR nativo ma **trailing a offset statico** → il 2,5 ATR va ricalcolato per barra (**Q7 da
  scrivere**), e **nessun cap di conto** (**Q6 da scrivere**). Costo: event-driven su core
  Rust/Cython, **giorni-settimane**.

### Griglia finale

| | Q1 uscita | Q2 retry stop | Q3 idempotenza | Q4 parziali | Q5 curva equity | Q6 cap di conto | Q7 strategia misurata |
|---|---|---|---|---|---|---|---|
| **freqtrade** | ✅ | ✅ | ⚠️ no chiave, recon sì | ✅ | ledger SQLite | ⚠️ parziale | ✅ ATR documentato |
| **nautilus** | ✅ | ✅ opt-in | ✅ nativo | ✅ | ✅ con DB | ❌ da scrivere | ⚠️ offset statico |
| **hummingbot** | ✅ | ⚠️ max 10, solo MARKET | ❌ id non durevole | ✅ | ❌ | ❌ | ❌ solo % di PnL |
| **jesse** | ⚠️ solo core | ❌ non verificabile | ❌ non verificabile | ✅ core | ✅ `LiveEquitySnapshot` | ❌ | ❌ non nativo |

### Verdetto

> **Correggere il motore proprietario, non adottare un framework.**

Motivi, in ordine di peso:

1. **Hummingbot scartato**: lo stop **non è sul venue**. Se il processo muore, non c'è nessuno stop
   — inaccettabile per una strategia direzionale, figurarsi in short. In più nessuna serie equity e
   nessun cap di conto.
2. **Jesse scartato**: il live è un binario licenziato. Non si può verificare l'esecutore che
   gestisce il denaro.
3. **freqtrade** copre Q1/Q2/Q4 e sa esprimere la strategia misurata, ma **non ha la chiave di
   idempotenza** — la voce che nel nostro difetto R3 è la più difficile da mitigare.
4. **nautilus** risolve Q3 e la riconciliazione come nessun altro, ma costa una **riscrittura
   event-driven** e lascia Q6 e Q7 da scrivere comunque.

Poiché nessun framework copre tutto, e i tre difetti del nostro motore hanno già **9 test di
accettazione pronti** (`denaro/tests/test_rischi_capitale.py`), la via più corta è correggere in
casa — che è anche quella che non butta la misura già fatta.

### Limite di questa verifica, dichiarato

La valutazione è **statica**: lettura del sorgente e della documentazione ufficiale. Il subagent
**non ha potuto eseguire nulla** (niente clone, niente rete) — quindi **zero verifica a runtime**
per tutti e quattro. Restano inoltre non verificati: stelle e date di release dei tre repo (API
GitHub in rate-limit), la versione Python richiesta da nautilus, la pagina sandbox di nautilus, e
una issue aperta sui duplicati al riavvio. `octobot` e `superalgos` non sono stati valutati.

---

## 57.6 Cosa farei adesso, in ordine

1. **Leggere il messaggio di blocco dell'attivazione X-Perps.** Costa zero, ed è la diagnosi.
   Se dice "posizioni/ordini/bot aperti", la strada è libera e si apre tutto il resto.
2. **Rifare il backtest a 0,10% taker / 0,08% maker.** Prima di qualunque altra ricerca: la
   conclusione economica attuale poggia su una tabella che non è l'unica disponibile.
3. **Misurare lo spread dall'order book** invece di usare 0,078%.
4. Solo dopo: scegliere l'esecutore, con il confronto Q1-Q7 completo (`docs/55`).
